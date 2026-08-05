"""HTTP entry point for SpecFlow Agent."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI

from specflow import __version__
from specflow.api_security import ApiSecurity
from specflow.db import Database, default_url
from specflow.projects import router as projects_router
from specflow.runs import recover_interrupted_runs
from specflow.runs import router as runs_router


def create_app(
    database_url: str | None = None,
    artifact_root: Path | None = None,
    security: ApiSecurity | None = None,
) -> FastAPI:
    database = Database(database_url or default_url())
    run_artifact_root = artifact_root or Path("data/runs")
    security = security or ApiSecurity.from_env()

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        application.state.database = database
        application.state.artifact_root = run_artifact_root
        application.state.security = security
        run_artifact_root.mkdir(parents=True, exist_ok=True)
        database.create_schema()
        recover_interrupted_runs(database)
        try:
            yield
        finally:
            database.engine.dispose()

    application = FastAPI(title="SpecFlow Agent", version=__version__, lifespan=lifespan)
    application.include_router(projects_router, dependencies=[Depends(security.require_api_key)])
    application.include_router(runs_router, dependencies=[Depends(security.require_api_key)])

    @application.get("/health", tags=["system"])
    def health_check() -> dict[str, str]:
        """Return a minimal liveness response for deployment and smoke tests."""
        return {"status": "ok"}

    return application


app = create_app()
