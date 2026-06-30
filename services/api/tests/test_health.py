import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


@pytest.mark.anyio
async def test_health_returns_ok(client):
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data
    assert "uptime_seconds" in data


@pytest.mark.anyio
async def test_readiness_returns_ok(client):
    response = await client.get("/api/v1/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "checks" in data


@pytest.mark.anyio
async def test_metrics_endpoint_exists(client):
    response = await client.get("/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]


@pytest.mark.anyio
async def test_openapi_schema_exists(client):
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert schema["info"]["title"] == "Production Data Reliability Platform"


@pytest.mark.anyio
async def test_docs_endpoint_exists(client):
    response = await client.get("/docs")
    assert response.status_code == 200


@pytest.mark.anyio
async def test_request_id_header_present(client):
    response = await client.get("/api/v1/health")
    assert "x-request-id" in response.headers
