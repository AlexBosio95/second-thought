import json
from typing import Any
import httpx
from pydantic import ValidationError
from app.config import Settings
from app.agent.prompts import SYSTEM_PROMPT
from app.decision.models import Proposal
from app.services.http import ProviderError, post_json
from app.tools.registry import definitions

class OpenRouterAgent:
    def __init__(self, settings: Settings, client: httpx.AsyncClient):
        self.settings, self.client = settings, client

    async def propose(self, message: str, context: dict) -> tuple[Proposal, str]:
        s = self.settings
        if not s.openrouter_model:
            raise ProviderError("OpenRouter", "model missing")
        messages = [{"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": json.dumps({"request": message, "context": context})}]
        body: dict[str, Any] = {"model": s.openrouter_model, "messages": messages,
                               "tools": definitions(), "tool_choice": "auto"}
        try:
            raw = await self._call(body)
        except ProviderError as exc:
            if exc.status not in {400, 404, 422}:
                raise
        else:
            try:
                calls = raw["choices"][0]["message"].get("tool_calls")
                if calls:
                    if len(calls) != 1:
                        raise ProviderError("OpenRouter", "multiple tool calls rejected")
                    call = calls[0]["function"]
                    return Proposal(tool=call["name"], arguments=json.loads(call["arguments"])), "tool_call"
            except (KeyError, IndexError, TypeError, ValueError, ValidationError):
                pass
        fallback = {"model": s.openrouter_model, "messages": [
            {"role": "system", "content": SYSTEM_PROMPT +
             '\nReturn only a JSON object with keys "tool" and "arguments". Available schemas: ' + json.dumps(definitions())},
            messages[1]], "response_format": {"type": "json_object"}}
        raw = await self._call(fallback)
        try:
            proposal = Proposal.model_validate_json(raw["choices"][0]["message"]["content"])
            return proposal, "json_fallback"
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise ProviderError("OpenRouter", "malformed proposal") from exc

    async def _call(self, body: dict) -> dict:
        s = self.settings
        return await post_json(self.client, "OpenRouter", s.openrouter_base_url.rstrip("/") + "/chat/completions",
                               s.openrouter_api_key.get_secret_value(), body, s.http_timeout_seconds)
