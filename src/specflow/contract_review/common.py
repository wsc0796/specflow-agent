"""Shared identities, canonical JSON and domain errors."""

import hashlib
import json
from datetime import UTC, datetime
from uuid import uuid4


def canonical(value) -> str:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )


def digest(value) -> str:
    data = value if isinstance(value, bytes) else canonical(value).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def identity(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class ReviewError(Exception):
    def __init__(self, code: str, message: str, status: int = 409, **details):
        super().__init__(message)
        self.code, self.message, self.status, self.details = code, message, status, details

    def envelope(self) -> dict:
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "request_id": identity("req"),
                "retryable": self.status in (429, 503),
                "details": self.details,
            }
        }
