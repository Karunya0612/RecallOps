"""Tests for Hindsight memory banks client and API endpoints."""

import json
import pytest
import httpx
from fastapi.testclient import TestClient

from app.main import app
from app.api.banks import get_hindsight_client
from app.core.config import Settings
from app.services.hindsight import (
    HindsightClient,
    HindsightAuthError,
    HindsightConnectionError,
    HindsightTimeoutError,
    HindsightError,
)

FAKE_KEY = "test-secret-key-12345"
BASE_URL = "https://mock.hindsight.test"


# --- Settings tests ---

def test_settings_default_bank_id() -> None:
    """Verify Settings includes hindsight_bank_id with recallops-dev default."""
    settings = Settings()
    assert hasattr(settings, "hindsight_bank_id")
    assert settings.hindsight_bank_id == "recallops-dev"


# --- HindsightClient: list_banks unit tests ---

@pytest.mark.anyio
async def test_hindsight_client_list_banks_success() -> None:
    """Verify HindsightClient successfully queries documented endpoint with Bearer auth."""
    recorded_requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        recorded_requests.append(request)
        return httpx.Response(
            200,
            json={
                "banks": [
                    {
                        "bank_id": "incident-recovery",
                        "name": "Incident Recovery Bank",
                        "disposition": {"skepticism": 3, "literalism": 3, "empathy": 3},
                        "background": "",
                        "created_at": "2026-01-01T00:00:00Z",
                        "updated_at": "2026-01-01T00:00:00Z",
                    }
                ]
            },
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as async_client:
        client = HindsightClient(base_url=BASE_URL, api_key=FAKE_KEY, client=async_client)
        result = await client.list_banks()

    assert len(recorded_requests) == 1
    req = recorded_requests[0]
    assert req.method == "GET"
    assert str(req.url) == f"{BASE_URL}/v1/default/banks"
    assert req.headers.get("Authorization") == f"Bearer {FAKE_KEY}"
    assert "banks" in result
    assert result["banks"][0]["bank_id"] == "incident-recovery"


@pytest.mark.anyio
async def test_hindsight_client_missing_key() -> None:
    """Verify error when API key is missing."""
    client = HindsightClient(base_url=BASE_URL, api_key="")
    with pytest.raises(HindsightAuthError, match="not configured"):
        await client.list_banks()


@pytest.mark.anyio
async def test_hindsight_client_unauthorized_error() -> None:
    """Verify 401 returns HindsightAuthError."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "Unauthorized"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as async_client:
        client = HindsightClient(base_url=BASE_URL, api_key=FAKE_KEY, client=async_client)
        with pytest.raises(HindsightAuthError, match="Invalid or unauthorized"):
            await client.list_banks()


@pytest.mark.anyio
async def test_hindsight_client_timeout_error() -> None:
    """Verify timeout translates into HindsightTimeoutError."""
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("Timeout connecting to server", request=request)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as async_client:
        client = HindsightClient(base_url=BASE_URL, api_key=FAKE_KEY, client=async_client)
        with pytest.raises(HindsightTimeoutError, match="timed out"):
            await client.list_banks()


@pytest.mark.anyio
async def test_hindsight_client_connection_error() -> None:
    """Verify connection error translates into HindsightConnectionError."""
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Network is unreachable", request=request)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as async_client:
        client = HindsightClient(base_url=BASE_URL, api_key=FAKE_KEY, client=async_client)
        with pytest.raises(HindsightConnectionError, match="Failed to connect"):
            await client.list_banks()


# --- HindsightClient: bank_id resolution tests ---

def test_hindsight_client_bank_id_resolution() -> None:
    """Verify HindsightClient properly resolves explicit vs default bank IDs."""
    client = HindsightClient(base_url=BASE_URL, api_key=FAKE_KEY, default_bank_id="recallops-dev")
    assert client.get_configured_bank_id() == "recallops-dev"
    assert client.resolve_bank_id() == "recallops-dev"
    assert client.resolve_bank_id("custom-bank") == "custom-bank"

    client_no_default = HindsightClient(base_url=BASE_URL, api_key=FAKE_KEY, default_bank_id="")
    with pytest.raises(HindsightError, match="Bank ID cannot be empty"):
        client_no_default.resolve_bank_id()


# --- HindsightClient: retain_memory unit tests ---

@pytest.mark.anyio
async def test_hindsight_client_retain_success() -> None:
    """Verify retain_memory queries POST /v1/default/banks/{bank_id}/memories with Bearer auth."""
    recorded_requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        recorded_requests.append(request)
        return httpx.Response(
            200,
            json={
                "success": True,
                "bank_id": "incident-bank",
                "items_count": 1,
                "async": False,
                "operation_id": None,
                "usage": {"input_tokens": 120, "output_tokens": 40, "total_tokens": 160},
            },
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as async_client:
        client = HindsightClient(base_url=BASE_URL, api_key=FAKE_KEY, client=async_client)
        items = [{"content": "Database disk usage exceeded 90%", "context": "alert"}]
        result = await client.retain_memory(bank_id="incident-bank", items=items, async_mode=False)

    assert len(recorded_requests) == 1
    req = recorded_requests[0]
    assert req.method == "POST"
    assert str(req.url) == f"{BASE_URL}/v1/default/banks/incident-bank/memories"
    assert req.headers.get("Authorization") == f"Bearer {FAKE_KEY}"
    assert req.headers.get("Content-Type") == "application/json"
    body = json.loads(req.content)
    assert body["items"] == items
    assert body["async"] is False
    assert result["success"] is True
    assert result["items_count"] == 1


@pytest.mark.anyio
async def test_hindsight_client_retain_uses_default_bank() -> None:
    """Verify retain_memory uses configured default_bank_id when bank_id is omitted."""
    recorded_requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        recorded_requests.append(request)
        return httpx.Response(
            200,
            json={
                "success": True,
                "bank_id": "recallops-dev",
                "items_count": 1,
                "async": False,
                "operation_id": None,
                "usage": {"input_tokens": 100, "output_tokens": 30, "total_tokens": 130},
            },
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as async_client:
        client = HindsightClient(
            base_url=BASE_URL,
            api_key=FAKE_KEY,
            client=async_client,
            default_bank_id="recallops-dev",
        )
        items = [{"content": "Memory using default bank"}]
        result = await client.retain_memory(items=items)

    assert len(recorded_requests) == 1
    assert str(recorded_requests[0].url) == f"{BASE_URL}/v1/default/banks/recallops-dev/memories"
    assert result["bank_id"] == "recallops-dev"


@pytest.mark.anyio
async def test_hindsight_client_retain_auth_error() -> None:
    """Verify retain 401 returns HindsightAuthError."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "Unauthorized"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as async_client:
        client = HindsightClient(base_url=BASE_URL, api_key=FAKE_KEY, client=async_client)
        with pytest.raises(HindsightAuthError, match="Invalid or unauthorized"):
            await client.retain_memory(bank_id="incident-bank", items=[{"content": "test"}])


@pytest.mark.anyio
async def test_hindsight_client_retain_timeout() -> None:
    """Verify retain timeout raises HindsightTimeoutError."""
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("Timeout", request=request)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as async_client:
        client = HindsightClient(base_url=BASE_URL, api_key=FAKE_KEY, client=async_client)
        with pytest.raises(HindsightTimeoutError):
            await client.retain_memory(bank_id="incident-bank", items=[{"content": "test"}])


@pytest.mark.anyio
async def test_hindsight_client_retain_connection_error() -> None:
    """Verify retain connection error raises HindsightConnectionError."""
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Connection refused", request=request)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as async_client:
        client = HindsightClient(base_url=BASE_URL, api_key=FAKE_KEY, client=async_client)
        with pytest.raises(HindsightConnectionError):
            await client.retain_memory(bank_id="incident-bank", items=[{"content": "test"}])


# --- HindsightClient: recall_memories unit tests ---

@pytest.mark.anyio
async def test_hindsight_client_recall_success() -> None:
    """Verify recall_memories queries POST /v1/default/banks/{bank_id}/memories/recall with Bearer auth."""
    recorded_requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        recorded_requests.append(request)
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "id": "mem_oom_1",
                        "text": "Checkout service encountered high memory usage.",
                        "type": "observation",
                        "entities": ["checkout-service"],
                        "context": "incident_report",
                        "mentioned_at": "2026-09-28T09:00:00Z",
                    }
                ],
                "entities": {
                    "checkout-service": {
                        "entity_id": "ent_1",
                        "canonical_name": "checkout-service",
                        "observations": [],
                    }
                },
            },
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as async_client:
        client = HindsightClient(base_url=BASE_URL, api_key=FAKE_KEY, client=async_client)
        result = await client.recall_memories(
            bank_id="incident-bank",
            query="high memory checkout",
            types=["observation"],
            budget="high",
            max_tokens=1024,
        )

    assert len(recorded_requests) == 1
    req = recorded_requests[0]
    assert req.method == "POST"
    assert str(req.url) == f"{BASE_URL}/v1/default/banks/incident-bank/memories/recall"
    assert req.headers.get("Authorization") == f"Bearer {FAKE_KEY}"
    assert req.headers.get("Content-Type") == "application/json"
    body = json.loads(req.content)
    assert body["query"] == "high memory checkout"
    assert body["types"] == ["observation"]
    assert body["budget"] == "high"
    assert body["max_tokens"] == 1024
    assert len(result["results"]) == 1
    assert result["results"][0]["id"] == "mem_oom_1"


