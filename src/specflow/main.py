"""HTTP entry point for SpecFlow Agent."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from specflow.db import Database, default_url
from specflow.projects import router


def create_app(database_url: str | None = None) -> FastAPI:
    database = Database(database_url or default_url())

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        application.state.database = database
        database.create_schema()
        yield

    application = FastAPI(title="SpecFlow Agent", version="0.2.0", lifespan=lifespan)
    application.include_router(router)
    return application


app = create_app()


@app.get("/health", tags=["system"])
def health_check() -> dict[str, str]:
    """Return a minimal liveness response for deployment and smoke tests."""
    return {"status": "ok"}
