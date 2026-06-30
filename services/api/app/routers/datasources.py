from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class Stub(BaseModel):
    message: str


@router.get("/datasources", response_model=Stub)
async def list_datasources():
    """List all registered data sources. [Sprint 2]"""
    return Stub(message="DataSources endpoint — implemented in Sprint 2")


@router.post("/datasources", response_model=Stub, status_code=201)
async def create_datasource():
    """Register a new data source. [Sprint 2]"""
    return Stub(message="Create DataSource — implemented in Sprint 2")
