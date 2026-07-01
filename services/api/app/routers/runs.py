import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.check_run import CheckRun
from app.schemas.check import CheckRunResponse

router = APIRouter()


@router.get(
    "/runs/{run_id}",
    response_model=CheckRunResponse,
    summary="Get a single check run result",
)
async def get_run(
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> CheckRunResponse:
    """Returns the full result of a specific check run including metric values and details."""
    result = await db.execute(select(CheckRun).where(CheckRun.id == run_id))
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="CheckRun not found")
    return CheckRunResponse.model_validate(run)
