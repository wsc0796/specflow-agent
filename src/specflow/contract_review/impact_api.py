"""Authenticated HTTP surface; all model I/O remains on the one worker."""

from typing import Annotated

from fastapi import APIRouter, Header, Query, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from specflow.contract_review.api import query_fields, service
from specflow.contract_review.impact_schemas import CreateImpactDiscovery, ImpactAdoption

router = APIRouter(prefix="/api/v1/contract-impact-discoveries", tags=["contract-impact"])
Key = Annotated[str, Header(min_length=1, max_length=128)]


@router.post("", status_code=202)
async def create_discovery(body: CreateImpactDiscovery, request: Request, idempotency_key: Key):
    query_fields(request)
    status, result = await run_in_threadpool(service(request).impacts.create, body, idempotency_key)
    return JSONResponse(result, status_code=status)


@router.get("/{discovery_id}")
def get_discovery(discovery_id: str, request: Request):
    query_fields(request)
    return service(request).impacts.get(discovery_id)


@router.get("/{discovery_id}/events")
def events(
    discovery_id: str,
    request: Request,
    cursor: Annotated[str | None, Query(min_length=1, max_length=512)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
):
    query_fields(request, ("cursor", "limit"))
    return service(request).impacts.events(discovery_id, cursor, limit)


@router.get("/{discovery_id}/events/{event_id}")
def event_detail(discovery_id: str, event_id: str, request: Request):
    query_fields(request)
    return service(request).impacts.event_detail(discovery_id, event_id)


@router.post("/{discovery_id}/adoptions", status_code=202)
async def adopt(discovery_id: str, body: ImpactAdoption, request: Request, idempotency_key: Key):
    query_fields(request)
    status, result = await run_in_threadpool(
        service(request).impacts.adopt, discovery_id, body, idempotency_key
    )
    return JSONResponse(result, status_code=status)
