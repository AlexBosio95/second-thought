from typing import Any
from app.decision.models import Decision, PolicyResult, Proposal
from app.tools.registry import validate
from app.tools.orders import get_order

def execute(proposal: Proposal, authorization: PolicyResult) -> dict[str, Any]:
    if authorization.decision != Decision.EXECUTE:
        raise PermissionError("Execution requires explicit EXECUTE from policy")
    args = validate(proposal)
    result: dict[str, Any] = {"status": "simulated", "tool": proposal.tool,
                             "message": f"{proposal.tool} would have been executed", "arguments": args}
    if proposal.tool == "respond_to_user":
        result["response"] = args["message"]
        result["message"] = "Reply authorized for display in the current chat"
    if proposal.tool == "get_order":
        result["order"] = get_order(args["order_id"])
    if proposal.tool == "send_tracking_link":
        result["tracking_url"] = f"https://tracking.example.com/{args['order_id']}"
    return result
