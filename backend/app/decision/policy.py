from app.config import Settings
from app.decision.models import Decision, PolicyResult, Signals

def decide(signals: Signals | None, risk: str, settings: Settings) -> PolicyResult:
    """First matching rule wins. next_action may restrict, never grant, execution."""
    def result(decision: Decision, rule: str, reason: str) -> PolicyResult:
        return PolicyResult(decision=decision, rule=rule, reason=reason)

    if signals is None:
        return result(Decision.BLOCK, "decision_unavailable", "Decision layer unavailable; fail closed.")
    if risk not in {"low", "high"}:
        return result(Decision.BLOCK, "unknown_risk", "Unknown tool risk.")
    s, c = signals, settings
    next_action = s.next_action
    strong_next = next_action.probabilities[next_action.choice] >= c.next_action_threshold
    if s.action_supported < c.supported_threshold:
        return result(Decision.BLOCK, "unsupported_action", "The request and context do not support this action.")
    if strong_next and next_action.choice == "block":
        return result(Decision.BLOCK, "next_block", "Strong Jev block signal triggers the policy veto.")
    if s.evidence_sufficient < c.evidence_threshold:
        return result(Decision.BLOCK, "insufficient_evidence", "Retrieve additional evidence before trying again.")
    if s.intent_clear < c.intent_threshold:
        return result(Decision.ASK_CLARIFICATION, "unclear_intent", "Clarify the intended action and missing details.")
    if s.human_review_required >= c.human_review_threshold:
        return result(Decision.REQUIRE_APPROVAL, "human_review", "Human review probability exceeds the policy threshold.")
    if strong_next and next_action.choice in {"clarify", "retrieve_more", "human"}:
        decisions = {"clarify": Decision.ASK_CLARIFICATION, "retrieve_more": Decision.BLOCK,
                     "human": Decision.REQUIRE_APPROVAL}
        return result(decisions[next_action.choice], "next_action_veto", "Jev's suggested next step restricts automatic execution.")
    required = max(c.safe_threshold, c.high_risk_safe_threshold) if risk == "high" else c.safe_threshold
    if s.safe_to_execute < required:
        return result(Decision.REQUIRE_APPROVAL, "safety_threshold", f"Automatic execution requires safety probability >= {required:.2f}.")
    return result(Decision.EXECUTE, "all_checks_passed", "All deterministic policy checks passed.")
