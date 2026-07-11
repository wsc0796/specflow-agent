"""Trace System models."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class LLMTrace:
    """Metadata-only record for one LLM execution."""

    run_id: str
    prompt_name: str
    prompt_version: str
    prompt_hash: str
    context_hash: str
    model: str
    latency_ms: int
    input_tokens: int
    output_tokens: int
    status: str
    error_type: str | None = None
    fallback_level: str | None = None
    retry_count: int = 0
    metadata: dict[str, str] = field(default_factory=dict)

    def as_dict(self) -> dict[str, object]:
        return {
            "run_id": self.run_id,
            "prompt_name": self.prompt_name,
            "prompt_version": self.prompt_version,
            "prompt_hash": self.prompt_hash,
            "context_hash": self.context_hash,
            "model": self.model,
            "latency_ms": self.latency_ms,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "status": self.status,
            "error_type": self.error_type,
            "fallback_level": self.fallback_level,
            "retry_count": self.retry_count,
            "metadata": dict(sorted(self.metadata.items())),
        }
