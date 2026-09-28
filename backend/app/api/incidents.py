from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from app.api.banks import get_hindsight_client
from app.api.schemas import (
    IncidentAnalysisRequest,
    IncidentAnalysisResponse,
    IncidentCreateRequest,
    IncidentListResponse,
    IncidentOutcomeRecord,
    IncidentOutcomeRequest,
    IncidentOutcomeResponse,
    IncidentOutcomeStatus,
    IncidentResponse,
)
from app.db.repository import IncidentRepository, get_incident_repository
from app.services.analyzer import IncidentAnalyzer
from app.services.hindsight import (
    HindsightAuthError,
    HindsightClient,
    HindsightConnectionError,
    HindsightError,
    HindsightTimeoutError,
)

router = APIRouter(prefix="/api/v1", tags=["incidents"])


@router.post(
    "/incidents",
    response_model=IncidentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_incident(
    payload: IncidentCreateRequest,
    repo: IncidentRepository = Depends(get_incident_repository),
) -> IncidentResponse:
    """Create a new incident record in local storage."""
    record = repo.create_incident(
        title=payload.title,
        description=payload.description,
        affected_service=payload.affected_service,
        severity=payload.severity.value,
        logs=payload.logs,
    )
    return IncidentResponse.model_validate(record)


@router.get(
    "/incidents/{incident_id}",
    response_model=IncidentResponse,
    status_code=status.HTTP_200_OK,
)
def get_incident(
    incident_id: str = Path(..., min_length=1, description="Unique incident identifier"),
    repo: IncidentRepository = Depends(get_incident_repository),
) -> IncidentResponse:
    """Retrieve an incident record by ID."""
    record = repo.get_incident(incident_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident '{incident_id}' not found.",
        )
    return IncidentResponse.model_validate(record)


@router.get(
    "/incidents",
    response_model=IncidentListResponse,
    status_code=status.HTTP_200_OK,
)
def list_incidents(
    limit: int = Query(default=20, ge=1, le=100, description="Maximum items to return (1-100)"),
    offset: int = Query(default=0, ge=0, description="Number of items to skip"),
    repo: IncidentRepository = Depends(get_incident_repository),
) -> IncidentListResponse:
    """Retrieve a paginated list of incidents ordered by creation time descending."""
    items, total = repo.list_incidents(limit=limit, offset=offset)
    return IncidentListResponse(
        items=[IncidentResponse.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/incidents/{incident_id}/analyze",
    response_model=IncidentAnalysisResponse,
    status_code=status.HTTP_200_OK,
)
async def analyze_incident(
    incident_id: str = Path(..., min_length=1, description="Unique incident identifier"),
    payload: Optional[IncidentAnalysisRequest] = None,
    repo: IncidentRepository = Depends(get_incident_repository),
    hindsight_client: HindsightClient = Depends(get_hindsight_client),
) -> IncidentAnalysisResponse:
    """Analyze an incident, extracting symptoms and recalling relevant memories from Hindsight."""
    analyzer = IncidentAnalyzer(repository=repo, hindsight_client=hindsight_client)
    query_override = payload.query_override if payload else None
    max_tokens = payload.max_tokens if payload else None
    return await analyzer.analyze_incident(
        incident_id=incident_id,
        query_override=query_override,
        max_tokens=max_tokens,
    )


@router.post(
    "/incidents/{incident_id}/outcome",
    response_model=IncidentOutcomeResponse,
    status_code=status.HTTP_200_OK,
)
async def record_incident_outcome(
    payload: IncidentOutcomeRequest,
    incident_id: str = Path(..., min_length=1, description="Unique incident identifier"),
    repo: IncidentRepository = Depends(get_incident_repository),
    hindsight_client: HindsightClient = Depends(get_hindsight_client),
) -> IncidentOutcomeResponse:
    """Record an engineer-confirmed resolution outcome and retain it in Hindsight Cloud."""
    # 1. Verify that the incident exists
    incident = repo.get_incident(incident_id)
    if incident is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident '{incident_id}' not found.",
        )

    # 2. Check for incident_id mismatch if provided in body
    if payload.incident_id and payload.incident_id != incident_id:
        raise HTTPException(
            status_code=422,
            detail=f"Payload incident_id '{payload.incident_id}' does not match path incident_id '{incident_id}'.",
        )

    # 3. Store outcome locally in SQLite
    outcome_record = repo.record_outcome(
        incident_id=incident_id,
        resolution_attempted=payload.resolution_attempted,
        outcome=payload.outcome.value,
        engineer_notes=payload.engineer_notes,
    )

    # 4. Construct structured outcome memory
    if payload.outcome == IncidentOutcomeStatus.SUCCESS:
        memory_content = (
            f"Incident {incident['id']}: '{incident['title']}' affecting service '{incident['affected_service']}' "
            f"with severity '{incident['severity']}'. "
            f"ENGINEER-CONFIRMED RESOLUTION: The incident was resolved by {payload.resolution_attempted}. "
            f"Outcome: SUCCESS. "
            f"Engineer notes: {payload.engineer_notes if payload.engineer_notes else 'None'}."
        )
    else:
        memory_content = (
            f"Incident {incident['id']}: '{incident['title']}' affecting service '{incident['affected_service']}' "
            f"with severity '{incident['severity']}'. "
            f"ENGINEER-CONFIRMED FAILED RESOLUTION ATTEMPT: Attempted action {payload.resolution_attempted} did not resolve the issue. "
            f"Outcome: FAILURE. "
            f"Engineer notes: {payload.engineer_notes if payload.engineer_notes else 'None'}."
        )

    bank_id = hindsight_client.get_configured_bank_id()

    # 5. Retain in Hindsight Cloud with safe error handling and local DB rollback
    try:
        retain_data = await hindsight_client.retain_memory(
            bank_id=bank_id,
            items=[
                {
                    "content": memory_content,
                    "context": f"engineer_outcome:{incident_id}",
                    "timestamp": outcome_record["created_at"],
                }
            ],
            async_mode=False,
        )
        hindsight_retained = bool(retain_data.get("success", True))
    except HindsightAuthError as exc:
        repo.delete_outcome(outcome_record["id"])
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Authentication with Hindsight Cloud failed.",
        ) from exc
    except HindsightTimeoutError as exc:
        repo.delete_outcome(outcome_record["id"])
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Hindsight Cloud request timed out.",
        ) from exc
    except HindsightConnectionError as exc:
        repo.delete_outcome(outcome_record["id"])
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to connect to Hindsight Cloud.",
        ) from exc
    except HindsightError as exc:
        repo.delete_outcome(outcome_record["id"])
        raise HTTPException(
            status_code=exc.status_code,
            detail=exc.message,
        ) from exc

    return IncidentOutcomeResponse(
        outcome=IncidentOutcomeRecord.model_validate(outcome_record),
        hindsight_retained=hindsight_retained,
        bank_id=bank_id,
    )
