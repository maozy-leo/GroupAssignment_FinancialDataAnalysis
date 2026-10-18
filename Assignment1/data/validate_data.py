"""Validate Assignment 1 data and write machine-readable results."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

import duckdb
import pandas as pd

from data_config import (
    ANALYSIS_START_DATE,
    DATABASE_PATH,
    PROJECT_ROOT,
    VALIDATION_RESULTS_PATH,
)


ValidationStatus = Literal["PASS", "WARN", "FAIL"]


@dataclass(frozen=True)
class ValidationCheck:
    """Describe the result of one validation rule."""

    name: str
    status: ValidationStatus
    detail: str


class AssignmentDataValidator:
    """Run structural, coverage and market-data sanity checks."""

    REQUIRED_TABLES = {
        "assets",
        "index_daily",
        "gov_yield_daily",
        "yield_curve_snapshot",
        "trading_calendar",
    }
    CORE_FULL_PERIOD_ASSETS = {
        "CSI300",
        "CSI500",
        "SSE_COMPOSITE",
        "SSE_TREASURY",
        "SSE_ENTERPRISE_BOND",
    }

    def __init__(self, database_path: Path) -> None:
        """Initialize the validator.

        Args:
            database_path: Existing DuckDB database to validate.

        Raises:
            FileNotFoundError: If the database does not exist.
        """
        if not database_path.exists():
            raise FileNotFoundError(f"Database does not exist: {database_path}")
        self.database_path = database_path

    @staticmethod
    def _table_names(connection: duckdb.DuckDBPyConnection) -> set[str]:
        """Read user table names from DuckDB.

        Args:
            connection: Open DuckDB connection.

        Returns:
            Set of table names in the main schema.
        """
        rows = connection.execute("SHOW TABLES").fetchall()
        return {str(row[0]) for row in rows}

    @staticmethod
    def _asset_summary(connection: duckdb.DuckDBPyConnection) -> pd.DataFrame:
        """Calculate row counts and date coverage for every asset.

        Args:
            connection: Open DuckDB connection.

        Returns:
            Summary with one row per asset.
        """
        return connection.execute(
            """
            SELECT
                asset_id,
                COUNT(*) AS row_count,
                MIN(trade_date) AS start_date,
                MAX(trade_date) AS end_date
            FROM index_daily
            GROUP BY asset_id
            ORDER BY asset_id
            """
        ).fetchdf()

    @staticmethod
    def _yearly_counts(connection: duckdb.DuckDBPyConnection) -> pd.DataFrame:
        """Calculate per-asset observation counts by calendar year.

        Args:
            connection: Open DuckDB connection.

        Returns:
            Long-form asset-year counts.
        """
        return connection.execute(
            """
            SELECT
                asset_id,
                YEAR(trade_date) AS calendar_year,
                COUNT(*) AS trading_days
            FROM index_daily
            GROUP BY asset_id, calendar_year
            ORDER BY asset_id, calendar_year
            """
        ).fetchdf()

    @staticmethod
    def _return_anomalies(connection: duckdb.DuckDBPyConnection) -> pd.DataFrame:
        """Find equity observations with absolute daily returns above 5%.

        Args:
            connection: Open DuckDB connection.

        Returns:
            Equity return anomalies with shape ``[K, 4]``.
        """
        return connection.execute(
            """
            WITH returns AS (
                SELECT
                    daily.asset_id,
                    daily.trade_date,
                    daily.close
                        / LAG(daily.close) OVER (
                            PARTITION BY daily.asset_id
                            ORDER BY daily.trade_date
                        )
                        - 1.0 AS simple_return
                FROM index_daily AS daily
                INNER JOIN assets USING (asset_id)
                WHERE assets.asset_class = 'equity'
            )
            SELECT asset_id, trade_date, simple_return
            FROM returns
            WHERE ABS(simple_return) > 0.05
            ORDER BY trade_date, asset_id
            """
        ).fetchdf()

    def run(self) -> dict[str, object]:
        """Execute validation checks and return the complete result payload.

        Returns:
            JSON-serializable validation payload.
        """
        checks: list[ValidationCheck] = []
        with duckdb.connect(str(self.database_path), read_only=True) as connection:
            table_names = self._table_names(connection)
            missing_tables = sorted(self.REQUIRED_TABLES - table_names)
            checks.append(
                ValidationCheck(
                    name="required_tables",
                    status="FAIL" if missing_tables else "PASS",
                    detail=(
                        f"Missing tables: {missing_tables}"
                        if missing_tables
                        else "All required tables exist."
                    ),
                )
            )
            if missing_tables:
                return self._write_results(checks, [], [], [])

            duplicate_count = connection.execute(
                """
                SELECT COUNT(*)
                FROM (
                    SELECT asset_id, trade_date
                    FROM index_daily
                    GROUP BY asset_id, trade_date
                    HAVING COUNT(*) > 1
                )
                """
            ).fetchone()[0]
            checks.append(
                ValidationCheck(
                    name="index_primary_key",
                    status="FAIL" if duplicate_count else "PASS",
                    detail=f"Duplicate asset-date keys: {duplicate_count}.",
                )
            )

            invalid_index_count = connection.execute(
                """
                SELECT COUNT(*)
                FROM index_daily
                WHERE asset_id IS NULL
                   OR trade_date IS NULL
                   OR close IS NULL
                   OR close <= 0
                """
            ).fetchone()[0]
            checks.append(
                ValidationCheck(
                    name="valid_index_values",
                    status="FAIL" if invalid_index_count else "PASS",
                    detail=f"Invalid index rows: {invalid_index_count}.",
                )
            )

            invalid_yield_count = connection.execute(
                """
                SELECT
                    (SELECT COUNT(*)
                     FROM gov_yield_daily
                     WHERE trade_date IS NULL
                        OR tenor_years IS NULL
                        OR tenor_years <= 0
                        OR yield_decimal IS NULL
                        OR yield_decimal NOT BETWEEN -0.05 AND 0.20)
                    +
                    (SELECT COUNT(*)
                     FROM yield_curve_snapshot
                     WHERE curve_date IS NULL
                        OR tenor_years IS NULL
                        OR tenor_years <= 0
                        OR yield_decimal IS NULL
                        OR yield_decimal NOT BETWEEN -0.05 AND 0.20)
                """
            ).fetchone()[0]
            checks.append(
                ValidationCheck(
                    name="valid_yield_values",
                    status="FAIL" if invalid_yield_count else "PASS",
                    detail=f"Invalid yield rows: {invalid_yield_count}.",
                )
            )

            asset_summary = self._asset_summary(connection)
            available_assets = set(asset_summary["asset_id"])
            missing_assets = sorted(
                set(self.CORE_FULL_PERIOD_ASSETS) - available_assets
            )
            checks.append(
                ValidationCheck(
                    name="required_assets",
                    status="FAIL" if missing_assets else "PASS",
                    detail=(
                        f"Missing core assets: {missing_assets}"
                        if missing_assets
                        else "All core assets contain observations."
                    ),
                )
            )

            late_core_assets = []
            analysis_start = pd.Timestamp(ANALYSIS_START_DATE)
            for row in asset_summary.itertuples(index=False):
                if row.asset_id not in self.CORE_FULL_PERIOD_ASSETS:
                    continue
                if pd.Timestamp(row.start_date) > analysis_start:
                    late_core_assets.append(
                        f"{row.asset_id} starts {row.start_date}"
                    )
            checks.append(
                ValidationCheck(
                    name="core_period_coverage",
                    status="FAIL" if late_core_assets else "PASS",
                    detail=(
                        "; ".join(late_core_assets)
                        if late_core_assets
                        else "Core assets cover the analysis start date."
                    ),
                )
            )

            supplemental_starts = {
                row.asset_id: row.start_date
                for row in asset_summary.itertuples(index=False)
                if row.asset_id in {"STAR50", "POLICY_BOND_7_10_PROXY"}
            }
            checks.append(
                ValidationCheck(
                    name="supplemental_period_coverage",
                    status="WARN",
                    detail=(
                        "STAR50 starts "
                        f"{supplemental_starts.get('STAR50')}; policy-bond "
                        "proxy starts "
                        f"{supplemental_starts.get('POLICY_BOND_7_10_PROXY')}."
                    ),
                )
            )

            ten_year_count = connection.execute(
                """
                SELECT COUNT(*)
                FROM gov_yield_daily
                WHERE tenor_years = 10.0
                """
            ).fetchone()[0]
            checks.append(
                ValidationCheck(
                    name="ten_year_yield",
                    status="FAIL" if ten_year_count == 0 else "PASS",
                    detail=f"10-year yield observations: {ten_year_count}.",
                )
            )

            curve_points = connection.execute(
                "SELECT COUNT(*) FROM yield_curve_snapshot"
            ).fetchone()[0]
            checks.append(
                ValidationCheck(
                    name="yield_curve_points",
                    status="FAIL" if curve_points < 5 else "PASS",
                    detail=f"Latest yield-curve points: {curve_points}.",
                )
            )

            calendar_difference = connection.execute(
                """
                SELECT COUNT(*)
                FROM (
                    SELECT trade_date
                    FROM index_daily
                    WHERE asset_id = 'CSI300'
                    EXCEPT
                    SELECT trade_date
                    FROM trading_calendar
                )
                """
            ).fetchone()[0]
            checks.append(
                ValidationCheck(
                    name="trading_calendar",
                    status="FAIL" if calendar_difference else "PASS",
                    detail=(
                        "CSI300 dates absent from the calendar: "
                        f"{calendar_difference}."
                    ),
                )
            )

            common_days = connection.execute(
                """
                SELECT COUNT(*)
                FROM index_daily AS stock
                INNER JOIN index_daily AS bond
                    ON stock.trade_date = bond.trade_date
                WHERE stock.asset_id = 'CSI300'
                  AND bond.asset_id = 'SSE_TREASURY'
                  AND stock.trade_date >= DATE '2019-01-01'
                """
            ).fetchone()[0]
            checks.append(
                ValidationCheck(
                    name="stock_bond_common_days",
                    status="FAIL" if common_days < 200 else "PASS",
                    detail=f"CSI300/SSE_TREASURY common days: {common_days}.",
                )
            )

            yearly_counts = self._yearly_counts(connection)
            anomalies = self._return_anomalies(connection)
            complete_year_mask = yearly_counts["calendar_year"].between(
                2019,
                2025,
                inclusive="both",
            )
            core_asset_mask = yearly_counts["asset_id"].isin(
                self.CORE_FULL_PERIOD_ASSETS
            )
            unreasonable_count_mask = ~yearly_counts["trading_days"].between(
                230,
                250,
                inclusive="both",
            )
            unreasonable_years = yearly_counts.loc[
                complete_year_mask & core_asset_mask & unreasonable_count_mask
            ]
            checks.append(
                ValidationCheck(
                    name="annual_trading_days",
                    status="FAIL" if not unreasonable_years.empty else "PASS",
                    detail=(
                        "Core-asset full-year counts are within [230, 250]."
                        if unreasonable_years.empty
                        else unreasonable_years.to_dict(orient="records").__str__()
                    ),
                )
            )

            event_dates = {
                pd.Timestamp(value).date()
                for value in anomalies["trade_date"]
                if pd.Timestamp("2024-09-20")
                <= pd.Timestamp(value)
                <= pd.Timestamp("2024-10-10")
            }
            expected_event_dates = {
                pd.Timestamp("2024-09-30").date(),
                pd.Timestamp("2024-10-08").date(),
            }
            missing_event_dates = sorted(expected_event_dates - event_dates)
            checks.append(
                ValidationCheck(
                    name="expected_event_anomalies",
                    status="FAIL" if missing_event_dates else "PASS",
                    detail=(
                        f"Missing expected dates: {missing_event_dates}."
                        if missing_event_dates
                        else "2024-09-30 and 2024-10-08 are both identified."
                    ),
                )
            )

        return self._write_results(
            checks,
            asset_summary.to_dict(orient="records"),
            yearly_counts.to_dict(orient="records"),
            anomalies.to_dict(orient="records"),
        )

    @staticmethod
    def _json_default(value: object) -> str | int | float:
        """Convert pandas and date values for JSON serialization.

        Args:
            value: Non-standard value passed by ``json.dumps``.

        Returns:
            JSON-compatible scalar.

        Raises:
            TypeError: If the value has no supported conversion.
        """
        if isinstance(value, (pd.Timestamp, datetime)):
            return value.isoformat()
        if hasattr(value, "isoformat"):
            return value.isoformat()
        if hasattr(value, "item"):
            return value.item()
        raise TypeError(f"Object of type {type(value).__name__} is not serializable.")

    def _write_results(
        self,
        checks: list[ValidationCheck],
        asset_summary: list[dict[str, object]],
        yearly_counts: list[dict[str, object]],
        anomalies: list[dict[str, object]],
    ) -> dict[str, object]:
        """Write validation results to JSON.

        Args:
            checks: Validation rule results.
            asset_summary: Per-asset row counts and date coverage.
            yearly_counts: Per-asset annual observation counts.
            anomalies: Equity daily returns above the configured threshold.

        Returns:
            JSON-serializable validation payload.
        """
        payload: dict[str, object] = {
            "generated_at": datetime.now().astimezone().isoformat(),
            "database": str(self.database_path.relative_to(PROJECT_ROOT)),
            "checks": [asdict(check) for check in checks],
            "asset_summary": asset_summary,
            "yearly_counts": yearly_counts,
            "equity_return_anomalies": anomalies,
        }
        VALIDATION_RESULTS_PATH.write_text(
            json.dumps(
                payload,
                ensure_ascii=False,
                indent=2,
                default=self._json_default,
            ),
            encoding="utf-8",
        )
        return payload


def main() -> None:
    """Run validation and return a nonzero status on failed checks."""
    validator = AssignmentDataValidator(DATABASE_PATH)
    payload = validator.run()
    checks = payload["checks"]
    for check in checks:
        print(f"[{check['status']}] {check['name']}: {check['detail']}")
    print(f"Validation results written to {VALIDATION_RESULTS_PATH}")

    if any(check["status"] == "FAIL" for check in checks):
        raise SystemExit(1)


if __name__ == "__main__":
    main()

