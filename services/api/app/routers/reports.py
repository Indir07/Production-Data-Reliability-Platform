from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class Stub(BaseModel):
    message: str


@router.get("/reports/sla", response_model=Stub)
async def sla_report():
    """SLA compliance report. [Sprint 5]"""
    return Stub(message="SLA report — implemented in Sprint 5")


@router.get("/tables/{table_name}/health", response_model=Stub)
async def table_health(table_name: str):
    """Per-table health scorecard. [Sprint 5]"""
    return Stub(message=f"Health for {table_name} — implemented in Sprint 5")
