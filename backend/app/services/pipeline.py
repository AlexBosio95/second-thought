from datetime import datetime, timezone
import logging
import re
from time import perf_counter
from uuid import uuid4
from app.config import Settings
from app.decision.jev import build_state, parse_signals
from app.decision.models import Decision, PolicyResult
from app.decision.policy import decide
from app.services.audit import AuditStore
from app.services.http import ProviderError
from app.tools.registry import REGISTRY, ToolValidationError, validate
from app.tools.orders import get_order
from app.tools.executor import execute

logger = logging.getLogger(__name__)
STEPS = ["User Request", "OpenRouter Agent", "Proposed Action", "Jev Evaluation", "Policy Decision", "Tool Execution"]

class Pipeline:
    def __init__(self, settings: Settings, agent, evaluator, audit: AuditStore):
        self.settings, self.agent, self.evaluator, self.audit = settings, agent, evaluator, audit

    async def run(self, message: str) -> dict:
        started = perf_counter()
        context = {oid: get_order(oid) for oid in sorted(set(re.findall(r"\bORD-\d{4}\b", message)))}
        record = {"id": str(uuid4()), "timestamp": datetime.now(timezone.utc).isoformat(),
                  "user_request": message, "context": context, "agent_proposal": None,
                  "jev": None, "jev_raw": None, "jev_state": None, "risk": None,
                  "policy_decision": "BLOCK", "executed": False, "tool_execution_result": None, "user_response": None,
                  "error": None, "models": {"agent": self.settings.openrouter_model, "judge": self.settings.jev_model},
                  "thresholds": {k: v for k, v in self.settings.model_dump().items() if k.endswith("threshold")},
                  "timeline": [{"name": name, "status": "waiting"} for name in STEPS]}
        record["timeline"][0]["status"] = "done"
        stage = 1
        policy = decide(None, "low", self.settings)
        try:
            proposal, mode = await self.agent.propose(message, context)
            record["agent_proposal"] = proposal.model_dump()
            record["proposal_mode"] = mode
            record["timeline"][1]["status"] = "done"
            stage = 2
            if proposal.tool == "none" and not proposal.arguments:
                policy = PolicyResult(decision=Decision.ASK_CLARIFICATION, rule="no_proposal",
                                      reason="Please clarify what you want to know or which action you want.")
            else:
                validate(proposal)
                record["risk"] = REGISTRY[proposal.tool][0]
                if proposal.tool != "respond_to_user":
                    oid = proposal.arguments["order_id"]
                    # Show referenced facts even if the agent proposed a different identifier.
                    context[oid] = get_order(oid)
                record["timeline"][2]["status"] = "done"
                stage = 3
                state = build_state(message, context, proposal, record["risk"])
                record["jev_state"] = state
                raw = await self.evaluator.evaluate(state)
                record["jev_raw"] = raw
                try:
                    signals = parse_signals(raw)
                except (KeyError, TypeError, ValueError) as exc:
                    raise ProviderError("TypeSafe", "malformed signals") from exc
                record["jev"] = signals.model_dump()
                record["timeline"][3]["status"] = "done"
                policy = decide(signals, record["risk"], self.settings)
        except ToolValidationError as exc:
            policy = PolicyResult(decision=Decision.ASK_CLARIFICATION if exc.missing else Decision.BLOCK,
                                  rule="tool_validation", reason=str(exc))
            record["timeline"][stage]["status"] = "blocked"
        except ProviderError as exc:
            record["error"] = {"provider": exc.provider, "kind": exc.kind, "status": exc.status}
            record["timeline"][stage]["status"] = "blocked"
            logger.warning("Evaluation %s failed: %s", record["id"], exc)
        record.update(policy_decision=policy.decision.value, policy=policy.model_dump(mode="json"))
        record["timeline"][4]["status"] = "done"
        # Persist authorization before entering the executor; audit failures prevent execution.
        self.audit.save(record)
        if policy.decision == Decision.EXECUTE:
            record["tool_execution_result"] = execute(proposal, policy)
            record["user_response"] = record["tool_execution_result"].get("response")
            record["executed"] = True
            record["timeline"][5]["status"] = "done"
        else:
            record["timeline"][5]["status"] = "blocked" if policy.decision == Decision.BLOCK else "waiting"
        record["duration_ms"] = round((perf_counter() - started) * 1000)
        self.audit.save(record)
        return record
