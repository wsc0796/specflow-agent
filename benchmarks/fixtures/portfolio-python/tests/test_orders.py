from app.orders import create_order


def test_create_order_is_pending() -> None:
    assert create_order("u-1", "coffee")["status"] == "pending"
