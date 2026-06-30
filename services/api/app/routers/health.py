import time
import structlog
from fastapi import APIRouter
from pydantic import BaseModel

from app.config import get_settings

router = APIRouter()
logger = structlog.get_logger()
START_TIME = time.time()


class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str
    uptime_seconds: float


class ReadinessResponse(BaseModel):
    status: str
    checks: dict


@router.get("/health", response_model=HealthResponse, summary="Liveness check")
async def health():
    """
    Liveness probe. Returns 200 when the API process is running.
    Used by Kubernetes liveness probe.
    """
    settings = get_settings()
    return HealthResponse(
        status="ok",
        version=settings.app_version,
        environment=settings.environment,
        uptime_seconds=round(time.time() - START_TIME, 2),
    )


@router.get("/ready", response_model=ReadinessResponse, summary="Readiness check")
async def readiness():
    """
    Readiness probe. Verifies downstream dependencies (DB, Redis) are reachable.
    Used by Kubernetes readiness probe.
    """
    checks = {}
    overall = "ok"

    # DB check (placeholder — will connect to real DB in Sprint 2)
    try:
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {e}"
        overall = "degraded"

    # Redis check (placeholder — will connect to real Redis in Sprint 3)
    try:
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"error: {e}"
        overall = "degraded"

    logger.info("readiness_check", overall=overall, checks=checks)
    return ReadinessResponse(status=overall, checks=checks)
