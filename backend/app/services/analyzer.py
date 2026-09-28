"""Incident Analysis Service with deterministic symptom extraction and Hindsight recall."""

from datetime import datetime, timezone
import re
from typing import Any, Optional
from fastapi import HTTPException, status

from app.api.schemas import (
    AnalysisSuggestion,
    ExtractedSymptoms,
    IncidentAnalysisResponse,
    MemoryResult,
)
from app.db.repository import IncidentRepository
from app.services.hindsight import (
    HindsightAuthError,
    HindsightConnectionError,
    HindsightError,
    HindsightTimeoutError,
    HindsightClient,
)

# Deterministic patterns for log and symptom analysis
_LOG_SEVERITY_PATTERN = re.compile(r"\[?(FATAL|CRITICAL|ERROR|WARN(?:ING)?)\]?[:\s]", re.IGNORECASE)
_HTTP_STATUS_PATTERN = re.compile(r"\b(?:HTTP|status|code)?\s*[:=]?\s*(50[0-4]|40[0-4]|408|429|5\d{2}|4\d{2})\b", re.IGNORECASE)
_EXCEPTION_PATTERN = re.compile(r"\b([A-Z][a-zA-Z0-9]*(?:Exception|Error|Failure|Timeout))\b")

_RESOURCE_INDICATORS = [
    (re.compile(r"\b(cpu throttle|high cpu|cpu spike|cpu saturation)\b", re.IGNORECASE), "CPU throttling or saturation"),
    (re.compile(r"\b(oom|out of memory|memory leak|heap exhaustion)\b", re.IGNORECASE), "Memory exhaustion / OOM"),
    (re.compile(r"\b(connection pool exhaustion|pool exhausted|pool timeout|max connections)\b", re.IGNORECASE), "Connection pool exhaustion"),
    (re.compile(r"\b(disk full|watermark exceeded|disk exhaustion|no space left)\b", re.IGNORECASE), "Disk exhaustion / watermark exceeded"),
    (re.compile(r"\b(latency spike|high latency|timeout waiting|response times exceeded)\b", re.IGNORECASE), "High latency / timeout"),
    (re.compile(r"\b(cache eviction|eviction storm)\b", re.IGNORECASE), "Cache eviction storm"),
    (re.compile(r"\b(deadlock|lock wait timeout)\b", re.IGNORECASE), "Database lock contention / deadlock"),
    (re.compile(r"\b(ssl handshake|tls handshake|cert expired)\b", re.IGNORECASE), "SSL/TLS handshake failure"),
]

_RESOLUTION_KEYWORDS = [
    "resolved by", "resolution:", "fixed by", "mitigated by", "action taken:",
    "restarted", "scaled", "increased", "flushed", "reverted", "patched", "rolled back"
]


def extract_symptoms(
    incident: dict[str, Any],
    query_override: Optional[str] = None,
) -> ExtractedSymptoms:
    """Extract deterministic symptoms and construct a Hindsight recall query."""
    title = incident.get("title", "")
    description = incident.get("description", "")
    affected_service = incident.get("affected_service", "")
    severity = incident.get("severity", "medium")
    logs = incident.get("logs") or ""

    combined_text = f"{title}\n{description}\n{logs}"

    indicators: list[str] = []
    seen_indicators: set[str] = set()

    def add_indicator(ind: str) -> None:
        key = ind.strip().lower()
        if key and key not in seen_indicators:
            seen_indicators.add(key)
            indicators.append(ind.strip())

    # 1. Log Severity
    severity_match = _LOG_SEVERITY_PATTERN.search(combined_text)
    if severity_match:
        add_indicator(f"Log level: {severity_match.group(1).upper()}")

    # 2. HTTP Status Codes
    for match in _HTTP_STATUS_PATTERN.finditer(combined_text):
        code = match.group(1)
        add_indicator(f"HTTP {code}")

    # 3. Exception Classes
    for match in _EXCEPTION_PATTERN.finditer(combined_text):
        exc_name = match.group(1)
        # Avoid generic keywords that are not specific error names
        if exc_name not in ("Error", "Exception", "Timeout"):
            add_indicator(exc_name)

    # 4. Known Resource & Infrastructure Indicators
    for pattern, description_text in _RESOURCE_INDICATORS:
        if pattern.search(combined_text):
            add_indicator(description_text)

    # Fallback indicator if none detected
    if not indicators:
        add_indicator(f"Service {affected_service} severity {severity}")

    # Build recall query
    if query_override and query_override.strip():
        recall_query = query_override.strip()
    else:
        top_indicators = [ind for ind in indicators[:4] if not ind.startswith("Log level:")]
        indicator_str = " ".join(top_indicators)
        raw_query = f"{affected_service} {title} {indicator_str}".strip()
        recall_query = " ".join(raw_query.split())

    return ExtractedSymptoms(
        affected_service=affected_service,
        severity=severity,
        indicators=indicators,
        recall_query=recall_query,
    )


