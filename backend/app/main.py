"""FastAPI application entrypoint."""

import time
import uuid
import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.v1.api import api_router
from app.api.v1.routes import health as health_routes
from app.core.config import get_settings
from app.core.database import close_db, get_engine, get_session_factory
from app.core.logging import get_logger, setup_logging
from app.services.discovery.vertex_ai import VertexAIDiscoveryService
from app.services.evaluation.sweeper import sweep_orphaned_runs
from app.services.gcp.auth import validate_adc_credentials
from app.services.gcp.eval_deps import check_evals_dependencies

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    setup_logging()
    logger.info(
        "Starting %s [%s]",
        settings.app_name,
        settings.app_env,
        extra={"component": "startup"},
    )

    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("PostgreSQL connection OK", extra={"component": "startup"})
    except Exception as exc:
        logger.error(
            "PostgreSQL connection failed: %s",
            exc,
            extra={"component": "startup"},
        )

    auth = validate_adc_credentials()
    if auth.available:
        logger.info(
            "GCP ADC available for project=%s",
            auth.project_id,
            extra={"component": "startup"},
        )
        # Discovery scans ten regions and can take tens of seconds. Awaiting it
        # inside lifespan means the app refuses connections until GCP answers,
        # so a slow or unreachable region looks like a dead server. Run it in
        # the background and start serving immediately.
        async def _startup_discovery() -> None:
            try:
                factory = get_session_factory()
                async with factory() as session:
                    summary = await VertexAIDiscoveryService(session).sync_to_database()
                    await session.commit()
                logger.info(
                    "Vertex AI discovery sync on startup: discovered=%s created=%s updated=%s unchanged=%s",
                    summary.discovered,
                    summary.created,
                    summary.updated,
                    summary.unchanged,
                    extra={"component": "startup"},
                )
                if summary.errors:
                    logger.warning(
                        "Vertex AI discovery sync errors: %s",
                        summary.errors,
                        extra={"component": "startup"},
                    )
            except Exception as exc:
                logger.warning(
                    "Vertex AI discovery sync failed at startup: %s",
                    exc,
                    extra={"component": "startup"},
                )

        asyncio.create_task(_startup_discovery())

    else:
        logger.warning(
            "GCP ADC not available at startup: %s",
            auth.error,
            extra={"component": "startup"},
        )

    # BackgroundTasks die with the process, so anything left "running" from a
    # previous boot is orphaned and will never complete. Mark it failed rather
    # than leaving a job that appears to be in progress forever.
    try:
        factory = get_session_factory()
        async with factory() as session:
            swept = await sweep_orphaned_runs(session)
            await session.commit()
        if swept:
            logger.warning(
                "Marked %s orphaned evaluation run(s) as failed after restart",
                swept,
                extra={"component": "startup"},
            )
    except Exception as exc:
        logger.warning(
            "Could not sweep orphaned runs: %s", exc, extra={"component": "startup"}
        )

    eval_ok, eval_err = check_evals_dependencies()
    if eval_ok:
        logger.info("Vertex AI evaluation dependencies OK", extra={"component": "startup"})
    else:
        logger.warning(
            "Vertex AI evaluation dependencies MISSING: %s",
            eval_err,
            extra={"component": "startup"},
        )

    yield

    await close_db()
    logger.info("Application shutdown complete", extra={"component": "shutdown"})


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        description="AI AgentOps Platform — Vertex AI Reasoning Engine discovery MVP",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Wildcard origins with credentials is rejected by browsers anyway, and the
    # old production branch was an empty list, which blocked every cross-origin
    # call. Origins come from config, and credentials are only offered when the
    # origins are explicit.
    origins = settings.cors_origin_list
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials="*" not in origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_logging_middleware(request: Request, call_next):
        request_id = str(uuid.uuid4())[:8]
        start = time.perf_counter()
        logger.info(
            "Request started %s %s",
            request.method,
            request.url.path,
            extra={"request_id": request_id, "component": "http"},
        )
        try:
            response = await call_next(request)
        except Exception:
            logger.exception(
                "Request failed %s %s",
                request.method,
                request.url.path,
                extra={"request_id": request_id, "component": "http"},
            )
            raise
        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "Request completed %s %s -> %s (%.1fms)",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            extra={"request_id": request_id, "component": "http"},
        )
        response.headers["X-Request-ID"] = request_id
        return response

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.exception(
            "Unhandled error on %s %s",
            request.method,
            request.url.path,
            extra={"component": "http"},
        )
        # The exception text can carry connection strings and resource names, so
        # it is logged rather than returned. The request id ties the response to
        # the log line.
        body: dict[str, str] = {"detail": "Internal server error"}
        if settings.is_development:
            body["message"] = str(exc)
        return JSONResponse(status_code=500, content=body)

    app.include_router(health_routes.router)
    app.include_router(api_router, prefix="/api/v1")

    return app


app = create_app()
