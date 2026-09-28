import json
from copy import deepcopy
from pathlib import Path

_ORDERS = json.loads((Path(__file__).resolve().parents[1] / "data/orders.json").read_text())

def all_orders() -> dict:
    return deepcopy(_ORDERS)

def get_order(order_id: str) -> dict | None:
    return deepcopy(_ORDERS.get(order_id))