_GENERIC_SERVICE_WORDS = {
    "service", "api", "gateway", "worker", "db", "database", "timeout",
    "error", "server", "host", "cluster", "system", "app", "application",
    "client", "node", "pod", "backend", "frontend", "infrastructure",
    "exception", "platform", "queue", "cache", "memory", "network", "cloud",
    "incident", "postmortem", "resolution", "fix", "log", "logs",
    "latency", "pool", "deadlock", "contention", "cpu", "disk", "heap",
    "socket", "proxy", "connectivity", "upstream", "downstream", "traffic",
}

_GENERIC_INFRASTRUCTURE_PHRASES = {
    "connection pool", "connection pooling", "connection pool exhaustion",
    "connection pool capacity", "pool capacity", "pool exhaustion",
    "pool timeout", "max connections", "connection limit", "pool limit",
    "outbound connection pool", "outbound connection pool capacity",
    "upstream connectivity", "downstream connectivity", "network connectivity",
    "network latency", "latency spike", "high latency", "timeout waiting",
    "response time", "response times", "database cluster", "database connection",
    "database lock", "lock contention", "deadlock cleared", "cache eviction",
    "heap exhaustion", "out of memory", "cpu throttle", "cpu spike",
    "ssl handshake", "tls handshake", "cert expired",
    "user session", "circuit breaker", "retry policy",
}

_NON_SERVICE_ID_PATTERNS = [
    # Incident identifiers: inc-dc1acd79dcd3, inc-1234, incident-99, incident_abc
    re.compile(r"^inc(?:ident)?[_-][a-zA-Z0-9]+(?:[-_][a-zA-Z0-9]+)*$", re.IGNORECASE),
    # Memory, bank, run, request, ticket, task identifiers
    re.compile(r"^(?:mem|memory|bank|item|req|request|task|job|ticket|run|alert|id)[_-][a-zA-Z0-9]+(?:[-_][a-zA-Z0-9]+)*$", re.IGNORECASE),
    # Standard UUID (8-4-4-4-12)
    re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE),
    # Hex hashes or alphanumeric IDs with 8+ chars
    re.compile(r"^[0-9a-f]{8,}$", re.IGNORECASE),
    # Timestamps / Dates (ISO dates, YYYY-MM-DD, epoch timestamps)
    re.compile(r"^\d{4}-\d{2}-\d{2}(?:[T\s].*)?$", re.IGNORECASE),
    re.compile(r"^\d+$"),
]

# Suffix pattern for legitimate service-like identifiers: inventory-api, payment-gateway, orders-db, auth-service, etc.
_SERVICE_IDENTIFIER_PATTERN = re.compile(
    r"^[a-zA-Z0-9]+(?:[-_][a-zA-Z0-9]+)*[-_](?:service|api|gateway|worker|db|cluster|app|proxy|consumer|producer|daemon|server)$",
    re.IGNORECASE,
)


def _is_identifier_or_timestamp(val: str) -> bool:
    """Check if a string matches an incident ID, UUID, timestamp, or memory ID."""
    clean = val.strip().lower()
    return any(p.match(clean) for p in _NON_SERVICE_ID_PATTERNS)


def _is_valid_service_name(name: Optional[str]) -> bool:
    """Validate whether an extracted string is a plausible service name rather than generic terminology, IDs, or timestamps."""
    if not name:
        return False
    clean = name.strip(" \t\n\r'\"`:,.")
    if len(clean) < 3:
        return False
    # Never classify incident IDs, UUIDs, timestamps, or memory IDs as service names
    if _is_identifier_or_timestamp(clean):
        return False
    lower_clean = clean.lower()
    if lower_clean in _GENERIC_SERVICE_WORDS:
        return False
    norm_space = re.sub(r"[-_\s]+", " ", lower_clean)
    if norm_space in _GENERIC_INFRASTRUCTURE_PHRASES:
        return False
    if not any(c.isalpha() for c in clean):
        return False
    return True


