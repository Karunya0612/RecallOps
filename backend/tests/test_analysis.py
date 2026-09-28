"""Tests for Phase 4: Incident Analysis and Hindsight Memory Recall."""

from unittest.mock import AsyncMock
import pytest
from fastapi.testclient import TestClient

from app.api.banks import get_hindsight_client
from app.db.repository import IncidentRepository, get_incident_repository
from app.main import app
from app.services.analyzer import (
    classify_memory_relevance,
    extract_symptoms,
    generate_suggestions,
)
from app.services.hindsight import (
    HindsightAuthError,
    HindsightConnectionError,
    HindsightTimeoutError,
    HindsightClient,
)
from app.api.schemas import ExtractedSymptoms, MemoryResult


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
    mock.recall_memories.return_value = {
        "results": [
            {
                "id": "mem-101",
                "text": "Incident #101: Payment gateway timeout resolved by scaling egress pool connections and flushing DNS cache.",
                "type": "experience",
                "entities": ["payment-gateway"],
                "context": "postmortem_archive",
                "mentioned_at": "2026-08-15T12:00:00Z",
            },
            {
                "id": "mem-102",
                "text": "Payment gateway experiences latency spikes during upstream vendor maintenance windows.",
                "type": "observation",
                "entities": ["payment-gateway"],
                "context": "runbook",
                "mentioned_at": "2026-07-10T09:00:00Z",
            },
        ]
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
# Unit Tests: Symptom Extraction and Suggestion Generation
# ============================================================================

def test_extract_symptoms_with_logs():
    """Test deterministic symptom extraction from incident details and logs."""
    incident = {
        "title": "Payment gateway latency spike",
        "description": "Checkout response times exceeded 5,000ms after release.",
        "affected_service": "payment-gateway",
        "severity": "high",
        "logs": "2026-09-28T18:40:00Z [ERROR] HTTP 504 TimeoutException waiting for upstream provider after 5000ms",
    }
    symptoms = extract_symptoms(incident)
    assert symptoms.affected_service == "payment-gateway"
    assert symptoms.severity == "high"
    assert "Log level: ERROR" in symptoms.indicators
    assert "HTTP 504" in symptoms.indicators
    assert "TimeoutException" in symptoms.indicators
    assert "High latency / timeout" in symptoms.indicators
    assert "payment-gateway" in symptoms.recall_query
    assert "latency spike" in symptoms.recall_query.lower()


def test_extract_symptoms_missing_logs():
    """Test symptom extraction when logs are None or omitted."""
    incident = {
        "title": "Database connection pool exhaustion",
        "description": "Max connections reached on primary database cluster with lock contention.",
        "affected_service": "orders-db",
        "severity": "critical",
        "logs": None,
    }
    symptoms = extract_symptoms(incident)
    assert symptoms.affected_service == "orders-db"
    assert symptoms.severity == "critical"
    assert "Connection pool exhaustion" in symptoms.indicators
    assert "orders-db" in symptoms.recall_query


def test_extract_symptoms_query_override():
    """Test that query_override takes precedence in recall_query."""
    incident = {
        "title": "Ingress SSL cert expired",
        "description": "TLS handshake failure on edge proxies.",
        "affected_service": "edge-proxy",
        "severity": "critical",
    }
    symptoms = extract_symptoms(incident, query_override="edge proxy cert renewal rollback")
    assert symptoms.recall_query == "edge proxy cert renewal rollback"


def test_classify_memory_relevance_direct():
    """Test direct service classification by entities, exact text, and case-insensitivity."""
    # Direct match via entity
    mem_ent = MemoryResult(
        id="mem-1",
        text="Service recovered after restart.",
        entities=["payment-gateway"],
    )
    rel, svc = classify_memory_relevance(mem_ent, "payment-gateway")
    assert rel == "direct"
    assert svc == "payment-gateway"

    # Direct match via text (case-insensitive and spaced/hyphenated)
    mem_text = MemoryResult(
        id="mem-2",
        text="Incident on Payment Gateway: connection timeout cleared.",
    )
    rel2, svc2 = classify_memory_relevance(mem_text, "payment-gateway")
    assert rel2 == "direct"


def test_classify_memory_relevance_cross_service():
    """Test cross-service classification when another service is explicitly referenced."""
    # Cross-service via entity
    mem_ent = MemoryResult(
        id="mem-inv-1",
        text="Worker pool saturation resolved by increasing replicas.",
        entities=["inventory-api"],
    )
    rel, svc = classify_memory_relevance(mem_ent, "payment-gateway")
    assert rel == "cross_service"
    assert svc == "inventory-api"

    # Cross-service via text pattern
    mem_text = MemoryResult(
        id="mem-inv-2",
        text="Incident affecting service 'inventory-api': deadlock cleared.",
    )
    rel2, svc2 = classify_memory_relevance(mem_text, "payment-gateway")
    assert rel2 == "cross_service"
    assert svc2 == "inventory-api"


def test_classify_memory_relevance_general_and_generic():
    """Test that generic terminology (API, service, timeout) is classified conservatively as general."""
    mem_gen = MemoryResult(
        id="mem-gen-1",
        text="Timeout occurred while calling external API service host.",
        entities=["api", "service", "timeout"],
    )
    rel, svc = classify_memory_relevance(mem_gen, "payment-gateway")
    assert rel == "general"
    assert svc is None


def test_classify_memory_relevance_incident_id_not_service():
    """Regression test: Incident IDs, UUIDs, and memory IDs must never be classified as services."""
    # Incident ID in entity
    mem_inc = MemoryResult(
        id="mem-inc-1",
        text="Incident inc-dc1acd79dcd3 resolved after restart.",
        entities=["inc-dc1acd79dcd3"],
    )
    rel, svc = classify_memory_relevance(mem_inc, "inventory-api")
    assert rel == "general"
    assert svc is None

    # UUID and memory ID in entities
    mem_uuid = MemoryResult(
        id="mem-uuid-1",
        text="Issue cleared in production.",
        entities=["550e8400-e29b-41d4-a716-446655440000", "mem_abc12345"],
    )
    rel2, svc2 = classify_memory_relevance(mem_uuid, "inventory-api")
    assert rel2 == "general"
    assert svc2 is None


def test_classify_memory_relevance_infrastructure_terms_not_service():
    """Regression test: Infrastructure terms (connection pool, database, latency) must not be classified as services."""
    mem_infra = MemoryResult(
        id="mem-infra-1",
        text="Connection pool exhaustion resolved by increasing max connections on database cluster.",
        entities=["connection pool", "upstream connectivity", "database", "latency", "timeout"],
    )
    rel, svc = classify_memory_relevance(mem_infra, "inventory-api")
    assert rel == "general"
    assert svc is None


def test_classify_memory_relevance_payment_gateway_cross_service_and_inventory_api_direct():
    """Regression test: payment-gateway is cross-service for inventory-api; inventory-api is direct for itself."""
    pg_mem = MemoryResult(
        id="mem-pg-live",
        text=(
            "Incident inc-dc1acd79dcd3: 'Payment gateway latency spike' affecting service 'payment-gateway' "
            "with severity 'high'. ENGINEER-CONFIRMED RESOLUTION: The incident was resolved by increasing connection pool max_size. "
            "Outcome: SUCCESS. Engineer notes: None."
        ),
        entities=["inc-dc1acd79dcd3", "payment-gateway", "connection pool"],
    )

    # 1. When target is inventory-api, payment-gateway is cross-service
    rel_cs, svc_cs = classify_memory_relevance(pg_mem, "inventory-api")
    assert rel_cs == "cross_service"
    assert svc_cs == "payment-gateway"

    # Verify suggestion and precaution generation
    symptoms = ExtractedSymptoms(
        affected_service="inventory-api",
        severity="high",
        indicators=["HTTP 500"],
        recall_query="inventory-api latency",
    )
    suggestions = generate_suggestions(symptoms, [pg_mem])
    cross_sug = next(s for s in suggestions if s.category == "cross_service_reference")
    assert "mem-pg-live" in cross_sug.suggestion
    assert "payment-gateway" in cross_sug.suggestion
    assert "NOT a verified fix for 'inventory-api'" in cross_sug.suggestion

    precaution_sug = [s for s in suggestions if s.category == "precaution"]
    assert any("Cross-service matches detected from: payment-gateway" in s.suggestion for s in precaution_sug)
    # Precaution must NEVER list incident IDs or infrastructure terms
    for p in precaution_sug:
        assert "inc-dc1acd79dcd3" not in p.suggestion
        assert "connection pool" not in p.suggestion

    # 2. When target is payment-gateway, the memory is direct
    rel_dir, svc_dir = classify_memory_relevance(pg_mem, "payment-gateway")
    assert rel_dir == "direct"
    assert svc_dir == "payment-gateway"

    # 3. When an inventory-api memory is evaluated against inventory-api, it is direct
    inv_mem = MemoryResult(
        id="mem-inv-live",
        text=(
            "Incident inc-dc1acd79dcd3: 'Inventory API deadlock' affecting service 'inventory-api' "
            "with severity 'critical'. ENGINEER-CONFIRMED RESOLUTION: The incident was resolved by clearing lock contention. "
            "Outcome: SUCCESS. Engineer notes: None."
        ),
        entities=["inc-dc1acd79dcd3", "inventory-api", "connection pool"],
    )
    rel_inv, svc_inv = classify_memory_relevance(inv_mem, "inventory-api")
    assert rel_inv == "direct"
    assert svc_inv == "inventory-api"


def test_classify_memory_relevance_exact_live_memories_for_inventory_api():
    """Exact reproduction test for the live Inventory API timeout incident memories.

    Verifies:
    1. Memories referencing payment-gateway are classified as cross_service with canonical 'payment-gateway'.
    2. Incident IDs, UUIDs, and infrastructure terms (connection pool) are never classified as services.
    3. Ambiguous memories are classified as general_reference, not cross_service_reference.
    4. The precaution lists ONLY 'payment-gateway'.
    """
    live_memories = [
        MemoryResult(
            id="b52e6761-d993-43f0-a084-a5c7063b7bd7",
            text="Incident inc-dc1acd79dcd3 involved a high-severity latency spike in the payment-gateway service. | When: 2026-09-28",
            entities=["inc-dc1acd79dcd3", "payment-gateway"],
        ),
        MemoryResult(
            id="3acf628d-64ac-409d-a91c-78c3d893fe1f",
            text="Incident inc-dc1acd79dcd3 involved a high-severity latency spike in the payment-gateway service. | When: 2026-09-28",
            entities=["payment gateway"],
        ),
        MemoryResult(
            id="68dec7ae-a88a-444a-908a-9c83702791d7",
            text="A high-severity latency spike incident (inc-dc1acd79dcd3) occurred in the payment-gateway service on 2026-09-28 due to exhausted outbound connection pool capacity; it was resolved by increasing the outbound connection pool capacity, confirmed via synthetic testing..",
            entities=["inc-dc1acd79dcd3", "payment-gateway", "connection pool capacity"],
        ),
        MemoryResult(
            id="56bb9de6-e009-4626-ab1f-24c3d118705a",
            text="The incident was resolved by increasing the outbound connection pool capacity, confirmed via synthetic testing. | When: 2026-09-28",
            entities=["inc-dc1acd79dcd3", "connection pool capacity"],
        ),
        MemoryResult(
            id="71bb4a77-6da2-4c29-ba5c-2316aa0f163c",
            text="A payment gateway timeout incident occurred due to exhausted outbound connection pool capacity. | When: 2026-09-28",
            entities=["payment gateway", "connection pool"],
        ),
        MemoryResult(
            id="c1653bfa-f446-4cc9-bbe7-0dc73b00d3ed",
            text="Incident inc-dc1acd79dcd3 was resolved by increasing the outbound connection pool capacity, confirmed via synthetic testing. | When: 2026-09-28",
            entities=["inc-dc1acd79dcd3"],
        ),
        MemoryResult(
            id="5e612aa9-2205-4c7d-a958-4d9cdbf24fff",
            text="The incident was resolved by increasing the connection pool limit and verifying upstream connectivity. | When: 2026-09-28",
            entities=["connection pool", "upstream connectivity"],
        ),
    ]

    target = "inventory-api"

    # Classifications
    rel_b5, svc_b5 = classify_memory_relevance(live_memories[0], target)
    assert rel_b5 == "cross_service"
    assert svc_b5 == "payment-gateway"

    rel_3a, svc_3a = classify_memory_relevance(live_memories[1], target)
    assert rel_3a == "cross_service"
    assert svc_3a == "payment-gateway"

    rel_68, svc_68 = classify_memory_relevance(live_memories[2], target)
    assert rel_68 == "cross_service"
    assert svc_68 == "payment-gateway"

    # Ambiguous memory without service mention: must be general, not cross-service
    rel_56, svc_56 = classify_memory_relevance(live_memories[3], target)
    assert rel_56 == "general"
    assert svc_56 is None

    # Memory with 'payment gateway' entity: canonical 'payment-gateway'
    rel_71, svc_71 = classify_memory_relevance(live_memories[4], target)
    assert rel_71 == "cross_service"
    assert svc_71 == "payment-gateway"

    # Ambiguous memory with only inc-dc1acd79dcd3: must be general, never cross-service
    rel_c1, svc_c1 = classify_memory_relevance(live_memories[5], target)
    assert rel_c1 == "general"
    assert svc_c1 is None

    # Ambiguous memory with connection pool and upstream connectivity: must be general
    rel_5e, svc_5e = classify_memory_relevance(live_memories[6], target)
    assert rel_5e == "general"
    assert svc_5e is None

    # Suggestion generation
    symptoms = ExtractedSymptoms(
        affected_service=target,
        severity="medium",
        indicators=["timeout"],
        recall_query="inventory-api timeout",
    )
    suggestions = generate_suggestions(symptoms, live_memories)

    # Check ambiguous memories are general_reference, NOT cross_service_reference
    sug_56 = next(s for s in suggestions if "56bb9de6" in s.evidence_source)
    assert sug_56.category == "general_reference"

    sug_c1 = next(s for s in suggestions if "c1653bfa" in s.evidence_source)
    assert sug_c1.category == "general_reference"

    sug_5e = next(s for s in suggestions if "5e612aa9" in s.evidence_source)
    assert sug_5e.category == "general_reference"

    # Precaution verification: ONLY payment-gateway, NO incident IDs or infrastructure terms
    precautions = [s for s in suggestions if s.category == "precaution"]
    cs_precaution = next(s for s in precautions if "Cross-service matches detected from:" in s.suggestion)
    assert cs_precaution.suggestion.startswith("Cross-service matches detected from: payment-gateway.")
    assert "inc-dc1acd79dcd3" not in cs_precaution.suggestion
    assert "connection pool" not in cs_precaution.suggestion
    assert "payment gateway" not in cs_precaution.suggestion  # must be canonical payment-gateway


def test_generate_suggestions_with_memories():
    """Test suggestions generated from direct same-service recalled memories citing real IDs and resolutions."""
    symptoms = ExtractedSymptoms(
        affected_service="payment-gateway",
        severity="high",
        indicators=["HTTP 504", "TimeoutException"],
        recall_query="payment-gateway query",
    )
    memories = [
        MemoryResult(
            id="mem-1",
            text="Incident on payment-gateway: Resolved by scaling egress pool connections and flushing DNS cache.",
            type="experience",
            entities=["payment-gateway"],
        ),
        MemoryResult(
            id="mem-2",
            text="Payment gateway experiences latency spikes during vendor maintenance on Sundays.",
            type="observation",
            entities=["payment-gateway"],
        ),
    ]
    suggestions = generate_suggestions(symptoms, memories)
    assert len(suggestions) == 3  # resolution + observation + precaution

    res_sug = next(s for s in suggestions if s.category == "historical_resolution")
    assert "mem-1" in res_sug.suggestion
    assert res_sug.evidence_source == "memory:mem-1"
    assert "verified same-service" in res_sug.suggestion

    obs_sug = next(s for s in suggestions if s.category == "historical_observation")
    assert "mem-2" in obs_sug.suggestion
    assert obs_sug.evidence_source == "memory:mem-2"

    precaution = next(s for s in suggestions if s.category == "precaution")
    assert precaution.evidence_source == "safety_guideline"


def test_generate_suggestions_cross_service_distinction():
    """Test that an inventory-api memory recalled for payment-gateway is NEVER labeled historical_resolution."""
    symptoms = ExtractedSymptoms(
        affected_service="payment-gateway",
        severity="high",
        indicators=["HTTP 504"],
        recall_query="payment-gateway query",
    )
    memories = [
        MemoryResult(
            id="mem-inv-99",
            text="Incident #45 affecting service 'inventory-api': resolved by restarting worker pods.",
            type="experience",
            entities=["inventory-api"],
        ),
    ]
    suggestions = generate_suggestions(symptoms, memories)

    # CRITICAL: Must NEVER be categorized as historical_resolution
    assert not any(s.category == "historical_resolution" for s in suggestions)

    # Must be categorized as cross_service_reference
    cross_sug = next(s for s in suggestions if s.category == "cross_service_reference")
    assert "mem-inv-99" in cross_sug.suggestion
    assert cross_sug.evidence_source == "memory:mem-inv-99"
    assert "inventory-api" in cross_sug.suggestion
    assert "NOT a verified fix for 'payment-gateway'" in cross_sug.suggestion

    # Explicit cross-service precaution must be present
    precaution_sug = [s for s in suggestions if s.category == "precaution"]
    assert any("Cross-service matches detected from: inventory-api" in s.suggestion for s in precaution_sug)


def test_generate_suggestions_general_service_ambiguous():
    """Test that ambiguous general memories are not presented as verified same-service fixes."""
    symptoms = ExtractedSymptoms(
        affected_service="payment-gateway",
        severity="medium",
        indicators=["timeout"],
        recall_query="payment-gateway query",
    )
    memories = [
        MemoryResult(
            id="mem-gen-42",
            text="Resolved by increasing connection timeout from 5s to 15s.",
            type="experience",
        ),
    ]
    suggestions = generate_suggestions(symptoms, memories)

    # Must NOT be historical_resolution
    assert not any(s.category == "historical_resolution" for s in suggestions)

    # Must be general_reference
    gen_sug = next(s for s in suggestions if s.category == "general_reference")
    assert "mem-gen-42" in gen_sug.suggestion
    assert "NOT a verified same-service resolution" in gen_sug.suggestion
    assert gen_sug.evidence_source == "memory:mem-gen-42"


def test_generate_suggestions_empty_memories():
    """Test suggestions generated when no historical memories exist."""
    symptoms = ExtractedSymptoms(
        affected_service="auth-service",
        severity="high",
        indicators=["HTTP 500", "OutOfMemoryError"],
        recall_query="auth-service query",
    )
    suggestions = generate_suggestions(symptoms, [])
    assert len(suggestions) >= 2
    notice = suggestions[0]
    assert notice.category == "diagnostic_step"
    assert "No matching historical incidents" in notice.suggestion
    assert notice.evidence_source == "general_triage"


# ============================================================================
# Integration Tests: POST /api/v1/incidents/{incident_id}/analyze
# ============================================================================

def test_analyze_incident_success_with_matches(client: TestClient, repo: IncidentRepository, mock_hindsight_client: AsyncMock):
    """Test successful analysis returning recalled memories and evidence-based suggestions."""
    inc = repo.create_incident(
        title="Payment gateway timeout",
        description="Checkout response time degraded after deploy.",
        affected_service="payment-gateway",
        severity="high",
        logs="2026-09-28 [ERROR] HTTP 504 TimeoutException",
    )

    resp = client.post(f"/api/v1/incidents/{inc['id']}/analyze")
    assert resp.status_code == 200

    data = resp.json()
    assert data["incident_id"] == inc["id"]
    assert data["bank_id"] == "recallops-dev"
    assert data["incident_title"] == "Payment gateway timeout"
    assert data["has_historical_matches"] is True
    assert len(data["recalled_memories"]) == 2
    assert data["recalled_memories"][0]["id"] == "mem-101"

    # Verify suggestions cite the memory ID
    suggestions = data["suggestions"]
    assert any("mem-101" in s["suggestion"] for s in suggestions)
    assert any(s["category"] == "precaution" for s in suggestions)

    # Verify Hindsight call parameters
    mock_hindsight_client.recall_memories.assert_awaited_once()
    call_kwargs = mock_hindsight_client.recall_memories.call_args.kwargs
    assert call_kwargs["bank_id"] == "recallops-dev"
    assert "payment-gateway" in call_kwargs["query"]


def test_analyze_incident_empty_recall_results(client: TestClient, repo: IncidentRepository, mock_hindsight_client: AsyncMock):
    """Test analysis returns 200 OK with has_historical_matches=False when recall returns no results."""
    mock_hindsight_client.recall_memories.return_value = {"results": []}

    inc = repo.create_incident(
        title="Unknown internal error",
        description="First-time service failure without history.",
        affected_service="new-service",
        severity="medium",
    )

    resp = client.post(f"/api/v1/incidents/{inc['id']}/analyze")
    assert resp.status_code == 200

    data = resp.json()
    assert data["has_historical_matches"] is False
    assert data["recalled_memories"] == []
    assert len(data["suggestions"]) > 0
    assert any("No matching historical incidents" in s["suggestion"] for s in data["suggestions"])


def test_analyze_incident_custom_query_override(client: TestClient, repo: IncidentRepository, mock_hindsight_client: AsyncMock):
    """Test that query_override in request payload overrides automatic query."""
    inc = repo.create_incident(
        title="Worker thread deadlock",
        description="Queue consumer halted processing.",
        affected_service="queue-worker",
        severity="high",
    )

    payload = {
        "query_override": "custom queue deadlock fix",
        "max_tokens": 1000,
    }
    resp = client.post(f"/api/v1/incidents/{inc['id']}/analyze", json=payload)
    assert resp.status_code == 200

    call_kwargs = mock_hindsight_client.recall_memories.call_args.kwargs
    assert call_kwargs["query"] == "custom queue deadlock fix"
    assert call_kwargs["max_tokens"] == 1000


def test_analyze_incident_validation_errors(client: TestClient, repo: IncidentRepository):
    """Test validation errors for invalid query_override or max_tokens bounds."""
    inc = repo.create_incident(
        title="Test incident",
        description="Test description",
        affected_service="test-svc",
        severity="low",
    )

    # max_tokens < 1
    resp = client.post(f"/api/v1/incidents/{inc['id']}/analyze", json={"max_tokens": 0})
    assert resp.status_code == 422

    # max_tokens > 4000
    resp = client.post(f"/api/v1/incidents/{inc['id']}/analyze", json={"max_tokens": 4001})
    assert resp.status_code == 422

    # query_override > 500 chars
    resp = client.post(f"/api/v1/incidents/{inc['id']}/analyze", json={"query_override": "x" * 501})
    assert resp.status_code == 422


def test_analyze_incident_nonexistent_id(client: TestClient):
    """Test analyzing a nonexistent incident returns HTTP 404."""
    resp = client.post("/api/v1/incidents/inc-doesnotexist/analyze")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


def test_analyze_incident_hindsight_auth_failure(client: TestClient, repo: IncidentRepository, mock_hindsight_client: AsyncMock):
    """Test Hindsight authentication failure maps safely to HTTP 502 without secrets."""
    mock_hindsight_client.recall_memories.side_effect = HindsightAuthError("Invalid credentials")

    inc = repo.create_incident(
        title="Auth fail incident",
        description="Test desc",
        affected_service="api",
        severity="medium",
    )

    resp = client.post(f"/api/v1/incidents/{inc['id']}/analyze")
    assert resp.status_code == 502
    assert resp.json()["detail"] == "Authentication with Hindsight Cloud failed."


def test_analyze_incident_hindsight_timeout(client: TestClient, repo: IncidentRepository, mock_hindsight_client: AsyncMock):
    """Test Hindsight timeout maps safely to HTTP 504."""
    mock_hindsight_client.recall_memories.side_effect = HindsightTimeoutError()

    inc = repo.create_incident(
        title="Timeout incident",
        description="Test desc",
        affected_service="api",
        severity="medium",
    )

    resp = client.post(f"/api/v1/incidents/{inc['id']}/analyze")
    assert resp.status_code == 504
    assert resp.json()["detail"] == "Hindsight Cloud request timed out."


def test_analyze_incident_hindsight_connection_failure(client: TestClient, repo: IncidentRepository, mock_hindsight_client: AsyncMock):
    """Test Hindsight connection failure maps safely to HTTP 503."""
    mock_hindsight_client.recall_memories.side_effect = HindsightConnectionError()

    inc = repo.create_incident(
        title="Connection failure incident",
        description="Test desc",
        affected_service="api",
        severity="medium",
    )

    resp = client.post(f"/api/v1/incidents/{inc['id']}/analyze")
    assert resp.status_code == 503
    assert resp.json()["detail"] == "Failed to connect to Hindsight Cloud."
