import asyncio
import logging
import json
from typing import Any
import httpx

logger = logging.getLogger(__name__)

def _reject_nonfinite(value: str) -> None:
    raise ValueError("Non-finite JSON number")

class ProviderError(Exception):
    def __init__(self, provider: str, kind: str, status: int | None = None):
        self.provider, self.kind, self.status = provider, kind, status
        super().__init__(f"{provider}: {kind}" + (f" (HTTP {status})" if status else ""))

async def post_json(client: httpx.AsyncClient, provider: str, url: str,
                    key: str, body: dict[str, Any], timeout: float) -> dict[str, Any]:
    if not key:
        raise ProviderError(provider, "API key missing")
    for attempt in range(4):
        try:
            async with asyncio.timeout(timeout):
                response = await client.post(url, headers={"Authorization": f"Bearer {key}"},
                                             json=body, timeout=timeout)
        except (httpx.TimeoutException, TimeoutError) as exc:
            raise ProviderError(provider, "timeout") from exc
        except httpx.RequestError as exc:
            raise ProviderError(provider, "connection failure") from exc
        if response.status_code in {429, 502, 503, 504} and attempt < 3:
            logger.warning("%s retry %d: HTTP %d", provider, attempt + 1, response.status_code)
            await asyncio.sleep(2 ** attempt)
            continue
        if response.is_error:
            raise ProviderError(provider, "request failed", response.status_code)
        try:
            data = json.loads(response.text, parse_constant=_reject_nonfinite)
            json.dumps(data, allow_nan=False)
            if not isinstance(data, dict):
                raise ValueError("Expected object")
            return data
        except ValueError as exc:
            raise ProviderError(provider, "malformed response") from exc
    raise ProviderError(provider, "retry budget exhausted")
