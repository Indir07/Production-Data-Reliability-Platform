"""Initial schema

Revision ID: 001
Revises:
Create Date: 2025-07-01

Creates:
  - data_sources table
  - check_definitions table
  - check_runs table (converted to TimescaleDB hypertable)

Indexes:
  - check_runs(check_definition_id, started_at DESC) — most common query pattern
  - check_runs(status, started_at DESC)              — alert queries
  - Partial index on failures only                   — fast failure queries
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Enums ─────────────────────────────────────────────────────────────────
    datasource_type = postgresql.ENUM(
        "postgresql", "bigquery", "snowflake", "delta_lake",
        "redshift", "mysql", "sqlite",
        name="datasource_type", create_type=False,
    )
    datasource_type.create(op.get_bind(), checkfirst=True)

    check_type_enum = postgresql.ENUM(
        "freshness", "schema_drift", "null_explosion",
        "volume_anomaly", "duplicate",
        name="check_type", create_type=False,
    )
    check_type_enum.create(op.get_bind(), checkfirst=True)

    check_severity_enum = postgresql.ENUM(
        "CRITICAL", "HIGH", "MEDIUM", "LOW",
        name="check_severity", create_type=False,
    )
    check_severity_enum.create(op.get_bind(), checkfirst=True)

    run_status_enum = postgresql.ENUM(
        "RUNNING", "PASS", "FAIL", "ERROR", "SKIPPED",
        name="run_status", create_type=False,
    )
    run_status_enum.create(op.get_bind(), checkfirst=True)

    triggered_by_enum = postgresql.ENUM(
        "SCHEDULED", "MANUAL", "WEBHOOK", "CI",
        name="triggered_by", create_type=False,
    )
    triggered_by_enum.create(op.get_bind(), checkfirst=True)

    # ── data_sources ─────────────────────────────────────────────────────────
    op.create_table(
        "data_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("source_type", datasource_type, nullable=False),
        sa.Column("connection_config", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("org_id", sa.String(100), nullable=False, server_default="default"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_data_sources_name", "data_sources", ["name"], unique=True)
    op.create_index("ix_data_sources_org_id", "data_sources", ["org_id"])

    # ── check_definitions ─────────────────────────────────────────────────────
    op.create_table(
        "check_definitions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("check_type", check_type_enum, nullable=False),
        sa.Column("severity", check_severity_enum, nullable=False, server_default="HIGH"),
        sa.Column("datasource_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("data_sources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_table", sa.String(500), nullable=False),
        sa.Column("target_column", sa.String(255), nullable=True),
        sa.Column("params", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("schedule_cron", sa.String(100), nullable=True),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("org_id", sa.String(100), nullable=False, server_default="default"),
        sa.Column("created_by", sa.String(255), nullable=False, server_default="system"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_check_definitions_name", "check_definitions", ["name"])
    op.create_index("ix_check_definitions_check_type", "check_definitions", ["check_type"])
    op.create_index("ix_check_definitions_datasource_id", "check_definitions", ["datasource_id"])
    op.create_index("ix_check_definitions_org_id", "check_definitions", ["org_id"])

    # ── check_runs ────────────────────────────────────────────────────────────
    op.create_table(
        "check_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("check_definition_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("check_definitions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", run_status_enum, nullable=False, server_default="RUNNING"),
        sa.Column("triggered_by", triggered_by_enum, nullable=False, server_default="MANUAL"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Float, nullable=True),
        sa.Column("result_payload", postgresql.JSONB, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
    )

    # Composite index: most common query (get recent runs for a check)
    op.create_index(
        "ix_check_runs_definition_time",
        "check_runs",
        ["check_definition_id", sa.text("started_at DESC")],
    )
    op.create_index(
        "ix_check_runs_status_time",
        "check_runs",
        ["status", sa.text("started_at DESC")],
    )
    # Partial index: only failures — used by the alert router
    op.execute("""
        CREATE INDEX ix_check_runs_failures
        ON check_runs (check_definition_id, started_at DESC)
        WHERE status = 'FAIL'
    """)

    # ── Convert check_runs to TimescaleDB hypertable ──────────────────────────
    # Guard: only run if TimescaleDB extension is available
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_extension WHERE extname = 'timescaledb'
            ) THEN
                PERFORM create_hypertable(
                    'check_runs',
                    'started_at',
                    if_not_exists => TRUE,
                    migrate_data  => TRUE
                );
                RAISE NOTICE 'check_runs converted to TimescaleDB hypertable';
            ELSE
                RAISE NOTICE 'TimescaleDB not available — check_runs remains a regular table';
            END IF;
        END
        $$;
    """)

    # ── updated_at trigger ─────────────────────────────────────────────────────
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    for table in ("data_sources", "check_definitions"):
        op.execute(f"""
            CREATE TRIGGER trigger_{table}_updated_at
            BEFORE UPDATE ON {table}
            FOR EACH ROW EXECUTE FUNCTION update_updated_at();
        """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS check_runs CASCADE")
    op.execute("DROP TABLE IF EXISTS check_definitions CASCADE")
    op.execute("DROP TABLE IF EXISTS data_sources CASCADE")
    op.execute("DROP FUNCTION IF EXISTS update_updated_at CASCADE")
    for enum_name in ("run_status", "triggered_by", "check_severity", "check_type", "datasource_type"):
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")
