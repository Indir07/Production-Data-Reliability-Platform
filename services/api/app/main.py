import time
import uuid
import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

from app.config import get_settings
from app.routers import health, datasources, checks, runs, reports

# ── Structured logging setup ─────────────────────────────────────────────────
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ]
)
logger = structlog.get_logger()

# ── Prometheus metrics ────────────────────────────────────────────────────────
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code"]
)
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency",
    ["method", "endpoint"]
)


# ── App lifespan ──────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logger.info(
        "startup",
        app=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
    )
    yield
    logger.info("shutdown", app=settings.app_name)


# ── App factory ───────────────────────────────────────────────────────────────
def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "Enterprise-grade Data Reliability Platform — "
            "monitor pipelines, detect anomalies, and alert before users do."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # ── CORS ──────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.debug else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Request ID + logging middleware ───────────────────────────────────────
    @app.middleware("http")
    async def request_middleware(request: Request, call_next):
        request_id = str(uuid.uuid4())
        start = time.perf_counter()
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )
        response = await call_next(request)
        duration = time.perf_counter() - start
        REQUEST_COUNT.labels(
            method=request.method,
            endpoint=request.url.path,
            status_code=response.status_code,
        ).inc()
        REQUEST_LATENCY.labels(
            method=request.method,
            endpoint=request.url.path,
        ).observe(duration)
        logger.info(
            "request",
            status_code=response.status_code,
            duration_ms=round(duration * 1000, 2),
        )
        response.headers["X-Request-ID"] = request_id
        return response

    # ── Prometheus metrics endpoint ───────────────────────────────────────────
    @app.get("/metrics", include_in_schema=False)
    async def metrics():
        return Response(
            content=generate_latest(),
            media_type=CONTENT_TYPE_LATEST,
        )

    # ── Routers ───────────────────────────────────────────────────────────────
    API_PREFIX = "/api/v1"
    app.include_router(health.router, prefix=API_PREFIX, tags=["Health"])
    app.include_router(datasources.router, prefix=API_PREFIX, tags=["Data Sources"])
    app.include_router(checks.router, prefix=API_PREFIX, tags=["Checks"])
    app.include_router(runs.router, prefix=API_PREFIX, tags=["Runs"])
    app.include_router(reports.router, prefix=API_PREFIX, tags=["Reports"])

    return app


app = create_app()
