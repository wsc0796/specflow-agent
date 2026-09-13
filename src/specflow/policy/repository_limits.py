"""Translate execution-policy repository settings into Tool limits."""

from __future__ import annotations

from specflow.policy.models import RepositoryPolicy
from specflow.tools.repository_policy import RepositoryPolicyLimits


def repository_tool_limits_from_policy(policy: RepositoryPolicy) -> RepositoryPolicyLimits:
    """Map only repository limits with a verified one-to-one meaning."""
    return RepositoryPolicyLimits(max_file_bytes=policy.max_file_bytes)
