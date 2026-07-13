FAILED_LOGINS: dict[str, int] = {}


def authenticate(user_id: str) -> None:
    if not user_id:
        raise ValueError("user is required")


def record_failed_login(user_id: str) -> int:
    FAILED_LOGINS[user_id] = FAILED_LOGINS.get(user_id, 0) + 1
    return FAILED_LOGINS[user_id]