def _normalize_service_name(name: Optional[str]) -> str:
    """Normalize a service name into canonical lowercase hyphenated form."""
    if not name:
        return ""
    clean = name.strip(" \t\n\r'\"`:,.")
    return re.sub(r"[-_\s]+", "-", clean).lower()


def _is_service_identifier(name: Optional[str]) -> bool:
    """Check if a candidate string matches a known service-like naming pattern (e.g. inventory-api, payment-gateway)."""
    if not _is_valid_service_name(name):
        return False
    norm = _normalize_service_name(name)
    return bool(_SERVICE_IDENTIFIER_PATTERN.match(norm))


def _services_match(svc1: str, svc2: str) -> bool:
    """Compare two service identifiers case-insensitively, normalizing hyphens, underscores, and spaces."""
    return _normalize_service_name(svc1) == _normalize_service_name(svc2)


def classify_memory_relevance(
    mem: MemoryResult,
    target_service: str,
) -> tuple[str, Optional[str]]:
    """Deterministically classify whether a memory is direct, cross-service, or general relevance.

    Returns:
        tuple[str, Optional[str]]: (classification, detected_service)
        classification is one of: "direct", "cross_service", or "general".
    """
    target_norm = _normalize_service_name(target_service)
    target_spaced = re.sub(r"[-_\s]+", " ", target_norm)

    mem_text = mem.text or ""
    mem_text_lower = mem_text.lower()

    # 1. Direct match check in entities (target matching)
    for ent in (mem.entities or []):
        if _services_match(ent, target_service):
            return "direct", target_norm

    # 2. Direct match check in text (target matching)
    escaped_target = re.escape(target_norm)
    escaped_spaced = re.escape(target_spaced)
    if re.search(rf"\b{escaped_target}\b", mem_text_lower) or re.search(rf"\b{escaped_spaced}\b", mem_text_lower):
        return "direct", target_norm

    # 3. Check for explicit service syntax in memory text
    # e.g., 'affecting service "payment-gateway"', 'service: inventory-api', 'on service payment-gateway'
    service_pattern = re.search(
        r"(?:affecting service|on service|for service)\s*[:=]?\s*['\"]?([a-zA-Z0-9_\s-]+)['\"]?",
        mem_text,
        re.IGNORECASE,
    )
    if not service_pattern:
        service_pattern = re.search(
            r"\bservice\s*[:=]\s*['\"]?([a-zA-Z0-9_\s-]+)['\"]?",
            mem_text,
            re.IGNORECASE,
        )
    if not service_pattern:
        service_pattern = re.search(
            r"\bservice\s+['\"]([a-zA-Z0-9_\s-]+)['\"]",
            mem_text,
            re.IGNORECASE,
        )

    if service_pattern:
        cand = service_pattern.group(1).strip()
        if _is_service_identifier(cand):
            norm_cand = _normalize_service_name(cand)
            if _services_match(norm_cand, target_service):
                return "direct", target_norm
            return "cross_service", norm_cand

    # 4. Check for known service-like identifiers in entities
    # Never infer cross-service from arbitrary nouns, incident IDs, or infrastructure terms
    for ent in (mem.entities or []):
        if _is_service_identifier(ent):
            norm_ent = _normalize_service_name(ent)
            if not _services_match(norm_ent, target_service):
                return "cross_service", norm_ent

    # 5. Check for known service-like identifiers in memory text
    # e.g. inventory-api, payment-gateway, auth-service, orders-db
    hyphenated_pattern = re.search(
        r"\b([a-zA-Z0-9]+(?:[-_][a-zA-Z0-9]+)*-(?:service|api|gateway|worker|db|cluster|app|proxy|consumer|producer))\b",
        mem_text,
        re.IGNORECASE,
    )
    if hyphenated_pattern:
        cand = hyphenated_pattern.group(1).strip()
        if _is_service_identifier(cand):
            norm_cand = _normalize_service_name(cand)
            if _services_match(norm_cand, target_service):
                return "direct", target_norm
            return "cross_service", norm_cand

    # 6. Default: ambiguous, general infrastructure context, or generic concepts
    return "general", None


