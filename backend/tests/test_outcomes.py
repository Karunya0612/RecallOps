"""Tests for Phase 5: Incident Outcome Recording and Hindsight Learning Loop."""

from unittest.mock import AsyncMock
import pytest
from fastapi.testclient import TestClient

from app.api.banks import get_hindsight_client
from app.db.repository import IncidentRepository, get_incident_repository
from app.main import app
from app.services.hindsight import (
    HindsightAuthError,
    HindsightConnectionError,
    HindsightTimeoutError,
    HindsightClient,
)


@pytest.fixture
def repo():
    """Provides an isolated in-memory repository for each test."""
    repository = IncidentRepository(db_path=":memory:")
    yield repository
    repository.close()


@pytest.fixture
def mock_hindsight_client():
    """Provides a mocked HindsightClient."""
    mock = AsyncMock(spec=HindsightClient)
    mock.get_configured_bank_id.return_value = "recallops-dev"
    mock.retain_memory.return_value = {
        "success": True,
        "bank_id": "recallops-dev",
        "items_count": 1,
    }
    return mock


@pytest.fixture
def client(repo, mock_hindsight_client):
    """Provides a TestClient with dependency overrides for repository and Hindsight client."""
    app.dependency_overrides[get_incident_repository] = lambda: repo
    app.dependency_overrides[get_hindsight_client] = lambda: mock_hindsight_client
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# ============================================================================
# Unit Tests: Repository Outcome Operations
# ============================================================================

def test_repository_outcome_crud(repo: IncidentRepository):
    """Test creating, fetching, listing, and deleting outcomes in SQLite repository."""
    inc = repo.create_incident(
        title="Test service crash",
        description="Process crashed with SIGSEGV.",
        affected_service="worker",
        severity="high",
    )

    # 1. Record outcome
    outcome = repo.record_outcome(
        incident_id=inc["id"],
        resolution_attempted="Upgraded native dependency",
        outcome="success",
        engineer_notes="Crash stopped occurring after upgrade.",
    )
    assert outcome["id"].startswith("out-")
    assert outcome["incident_id"] == inc["id"]
    assert outcome["outcome"] == "success"

    # 2. Get outcome by ID
    fetched = repo.get_outcome(outcome["id"])
    assert fetched is not None
    assert fetched["resolution_attempted"] == "Upgraded native dependency"

    # 3. List outcomes for incident
    outcomes_list = repo.list_outcomes_for_incident(inc["id"])
    assert len(outcomes_list) == 1
    assert outcomes_list[0]["id"] == outcome["id"]

    # 4. Delete outcome
    deleted = repo.delete_outcome(outcome["id"])
    assert deleted is True
    assert repo.get_outcome(outcome["id"]) is None
    assert len(repo.list_outcomes_for_incident(inc["id"])) == 0


# ============================================================================
# Integration Tests: POST /api/v1/incidents/{incident_id}/outcome
# ============================================================================

def test_record_outcome_success(client: TestClient, repo: IncidentRepository, mock_hindsight_client: AsyncMock):
    """Test recording a successful outcome stores in SQLite and retains in Hindsight."""
    inc = repo.create_incident(
        title="Payment gateway timeout",
        description="Checkout response time degraded after release.",
        affected_service="payment-gateway",
        severity="high",
    )

    payload = {
        "resolution_attempted": "Scaled connection pool from 10 to 50 and recycled idle connections.",
        "outcome": "success",
        "engineer_notes": "Latency dropped from 5000ms to 45ms immediately.",
    }

    resp = client.post(f"/api/v1/incidents/{inc['id']}/outcome", json=payload)
    assert resp.status_code == 200

    data = resp.json()
    assert data["hindsight_retained"] is True
    assert data["bank_id"] == "recallops-dev"
    assert data["outcome"]["incident_id"] == inc["id"]
    assert data["outcome"]["resolution_attempted"] == payload["resolution_attempted"]
    assert data["outcome"]["outcome"] == "success"
    assert data["outcome"]["engineer_notes"] == payload["engineer_notes"]
    assert data["outcome"]["id"].startswith("out-")

    # Verify Hindsight retain call arguments
    mock_hindsight_client.retain_memory.assert_awaited_once()
    call_kwargs = mock_hindsight_client.retain_memory.call_args.kwargs
    assert call_kwargs["bank_id"] == "recallops-dev"
    items = call_kwargs["items"]
    assert len(items) == 1
    assert "ENGINEER-CONFIRMED RESOLUTION" in items[0]["content"]
    assert "resolved by Scaled connection pool" in items[0]["content"]
    assert items[0]["context"] == f"engineer_outcome:{inc['id']}"

    # Verify persisted in SQLite
    persisted = repo.get_outcome(data["outcome"]["id"])
    assert persisted is not None
    assert persisted["outcome"] == "success"


