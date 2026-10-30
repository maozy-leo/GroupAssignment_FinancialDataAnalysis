"""Read fixed-income source observations from Assignment 1 DuckDB."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

from config import (
    BOND_ASSETS,
    LATE_2024_END_DATE,
    LATE_2024_START_DATE,
    FixedIncomeDataAudit,
)


class FixedIncomeRepository:
    """Provide validated, read-only access to fixed-income source data."""

    def __init__(self, database: Path) -> None:
        """Initialize the repository.

        Args:
            database: Existing DuckDB database path.

        Raises:
            FileNotFoundError: If the database does not exist.
        """
        if not database.is_file():
            raise FileNotFoundError(
                f"Expected DuckDB database at '{database}', but it was absent."
            )
        self.database = database

    def load_curve_snapshot(self) -> pd.DataFrame:
        """Read and validate the latest eight-point government yield curve.

        Returns:
            Curve observations sorted by maturity.

        Raises:
            ValueError: If the latest curve is incomplete or contains nulls.
        """
        query = """
            SELECT curve_date, tenor_years, yield_decimal
            FROM yield_curve_snapshot
            WHERE curve_date = (SELECT MAX(curve_date) FROM yield_curve_snapshot)
            ORDER BY tenor_years
        """
        with duckdb.connect(str(self.database), read_only=True) as connection:
            curve = connection.execute(query).fetch_df()
        if len(curve) != 8:
            raise ValueError(
                "Expected the latest curve to contain 8 tenor points, but got "
                f"{len(curve)}."
            )
        if curve[["tenor_years", "yield_decimal"]].isna().any().any():
            raise ValueError(
                "Latest yield curve contains missing tenor or yield values."
            )
        return curve

    def load_data_audit(self) -> FixedIncomeDataAudit:
        """Load source-table and series coverage for the HTML report.

        Returns:
            Row counts, date ranges, metadata, and yield-tenor coverage.
        """
        table_queries = {
            "index_daily": "trade_date",
            "gov_yield_daily": "trade_date",
            "yield_curve_snapshot": "curve_date",
            "trading_calendar": "trade_date",
        }
        table_rows: list[dict[str, object]] = []
        asset_ids = tuple(BOND_ASSETS)
        placeholders = ", ".join("?" for _ in asset_ids)

        with duckdb.connect(str(self.database), read_only=True) as connection:
            asset_count = connection.execute(
                "SELECT COUNT(*) FROM assets"
            ).fetchone()[0]
            table_rows.append(
                {
                    "table_name": "assets",
                    "n_rows": asset_count,
                    "start_date": None,
                    "end_date": None,
                }
            )
            for table_name, date_column in table_queries.items():
                summary = connection.execute(
                    f"""
                    SELECT
                        COUNT(*) AS n_rows,
                        MIN({date_column}) AS start_date,
                        MAX({date_column}) AS end_date
                    FROM {table_name}
                    """
                ).fetchone()
                table_rows.append(
                    {
                        "table_name": table_name,
                        "n_rows": summary[0],
                        "start_date": summary[1],
                        "end_date": summary[2],
                    }
                )

            bond_assets = connection.execute(
                f"""
                SELECT
                    assets.asset_id,
                    assets.asset_name,
                    assets.symbol,
                    assets.source,
                    assets.return_type,
                    assets.tenor_bucket,
                    COUNT(daily.trade_date) AS n_rows,
                    MIN(daily.trade_date) AS start_date,
                    MAX(daily.trade_date) AS end_date
                FROM assets
                INNER JOIN index_daily AS daily USING (asset_id)
                WHERE assets.asset_id IN ({placeholders})
                GROUP BY ALL
                """,
                list(asset_ids),
            ).fetch_df()
            bond_assets["asset_order"] = bond_assets["asset_id"].map(
                {asset_id: index for index, asset_id in enumerate(asset_ids)}
            )
            bond_assets = bond_assets.sort_values("asset_order").drop(
                columns="asset_order"
            )
            yield_tenors = connection.execute(
                """
                SELECT
                    tenor_years,
                    COUNT(*) AS n_rows,
                    MIN(trade_date) AS start_date,
                    MAX(trade_date) AS end_date
                FROM gov_yield_daily
                GROUP BY tenor_years
                ORDER BY tenor_years
                """
            ).fetch_df()

        return FixedIncomeDataAudit(
            source_tables=pd.DataFrame(table_rows),
            bond_assets=bond_assets,
            yield_tenors=yield_tenors,
        )

    def load_regression_sample(
        self,
        asset_id: str,
        start_date: str,
    ) -> pd.DataFrame:
        """Load aligned bond returns and 10-year yield changes.

        Args:
            asset_id: Bond asset identifier in ``index_daily``.
            start_date: Inclusive analysis start in ``YYYY-MM-DD`` format.

        Returns:
            Common-date sample with log return and decimal yield change.

        Raises:
            ValueError: If ``asset_id`` is not configured for Module 3.
        """
        if asset_id not in BOND_ASSETS:
            raise ValueError(f"Unknown bond 'asset_id': {asset_id!r}.")
        query = """
            WITH index_returns AS (
                SELECT
                    asset_id,
                    trade_date,
                    LN(close / LAG(close) OVER (
                        PARTITION BY asset_id ORDER BY trade_date
                    )) AS bond_log_return
                FROM index_daily
                WHERE asset_id = ?
            ),
            yield_changes AS (
                SELECT
                    trade_date,
                    yield_decimal - LAG(yield_decimal) OVER (
                        ORDER BY trade_date
                    ) AS yield_change_10y
                FROM gov_yield_daily
                WHERE tenor_years = 10.0
            )
            SELECT
                returns.trade_date,
                returns.bond_log_return,
                yields.yield_change_10y
            FROM index_returns AS returns
            INNER JOIN yield_changes AS yields USING (trade_date)
            WHERE returns.trade_date >= ?
                AND returns.bond_log_return IS NOT NULL
                AND yields.yield_change_10y IS NOT NULL
            ORDER BY returns.trade_date
        """
        with duckdb.connect(str(self.database), read_only=True) as connection:
            return connection.execute(query, [asset_id, start_date]).fetch_df()

    def load_late_2024_period(self) -> pd.DataFrame:
        """Load 10-year yields and cumulative bond returns for late 2024.

        Returns:
            Common-date observations from 2024-11-01 through 2024-12-31.

        Raises:
            ValueError: If the common-date panel is empty or incomplete.
        """
        query = """
            WITH bond_prices AS (
                SELECT trade_date, asset_id, close
                FROM index_daily
                WHERE asset_id IN (
                    'SSE_TREASURY',
                    'SSE_ENTERPRISE_BOND',
                    'POLICY_BOND_7_10_PROXY'
                )
                    AND trade_date BETWEEN ? AND ?
            ),
            bond_panel AS (
                SELECT
                    trade_date,
                    MAX(CASE WHEN asset_id = 'SSE_TREASURY' THEN close END)
                        AS SSE_TREASURY,
                    MAX(CASE WHEN asset_id = 'SSE_ENTERPRISE_BOND' THEN close END)
                        AS SSE_ENTERPRISE_BOND,
                    MAX(CASE WHEN asset_id = 'POLICY_BOND_7_10_PROXY' THEN close END)
                        AS POLICY_BOND_7_10_PROXY
                FROM bond_prices
                GROUP BY trade_date
            ),
            yields AS (
                SELECT trade_date, yield_decimal AS yield_10y_decimal
                FROM gov_yield_daily
                WHERE tenor_years = 10.0
                    AND trade_date BETWEEN ? AND ?
            )
            SELECT bond_panel.*, yields.yield_10y_decimal
            FROM bond_panel
            INNER JOIN yields USING (trade_date)
            ORDER BY trade_date
        """
        parameters = [
            LATE_2024_START_DATE,
            LATE_2024_END_DATE,
            LATE_2024_START_DATE,
            LATE_2024_END_DATE,
        ]
        with duckdb.connect(str(self.database), read_only=True) as connection:
            period = connection.execute(query, parameters).fetch_df()
        if period.empty:
            raise ValueError(
                "No common bond and 10-year-yield data found for late 2024."
            )

        for asset_id in BOND_ASSETS:
            if asset_id not in period or period[asset_id].isna().any():
                raise ValueError(
                    f"Late-2024 common-date panel is incomplete for '{asset_id}'."
                )
            period[f"{asset_id}_cumulative_return"] = (
                period[asset_id] / period[asset_id].iloc[0] - 1.0
            )
        return period