@pytest.mark.anyio
async def test_hindsight_client_recall_uses_default_bank() -> None:
    """Verify recall_memories uses configured default_bank_id when bank_id is omitted."""
    recorded_requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        recorded_requests.append(request)
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "id": "mem_default_1",
                        "text": "Recalled from default bank",
                        "type": "world",
                        "entities": [],
                        "context": "",
                        "mentioned_at": "2026-09-28T10:00:00Z",
                    }
                ],
                "entities": {},
            },
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as async_client:
        client = HindsightClient(
            base_url=BASE_URL,
            api_key=FAKE_KEY,
            client=async_client,
            default_bank_id="recallops-dev",
        )
        result = await client.recall_memories(query="test query")

    assert len(recorded_requests) == 1
    assert str(recorded_requests[0].url) == f"{BASE_URL}/v1/default/banks/recallops-dev/memories/recall"
    assert len(result["results"]) == 1


@pytest.mark.anyio
async def test_hindsight_client_recall_auth_error() -> None:
    """Verify recall 401 returns HindsightAuthError."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "Unauthorized"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as async_client:
        client = HindsightClient(base_url=BASE_URL, api_key=FAKE_KEY, client=async_client)
        with pytest.raises(HindsightAuthError, match="Invalid or unauthorized"):
            await client.recall_memories(bank_id="incident-bank", query="query text")


@pytest.mark.anyio
async def test_hindsight_client_recall_timeout() -> None:
    """Verify recall timeout raises HindsightTimeoutError."""
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("Timeout", request=request)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as async_client:
        client = HindsightClient(base_url=BASE_URL, api_key=FAKE_KEY, client=async_client)
        with pytest.raises(HindsightTimeoutError):
            await client.recall_memories(bank_id="incident-bank", query="query text")


@pytest.mark.anyio
async def test_hindsight_client_recall_connection_error() -> None:
    """Verify recall connection error raises HindsightConnectionError."""
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Connection failed", request=request)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as async_client:
        client = HindsightClient(base_url=BASE_URL, api_key=FAKE_KEY, client=async_client)
        with pytest.raises(HindsightConnectionError):
            await client.recall_memories(bank_id="incident-bank", query="query text")


# --- Endpoint Integration Tests (fully mocked via dependency overrides) ---

def test_api_list_banks_endpoint_success() -> None:
    """Test GET /api/v1/banks endpoint success."""
    class MockService:
        async def list_banks(self):
            return {
                "banks": [
                    {
                        "bank_id": "test-bank-1",
                        "name": "Test Bank",
                    }
                ]
            }

    app.dependency_overrides[get_hindsight_client] = lambda: MockService()
    try:
        client = TestClient(app)
        response = client.get("/api/v1/banks")
        assert response.status_code == 200
        data = response.json()
        assert "banks" in data
        assert data["banks"][0]["bank_id"] == "test-bank-1"
    finally:
        app.dependency_overrides.clear()


def test_api_get_default_bank_endpoint() -> None:
    """Test GET /api/v1/banks/default endpoint returns configured default bank ID."""
    class MockService:
        def get_configured_bank_id(self):
            return "recallops-dev"

    app.dependency_overrides[get_hindsight_client] = lambda: MockService()
    try:
        client = TestClient(app)
        response = client.get("/api/v1/banks/default")
        assert response.status_code == 200
        assert response.json() == {"default_bank_id": "recallops-dev"}
    finally:
        app.dependency_overrides.clear()


def test_api_list_banks_endpoint_auth_failure_no_secret_leak() -> None:
    """Test GET /api/v1/banks handles auth failure safely without leaking secrets."""
    class MockFailingService:
        async def list_banks(self):
            raise HindsightAuthError("Invalid or unauthorized Hindsight Cloud credentials.")

    app.dependency_overrides[get_hindsight_client] = lambda: MockFailingService()
    try:
        client = TestClient(app)
        response = client.get("/api/v1/banks")
        assert response.status_code == 502
        assert response.json() == {"detail": "Invalid or unauthorized Hindsight Cloud credentials."}
        assert FAKE_KEY not in response.text
    finally:
        app.dependency_overrides.clear()


def test_api_list_banks_endpoint_timeout_failure() -> None:
    """Test GET /api/v1/banks handles timeout error with HTTP 504."""
    class MockTimeoutService:
        async def list_banks(self):
            raise HindsightTimeoutError("Hindsight Cloud request timed out.")

    app.dependency_overrides[get_hindsight_client] = lambda: MockTimeoutService()
    try:
        client = TestClient(app)
        response = client.get("/api/v1/banks")
        assert response.status_code == 504
        assert response.json() == {"detail": "Hindsight Cloud request timed out."}
    finally:
        app.dependency_overrides.clear()


def test_api_list_banks_endpoint_connection_failure() -> None:
    """Test GET /api/v1/banks handles network error with HTTP 503."""
    class MockConnectionService:
        async def list_banks(self):
            raise HindsightConnectionError("Failed to connect to Hindsight Cloud.")

    app.dependency_overrides[get_hindsight_client] = lambda: MockConnectionService()
    try:
        client = TestClient(app)
        response = client.get("/api/v1/banks")
        assert response.status_code == 503
        assert response.json() == {"detail": "Failed to connect to Hindsight Cloud."}
    finally:
        app.dependency_overrides.clear()


def test_api_retain_endpoint_success() -> None:
    """Test POST /api/v1/banks/{bank_id}/memories success."""
    class MockRetainService:
        async def retain_memory(self, bank_id=None, items=None, async_mode=False):
            return {
                "success": True,
                "bank_id": bank_id or "recallops-dev",
                "items_count": len(items or []),
                "async": async_mode,
                "operation_id": None,
                "usage": {"input_tokens": 50, "output_tokens": 20, "total_tokens": 70},
            }

    app.dependency_overrides[get_hindsight_client] = lambda: MockRetainService()
    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/banks/prod-incident-bank/memories",
            json={
                "items": [
                    {
                        "content": "Redis connection pool timeout during traffic spike",
                        "context": "postmortem",
                    }
                ],
                "async": False,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["bank_id"] == "prod-incident-bank"
        assert data["items_count"] == 1
        assert data["usage"]["total_tokens"] == 70
    finally:
        app.dependency_overrides.clear()


def test_api_retain_endpoint_auth_failure_no_secret_leak() -> None:
    """Test POST /api/v1/banks/{bank_id}/memories auth failure without secret leakage."""
    class MockFailingService:
        async def retain_memory(self, bank_id=None, items=None, async_mode=False):
            raise HindsightAuthError("Invalid or unauthorized Hindsight Cloud credentials.")

    app.dependency_overrides[get_hindsight_client] = lambda: MockFailingService()
    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/banks/prod-incident-bank/memories",
            json={"items": [{"content": "some error"}]},
        )
        assert response.status_code == 502
        assert response.json() == {"detail": "Invalid or unauthorized Hindsight Cloud credentials."}
        assert FAKE_KEY not in response.text
    finally:
        app.dependency_overrides.clear()


def test_api_retain_endpoint_validation_error() -> None:
    """Test POST /api/v1/banks/{bank_id}/memories fails validation on empty items."""
    client = TestClient(app)
    response = client.post(
        "/api/v1/banks/prod-incident-bank/memories",
        json={"items": []},
    )
    assert response.status_code == 422


def test_api_recall_endpoint_success() -> None:
    """Test POST /api/v1/banks/{bank_id}/memories/recall success."""
    class MockRecallService:
        async def recall_memories(self, bank_id=None, query=None, **kwargs):
            return {
                "results": [
                    {
                        "id": "mem_redis_1",
                        "text": "Redis connection pool timeout during traffic spike",
                        "type": "observation",
                        "entities": ["redis"],
                        "context": "postmortem",
                        "mentioned_at": "2026-09-28T10:00:00Z",
                    }
                ],
                "entities": {
                    "redis": {
                        "entity_id": "ent_redis",
                        "canonical_name": "redis",
                        "observations": [],
                    }
                },
            }

    app.dependency_overrides[get_hindsight_client] = lambda: MockRecallService()
    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/banks/prod-incident-bank/memories/recall",
            json={
                "query": "Redis pool timeout",
                "types": ["observation"],
                "budget": "high",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) == 1
        assert data["results"][0]["id"] == "mem_redis_1"
        assert "redis" in data["entities"]
    finally:
        app.dependency_overrides.clear()


def test_api_recall_endpoint_auth_failure_no_secret_leak() -> None:
    """Test POST /api/v1/banks/{bank_id}/memories/recall auth failure without secret leakage."""
    class MockFailingService:
        async def recall_memories(self, bank_id=None, query=None, **kwargs):
            raise HindsightAuthError("Invalid or unauthorized Hindsight Cloud credentials.")

    app.dependency_overrides[get_hindsight_client] = lambda: MockFailingService()
    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/banks/prod-incident-bank/memories/recall",
            json={"query": "Redis pool timeout"},
        )
        assert response.status_code == 502
        assert response.json() == {"detail": "Invalid or unauthorized Hindsight Cloud credentials."}
        assert FAKE_KEY not in response.text
    finally:
        app.dependency_overrides.clear()


def test_api_recall_endpoint_validation_error() -> None:
    """Test POST /api/v1/banks/{bank_id}/memories/recall fails validation on empty query."""
    client = TestClient(app)
    response = client.post(
        "/api/v1/banks/prod-incident-bank/memories/recall",
        json={"query": ""},
    )
    assert response.status_code == 422
