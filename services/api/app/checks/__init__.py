"""
Data Quality Check Engine
=========================
Each checker implements BaseCheck and returns a CheckResult.

Usage:
    from app.checks.freshness import FreshnessCheck
    from app.checks.schema_drift import SchemaDriftCheck
    from app.checks.nulls import NullCheck
    from app.checks.volume import VolumeCheck
    from app.checks.duplicates import DuplicateCheck
"""
from app.checks.base import BaseCheck, CheckResult, CheckStatus

__all__ = ["BaseCheck", "CheckResult", "CheckStatus"]
