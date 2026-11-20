"""REDUTAX FastAPI application.

Run locally:  uvicorn app.main:app --reload   (from the backend/ folder)
"""
from __future__ import annotations

import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api import benchmarks, counting, health, samples
from app.api.errors import install_error_handlers
from app.core.config import APP_NAME, APP_VERSION, get_settings

logger = logging.getLogger("redutax")


def create_app() -> FastAPI:
    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    app = FastAPI(title=APP_NAME, version=APP_VERSION)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_id_and_timing(request: Request, call_next):
        # Observability (BRD §16): request ID + timing, no request bodies logged.
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000
        response.headers["x-request-id"] = request_id
        logger.info(
            "request_id=%s method=%s path=%s status=%s ms=%.1f",
            request_id, request.method, request.url.path, response.status_code, elapsed_ms,
        )
        return response

    install_error_handlers(app)
    app.include_router(health.router)
    app.include_router(counting.router)
    app.include_router(samples.router)
    app.include_router(benchmarks.router)
    logger.info("starting %s %s settings=%s", APP_NAME, APP_VERSION, settings.safe_dict())
    return app


app = create_app()
