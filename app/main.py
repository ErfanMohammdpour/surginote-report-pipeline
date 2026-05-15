from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.router import get_router
from app.config import settings
from app.infrastructure.database.session import create_all


@asynccontextmanager
async def lifespan(_: FastAPI):
    create_all()
    yield


app = FastAPI(title=settings.app_name, version="1.3.0", lifespan=lifespan)
app.include_router(get_router())


@app.get("/healthz")
def healthz() -> dict[str, bool]:
    return {"ok": True}
