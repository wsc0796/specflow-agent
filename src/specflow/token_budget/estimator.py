"""Deterministic token estimation."""

from __future__ import annotations


class TokenEstimator:
    """Estimate tokens without provider-specific tokenizers."""

    def __init__(self, chars_per_token: int = 4) -> None:
        if chars_per_token <= 0:
            raise ValueError("chars_per_token must be positive")
        self._chars_per_token = chars_per_token

    def estimate(self, *messages: str) -> int:
        total_chars = sum(len(message) for message in messages)
        return max(1, (total_chars + self._chars_per_token - 1) // self._chars_per_token)
