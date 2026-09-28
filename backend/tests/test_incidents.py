"""Tests for incident intake foundation, SQLite persistence, and API endpoints."""

from datetime import datetime
import pytest
from fastapi.testclient import TestClient

from app.db.repository import IncidentRepository, get_incident_repository
from app.main import app


@pytest.fixture
def repo():
    """Provides an isolated in-memory IncidentRepository for testing."""
    repository = IncidentRepository(db_path=":memory:")
    yield repository
    repository.close()


@pytest.fixture
def client(repo):
    """Provides a TestClient with dependency override to the test repository."""
    app.dependency_overrides[get_incident_repository] = lambda: repo
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# ============================================================================
# Unit Tests: IncidentRepository
# ============================================================================

def test_repository_create_and_get(repo: IncidentRepository):
    """Test incident creation and retrieval via IncidentRepository."""
    record = repo.create_incident(
        title="High CPU in auth-service",
        description="CPU usage reached 98% across all pods.",
        affected_service="auth-service",
        severity="high",
        logs="2026-09-28 [ERROR] CPU throttle detected",
    )

    assert record["id"].startswith("inc-")
    assert record["title"] == "High CPU in auth-service"
    assert record["description"] == "CPU usage reached 98% across all pods."
    assert record["affected_service"] == "auth-service"
    assert record["severity"] == "high"
    assert record["logs"] == "2026-09-28 [ERROR] CPU throttle detected"
    assert record["status"] == "open"
    assert record["updated_at"] is None

    # Check timezone-aware UTC timestamp
    dt = datetime.fromisoformat(record["created_at"])
    assert dt.tzinfo is not None

    # Fetch from repository
    fetched = repo.get_incident(record["id"])
    assert fetched is not None
    assert fetched["id"] == record["id"]
    assert fetched["title"] == record["title"]


def test_repository_get_nonexistent(repo: IncidentRepository):
    """Test getting an incident that does not exist."""
    assert repo.get_incident("inc-unknown") is None


def test_repository_list_and_pagination(repo: IncidentRepository):
    """Test listing incidents with pagination and descending order."""
    ids = []
    for i in range(5):
        rec = repo.create_incident(
            title=f"Incident {i}",
            description=f"Description {i}",
            affected_service=f"service-{i}",
            severity="low",
            created_at=f"2026-09-28T10:0{i}:00+00:00",
        )
        ids.append(rec["id"])

    # Page 1 (limit=2, offset=0)
    items, total = repo.list_incidents(limit=2, offset=0)
    assert total == 5
    assert len(items) == 2
    # Incident 4 was created last, should appear first
    assert items[0]["id"] == ids[4]
    assert items[1]["id"] == ids[3]

    # Page 2 (limit=2, offset=2)
    items_p2, total_p2 = repo.list_incidents(limit=2, offset=2)
    assert total_p2 == 5
    assert len(items_p2) == 2
    assert items_p2[0]["id"] == ids[2]
    assert items_p2[1]["id"] == ids[1]


def test_repository_transaction_rollback(repo: IncidentRepository):
    """Test that SQLite transaction rolls back properly on conflict."""
    repo.create_incident(
        title="First Incident",
        description="First description",
        affected_service="api",
        severity="low",
        incident_id="fixed-id-1",
    )

    with pytest.raises(Exception):
        with repo._conn:
            # Duplicate ID insertion must fail and roll back
            repo._conn.execute(
                """
                INSERT INTO incidents (id, title, description, affected_service, severity, created_at)
                VALUES ('fixed-id-1', 'Duplicate', 'Duplicate desc', 'api', 'low', '2026-09-28T00:00:00+00:00');
                """
            )

    items, total = repo.list_incidents()
    assert total == 1
    assert items[0]["title"] == "First Incident"


# ============================================================================
# Integration Tests: POST /api/v1/incidents
# ============================================================================

def test_api_create_incident_success_all_fields(client: TestClient):
    """Test creating an incident with all fields returns HTTP 201."""
    payload = {
        "title": "Payment gateway latency spike",
        "description": "Checkout service response times exceeded 5,000ms after v2.4.1 release.",
        "affected_service": "payment-gateway",
        "severity": "high",
        "logs": "2026-09-28T18:40:00Z [ERROR] Timeout waiting for upstream payment provider after 5000ms",
    }
    response = client.post("/api/v1/incidents", json=payload)
    assert response.status_code == 201

    data = response.json()
    assert data["id"].startswith("inc-")
    assert data["title"] == payload["title"]
    assert data["description"] == payload["description"]
    assert data["affected_service"] == payload["affected_service"]
    assert data["severity"] == "high"
    assert data["logs"] == payload["logs"]
    assert data["status"] == "open"
    assert data["updated_at"] is None

    dt = datetime.fromisoformat(data["created_at"])
    assert dt.tzinfo is not None


def test_api_create_incident_success_optional_logs_omitted(client: TestClient):
    """Test creating an incident without logs returns HTTP 201 with null logs."""
    payload = {
        "title": "Database connection pool exhaustion",
        "description": "Max connections reached on primary database cluster.",
        "affected_service": "orders-db",
        "severity": "critical",
    }
    response = client.post("/api/v1/incidents", json=payload)
    assert response.status_code == 201

    data = response.json()
    assert data["logs"] is None
    assert data["severity"] == "critical"


