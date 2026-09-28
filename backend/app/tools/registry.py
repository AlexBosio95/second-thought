from typing import Any
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from app.decision.models import Proposal
from app.tools.orders import get_order

class OrderArgs(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    order_id: str = Field(pattern=r"^ORD-\d{4}$")

class AddressArgs(OrderArgs):
    new_address: str = Field(min_length=5, max_length=300, pattern=r"\S")

class RefundArgs(OrderArgs):
    amount: float = Field(gt=0, allow_inf_nan=False)

class ReplyArgs(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    message: str = Field(min_length=1, max_length=4000, pattern=r"\S")

REGISTRY = {
    "respond_to_user": ("low", ReplyArgs, "Propose a text reply to a general question in the current chat. No external effects; requires policy authorization before display as an answer."),
    "get_order": ("low", OrderArgs, "Look up one mock order."),
    "send_tracking_link": ("low", OrderArgs, "Simulate sending an order tracking link."),
    "update_address": ("high", AddressArgs, "Simulate changing an order delivery address."),
    "refund_order": ("high", RefundArgs, "Simulate a refund in the order currency."),
    "cancel_order": ("high", OrderArgs, "Simulate cancelling one order."),
}

class ToolValidationError(Exception):
    def __init__(self, message: str, missing: bool = False):
        self.missing = missing
        super().__init__(message)

def definitions() -> list[dict[str, Any]]:
    return [{"type": "function", "function": {"name": name, "description": description,
            "parameters": model.model_json_schema()}}
            for name, (_, model, description) in REGISTRY.items()]

def validate(proposal: Proposal) -> dict[str, Any]:
    if proposal.tool not in REGISTRY:
        raise ToolValidationError("Unknown tool")
    try:
        args = REGISTRY[proposal.tool][1].model_validate(proposal.arguments).model_dump()
    except ValidationError as exc:
        missing = all(e["type"] == "missing" for e in exc.errors())
        fields = ", ".join(str(e["loc"][0]) for e in exc.errors())
        raise ToolValidationError(f"{'Missing' if missing else 'Invalid'} arguments: {fields}", missing) from exc
    if proposal.tool == "respond_to_user":
        return args
    order = get_order(args["order_id"])
    if order is None:
        raise ToolValidationError("Order does not exist")
    if proposal.tool == "refund_order" and args["amount"] > order["amount"]:
        raise ToolValidationError("Refund exceeds order amount")
    return args
