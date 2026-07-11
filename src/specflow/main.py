"""HTTP entry point for SpecFlow Agent."""

from fastapi import FastAPI

app = FastAPI(title="SpecFlow Agent", version="0.1.0")


@app.get("/health", tags=["system"])
def health_check() -> dict[str, str]:
    """Return a minimal liveness response for deployment and smoke tests."""
    return {"status": "ok"}
