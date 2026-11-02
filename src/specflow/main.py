"""HTTP entry point for SpecFlow Agent."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from specflow import __version__
from specflow.api_security import ApiSecurity
from specflow.contract_review.api import BodyLimitMiddleware, decisions_router
from specflow.contract_review.api import router as contract_reviews_router
from specflow.contract_review.common import ReviewError
from specflow.contract_review.impact_api import router as contract_impacts_router
from specflow.contract_review.instance_lock import InstanceLock
from specflow.contract_review.service import ReviewService
from specflow.contract_review.sources import GitSnapshotReader
from specflow.contract_review.store import ReviewStore
from specflow.contract_review.worker import ReviewWorker
from specflow.db import Database, default_url
from specflow.projects import router as projects_router
from specflow.runs import recover_interrupted_runs
from specflow.runs import router as runs_router


def create_app(
    database_url: str | None = None,
    artifact_root: Path | None = None,
    security: ApiSecurity | None = None,
    contract_review_profiles: dict | None = None,
    contract_review_adapter=None,
    contract_impact_profiles: dict | None = None,
) -> FastAPI:
    database = Database(database_url or default_url())
    run_artifact_root = artifact_root or Path("data/runs")
    security = security or ApiSecurity.from_env()

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        security.validate_configuration()
        application.state.database = database
        application.state.artifact_root = run_artifact_root
        application.state.security = security
        run_artifact_root.mkdir(parents=True, exist_ok=True)
        review_lock = None
        review_worker = None
        try:
            # Explicit configuration is required. The legacy application never
            # selects a real provider or a fake profile on behalf of a caller.
            if contract_review_profiles is not None or contract_impact_profiles is not None:
                db_path = database.engine.url.database
                if not db_path or db_path == ":memory:":
                    raise RuntimeError("Contract reviews require a file-backed SQLite database")
                review_lock = InstanceLock(db_path)
                review_lock.acquire()
            database.create_schema()
            recover_interrupted_runs(database)
            if contract_review_profiles is not None or contract_impact_profiles is not None:
                store = ReviewStore(database)
                store.migrate()

                def validate_review_path(path):
                    try:
                        return security.validate_repository_path(str(path))
                    except HTTPException as error:
                        raise ReviewError(
                            "REPOSITORY_PATH_FORBIDDEN", "仓库或 Git 元数据超出允许范围。", 403
                        ) from error

                application.state.contract_reviews = ReviewService(
                    store,
                    GitSnapshotReader(validate_review_path),
                    contract_review_profiles,
                    impact_profiles=contract_impact_profiles,
                )
                if contract_review_adapter is not None:
                    review_worker = ReviewWorker(
                        application.state.contract_reviews, contract_review_adapter
                    )
                    application.state.contract_reviews.worker = review_worker
                    review_worker.start()
            yield
        finally:
            try:
                if review_worker is not None:
                    review_worker.close()
            finally:
                if review_lock is not None:
                    review_lock.release()
                database.engine.dispose()

    application = FastAPI(title="SpecFlow Agent", version=__version__, lifespan=lifespan)
    application.add_middleware(BodyLimitMiddleware)

    @application.exception_handler(ReviewError)
    async def review_error_handler(request: Request, error: ReviewError):
        return JSONResponse(error.envelope(), status_code=error.status)

    @application.middleware("http")
    async def require_authenticated_route(request: Request, call_next):
        if request.url.path == "/health":
            return await call_next(request)
        try:
            security.require_request(request)
        except HTTPException as error:
            return JSONResponse(
                status_code=error.status_code,
                content={"detail": error.detail},
                headers=error.headers,
            )
        return await call_next(request)

    application.include_router(projects_router, dependencies=[Depends(security.require_api_key)])
    application.include_router(runs_router, dependencies=[Depends(security.require_api_key)])
    application.include_router(
        contract_reviews_router, dependencies=[Depends(security.require_api_key)]
    )
    application.include_router(decisions_router, dependencies=[Depends(security.require_api_key)])
    application.include_router(
        contract_impacts_router, dependencies=[Depends(security.require_api_key)]
    )

    @application.get("/health", tags=["system"])
    def health_check() -> dict[str, str]:
        """Return a minimal liveness response for deployment and smoke tests."""
        return {"status": "ok"}

    original_openapi = application.openapi

    def secured_openapi() -> dict:
        schema = original_openapi()
        components = schema.setdefault("components", {})
        security_schemes = components.setdefault("securitySchemes", {})
        security_schemes["ApiKeyAuth"] = {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
        }
        security_schemes["BearerAuth"] = {"type": "http", "scheme": "bearer"}
        schema["security"] = [{"ApiKeyAuth": []}, {"BearerAuth": []}]
        schema["paths"]["/health"]["get"]["security"] = []
        return schema

    application.openapi = secured_openapi

    return application


app = create_app()
