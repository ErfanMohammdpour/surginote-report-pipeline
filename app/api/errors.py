"""Central HTTP error mapping — all domain + unexpected errors."""

from __future__ import annotations

import logging
import os
import traceback

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

_DEBUG = os.getenv("SN_DEBUG", "false").lower() in ("1", "true", "yes")

from app.domain.errors import (
    AgentError,
    AgentInputError,
    AgentOutputParseError,
    AgentRateLimitError,
    AgentUpstreamError,
    AgentValidationError,
    DomainError,
    IdempotencyConflict,
    ParseError,
    StorageError,
    UploadError,
    ValidationError,
)
from app.infrastructure.llm.gemini_rest import GeminiError

logger = logging.getLogger(__name__)

_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Referrer-Policy": "strict-origin-when-cross-origin",
}


def _sec(resp: JSONResponse) -> JSONResponse:
    for k, v in _SECURITY_HEADERS.items():
        resp.headers[k] = v
    return resp


def register_exception_handlers(app: FastAPI) -> None:

    @app.exception_handler(ValidationError)
    async def validation_error(_: Request, exc: ValidationError):
        return _sec(JSONResponse(
            status_code=422,
            content={"code": "validation_error", "valid": False, "errors": exc.errors},
        ))

    @app.exception_handler(UploadError)
    async def upload_error(_: Request, exc: UploadError):
        status = 413 if exc.code == "file_too_large" else 400
        return _sec(JSONResponse(status_code=status, content={"code": exc.code, "message": str(exc)}))

    @app.exception_handler(StorageError)
    async def storage_error(_: Request, exc: StorageError):
        logger.error("storage error: %s", exc)
        body: dict = {"code": "storage_unavailable", "message": "Object storage temporarily unavailable"}
        if _DEBUG:
            body["detail"] = str(exc)
        return _sec(JSONResponse(status_code=503, content=body))

    @app.exception_handler(IdempotencyConflict)
    async def idem_conflict(_: Request, exc: IdempotencyConflict):
        return _sec(JSONResponse(
            status_code=409,
            content={"code": "idempotency_conflict", "message": str(exc)},
        ))

    @app.exception_handler(ParseError)
    async def parse_error(_: Request, exc: ParseError):
        return _sec(JSONResponse(
            status_code=422,
            content={"code": "parse_error", "message": str(exc)},
        ))

    @app.exception_handler(GeminiError)
    async def gemini_error(_: Request, exc: GeminiError):
        status = 429 if exc.status_code == 429 else 502
        logger.warning("gemini upstream %d", exc.status_code)
        return _sec(JSONResponse(
            status_code=status,
            content={
                "code": "gemini_rate_limited" if status == 429 else "gemini_upstream_error",
                "http_status": exc.status_code,
                "message": "Gemini request failed — check GEMINI_API_KEY and quota",
            },
        ))

    def _agent_body(req: Request, exc: AgentError) -> dict:
        req_id = getattr(getattr(req, "state", None), "request_id", "-")
        body: dict = {"code": exc.code, "message": str(exc), "request_id": req_id}
        if exc.agent:
            body["agent"] = exc.agent
        if isinstance(exc, AgentValidationError) and exc.errors:
            body["errors"] = exc.errors
        return body

    @app.exception_handler(AgentValidationError)
    async def agent_validation_error(req: Request, exc: AgentValidationError):
        return _sec(JSONResponse(status_code=422, content=_agent_body(req, exc)))

    @app.exception_handler(AgentInputError)
    async def agent_input_error(req: Request, exc: AgentInputError):
        return _sec(JSONResponse(status_code=422, content=_agent_body(req, exc)))

    @app.exception_handler(AgentOutputParseError)
    async def agent_output_parse_error(req: Request, exc: AgentOutputParseError):
        return _sec(JSONResponse(status_code=422, content=_agent_body(req, exc)))

    @app.exception_handler(AgentRateLimitError)
    async def agent_rate_limit_error(req: Request, exc: AgentRateLimitError):
        return _sec(JSONResponse(status_code=429, content=_agent_body(req, exc)))

    @app.exception_handler(AgentUpstreamError)
    async def agent_upstream_error(req: Request, exc: AgentUpstreamError):
        return _sec(JSONResponse(status_code=502, content=_agent_body(req, exc)))

    @app.exception_handler(AgentError)
    async def agent_error(req: Request, exc: AgentError):
        return _sec(JSONResponse(status_code=400, content=_agent_body(req, exc)))

    @app.exception_handler(DomainError)
    async def domain_error(_: Request, exc: DomainError):
        return _sec(JSONResponse(
            status_code=400,
            content={"code": "domain_error", "message": str(exc)},
        ))

    @app.exception_handler(RequestValidationError)
    async def pydantic_validation_error(_: Request, exc: RequestValidationError):
        errors = [
            {
                "path": ".".join(str(x) for x in e.get("loc", [])),
                "message": e.get("msg"),
                "code": "REQUEST_VALIDATION",
                "severity": "error",
            }
            for e in exc.errors()
        ]
        return _sec(JSONResponse(
            status_code=422,
            content={"code": "request_validation_error", "valid": False, "errors": errors},
        ))

    @app.exception_handler(ValueError)
    async def value_error(_: Request, exc: ValueError):
        msg = str(exc)
        # surface gemini_api_key_missing as structured 400
        if "gemini_api_key_missing" in msg:
            return _sec(JSONResponse(
                status_code=400,
                content={"code": "gemini_api_key_missing", "message": "Set GEMINI_API_KEY in .env"},
            ))
        if "openai_api_key_missing" in msg:
            return _sec(JSONResponse(
                status_code=400,
                content={"code": "openai_api_key_missing", "message": "Set OPENAI_API_KEY in .env"},
            ))
        logger.warning("value error in request: %s", msg)
        return _sec(JSONResponse(status_code=400, content={"code": "bad_request", "message": msg}))

    @app.exception_handler(Exception)
    async def unhandled_error(req: Request, exc: Exception):
        req_id = getattr(getattr(req, "state", None), "request_id", "-")
        logger.error(
            "unhandled exception req_id=%s %s %s: %s\n%s",
            req_id,
            req.method,
            req.url.path,
            exc,
            traceback.format_exc(),
        )
        body: dict = {"code": "internal_server_error", "message": "An unexpected error occurred", "request_id": req_id}
        if _DEBUG:
            body["detail"] = traceback.format_exc()
        return _sec(JSONResponse(status_code=500, content=body))
