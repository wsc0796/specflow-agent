"""HTTP entry point for SpecFlow Agent."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from specflow.db import Database, default_url
from specflow.projects import router as projects_router
from specflow.runs import router as runs_router


def create_app(database_url: str | None = None, artifact_root: Path | None = None) -> FastAPI:
    database = Database(database_url or default_url())
    run_artifact_root = artifact_root or Path("data/runs")

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        application.state.database = database
        application.state.artifact_root = run_artifact_root
        run_artifact_root.mkdir(parents=True, exist_ok=True)
        database.create_schema()
        yield

    application = FastAPI(title="SpecFlow Agent", version="1.0.1", lifespan=lifespan)
    application.include_router(projects_router)
    application.include_router(runs_router)
    return application


app = create_app()


@app.get("/health", tags=["system"])
def health_check() -> dict[str, str]:
    """Return a minimal liveness response for deployment and smoke tests."""
    return {"status": "ok"}
