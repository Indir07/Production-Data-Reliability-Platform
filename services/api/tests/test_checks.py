"""
Unit tests for the Data Quality Check Engine.

All tests use MockConnector — no real database required.
Tests cover: PASS, FAIL, ERROR, SKIPPED, and edge cases for each checker.
"""
import pytest

from app.checks.base import CheckConfig, CheckSeverity, CheckStatus
from app.checks.duplicates import DuplicateCheck
from app.checks.freshness import FreshnessCheck
from app.checks.nulls import NullCheck
from app.checks.schema_drift import SchemaDriftCheck, _diff_schemas, _schema_hash
from app.checks.volume import VolumeCheck, _compute_z_score
from app.connectors.base import MockConnector


def make_config(table: str, params: dict) -> CheckConfig:
    return CheckConfig(
        check_id="test-check-001",
        datasource_id="test-ds-001",
        target_table=table,
        severity=CheckSeverity.HIGH,
        params=params,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Freshness Check Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestFreshnessCheck:
    checker = FreshnessCheck()

    @pytest.mark.asyncio
    async def test_fresh_table_passes(self):
        conn = MockConnector().set_result(
            "max",
            {"last_updated_at": "2025-06-30 10:00:00", "age_hours": 1.5, "row_count": 5000}
        )
        config = make_config("analytics.orders", {"timestamp_column": "updated_at", "max_age_hours": 6.0})
        result = await self.checker.run(conn, config)

        assert result.status == CheckStatus.PASS
        assert result.metric_value == 1.5
        assert result.threshold == 6.0
        assert "FRESH" in result.message

    @pytest.mark.asyncio
    async def test_stale_table_fails(self):
        conn = MockConnector().set_result(
            "max",
            {"last_updated_at": "2025-06-29 08:00:00", "age_hours": 26.0, "row_count": 5000}
        )
        config = make_config("analytics.orders", {"timestamp_column": "updated_at", "max_age_hours": 6.0})
        result = await self.checker.run(conn, config)

        assert result.status == CheckStatus.FAIL
        assert result.metric_value == 26.0
        assert "STALE" in result.message

    @pytest.mark.asyncio
    async def test_empty_table_fails(self):
        conn = MockConnector().set_result(
            "max",
            {"last_updated_at": None, "age_hours": None, "row_count": 0}
        )
        config = make_config("analytics.orders", {"timestamp_column": "updated_at", "max_age_hours": 6.0})
        result = await self.checker.run(conn, config)

        assert result.status == CheckStatus.FAIL
        assert "empty" in result.message.lower()

    @pytest.mark.asyncio
    async def test_null_timestamp_column_fails(self):
        conn = MockConnector().set_result(
            "max",
            {"last_updated_at": None, "age_hours": None, "row_count": 100}
        )
        config = make_config("analytics.orders", {"timestamp_column": "updated_at", "max_age_hours": 6.0})
        result = await self.checker.run(conn, config)

        assert result.status == CheckStatus.FAIL
        assert "no non-null values" in result.message.lower()

    @pytest.mark.asyncio
    async def test_missing_timestamp_column_param_errors(self):
        conn = MockConnector()
        config = make_config("analytics.orders", {})
        result = await self.checker.run(conn, config)

        assert result.status == CheckStatus.ERROR
        assert "timestamp_column" in result.message

    @pytest.mark.asyncio
    async def test_exactly_at_threshold_passes(self):
        conn = MockConnector().set_result(
            "max",
            {"last_updated_at": "2025-06-30 10:00:00", "age_hours": 6.0, "row_count": 100}
        )
        config = make_config("analytics.orders", {"timestamp_column": "updated_at", "max_age_hours": 6.0})
        result = await self.checker.run(conn, config)

        assert result.status == CheckStatus.PASS

    @pytest.mark.asyncio
    async def test_connector_error_returns_error_status(self):
        conn = MockConnector()  # returns None for everything
        config = make_config("analytics.orders", {"timestamp_column": "updated_at"})
        result = await self.checker.run(conn, config)

        assert result.status in (CheckStatus.ERROR, CheckStatus.FAIL)

    @pytest.mark.asyncio
    async def test_result_has_duration(self):
        conn = MockConnector().set_result(
            "max",
            {"last_updated_at": "2025-06-30", "age_hours": 1.0, "row_count": 10}
        )
        config = make_config("orders", {"timestamp_column": "created_at", "max_age_hours": 24.0})
        result = await self.checker.run(conn, config)

        assert result.duration_ms >= 0


# ─────────────────────────────────────────────────────────────────────────────
# Schema Drift Tests
# ─────────────────────────────────────────────────────────────────────────────

BASELINE = [
    {"column_name": "id",         "data_type": "integer",           "is_nullable": False},
    {"column_name": "email",      "data_type": "character varying",  "is_nullable": False},
    {"column_name": "created_at", "data_type": "timestamp",          "is_nullable": True},
]

class TestSchemaDriftCheck:
    checker = SchemaDriftCheck()

    def test_diff_no_changes(self):
        changes = _diff_schemas(BASELINE, BASELINE, [])
        assert changes == []

    def test_diff_column_added(self):
        current = BASELINE + [{"column_name": "phone", "data_type": "character varying", "is_nullable": True}]
        changes = _diff_schemas(BASELINE, current, [])
        assert len(changes) == 1
        assert changes[0]["change_type"] == "COLUMN_ADDED"
        assert changes[0]["column"] == "phone"

    def test_diff_column_removed(self):
        current = [c for c in BASELINE if c["column_name"] != "email"]
        changes = _diff_schemas(BASELINE, current, [])
        assert len(changes) == 1
        assert changes[0]["change_type"] == "COLUMN_REMOVED"
        assert changes[0]["column"] == "email"

    def test_diff_type_changed(self):
        current = [
            {"column_name": "id",         "data_type": "bigint",            "is_nullable": False},
            {"column_name": "email",      "data_type": "character varying",  "is_nullable": False},
            {"column_name": "created_at", "data_type": "timestamp",          "is_nullable": True},
        ]
        changes = _diff_schemas(BASELINE, current, [])
        assert len(changes) == 1
        assert changes[0]["change_type"] == "TYPE_CHANGED"
        assert changes[0]["column"] == "id"
        assert changes[0]["baseline_type"] == "integer"
        assert changes[0]["current_type"] == "bigint"

    def test_diff_ignore_columns(self):
        current = [c for c in BASELINE if c["column_name"] != "created_at"]
        # created_at is ignored — should not appear in changes
        changes = _diff_schemas(BASELINE, current, ignore_columns=["created_at"])
        assert changes == []

    def test_schema_hash_deterministic(self):
        h1 = _schema_hash(BASELINE)
        h2 = _schema_hash(list(reversed(BASELINE)))  # order shouldn't matter
        assert h1 == h2

    def test_schema_hash_changes_on_drift(self):
        modified = [
            {"column_name": "id",    "data_type": "bigint",           "is_nullable": False},
            {"column_name": "email", "data_type": "character varying", "is_nullable": False},
        ]
        assert _schema_hash(BASELINE) != _schema_hash(modified)

    @pytest.mark.asyncio
    async def test_no_drift_passes(self):
        conn = MockConnector().set_result("information_schema", BASELINE)
        config = make_config("public.users", {"baseline_schema": BASELINE})
        result = await self.checker.run(conn, config)

        assert result.status == CheckStatus.PASS
        assert result.metric_value == 0.0

    @pytest.mark.asyncio
    async def test_drift_detected_fails(self):
        current = BASELINE + [{"column_name": "deleted_at", "data_type": "timestamp", "is_nullable": True}]
        conn = MockConnector().set_result("information_schema", current)
        config = make_config("public.users", {"baseline_schema": BASELINE})
        result = await self.checker.run(conn, config)

        assert result.status == CheckStatus.FAIL
        assert result.metric_value == 1.0
        assert "COLUMN_ADDED" in result.details["changes"][0]["change_type"]

    @pytest.mark.asyncio
    async def test_missing_baseline_errors(self):
        conn = MockConnector()
        config = make_config("public.users", {})
        result = await self.checker.run(conn, config)

        assert result.status == CheckStatus.ERROR
        assert "baseline_schema" in result.message

    @pytest.mark.asyncio
    async def test_table_not_found_errors(self):
        conn = MockConnector().set_result("information_schema", [])  # empty = table not found
        config = make_config("public.nonexistent", {"baseline_schema": BASELINE})
        result = await self.checker.run(conn, config)

        assert result.status == CheckStatus.ERROR
        assert "not found" in result.message.lower()


# ─────────────────────────────────────────────────────────────────────────────
# Null Check Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestNullCheck:
    checker = NullCheck()

    @pytest.mark.asyncio
    async def test_acceptable_null_rate_passes(self):
        conn = MockConnector().set_result(
            "count",
            {"total_rows": 10000, "non_null_rows": 9800, "null_rows": 200}
        )
        config = make_config("orders", {"column": "customer_id", "max_null_rate": 0.05})
        result = await self.checker.run(conn, config)

        assert result.status == CheckStatus.PASS
        assert result.metric_value == pytest.approx(0.02, abs=1e-4)

    @pytest.mark.asyncio
    async def test_null_explosion_fails(self):
        conn = MockConnector().set_result(
            "count",
            {"total_rows": 10000, "non_null_rows": 6000, "null_rows": 4000}
        )
        config = make_config("orders", {"column": "customer_id", "max_null_rate": 0.05})
        result = await self.checker.run(conn, config)

        assert result.status == CheckStatus.FAIL
        assert result.metric_value == pytest.approx(0.4, abs=1e-4)
        assert "null explosion" in result.message.lower()

    @pytest.mark.asyncio
    async def test_empty_table_is_skipped(self):
        conn = MockConnector().set_result(
            "count",
            {"total_rows": 0, "non_null_rows": 0, "null_rows": 0}
        )
        config = make_config("orders", {"column": "customer_id", "max_null_rate": 0.05})
        result = await self.checker.run(conn, config)

        assert result.status == CheckStatus.SKIPPED

    @pytest.mark.asyncio
    async def test_zero_nulls_passes(self):
        conn = MockConnector().set_result(
            "count",
            {"total_rows": 500, "non_null_rows": 500, "null_rows": 0}
        )
        config = make_config("orders", {"column": "order_id", "max_null_rate": 0.0})
        result = await self.checker.run(conn, config)

        assert result.status == CheckStatus.PASS
        assert result.metric_value == 0.0

    @pytest.mark.asyncio
    async def test_missing_column_param_errors(self):
        conn = MockConnector()
        config = make_config("orders", {})
        result = await self.checker.run(conn, config)

        assert result.status == CheckStatus.ERROR

    @pytest.mark.asyncio
    async def test_100_percent_nulls_fails(self):
        conn = MockConnector().set_result(
            "count",
            {"total_rows": 1000, "non_null_rows": 0, "null_rows": 1000}
        )
        config = make_config("events", {"column": "user_id", "max_null_rate": 0.01})
        result = await self.checker.run(conn, config)

        assert result.status == CheckStatus.FAIL
        assert result.metric_value == 1.0


# ─────────────────────────────────────────────────────────────────────────────
# Volume Anomaly Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestVolumeCheck:
    checker = VolumeCheck()

    def test_z_score_positive(self):
        z = _compute_z_score(130, mean=100, stddev=10)
        assert z == pytest.approx(3.0, abs=1e-4)

    def test_z_score_negative(self):
        z = _compute_z_score(70, mean=100, stddev=10)
        assert z == pytest.approx(-3.0, abs=1e-4)

    def test_z_score_zero_stddev_returns_none(self):
        z = _compute_z_score(100, mean=100, stddev=0)
        assert z is None

    @pytest.mark.asyncio
    async def test_normal_volume_passes(self):
        conn = MockConnector().set_result("count", {"row_count": 10200})
        config = make_config("orders", {
            "baseline_mean": 10000.0,
            "baseline_stddev": 500.0,
            "z_threshold": 3.0,
        })
        result = await self.checker.run(conn, config)

        assert result.status == CheckStatus.PASS
        assert abs(result.metric_value) < 3.0

    @pytest.mark.asyncio
    async def test_volume_spike_fails(self):
        conn = MockConnector().set_result("count", {"row_count": 50000})
        config = make_config("orders", {
            "baseline_mean": 10000.0,
            "baseline_stddev": 500.0,
            "z_threshold": 3.0,
        })
        result = await self.checker.run(conn, config)

        assert result.status == CheckStatus.FAIL
        assert result.metric_value > 3.0
        assert "spike" in result.message.lower()

    @pytest.mark.asyncio
    async def test_volume_drop_fails(self):
        conn = MockConnector().set_result("count", {"row_count": 100})
        config = make_config("orders", {
            "baseline_mean": 10000.0,
            "baseline_stddev": 500.0,
            "z_threshold": 3.0,
        })
        result = await self.checker.run(conn, config)

        assert result.status == CheckStatus.FAIL
        assert result.metric_value < -3.0
        assert "drop" in result.message.lower()

    @pytest.mark.asyncio
    async def test_below_min_row_count_fails(self):
        conn = MockConnector().set_result("count", {"row_count": 0})
        config = make_config("orders", {
            "baseline_mean": 10000.0,
            "baseline_stddev": 500.0,
            "min_row_count": 1,
        })
        result = await self.checker.run(conn, config)

        assert result.status == CheckStatus.FAIL
        assert "critically low" in result.message.lower()

    @pytest.mark.asyncio
    async def test_missing_baseline_params_errors(self):
        conn = MockConnector()
        config = make_config("orders", {})
        result = await self.checker.run(conn, config)

        assert result.status == CheckStatus.ERROR

    @pytest.mark.asyncio
    async def test_details_contain_bounds(self):
        conn = MockConnector().set_result("count", {"row_count": 10000})
        config = make_config("orders", {
            "baseline_mean": 10000.0,
            "baseline_stddev": 1000.0,
            "z_threshold": 3.0,
        })
        result = await self.checker.run(conn, config)

        assert "p_lower" in result.details
        assert "p_upper" in result.details
        assert result.details["p_upper"] == 13000.0


# ─────────────────────────────────────────────────────────────────────────────
# Duplicate Check Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestDuplicateCheck:
    checker = DuplicateCheck()

    @pytest.mark.asyncio
    async def test_no_duplicates_passes(self):
        conn = MockConnector().set_result(
            "count",
            {"total_rows": 5000, "unique_rows": 5000}
        )
        config = make_config("orders", {"primary_key_columns": ["order_id"]})
        result = await self.checker.run(conn, config)

        assert result.status == CheckStatus.PASS
        assert result.metric_value == 0.0

    @pytest.mark.asyncio
    async def test_duplicates_exceed_threshold_fails(self):
        conn = MockConnector().set_result(
            "count",
            {"total_rows": 1000, "unique_rows": 900}
        )
        config = make_config("orders", {
            "primary_key_columns": ["order_id"],
            "max_duplicate_rate": 0.0,
        })
        result = await self.checker.run(conn, config)

        assert result.status == CheckStatus.FAIL
        assert result.metric_value == pytest.approx(0.1, abs=1e-4)
        assert result.details["duplicate_count"] == 100

    @pytest.mark.asyncio
    async def test_duplicates_within_tolerance_passes(self):
        conn = MockConnector().set_result(
            "count",
            {"total_rows": 1000, "unique_rows": 990}
        )
        config = make_config("orders", {
            "primary_key_columns": ["order_id"],
            "max_duplicate_rate": 0.02,  # 2% tolerance
        })
        result = await self.checker.run(conn, config)

        assert result.status == CheckStatus.PASS

    @pytest.mark.asyncio
    async def test_composite_pk_check(self):
        conn = MockConnector().set_result(
            "count",
            {"total_rows": 2000, "unique_rows": 2000}
        )
        config = make_config("events", {
            "primary_key_columns": ["user_id", "event_date", "event_type"],
        })
        result = await self.checker.run(conn, config)

        assert result.status == CheckStatus.PASS
        assert result.details["primary_key_columns"] == ["user_id", "event_date", "event_type"]

    @pytest.mark.asyncio
    async def test_empty_table_is_skipped(self):
        conn = MockConnector().set_result(
            "count",
            {"total_rows": 0, "unique_rows": 0}
        )
        config = make_config("orders", {"primary_key_columns": ["order_id"]})
        result = await self.checker.run(conn, config)

        assert result.status == CheckStatus.SKIPPED

    @pytest.mark.asyncio
    async def test_missing_pk_columns_errors(self):
        conn = MockConnector()
        config = make_config("orders", {})
        result = await self.checker.run(conn, config)

        assert result.status == CheckStatus.ERROR

    @pytest.mark.asyncio
    async def test_100_percent_duplicates_fails(self):
        conn = MockConnector().set_result(
            "count",
            {"total_rows": 5000, "unique_rows": 1}
        )
        config = make_config("orders", {"primary_key_columns": ["order_id"]})
        result = await self.checker.run(conn, config)

        assert result.status == CheckStatus.FAIL
        assert result.metric_value > 0.99
