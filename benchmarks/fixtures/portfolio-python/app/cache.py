CACHE: dict[str, object] = {}


def invalidate_product_cache(product_id: str) -> None:
    CACHE.pop(f"product:{product_id}", None)
