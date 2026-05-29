from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.errors import register_exception_handlers
from app.api.router import get_router
from app.api.pipeline_router import get_pipeline_router
from app.config import settings
from app.infrastructure.database.session import create_all
from app.infrastructure.logging_setup import configure_logging

configure_logging()
logger = logging.getLogger(__name__)


# ── Security headers middleware ───────────────────────────────────────────────
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response


# ── Request-ID middleware ─────────────────────────────────────────────────────
class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = req_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = req_id
        return response


# ── Logging middleware ────────────────────────────────────────────────────────
class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        import time
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        req_id = getattr(request.state, "request_id", "-")
        logger.info(
            "%s %s %d %dms req_id=%s",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
            req_id,
        )
        return response


# ── App factory ───────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    create_all()
    app.state.arq_pool = None
    if not settings.sync_jobs:
        try:
            from arq import create_pool
            from app.infrastructure.queue.worker import WorkerSettings

            app.state.arq_pool = await create_pool(WorkerSettings.redis_settings)
        except Exception:  # noqa: BLE001
            logger.warning("ARQ pool unavailable — async jobs will fail until Redis is reachable")
            app.state.arq_pool = None
    yield
    pool = getattr(app.state, "arq_pool", None)
    if pool is not None:
        await pool.close()


app = FastAPI(
    title="SurgiNote Report Service",
    version="3.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# CORS — configure SN_CORS_ORIGINS for production
_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "X-Idempotent-Replay"],
)

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(LoggingMiddleware)

# Rate limiting
try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    from slowapi.util import get_remote_address

    limiter = Limiter(key_func=get_remote_address, default_limits=[settings.rate_limit])
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]
except ImportError:
    logger.warning("slowapi not installed — rate limiting disabled")

register_exception_handlers(app)
app.include_router(get_router())
app.include_router(get_pipeline_router())


@app.get("/healthz", tags=["ops"])
def healthz() -> dict[str, bool]:
    return {"ok": True}


@app.get("/readyz", tags=["ops"])
def readyz() -> JSONResponse:
    from sqlalchemy import text
    from app.infrastructure.database.session import engine

    import os as _os
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return JSONResponse({"ok": True, "database": "up"})
    except Exception as e:  # noqa: BLE001
        logger.error("readyz db check failed: %s", e)
        body: dict = {"ok": False, "database": "unreachable"}
        if _os.getenv("SN_DEBUG", "false").lower() in ("1", "true", "yes"):
            body["detail"] = str(e)
        return JSONResponse(status_code=503, content=body)
