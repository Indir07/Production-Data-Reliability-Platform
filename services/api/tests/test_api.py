"""
Sprint 2 Integration Tests — DataSource and CheckDefinition CRUD API
=====================================================================
Uses an in-memory SQLite database via aiosqlite so no Docker/PostgreSQL
is required in CI. The FastAPI app's get_db dependency is overridden
to use the test database.
"""
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine

from app.database import override_engine
from app.main import app
from app.models.base import Base

# ── Test database setup ───────────────────────────────────────────────────────

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="function")
async def test_db():
    """Create a fresh in-memory SQLite DB for each test function."""
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    override_engine(engine)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
    # Reset engine so next test gets a fresh one
    override_engine(None)


@pytest_asyncio.fixture(scope="function")
async def client(test_db):
    """HTTP test client wired to the test database."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


# ── Helper ────────────────────────────────────────────────────────────────────

async def create_datasource(client, name="test-postgres") -> dict:
    resp = await client.post("/api/v1/datasources", json={
        "name": name,
        "source_type": "postgresql",
        "connection_config": {"host": "localhost", "port": 5432},
    })
    assert resp.status_code == 201
    return resp.json()


async def create_check(client, datasource_id: str, name="orders-freshness") -> dict:
    resp = await client.post("/api/v1/checks", json={
        "name": name,
        "check_type": "freshness",
        "severity": "HIGH",
        "datasource_id": datasource_id,
        "target_table": "public.orders",
        "params": {"timestamp_column": "updated_at", "max_age_hours": 6},
    })
    assert resp.status_code == 201
    return resp.json()


# ── DataSource CRUD tests ─────────────────────────────────────────────────────

class TestDataSourceCRUD:

    @pytest.mark.asyncio
    async def test_create_datasource_returns_201(self, client):
        resp = await client.post("/api/v1/datasources", json={
            "name": "prod-pg",
            "source_type": "postgresql",
            "connection_config": {"host": "db.example.com", "port": 5432},
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "prod-pg"
        assert data["source_type"] == "postgresql"
        assert data["enabled"] is True
        assert "id" in data
        # connection_config must NOT appear in response (security)
        assert "connection_config" not in data

    @pytest.mark.asyncio
    async def test_create_datasource_duplicate_name_returns_409(self, client):
        await create_datasource(client, "unique-ds")
        resp = await client.post("/api/v1/datasources", json={
            "name": "unique-ds",
            "source_type": "postgresql",
            "connection_config": {},
        })
        assert resp.status_code == 409
        assert "already exists" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_list_datasources_returns_items(self, client):
        await create_datasource(client, "ds-one")
        await create_datasource(client, "ds-two")
        resp = await client.get("/api/v1/datasources")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

    @pytest.mark.asyncio
    async def test_list_datasources_empty(self, client):
        resp = await client.get("/api/v1/datasources")
        assert resp.status_code == 200
        assert resp.json() == {"items": [], "total": 0}

    @pytest.mark.asyncio
    async def test_get_datasource_by_id(self, client):
        created = await create_datasource(client, "get-me")
        resp = await client.get(f"/api/v1/datasources/{created['id']}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "get-me"

    @pytest.mark.asyncio
    async def test_get_datasource_not_found_returns_404(self, client):
        resp = await client.get(f"/api/v1/datasources/{uuid.uuid4()}")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_update_datasource(self, client):
        created = await create_datasource(client, "update-me")
        resp = await client.patch(
            f"/api/v1/datasources/{created['id']}",
            json={"enabled": False},
        )
        assert resp.status_code == 200
        assert resp.json()["enabled"] is False

    @pytest.mark.asyncio
    async def test_delete_datasource(self, client):
        created = await create_datasource(client, "delete-me")
        resp = await client.delete(f"/api/v1/datasources/{created['id']}")
        assert resp.status_code == 204
        # Verify it's gone
        resp = await client.get(f"/api/v1/datasources/{created['id']}")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_nonexistent_returns_404(self, client):
        resp = await client.delete(f"/api/v1/datasources/{uuid.uuid4()}")
        assert resp.status_code == 404


# ── CheckDefinition CRUD tests ────────────────────────────────────────────────

class TestCheckDefinitionCRUD:

    @pytest.mark.asyncio
    async def test_create_check_returns_201(self, client):
        ds = await create_datasource(client)
        resp = await client.post("/api/v1/checks", json={
            "name": "orders-freshness",
            "check_type": "freshness",
            "severity": "CRITICAL",
            "datasource_id": ds["id"],
            "target_table": "public.orders",
            "params": {"timestamp_column": "updated_at", "max_age_hours": 6},
            "schedule_cron": "0 * * * *",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "orders-freshness"
        assert data["check_type"] == "freshness"
        assert data["severity"] == "CRITICAL"
        assert data["schedule_cron"] == "0 * * * *"
        assert data["params"]["max_age_hours"] == 6

    @pytest.mark.asyncio
    async def test_list_checks_empty(self, client):
        resp = await client.get("/api/v1/checks")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    @pytest.mark.asyncio
    async def test_list_checks_filter_by_type(self, client):
        ds = await create_datasource(client)
        await create_check(client, ds["id"], "freshness-check")
        # Create a different type
        await client.post("/api/v1/checks", json={
            "name": "null-check",
            "check_type": "null_explosion",
            "datasource_id": ds["id"],
            "target_table": "public.orders",
            "params": {"column": "customer_id"},
        })
        resp = await client.get("/api/v1/checks?check_type=freshness")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1
        assert resp.json()["items"][0]["name"] == "freshness-check"

    @pytest.mark.asyncio
    async def test_get_check_by_id(self, client):
        ds = await create_datasource(client)
        check = await create_check(client, ds["id"])
        resp = await client.get(f"/api/v1/checks/{check['id']}")
        assert resp.status_code == 200
        assert resp.json()["id"] == check["id"]

    @pytest.mark.asyncio
    async def test_update_check_severity(self, client):
        ds = await create_datasource(client)
        check = await create_check(client, ds["id"])
        resp = await client.patch(
            f"/api/v1/checks/{check['id']}",
            json={"severity": "LOW", "enabled": False},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["severity"] == "LOW"
        assert data["enabled"] is False

    @pytest.mark.asyncio
    async def test_delete_check(self, client):
        ds = await create_datasource(client)
        check = await create_check(client, ds["id"])
        resp = await client.delete(f"/api/v1/checks/{check['id']}")
        assert resp.status_code == 204
        resp = await client.get(f"/api/v1/checks/{check['id']}")
        assert resp.status_code == 404


# ── Check Run trigger tests ───────────────────────────────────────────────────

class TestCheckRunTrigger:

    @pytest.mark.asyncio
    async def test_trigger_run_returns_202(self, client):
        ds = await create_datasource(client)
        check = await create_check(client, ds["id"])
        resp = await client.post(f"/api/v1/checks/{check['id']}/run")
        assert resp.status_code == 202
        data = resp.json()
        assert data["check_definition_id"] == check["id"]
        assert data["status"] in ("PASS", "FAIL", "ERROR", "SKIPPED")
        assert data["triggered_by"] == "MANUAL"
        assert data["duration_ms"] is not None

    @pytest.mark.asyncio
    async def test_trigger_run_has_result_payload(self, client):
        ds = await create_datasource(client)
        check = await create_check(client, ds["id"])
        resp = await client.post(f"/api/v1/checks/{check['id']}/run")
        assert resp.status_code == 202
        data = resp.json()
        # MockConnector returns None → ERROR status with result_payload
        assert data["result_payload"] is not None or data["error_message"] is not None

    @pytest.mark.asyncio
    async def test_trigger_nonexistent_check_returns_404(self, client):
        resp = await client.post(f"/api/v1/checks/{uuid.uuid4()}/run")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_run_appears_in_history(self, client):
        ds = await create_datasource(client)
        check = await create_check(client, ds["id"])
        await client.post(f"/api/v1/checks/{check['id']}/run")
        await client.post(f"/api/v1/checks/{check['id']}/run")

        resp = await client.get(f"/api/v1/checks/{check['id']}/runs")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2

    @pytest.mark.asyncio
    async def test_get_run_by_id(self, client):
        ds = await create_datasource(client)
        check = await create_check(client, ds["id"])
        run_resp = await client.post(f"/api/v1/checks/{check['id']}/run")
        run_id = run_resp.json()["id"]

        resp = await client.get(f"/api/v1/runs/{run_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == run_id

    @pytest.mark.asyncio
    async def test_get_nonexistent_run_returns_404(self, client):
        resp = await client.get(f"/api/v1/runs/{uuid.uuid4()}")
        assert resp.status_code == 404
