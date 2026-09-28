"""Dedicated Hindsight Cloud client service."""

from typing import Any, Optional
from urllib.parse import quote
import httpx


class HindsightError(Exception):
    """Base exception for Hindsight client errors."""

    def __init__(self, message: str, status_code: int = 502) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class HindsightAuthError(HindsightError):
    """Authentication or authorization failure with Hindsight Cloud."""

    def __init__(self, message: str = "Authentication with Hindsight Cloud failed.") -> None:
        super().__init__(message=message, status_code=502)


class HindsightConnectionError(HindsightError):
    """Connection or network error communicating with Hindsight Cloud."""

    def __init__(self, message: str = "Failed to connect to Hindsight Cloud.") -> None:
        super().__init__(message=message, status_code=503)


class HindsightTimeoutError(HindsightError):
    """Timeout communicating with Hindsight Cloud."""

    def __init__(self, message: str = "Hindsight Cloud request timed out.") -> None:
        super().__init__(message=message, status_code=504)


class HindsightClient:
    """Client for interacting with Hindsight Cloud."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        client: Optional[httpx.AsyncClient] = None,
        timeout: float = 15.0,
        default_bank_id: str = "recallops-dev",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.default_bank_id = default_bank_id
        self._injected_client = client

    def get_configured_bank_id(self) -> str:
        """Return the default configured bank ID for incident recovery workflows."""
        return self.default_bank_id

    def resolve_bank_id(self, bank_id: Optional[str] = None) -> str:
        """Resolve the target bank ID, falling back to the configured default if omitted."""
        chosen = (bank_id if bank_id is not None else self.default_bank_id or "").strip()
        if not chosen:
            raise HindsightError("Bank ID cannot be empty and no default bank ID is configured.", status_code=400)
        return chosen

    async def _send_request(
        self,
        method: str,
        endpoint: str,
        json_body: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Send an authenticated HTTP request to Hindsight Cloud with safe error mapping."""
        if not self.api_key:
            raise HindsightAuthError("Hindsight API key is not configured.")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
        }
        if json_body is not None:
            headers["Content-Type"] = "application/json"

        try:
            if self._injected_client:
                response = await self._injected_client.request(
                    method, endpoint, headers=headers, json=json_body
                )
            else:
                async with httpx.AsyncClient(timeout=self.timeout) as http_client:
                    response = await http_client.request(
                        method, endpoint, headers=headers, json=json_body
                    )

            if response.status_code in (401, 403):
                raise HindsightAuthError("Invalid or unauthorized Hindsight Cloud credentials.")

            if response.status_code == 404:
                raise HindsightError("Requested Hindsight bank or resource was not found.", status_code=404)

            response.raise_for_status()
            data = response.json()
            return data

        except httpx.TimeoutException as exc:
            raise HindsightTimeoutError() from exc
        except (httpx.ConnectError, httpx.RequestError) as exc:
            raise HindsightConnectionError() from exc
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            raise HindsightError(
                f"Hindsight Cloud returned HTTP error {status}.",
                status_code=502,
            ) from exc

    async def list_banks(self) -> dict[str, Any]:
        """List all available memory banks from Hindsight Cloud.

        Documented endpoint: GET /v1/default/banks
        Header: Authorization: Bearer <API_KEY>
        """
        endpoint = f"{self.base_url}/v1/default/banks"
        return await self._send_request("GET", endpoint)

    async def retain_memory(
        self,
        bank_id: Optional[str] = None,
        items: Optional[list[dict[str, Any]]] = None,
        async_mode: bool = False,
    ) -> dict[str, Any]:
        """Store (retain) memories in a specified or default memory bank.

        Documented endpoint: POST /v1/default/banks/{bank_id}/memories
        Header: Authorization: Bearer <API_KEY>
        """
        target_bank = self.resolve_bank_id(bank_id)
        safe_bank_id = quote(target_bank, safe="")
        endpoint = f"{self.base_url}/v1/default/banks/{safe_bank_id}/memories"
        payload = {
            "items": items or [],
            "async": async_mode,
        }
        return await self._send_request("POST", endpoint, json_body=payload)

    async def recall_memories(
        self,
        bank_id: Optional[str] = None,
        query: Optional[str] = None,
        types: Optional[list[str]] = None,
        budget: Optional[str] = None,
        max_tokens: Optional[int] = None,
        trace: bool = False,
        query_timestamp: Optional[str] = None,
    ) -> dict[str, Any]:
        """Search (recall) relevant memories from a specified or default memory bank.

        Documented endpoint: POST /v1/default/banks/{bank_id}/memories/recall
        Header: Authorization: Bearer <API_KEY>
        """
        target_bank = self.resolve_bank_id(bank_id)
        clean_query = (query or "").strip()
        if not clean_query:
            raise HindsightError("Query cannot be empty.", status_code=400)

        safe_bank_id = quote(target_bank, safe="")
        endpoint = f"{self.base_url}/v1/default/banks/{safe_bank_id}/memories/recall"

        payload: dict[str, Any] = {"query": clean_query}
        if types is not None:
            payload["types"] = types
        if budget is not None:
            payload["budget"] = budget
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if trace:
            payload["trace"] = trace
        if query_timestamp is not None:
            payload["query_timestamp"] = query_timestamp

        return await self._send_request("POST", endpoint, json_body=payload)