def generate_suggestions(
    symptoms: ExtractedSymptoms,
    memories: list[MemoryResult],
) -> list[AnalysisSuggestion]:
    """Generate evidence-based suggestions referencing real recalled memories or baseline triage."""
    suggestions: list[AnalysisSuggestion] = []
    cross_services_detected: set[str] = set()

    if memories:
        for mem in memories:
            text_lower = mem.text.lower()
            has_resolution = any(kw in text_lower for kw in _RESOLUTION_KEYWORDS)
            relevance, detected_service = classify_memory_relevance(mem, symptoms.affected_service)

            if relevance == "direct":
                if has_resolution:
                    suggestions.append(
                        AnalysisSuggestion(
                            category="historical_resolution",
                            suggestion=(
                                f"Past resolution from memory '{mem.id}' for '{symptoms.affected_service}': "
                                f"{mem.text.strip()}. "
                                f"Review whether current symptoms match this verified same-service historical context."
                            ),
                            evidence_source=f"memory:{mem.id}",
                        )
                    )
                else:
                    suggestions.append(
                        AnalysisSuggestion(
                            category="historical_observation",
                            suggestion=f"Historical context from memory '{mem.id}' for '{symptoms.affected_service}': {mem.text.strip()}.",
                            evidence_source=f"memory:{mem.id}",
                        )
                    )

            elif relevance == "cross_service":
                other_svc = detected_service or "another service"
                cross_services_detected.add(other_svc)
                if has_resolution:
                    suggestions.append(
                        AnalysisSuggestion(
                            category="cross_service_reference",
                            suggestion=(
                                f"Cross-service reference from memory '{mem.id}' (service '{other_svc}' vs current '{symptoms.affected_service}'): "
                                f"{mem.text.strip()}. "
                                f"NOTE: This resolution is from a different service and is NOT a verified fix for '{symptoms.affected_service}'. "
                                f"Review only for shared dependencies, architectural analogies, or cascading failures."
                            ),
                            evidence_source=f"memory:{mem.id}",
                        )
                    )
                else:
                    suggestions.append(
                        AnalysisSuggestion(
                            category="cross_service_reference",
                            suggestion=(
                                f"Cross-service observation from memory '{mem.id}' (service '{other_svc}'): "
                                f"{mem.text.strip()}. "
                                f"NOTE: This context originated from '{other_svc}' rather than '{symptoms.affected_service}'."
                            ),
                            evidence_source=f"memory:{mem.id}",
                        )
                    )

            else:  # "general"
                if has_resolution:
                    suggestions.append(
                        AnalysisSuggestion(
                            category="general_reference",
                            suggestion=(
                                f"General reference from memory '{mem.id}': {mem.text.strip()}. "
                                f"NOTE: This memory does not specifically identify service '{symptoms.affected_service}' "
                                f"and is NOT a verified same-service resolution. Evaluate whether this mitigation applies."
                            ),
                            evidence_source=f"memory:{mem.id}",
                        )
                    )
                else:
                    suggestions.append(
                        AnalysisSuggestion(
                            category="general_reference",
                            suggestion=(
                                f"General observation from memory '{mem.id}': {mem.text.strip()}. "
                                f"NOTE: This context is general or ambiguous and does not identify service '{symptoms.affected_service}'."
                            ),
                            evidence_source=f"memory:{mem.id}",
                        )
                    )

        # Explicit precaution for cross-service matches
        if cross_services_detected:
            valid_cross_services = {
                svc for svc in cross_services_detected
                if svc and _is_valid_service_name(svc) and not _is_identifier_or_timestamp(svc)
            }
            if valid_cross_services:
                svc_list = ", ".join(sorted(valid_cross_services))
                suggestions.append(
                    AnalysisSuggestion(
                        category="precaution",
                        suggestion=(
                            f"Cross-service matches detected from: {svc_list}. "
                            f"Do not apply resolutions from other services directly to '{symptoms.affected_service}' "
                            f"without verifying shared infrastructure, common libraries, or cascading dependencies."
                        ),
                        evidence_source="safety_guideline",
                    )
                )

        # Baseline safety precaution
        suggestions.append(
            AnalysisSuggestion(
                category="precaution",
                suggestion=(
                    "Validate that current service configuration, dependencies, and environment match "
                    "past incident conditions before applying historical mitigations. Past resolutions "
                    "are not guaranteed to resolve current symptoms."
                ),
                evidence_source="safety_guideline",
            )
        )
    else:
        # Fallback when no memories matched in Hindsight
        suggestions.append(
            AnalysisSuggestion(
                category="diagnostic_step",
                suggestion=(
                    f"No matching historical incidents or resolutions were found in Hindsight memory bank "
                    f"for '{symptoms.affected_service}'."
                ),
                evidence_source="general_triage",
            )
        )

        indicators_str = " ".join(symptoms.indicators).lower()

        if any(term in indicators_str for term in ("timeout", "http 504", "http 502", "latency", "connection")):
            suggestions.append(
                AnalysisSuggestion(
                    category="diagnostic_step",
                    suggestion=(
                        f"Inspect network latency, connection pool utilization, and upstream service availability "
                        f"for '{symptoms.affected_service}'."
                    ),
                    evidence_source="general_triage",
                )
            )

        if any(term in indicators_str for term in ("cpu", "oom", "memory", "disk", "exhaustion", "watermark")):
            suggestions.append(
                AnalysisSuggestion(
                    category="diagnostic_step",
                    suggestion=(
                        f"Verify system resource metrics (CPU, memory, disk headroom) and container restart counts "
                        f"for '{symptoms.affected_service}'."
                    ),
                    evidence_source="general_triage",
                )
            )

        if any(term in indicators_str for term in ("http 500", "error", "exception", "failure")):
            suggestions.append(
                AnalysisSuggestion(
                    category="diagnostic_step",
                    suggestion=(
                        f"Examine application logs and stack traces around the incident window for "
                        f"'{symptoms.affected_service}' to diagnose unhandled errors."
                    ),
                    evidence_source="general_triage",
                )
            )

        suggestions.append(
            AnalysisSuggestion(
                category="diagnostic_step",
                suggestion=(
                    f"Review recent releases, configuration updates, and infrastructure changes affecting "
                    f"'{symptoms.affected_service}'."
                ),
                evidence_source="general_triage",
            )
        )

    return suggestions