def test_api_create_incident_severity_normalization(client: TestClient):
    """Test that uppercase or whitespace-padded severity is normalized to lowercase."""
    payload = {
        "title": "Cache eviction storm",
        "description": "Redis cluster evicted 100k keys unexpectedly.",
        "affected_service": "cache-cluster",
        "severity": "  CRITICAL  ",
    }
    response = client.post("/api/v1/incidents", json=payload)
    assert response.status_code == 201
    assert response.json()["severity"] == "critical"


def test_api_create_incident_whitespace_trimming(client: TestClient):
    """Test that leading/trailing whitespaces in fields are automatically trimmed."""
    payload = {
        "title": "   Notification queue backed up   ",
        "description": "   Queue depth exceeded 50,000 messages.   ",
        "affected_service": "   notification-worker   ",
        "severity": "medium",
        "logs": "   queue log trace   ",
    }
    response = client.post("/api/v1/incidents", json=payload)
    assert response.status_code == 201

    data = response.json()
    assert data["title"] == "Notification queue backed up"
    assert data["description"] == "Queue depth exceeded 50,000 messages."
    assert data["affected_service"] == "notification-worker"
    assert data["logs"] == "queue log trace"


def test_api_create_incident_validation_empty_whitespace_rejected(client: TestClient):
    """Test that empty or whitespace-only required fields return HTTP 422."""
    bad_payloads = [
        {"title": "   ", "description": "Valid desc", "affected_service": "api", "severity": "low"},
        {"title": "Valid title", "description": "   ", "affected_service": "api", "severity": "low"},
        {"title": "Valid title", "description": "Valid desc", "affected_service": "   ", "severity": "low"},
        {"title": "", "description": "Valid desc", "affected_service": "api", "severity": "low"},
    ]

    for bad in bad_payloads:
        response = client.post("/api/v1/incidents", json=bad)
        assert response.status_code == 422


def test_api_create_incident_validation_missing_required_fields(client: TestClient):
    """Test that missing required fields return HTTP 422."""
    missing_fields = [
        {"description": "desc", "affected_service": "api", "severity": "low"},
        {"title": "title", "affected_service": "api", "severity": "low"},
        {"title": "title", "description": "desc", "severity": "low"},
        {"title": "title", "description": "desc", "affected_service": "api"},
    ]

    for bad in missing_fields:
        response = client.post("/api/v1/incidents", json=bad)
        assert response.status_code == 422


def test_api_create_incident_validation_invalid_severity(client: TestClient):
    """Test that invalid severity values return HTTP 422."""
    payload = {
        "title": "Ingress SSL cert expired",
        "description": "TLS handshake failures on edge proxies.",
        "affected_service": "edge-proxy",
        "severity": "catastrophic",
    }
    response = client.post("/api/v1/incidents", json=payload)
    assert response.status_code == 422


# ============================================================================
# Integration Tests: GET /api/v1/incidents/{incident_id}
# ============================================================================

def test_api_get_incident_persistence(client: TestClient):
    """Test that a created incident persists and is retrievable via GET."""
    payload = {
        "title": "Elasticsearch disk full",
        "description": "Storage utilization exceeded 95% on log nodes.",
        "affected_service": "es-logging",
        "severity": "high",
        "logs": "DiskWatermarkExceededException: high watermark exceeded",
    }
    create_resp = client.post("/api/v1/incidents", json=payload)
    assert create_resp.status_code == 201
    incident_id = create_resp.json()["id"]

    get_resp = client.get(f"/api/v1/incidents/{incident_id}")
    assert get_resp.status_code == 200

    data = get_resp.json()
    assert data["id"] == incident_id
    assert data["title"] == payload["title"]
    assert data["description"] == payload["description"]
    assert data["affected_service"] == payload["affected_service"]
    assert data["severity"] == "high"
    assert data["logs"] == payload["logs"]


def test_api_get_incident_not_found(client: TestClient):
    """Test retrieving a non-existent incident returns HTTP 404."""
    response = client.get("/api/v1/incidents/inc-nonexistent-123")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


# ============================================================================
# Integration Tests: GET /api/v1/incidents (Listing & Pagination)
# ============================================================================

def test_api_list_incidents_empty(client: TestClient):
    """Test listing incidents on an empty store returns empty items list."""
    response = client.get("/api/v1/incidents")
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert data["limit"] == 20
    assert data["offset"] == 0


def test_api_list_incidents_pagination(client: TestClient):
    """Test listing incidents with custom limit and offset."""
    for i in range(4):
        client.post(
            "/api/v1/incidents",
            json={
                "title": f"Incident {i}",
                "description": f"Incident desc {i}",
                "affected_service": f"service-{i}",
                "severity": "low",
            },
        )

    # First page
    resp1 = client.get("/api/v1/incidents?limit=2&offset=0")
    assert resp1.status_code == 200
    d1 = resp1.json()
    assert d1["total"] == 4
    assert len(d1["items"]) == 2
    assert d1["limit"] == 2
    assert d1["offset"] == 0

    # Second page
    resp2 = client.get("/api/v1/incidents?limit=2&offset=2")
    assert resp2.status_code == 200
    d2 = resp2.json()
    assert d2["total"] == 4
    assert len(d2["items"]) == 2
    assert d2["offset"] == 2


def test_api_list_incidents_validation_errors(client: TestClient):
    """Test invalid limit or offset queries return HTTP 422."""
    assert client.get("/api/v1/incidents?limit=0").status_code == 422
    assert client.get("/api/v1/incidents?limit=101").status_code == 422
    assert client.get("/api/v1/incidents?offset=-1").status_code == 422


# ============================================================================
# Regression Tests
# ============================================================================

def test_health_check_endpoint_unaffected(client: TestClient):
    """Test that existing health check endpoint continues working."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "RecallOps"}
