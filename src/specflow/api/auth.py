"""Bearer token authentication for the SpecFlow API."""

from __future__ import annotations

import os

from fastapi import HTTPException, status

DEV_MODE = os.environ.get("SPECFLOW_DEV_MODE", "0") == "1"


def require_auth() -> str:
    """Require valid Bearer token in production, skip in dev mode."""
    if DEV_MODE:
        return "dev-mode"

    expected = os.environ.get("SPECFLOW_API_TOKEN", "")
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server authentication not configured",
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Bearer token required in production mode",
    )
