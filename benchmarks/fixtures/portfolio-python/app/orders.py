from datetime import UTC, datetime


def create_order(user_id: str, item_id: str) -> dict[str, str]:
    return {"user_id": user_id, "item_id": item_id, "status": "pending"}


def cancel_expired_order(order: dict[str, str]) -> dict[str, str]:
    order["status"] = "cancelled"
    order["cancelled_at"] = datetime.now(UTC).isoformat()
    return order
