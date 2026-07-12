"""Run management API endpoints."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from specflow.api.auth import require_auth

router = APIRouter(prefix="/api/v1", tags=["runs"])

# In-memory run store (SQLite integration deferred)
_runs: dict[str, dict[str, Any]] = {}
_cancellations: set[str] = set()

# Rate limiting
_rate_limits: dict[str, list[float]] = {}
MAX_CONCURRENT = int(os.environ.get("SPECFLOW_MAX_CONCURRENT", "2"))
MAX_PER_MINUTE = int(os.environ.get("SPECFLOW_MAX_PER_MINUTE", "10"))


class RunRequest(BaseModel):
    repository_path: str = Field(..., min_length=1)
    requirement: str = Field(..., min_length=1)
    mode: str = Field(default="multi-agent")
    provider: str = Field(default="openai-compatible")
    model: str = Field(default="deepseek-v4-flash")


def _check_rate_limit(requester: str) -> None:
    import time

    now = time.time()
    entries = _rate_limits.get(requester, [])
    entries = [t for t in entries if now - t < 60]
    if len(entries) >= MAX_PER_MINUTE:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    entries.append(now)
    _rate_limits[requester] = entries

    if len([r for r in _runs.values() if r.get("status") == "running"]) >= MAX_CONCURRENT:
        raise HTTPException(status_code=429, detail="Concurrent run limit reached")


def _validate_repo_path(path: str) -> Path:
    """Reject paths outside the allowed repository root."""
    allowed_root = os.environ.get("SPECFLOW_REPO_ROOT", "")
    resolved = Path(path).resolve()
    if allowed_root:
        allowed = Path(allowed_root).resolve()
        try:
            resolved.relative_to(allowed)
        except ValueError:
            raise HTTPException(status_code=403, detail="Repository path not allowed")
    if not resolved.exists() or not resolved.is_dir():
        raise HTTPException(status_code=400, detail="Repository not found or not a directory")
    return resolved


@router.post("/runs", status_code=201)
def create_run(
    body: RunRequest,
    request: Request,
    _auth: str = Depends(require_auth),
) -> dict[str, Any]:
    """Submit a new analysis run."""
    requester = request.client.host if request.client else "unknown"
    _check_rate_limit(requester)

    repo = _validate_repo_path(body.repository_path)
    run_id = f"run-api-{abs(hash(body.requirement)):08x}"

    if run_id in _runs and _runs[run_id].get("status") == "running":
        raise HTTPException(status_code=409, detail="Run already in progress")
    _runs[run_id] = {
        "run_id": run_id,
        "status": "queued",
        "repository": str(repo),
        "requirement": body.requirement,
        "mode": body.mode,
        "provider": body.provider,
        "model": body.model,
        "created_at": "",
        "completed_at": None,
        "error": None,
    }

    return _runs[run_id]


@router.get("/runs")
def list_runs(_auth: str = Depends(require_auth)) -> list[dict[str, Any]]:
    """List all runs."""
    return list(_runs.values())


@router.get("/runs/{run_id}")
def get_run(run_id: str, _auth: str = Depends(require_auth)) -> dict[str, Any]:
    """Get a single run by ID."""
    run = _runs.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.post("/runs/{run_id}/cancel")
def cancel_run(run_id: str, _auth: str = Depends(require_auth)) -> dict[str, Any]:
    """Request cancellation of a running analysis."""
    run = _runs.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.get("status") not in ("queued", "running"):
        raise HTTPException(status_code=409, detail="Run is not active")
    _cancellations.add(run_id)
    run["status"] = "cancelling"
    return run
