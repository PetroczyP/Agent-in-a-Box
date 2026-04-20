from dataclasses import dataclass


@dataclass
class OrderItem:
    name: str
    quantity: int
    unit_price: float


def calculate_total(items: list[OrderItem]) -> float:
    total = 0.0
    for item in items:
        total += item.quantity * item.unit_price
    return total


def place_order(items: list[OrderItem]) -> dict:
    total = calculate_total(items)
    return {"status": "confirmed", "total": total, "items": len(items)}
