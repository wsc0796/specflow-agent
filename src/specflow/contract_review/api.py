"""Authenticated HTTP projection of contract-review intake and records."""

import base64
import json
from typing import Annotated

from fastapi import APIRouter, Header, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from specflow.contract_review.checkpoints import ResolutionBatch, RevisionRequest
from specflow.contract_review.common import ReviewError, canonical
from specflow.contract_review.schemas import CreateReview
from specflow.contract_review.verification import VerificationImport

router = APIRouter(prefix="/api/v1/contract-reviews", tags=["contract-reviews"])


class BodyLimitMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not scope["path"].startswith("/api/v1/contract-reviews"):
            return await self.app(scope, receive, send)
        chunks, size = [], 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            size += len(chunk)
            if size > 1024**2:
                error = ReviewError("REQUEST_TOO_LARGE", "请求正文超过 1 MiB。", 413)
                return await JSONResponse(error.envelope(), status_code=413)(scope, receive, send)
            chunks.append(chunk)
            if not message.get("more_body", False):
                break
        delivered = False

        async def bounded_receive():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": b"".join(chunks), "more_body": False}
            return await receive()

        await self.app(scope, bounded_receive, send)


def service(request):
    value = getattr(request.app.state, "contract_reviews", None)
    if value is None:
        raise ReviewError("DEPENDENCY_UNAVAILABLE", "尚未配置审查运行底座。", 503)
    return value


def query_fields(request, allowed=()):
    if any(key not in allowed for key in request.query_params):
        raise ReviewError("INVALID_QUERY", "存在未定义的查询参数。", 422)
    if len(request.query_params.multi_items()) != len(request.query_params):
        raise ReviewError("INVALID_QUERY", "查询参数不得重复。", 422)


@router.post("", status_code=202)
async def create_review(
    body: CreateReview,
    request: Request,
    idempotency_key: Annotated[str, Header(min_length=1, max_length=128)],
):
    query_fields(request)
    from starlette.concurrency import run_in_threadpool

    original = await request.json()
    status, response = await run_in_threadpool(
        service(request).create, body, idempotency_key, original
    )
    return JSONResponse(response, status_code=status)


@router.get("/{review_id}")
def get_review(review_id: str, request: Request):
    query_fields(request)
    return service(request).get(review_id)


@router.post("/{review_id}/resolution-batches")
def resolution_batch(
    review_id: str,
    body: ResolutionBatch,
    request: Request,
    idempotency_key: Annotated[str, Header(min_length=1, max_length=128)],
):
    query_fields(request)
    status, response = service(request).checkpoints.answer(review_id, body, idempotency_key)
    return JSONResponse(response, status_code=status)


@router.post("/{review_id}/revisions", status_code=202)
def revise_review(
    review_id: str,
    body: RevisionRequest,
    request: Request,
    idempotency_key: Annotated[str, Header(min_length=1, max_length=128)],
):
    query_fields(request)
    status, response = service(request).checkpoints.revise(review_id, body, idempotency_key)
    return JSONResponse(response, status_code=status)


@router.get("/{review_id}/report")
def get_report(
    review_id: str,
    request: Request,
    report_revision_id: Annotated[str | None, Query(min_length=1, max_length=64)] = None,
):
    query_fields(request, ("report_revision_id",))
    return service(request).report(review_id, report_revision_id)


@router.get("/{review_id}/events")
def events(
    review_id: str,
    request: Request,
    job_id: str | None = None,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
):
    query_fields(request, ("job_id", "cursor", "limit"))
    domain = service(request)
    after = 0
    if cursor:
        try:
            value = json.loads(base64.urlsafe_b64decode(cursor.encode("ascii")))
            if (
                set(value) != {"review", "job", "after"}
                or value["review"] != review_id
                or value["job"] != job_id
                or type(value["after"]) is not int
                or value["after"] < 0
            ):
                raise ValueError("Cursor scope mismatch")
            after = value["after"]
        except (ValueError, TypeError, KeyError, UnicodeError) as error:
            raise ReviewError("INVALID_CURSOR", "游标无效或过滤范围不匹配。", 422) from error
    with domain.store.read() as conn:
        domain.require_review(conn, review_id)
        if (
            job_id
            and domain.store.row(
                conn,
                "SELECT id FROM contract_review_jobs WHERE id=:id AND review_id=:review",
                id=job_id,
                review=review_id,
            )
            is None
        ):
            raise ReviewError("RESOURCE_NOT_FOUND", "作业不属于本审查。", 404)
        rows = (
            conn.execute(
                text(
                    "SELECT body,event_seq FROM contract_review_events "
                    "WHERE review_id=:review AND event_seq>:after "
                    "AND (:job IS NULL OR job_id=:job) "
                    "ORDER BY event_seq LIMIT :count"
                ),
                {"review": review_id, "after": after, "job": job_id, "count": limit + 1},
            )
            .mappings()
            .all()
        )
        next_cursor = None
        if len(rows) > limit:
            next_cursor = base64.urlsafe_b64encode(
                canonical(
                    {
                        "review": review_id,
                        "job": job_id,
                        "after": rows[limit - 1]["event_seq"],
                    }
                ).encode("utf-8")
            ).decode("ascii")
        return {
            "items": [json.loads(row["body"]) for row in rows[:limit]],
            "next_cursor": next_cursor,
        }


@router.get("/{review_id}/events/{event_id}")
def event_detail(review_id: str, event_id: str, request: Request):
    query_fields(request)
    domain = service(request)
    with domain.store.read() as conn:
        domain.require_review(conn, review_id)
        row = domain.store.row(
            conn,
            "SELECT body,payload FROM contract_review_events WHERE id=:id AND review_id=:review",
            id=event_id,
            review=review_id,
        )
        if row is None:
            raise ReviewError("RESOURCE_NOT_FOUND", "事件不属于本审查。", 404)
        return {**json.loads(row["body"]), "payload": json.loads(row["payload"])}


@router.post("/{review_id}/verification-evidence", status_code=201)
def import_verification(
    review_id: str,
    body: VerificationImport,
    request: Request,
    idempotency_key: Annotated[str, Header(min_length=1, max_length=128)],
):
    query_fields(request)
    status, response = service(request).verifications.import_evidence(
        review_id, body, idempotency_key
    )
    return JSONResponse(response, status_code=status)


@router.get("/{review_id}/verification-evidence")
def verification_list(
    review_id: str,
    request: Request,
    input_revision_id: Annotated[str | None, Query(min_length=1, max_length=64)] = None,
    report_revision_id: Annotated[str | None, Query(min_length=1, max_length=64)] = None,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
):
    query_fields(request, ("input_revision_id", "report_revision_id", "cursor", "limit"))
    return service(request).verifications.list(
        review_id, input_revision_id, report_revision_id, cursor, limit
    )


@router.get("/{review_id}/verification-evidence/{evidence_id}")
def verification_detail(review_id: str, evidence_id: str, request: Request):
    query_fields(request)
    return service(request).verifications.get(review_id, evidence_id)
