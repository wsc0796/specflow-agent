from app.auth import authenticate
from app.orders import create_order
from fastapi import FastAPI

app = FastAPI()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/orders")
def submit_order(user_id: str, item_id: str) -> dict[str, str]:
    authenticate(user_id)
    return create_order(user_id, item_id)
