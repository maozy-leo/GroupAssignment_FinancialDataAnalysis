"""Download Assignment 1 market data and ingest it into DuckDB."""

from __future__ import annotations

import sys
import time
from datetime import date
from pathlib import Path
from typing import Callable

import duckdb
import numpy as np
import pandas as pd

from data_config import (
    ASSET_SPECS,
    DATABASE_PATH,
    GOVERNMENT_YIELD_COLUMNS,
    PROJECT_ROOT,
    RAW_START_DATE,
    AssetSpec,
)


sys.path.insert(0, str(PROJECT_ROOT / "utils"))

from findata_lib import (  # noqa: E402
    get_bond_index_close,
    get_bond_rates,
    get_china_yield_curve,
    get_etf_price,
    get_index_close,
)


MAX_DOWNLOAD_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 2


class AssignmentDataDownloader:
    """Download configured data and atomically replace DuckDB observations."""

    def __init__(
        self,
        database_path: Path,
        start_date: str,
        end_date: str,
    ) -> None:
        """Initialize the downloader.

        Args:
            database_path: Target DuckDB database path.
            start_date: Inclusive raw-data start in ``YYYY-MM-DD`` format.
            end_date: Inclusive raw-data end in ``YYYY-MM-DD`` format.
        """
        self.database_path = database_path
        self.start_date = start_date
        self.end_date = end_date

    @staticmethod
    def _call_with_retry(
        operation: Callable[[], object],
        description: str,
    ) -> object:
        """Run one network operation with bounded retries.

        Args:
            operation: Zero-argument callable that performs the download.
            description: Dataset label included in failure messages.

        Returns:
            Object returned by ``operation``.

        Raises:
            RuntimeError: If every attempt fails.
        """
        failures: list[str] = []
        for attempt in range(1, MAX_DOWNLOAD_ATTEMPTS + 1):
            try:
                return operation()
            except Exception as exc:
                failures.append(f"attempt {attempt}: {type(exc).__name__}: {exc}")
                if attempt < MAX_DOWNLOAD_ATTEMPTS:
                    time.sleep(RETRY_DELAY_SECONDS * attempt)

        details = "; ".join(failures)
        raise RuntimeError(f"Failed to download {description}. {details}")

    def _download_asset(self, spec: AssetSpec) -> pd.DataFrame:
        """Download and normalize one asset series.

        Args:
            spec: Asset definition containing its symbol and fetch method.

        Returns:
            DataFrame with columns ``asset_id``, ``trade_date`` and ``close``.
        """
        fetchers: dict[str, Callable[[], pd.Series]] = {
            "index": lambda: get_index_close(
                spec.symbol,
                start=self.start_date,
                end=self.end_date,
            ),
            "bond_index": lambda: get_bond_index_close(
                spec.symbol,
                start=self.start_date,
                end=self.end_date,
            ),
            "etf_price": lambda: get_etf_price(
                spec.symbol,
                start=self.start_date,
                end=self.end_date,
            ),
        }
        series = self._call_with_retry(
            fetchers[spec.fetch_method],
            spec.asset_name,
        )
        if not isinstance(series, pd.Series):
            raise TypeError(
                f"Expected '{spec.asset_name}' to return a pandas Series, "
                f"but got {type(series).__name__}."
            )

        frame = series.rename("close").rename_axis("trade_date").reset_index()
        frame.insert(0, "asset_id", spec.asset_id)
        frame["trade_date"] = pd.to_datetime(
            frame["trade_date"],
            errors="coerce",
        ).dt.date
        frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
        return frame[["asset_id", "trade_date", "close"]]

    def download_index_daily(self) -> pd.DataFrame:
        """Download all configured equity and bond market series.

        Returns:
            Long-form observations with shape ``[N, 3]`` and columns
            ``asset_id``, ``trade_date`` and ``close``.
        """
        frames = []
        for spec in ASSET_SPECS:
            print(f"Downloading {spec.asset_id}: {spec.asset_name}")
            frames.append(self._download_asset(spec))
        return pd.concat(frames, ignore_index=True)

    def download_government_yields(self) -> pd.DataFrame:
        """Download and normalize historical Chinese government-bond yields.

        Returns:
            Long-form yield observations with shape ``[N, 3]``. Yields are
            decimals rather than percentages.

        Raises:
            ValueError: If the required 10-year yield is unavailable.
        """
        raw_frame = self._call_with_retry(
            lambda: get_bond_rates(start=self.start_date.replace("-", "")),
            "government-bond yield history",
        )
        if not isinstance(raw_frame, pd.DataFrame):
            raise TypeError(
                "Expected government-bond yields to return a pandas DataFrame, "
                f"but got {type(raw_frame).__name__}."
            )
        if GOVERNMENT_YIELD_COLUMNS[10.0] not in raw_frame.columns:
            raise ValueError("Required 10-year Chinese government yield is missing.")

        normalized_frames = []
        for tenor_years, column_name in GOVERNMENT_YIELD_COLUMNS.items():
            if column_name not in raw_frame.columns:
                continue
            tenor_frame = pd.DataFrame(
                {
                    "trade_date": pd.to_datetime(
                        raw_frame["日期"],
                        errors="coerce",
                    ).dt.date,
                    "tenor_years": tenor_years,
                    "yield_decimal": pd.to_numeric(
                        raw_frame[column_name],
                        errors="coerce",
                    )
                    / 100.0,
                }
            )
            normalized_frames.append(tenor_frame)

        normalized = pd.concat(normalized_frames, ignore_index=True)
        return normalized.dropna(
            subset=["trade_date", "yield_decimal"]
        ).reset_index(drop=True)

    def download_yield_curve_snapshot(
        self,
        curve_date: date,
    ) -> pd.DataFrame:
        """Download the latest Chinese government yield-curve cross-section.

        Args:
            curve_date: Date assigned to the snapshot. The public interface
                does not expose its source row date, so the latest historical
                government-yield date is used.

        Returns:
            Curve points with shape ``[T, 3]``. Tenors are in years and yields
            are decimals.
        """
        result = self._call_with_retry(
            get_china_yield_curve,
            "latest China government yield curve",
        )
        maturities, yields = result
        maturity_array = np.asarray(maturities, dtype="float64")
        yield_array = np.asarray(yields, dtype="float64")
        if maturity_array.shape != yield_array.shape:
            raise ValueError(
                "Expected yield-curve maturities and yields to share a shape, "
                f"but got {maturity_array.shape} and {yield_array.shape}."
            )

        return pd.DataFrame(
            {
                "curve_date": curve_date,
                "tenor_years": maturity_array,
                "yield_decimal": yield_array,
            }
        )

    @staticmethod
    def build_assets_frame() -> pd.DataFrame:
        """Build the asset metadata table from configuration.

        Returns:
            One row per configured asset.
        """
        return pd.DataFrame(
            [
                {
                    "asset_id": spec.asset_id,
                    "asset_name": spec.asset_name,
                    "asset_class": spec.asset_class,
                    "symbol": spec.symbol,
                    "source": spec.source,
                    "return_type": spec.return_type,
                    "tenor_bucket": spec.tenor_bucket,
                }
                for spec in ASSET_SPECS
            ]
        )

    @staticmethod
    def build_trading_calendar(index_daily: pd.DataFrame) -> pd.DataFrame:
        """Build the A-share trading calendar from CSI 300 observations.

        Args:
            index_daily: Long-form index observations with shape ``[N, 3]``.

        Returns:
            Unique CSI 300 trading dates with shape ``[D, 1]``.
        """
        calendar = index_daily.loc[
            index_daily["asset_id"] == "CSI300",
            ["trade_date"],
        ]
        return calendar.drop_duplicates().sort_values("trade_date")

    @staticmethod
    def _create_schema(connection: duckdb.DuckDBPyConnection) -> None:
        """Create the final DuckDB tables when absent.

        Args:
            connection: Open DuckDB connection.
        """
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS assets (
                asset_id VARCHAR PRIMARY KEY,
                asset_name VARCHAR NOT NULL,
                asset_class VARCHAR NOT NULL,
                symbol VARCHAR NOT NULL,
                source VARCHAR NOT NULL,
                return_type VARCHAR NOT NULL,
                tenor_bucket VARCHAR
            );

            CREATE TABLE IF NOT EXISTS index_daily (
                asset_id VARCHAR NOT NULL REFERENCES assets(asset_id),
                trade_date DATE NOT NULL,
                close DOUBLE NOT NULL CHECK (close > 0),
                PRIMARY KEY (asset_id, trade_date)
            );

            CREATE TABLE IF NOT EXISTS gov_yield_daily (
                trade_date DATE NOT NULL,
                tenor_years DOUBLE NOT NULL CHECK (tenor_years > 0),
                yield_decimal DOUBLE NOT NULL,
                PRIMARY KEY (trade_date, tenor_years)
            );

            CREATE TABLE IF NOT EXISTS yield_curve_snapshot (
                curve_date DATE NOT NULL,
                tenor_years DOUBLE NOT NULL CHECK (tenor_years > 0),
                yield_decimal DOUBLE NOT NULL,
                PRIMARY KEY (curve_date, tenor_years)
            );

            CREATE TABLE IF NOT EXISTS trading_calendar (
                trade_date DATE PRIMARY KEY
            );
            """
        )

    def ingest(
        self,
        assets: pd.DataFrame,
        index_daily: pd.DataFrame,
        government_yields: pd.DataFrame,
        yield_curve: pd.DataFrame,
        trading_calendar: pd.DataFrame,
    ) -> None:
        """Atomically replace all Assignment 1 data tables.

        Args:
            assets: Asset metadata with shape ``[A, 7]``.
            index_daily: Index observations with shape ``[N, 3]``.
            government_yields: Historical yields with shape ``[Y, 3]``.
            yield_curve: Latest curve points with shape ``[T, 3]``.
            trading_calendar: A-share dates with shape ``[D, 1]``.
        """
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.database_path.with_name(
            f"{self.database_path.stem}.tmp{self.database_path.suffix}"
        )
        if temporary_path.exists():
            temporary_path.unlink()

        try:
            with duckdb.connect(str(temporary_path)) as connection:
                self._create_schema(connection)
                frames = {
                    "assets_frame": assets,
                    "index_daily_frame": index_daily,
                    "government_yields_frame": government_yields,
                    "yield_curve_frame": yield_curve,
                    "trading_calendar_frame": trading_calendar,
                }
                for name, frame in frames.items():
                    connection.register(name, frame)

                connection.execute("BEGIN TRANSACTION")
                connection.execute("INSERT INTO assets SELECT * FROM assets_frame")
                connection.execute(
                    "INSERT INTO index_daily SELECT * FROM index_daily_frame"
                )
                connection.execute(
                    "INSERT INTO gov_yield_daily "
                    "SELECT * FROM government_yields_frame"
                )
                connection.execute(
                    "INSERT INTO yield_curve_snapshot "
                    "SELECT * FROM yield_curve_frame"
                )
                connection.execute(
                    "INSERT INTO trading_calendar "
                    "SELECT * FROM trading_calendar_frame"
                )
                connection.execute("COMMIT")
            temporary_path.replace(self.database_path)
        finally:
            if temporary_path.exists():
                temporary_path.unlink()

    def run(self) -> None:
        """Download every dataset and write one consistent database snapshot."""
        index_daily = self.download_index_daily()
        government_yields = self.download_government_yields()
        valid_yield_dates = government_yields["trade_date"].dropna()
        if valid_yield_dates.empty:
            raise ValueError("Government-bond yield history contains no valid date.")
        curve_date = max(valid_yield_dates)
        yield_curve = self.download_yield_curve_snapshot(curve_date)
        assets = self.build_assets_frame()
        trading_calendar = self.build_trading_calendar(index_daily)

        self.ingest(
            assets=assets,
            index_daily=index_daily,
            government_yields=government_yields,
            yield_curve=yield_curve,
            trading_calendar=trading_calendar,
        )
        print(f"Database written to {self.database_path}")


def main() -> None:
    """Run the Assignment 1 download and ingestion stage."""
    downloader = AssignmentDataDownloader(
        database_path=DATABASE_PATH,
        start_date=RAW_START_DATE,
        end_date=date.today().isoformat(),
    )
    downloader.run()


if __name__ == "__main__":
    main()