def test_record_outcome_failure(client: TestClient, repo: IncidentRepository, mock_hindsight_client: AsyncMock):
    """Test recording a failed resolution attempt retains a clear failure warning in Hindsight."""
    inc = repo.create_incident(
        title="Database lock contention",
        description="Row locks on orders table blocking transactions.",
        affected_service="orders-db",
        severity="critical",
    )

    payload = {
        "resolution_attempted": "Flushed Redis cache keys.",
        "outcome": "failure",
        "engineer_notes": "Did not resolve the issue; database locks persisted.",
    }

    resp = client.post(f"/api/v1/incidents/{inc['id']}/outcome", json=payload)
    assert resp.status_code == 200

    data = resp.json()
    assert data["hindsight_retained"] is True
    assert data["outcome"]["outcome"] == "failure"

    # Verify Hindsight retain call specifically marks failure
    call_kwargs = mock_hindsight_client.retain_memory.call_args.kwargs
    content = call_kwargs["items"][0]["content"]
    assert "ENGINEER-CONFIRMED FAILED RESOLUTION ATTEMPT" in content
    assert "did not resolve the issue" in content
    assert "Outcome: FAILURE" in content


def test_record_outcome_case_insensitive_and_whitespace(client: TestClient, repo: IncidentRepository):
    """Test outcome normalization handles uppercase and whitespace trimming."""
    inc = repo.create_incident(
        title="Cache latency",
        description="Slow response from Redis.",
        affected_service="cache",
        severity="medium",
    )

    payload = {
        "resolution_attempted": "  Restarted Redis cluster  ",
        "outcome": "  SUCCESS  ",
        "engineer_notes": "  Worked well.  ",
    }

    resp = client.post(f"/api/v1/incidents/{inc['id']}/outcome", json=payload)
    assert resp.status_code == 200
    assert resp.json()["outcome"]["outcome"] == "success"
    assert resp.json()["outcome"]["resolution_attempted"] == "Restarted Redis cluster"
    assert resp.json()["outcome"]["engineer_notes"] == "Worked well."


def test_record_outcome_missing_incident(client: TestClient, mock_hindsight_client: AsyncMock):
    """Test recording an outcome for a nonexistent incident returns HTTP 404."""
    payload = {
        "resolution_attempted": "Restarted service",
        "outcome": "success",
    }
    resp = client.post("/api/v1/incidents/inc-nonexistent-999/outcome", json=payload)
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()
    mock_hindsight_client.retain_memory.assert_not_called()


def test_record_outcome_invalid_outcome_value(client: TestClient, repo: IncidentRepository):
    """Test invalid outcome enum value returns HTTP 422."""
    inc = repo.create_incident(
        title="Test incident",
        description="Desc",
        affected_service="service",
        severity="low",
    )
    payload = {
        "resolution_attempted": "Restarted server",
        "outcome": "partial_success",
    }
    resp = client.post(f"/api/v1/incidents/{inc['id']}/outcome", json=payload)
    assert resp.status_code == 422


