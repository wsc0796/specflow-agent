PRODUCTS = {"coffee": {"price": 12, "enabled": True}}


def search_products(query: str) -> list[str]:
    return [name for name in PRODUCTS if query.lower() in name]