class IncidentAnalyzer:
    """Service orchestrating incident analysis and Hindsight Cloud memory recall."""

    def __init__(
        self,
        repository: IncidentRepository,
        hindsight_client: HindsightClient,
    ) -> None:
        self.repository = repository
        self.hindsight_client = hindsight_client

    async def analyze_incident(
        self,
        incident_id: str,
        query_override: Optional[str] = None,
        max_tokens: Optional[int] = None,
    ) -> IncidentAnalysisResponse:
        """Analyze an incident by ID, extracting symptoms and recalling relevant memories."""
        incident = self.repository.get_incident(incident_id)
        if incident is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Incident '{incident_id}' not found.",
            )

        symptoms = extract_symptoms(incident, query_override=query_override)
        bank_id = self.hindsight_client.get_configured_bank_id()

        try:
            recall_data = await self.hindsight_client.recall_memories(
                bank_id=bank_id,
                query=symptoms.recall_query,
                max_tokens=max_tokens,
            )
        except HindsightAuthError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Authentication with Hindsight Cloud failed.",
            ) from exc
        except HindsightTimeoutError as exc:
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="Hindsight Cloud request timed out.",
            ) from exc
        except HindsightConnectionError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Failed to connect to Hindsight Cloud.",
            ) from exc
        except HindsightError as exc:
            raise HTTPException(
                status_code=exc.status_code,
                detail=exc.message,
            ) from exc

        recalled_raw = recall_data.get("results", [])
        recalled_memories = [
            MemoryResult.model_validate(item)
            for item in recalled_raw
        ]

        suggestions = generate_suggestions(symptoms, recalled_memories)

        return IncidentAnalysisResponse(
            incident_id=incident_id,
            analyzed_at=datetime.now(timezone.utc).isoformat(),
            bank_id=bank_id,
            incident_title=incident["title"],
            extracted_symptoms=symptoms,
            recalled_memories=recalled_memories,
            suggestions=suggestions,
            has_historical_matches=len(recalled_memories) > 0,
        )