def test_record_outcome_empty_resolution_attempted(client: TestClient, repo: IncidentRepository):
    """Test empty or whitespace-only resolution_attempted returns HTTP 422."""
    inc = repo.create_incident(
        title="Test incident",
        description="Desc",
        affected_service="service",
        severity="low",
    )
    payload = {
        "resolution_attempted": "   ",
        "outcome": "success",
    }
    resp = client.post(f"/api/v1/incidents/{inc['id']}/outcome", json=payload)
    assert resp.status_code == 422


def test_record_outcome_payload_incident_id_mismatch(client: TestClient, repo: IncidentRepository):
    """Test that payload incident_id mismatching path returns HTTP 422."""
    inc = repo.create_incident(
        title="Test incident",
        description="Desc",
        affected_service="service",
        severity="low",
    )
    payload = {
        "incident_id": "inc-different-id",
        "resolution_attempted": "Restarted server",
        "outcome": "success",
    }
    resp = client.post(f"/api/v1/incidents/{inc['id']}/outcome", json=payload)
    assert resp.status_code == 422
    assert "does not match" in resp.json()["detail"].lower()


# ============================================================================
# Integration Tests: Hindsight Failures and Consistency Rollback
# ============================================================================

def test_record_outcome_hindsight_auth_failure_with_rollback(client: TestClient, repo: IncidentRepository, mock_hindsight_client: AsyncMock):
    """Test Hindsight authentication failure returns HTTP 502 and rolls back local SQLite outcome."""
    mock_hindsight_client.retain_memory.side_effect = HindsightAuthError("Invalid credentials")

    inc = repo.create_incident(
        title="Auth fail incident",
        description="Desc",
        affected_service="api",
        severity="high",
    )

    payload = {
        "resolution_attempted": "Applied patch",
        "outcome": "success",
    }

    resp = client.post(f"/api/v1/incidents/{inc['id']}/outcome", json=payload)
    assert resp.status_code == 502
    assert resp.json()["detail"] == "Authentication with Hindsight Cloud failed."

    # Consistency check: ensure no outcome was left orphaned in SQLite
    outcomes = repo.list_outcomes_for_incident(inc["id"])
    assert len(outcomes) == 0


def test_record_outcome_hindsight_timeout_with_rollback(client: TestClient, repo: IncidentRepository, mock_hindsight_client: AsyncMock):
    """Test Hindsight timeout returns HTTP 504 and rolls back local SQLite outcome."""
    mock_hindsight_client.retain_memory.side_effect = HindsightTimeoutError()

    inc = repo.create_incident(
        title="Timeout incident",
        description="Desc",
        affected_service="api",
        severity="high",
    )

    payload = {
        "resolution_attempted": "Applied patch",
        "outcome": "success",
    }

    resp = client.post(f"/api/v1/incidents/{inc['id']}/outcome", json=payload)
    assert resp.status_code == 504
    assert resp.json()["detail"] == "Hindsight Cloud request timed out."

    # Consistency check
    outcomes = repo.list_outcomes_for_incident(inc["id"])
    assert len(outcomes) == 0


def test_record_outcome_hindsight_connection_failure_with_rollback(client: TestClient, repo: IncidentRepository, mock_hindsight_client: AsyncMock):
    """Test Hindsight connection failure returns HTTP 503 and rolls back local SQLite outcome."""
    mock_hindsight_client.retain_memory.side_effect = HindsightConnectionError()

    inc = repo.create_incident(
        title="Connection fail incident",
        description="Desc",
        affected_service="api",
        severity="high",
    )

    payload = {
        "resolution_attempted": "Applied patch",
        "outcome": "success",
    }

    resp = client.post(f"/api/v1/incidents/{inc['id']}/outcome", json=payload)
    assert resp.status_code == 503
    assert resp.json()["detail"] == "Failed to connect to Hindsight Cloud."

    # Consistency check
    outcomes = repo.list_outcomes_for_incident(inc["id"])
    assert len(outcomes) == 0
