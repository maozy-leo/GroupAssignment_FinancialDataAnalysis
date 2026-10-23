"""Read fixed-income source observations from Assignment 1 DuckDB."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

from config import BOND_ASSETS, LATE_2024_END_DATE, LATE_2024_START_DATE


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

    def load_bond_returns(
        self,
        asset_id: str,
        start_date: str,
    ) -> pd.DataFrame:
        """Load one bond asset's daily log returns.

        Args:
            asset_id: Bond asset identifier in ``index_daily``.
            start_date: Inclusive analysis start in ``YYYY-MM-DD`` format.

        Returns:
            Trade dates and daily log returns.

        Raises:
            ValueError: If ``asset_id`` is not configured for Module 3.
        """
        if asset_id not in BOND_ASSETS:
            raise ValueError(f"Unknown bond 'asset_id': {asset_id!r}.")
        query = """
            WITH returns AS (
                SELECT
                    trade_date,
                    LN(close / LAG(close) OVER (ORDER BY trade_date))
                        AS bond_log_return
                FROM index_daily
                WHERE asset_id = ?
            )
            SELECT trade_date, bond_log_return
            FROM returns
            WHERE trade_date >= ? AND bond_log_return IS NOT NULL
            ORDER BY trade_date
        """
        with duckdb.connect(str(self.database), read_only=True) as connection:
            return connection.execute(query, [asset_id, start_date]).fetch_df()

    def load_yield_change_panel(self, start_date: str) -> pd.DataFrame:
        """Load aligned daily changes for 2-, 5-, 10-, and 30-year yields.

        Args:
            start_date: Inclusive analysis start in ``YYYY-MM-DD`` format.

        Returns:
            One row per date with four decimal yield-change columns.
        """
        query = """
            WITH changes AS (
                SELECT
                    trade_date,
                    tenor_years,
                    yield_decimal - LAG(yield_decimal) OVER (
                        PARTITION BY tenor_years ORDER BY trade_date
                    ) AS yield_change
                FROM gov_yield_daily
                WHERE tenor_years IN (2.0, 5.0, 10.0, 30.0)
            )
            SELECT
                trade_date,
                MAX(CASE WHEN tenor_years = 2.0 THEN yield_change END)
                    AS yield_change_2y,
                MAX(CASE WHEN tenor_years = 5.0 THEN yield_change END)
                    AS yield_change_5y,
                MAX(CASE WHEN tenor_years = 10.0 THEN yield_change END)
                    AS yield_change_10y,
                MAX(CASE WHEN tenor_years = 30.0 THEN yield_change END)
                    AS yield_change_30y
            FROM changes
            WHERE trade_date >= ?
            GROUP BY trade_date
            HAVING COUNT(yield_change) = 4
            ORDER BY trade_date
        """
        with duckdb.connect(str(self.database), read_only=True) as connection:
            return connection.execute(query, [start_date]).fetch_df()

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
