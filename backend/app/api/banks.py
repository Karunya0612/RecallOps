from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Path

from app.api.schemas import (
    RecallRequest,
    RecallResponse,
    RetainRequest,
    RetainResponse,
)
from app.core.config import Settings, get_settings
from app.services.hindsight import HindsightClient, HindsightError

router = APIRouter(prefix="/api/v1", tags=["banks"])


def get_hindsight_client(settings: Settings = Depends(get_settings)) -> HindsightClient:
    return HindsightClient(
        base_url=settings.hindsight_base_url,
        api_key=settings.hindsight_api_key,
        default_bank_id=settings.hindsight_bank_id,
    )


@router.get("/banks")
async def list_banks(
    client: HindsightClient = Depends(get_hindsight_client),
) -> dict[str, Any]:
    """List available memory banks from Hindsight Cloud."""
    try:
        data = await client.list_banks()
        return data
    except HindsightError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)


@router.get("/banks/default")
async def get_default_bank(
    client: HindsightClient = Depends(get_hindsight_client),
) -> dict[str, str]:
    """Get the currently configured default Hindsight memory bank ID."""
    return {"default_bank_id": client.get_configured_bank_id()}


@router.post("/banks/{bank_id}/memories", response_model=RetainResponse)
async def retain_memories(
    payload: RetainRequest,
    bank_id: str = Path(..., min_length=1, description="Memory bank identifier"),
    client: HindsightClient = Depends(get_hindsight_client),
) -> RetainResponse:
    """Retain (store) memories into a specified memory bank."""
    try:
        items = [item.model_dump(exclude_none=True) for item in payload.items]
        data = await client.retain_memory(
            bank_id=bank_id,
            items=items,
            async_mode=payload.async_mode,
        )
        return RetainResponse.model_validate(data)
    except HindsightError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)


@router.post("/banks/{bank_id}/memories/recall", response_model=RecallResponse)
async def recall_memories(
    payload: RecallRequest,
    bank_id: str = Path(..., min_length=1, description="Memory bank identifier"),
    client: HindsightClient = Depends(get_hindsight_client),
) -> RecallResponse:
    """Recall (search) relevant memories from a specified memory bank."""
    try:
        data = await client.recall_memories(
            bank_id=bank_id,
            query=payload.query,
            types=payload.types,
            budget=payload.budget,
            max_tokens=payload.max_tokens,
            trace=payload.trace or False,
            query_timestamp=payload.query_timestamp,
        )
        return RecallResponse.model_validate(data)
    except HindsightError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
