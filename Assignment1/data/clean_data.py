"""Clean the Assignment 1 DuckDB tables in place."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import duckdb
import pandas as pd

from data_config import CLEANING_SUMMARY_PATH, DATABASE_PATH


MIN_VALID_YIELD = -0.05
MAX_VALID_YIELD = 0.20


@dataclass(frozen=True)
class CleaningResult:
    """Record row counts for one cleaned table."""

    table_name: str
    rows_before: int
    rows_after: int
    invalid_rows_removed: int
    duplicate_rows_removed: int


class AssignmentDataCleaner:
    """Apply deterministic cleaning rules to the Assignment 1 database."""

    def __init__(self, database_path: Path) -> None:
        """Initialize the cleaner.

        Args:
            database_path: Existing DuckDB database to clean.

        Raises:
            FileNotFoundError: If the database does not exist.
        """
        if not database_path.exists():
            raise FileNotFoundError(f"Database does not exist: {database_path}")
        self.database_path = database_path

    @staticmethod
    def _clean_index_daily(
        frame: pd.DataFrame,
    ) -> tuple[pd.DataFrame, CleaningResult]:
        """Clean index levels and remove duplicate asset-date keys.

        Args:
            frame: Raw index observations with shape ``[N, 3]``.

        Returns:
            Clean observations and row-count diagnostics.
        """
        rows_before = len(frame)
        cleaned = frame.copy()
        cleaned["trade_date"] = pd.to_datetime(
            cleaned["trade_date"],
            errors="coerce",
        )
        cleaned["close"] = pd.to_numeric(cleaned["close"], errors="coerce")
        valid_mask = (
            cleaned["asset_id"].notna()
            & cleaned["trade_date"].notna()
            & cleaned["close"].notna()
            & (cleaned["close"] > 0)
        )
        invalid_rows_removed = int((~valid_mask).sum())
        cleaned = cleaned.loc[valid_mask]
        rows_before_deduplication = len(cleaned)
        cleaned = cleaned.drop_duplicates(
            subset=["asset_id", "trade_date"],
            keep="last",
        )
        duplicate_rows_removed = rows_before_deduplication - len(cleaned)
        cleaned = cleaned.sort_values(["asset_id", "trade_date"])
        cleaned["trade_date"] = cleaned["trade_date"].dt.date

        result = CleaningResult(
            table_name="index_daily",
            rows_before=rows_before,
            rows_after=len(cleaned),
            invalid_rows_removed=invalid_rows_removed,
            duplicate_rows_removed=duplicate_rows_removed,
        )
        return cleaned, result

    @staticmethod
    def _clean_yield_table(
        frame: pd.DataFrame,
        table_name: str,
        date_column: str,
    ) -> tuple[pd.DataFrame, CleaningResult]:
        """Clean one long-form yield table.

        Args:
            frame: Yield observations with shape ``[N, 3]``.
            table_name: DuckDB table name for diagnostics.
            date_column: Name of the date column in ``frame``.

        Returns:
            Clean observations and row-count diagnostics.
        """
        rows_before = len(frame)
        cleaned = frame.copy()
        cleaned[date_column] = pd.to_datetime(
            cleaned[date_column],
            errors="coerce",
        )
        cleaned["tenor_years"] = pd.to_numeric(
            cleaned["tenor_years"],
            errors="coerce",
        )
        cleaned["yield_decimal"] = pd.to_numeric(
            cleaned["yield_decimal"],
            errors="coerce",
        )
        valid_mask = (
            cleaned[date_column].notna()
            & cleaned["tenor_years"].notna()
            & (cleaned["tenor_years"] > 0)
            & cleaned["yield_decimal"].between(
                MIN_VALID_YIELD,
                MAX_VALID_YIELD,
                inclusive="both",
            )
        )
        invalid_rows_removed = int((~valid_mask).sum())
        cleaned = cleaned.loc[valid_mask]
        rows_before_deduplication = len(cleaned)
        cleaned = cleaned.drop_duplicates(
            subset=[date_column, "tenor_years"],
            keep="last",
        )
        duplicate_rows_removed = rows_before_deduplication - len(cleaned)
        cleaned = cleaned.sort_values([date_column, "tenor_years"])
        cleaned[date_column] = cleaned[date_column].dt.date

        result = CleaningResult(
            table_name=table_name,
            rows_before=rows_before,
            rows_after=len(cleaned),
            invalid_rows_removed=invalid_rows_removed,
            duplicate_rows_removed=duplicate_rows_removed,
        )
        return cleaned, result

    @staticmethod
    def _clean_calendar(
        frame: pd.DataFrame,
    ) -> tuple[pd.DataFrame, CleaningResult]:
        """Clean the A-share trading calendar.

        Args:
            frame: Calendar observations with shape ``[D, 1]``.

        Returns:
            Clean dates and row-count diagnostics.
        """
        rows_before = len(frame)
        cleaned = frame.copy()
        cleaned["trade_date"] = pd.to_datetime(
            cleaned["trade_date"],
            errors="coerce",
        )
        valid_mask = cleaned["trade_date"].notna()
        invalid_rows_removed = int((~valid_mask).sum())
        cleaned = cleaned.loc[valid_mask]
        rows_before_deduplication = len(cleaned)
        cleaned = cleaned.drop_duplicates(subset=["trade_date"], keep="last")
        duplicate_rows_removed = rows_before_deduplication - len(cleaned)
        cleaned = cleaned.sort_values("trade_date")
        cleaned["trade_date"] = cleaned["trade_date"].dt.date

        result = CleaningResult(
            table_name="trading_calendar",
            rows_before=rows_before,
            rows_after=len(cleaned),
            invalid_rows_removed=invalid_rows_removed,
            duplicate_rows_removed=duplicate_rows_removed,
        )
        return cleaned, result

    def run(self) -> list[CleaningResult]:
        """Clean all fact tables and atomically write the cleaned values.

        Returns:
            Per-table cleaning diagnostics.
        """
        with duckdb.connect(str(self.database_path)) as connection:
            index_daily, index_result = self._clean_index_daily(
                connection.execute("SELECT * FROM index_daily").fetchdf()
            )
            government_yields, yield_result = self._clean_yield_table(
                connection.execute("SELECT * FROM gov_yield_daily").fetchdf(),
                table_name="gov_yield_daily",
                date_column="trade_date",
            )
            yield_curve, curve_result = self._clean_yield_table(
                connection.execute(
                    "SELECT * FROM yield_curve_snapshot"
                ).fetchdf(),
                table_name="yield_curve_snapshot",
                date_column="curve_date",
            )
            trading_calendar, calendar_result = self._clean_calendar(
                connection.execute("SELECT * FROM trading_calendar").fetchdf()
            )

            frames = {
                "clean_index_daily": index_daily,
                "clean_government_yields": government_yields,
                "clean_yield_curve": yield_curve,
                "clean_trading_calendar": trading_calendar,
            }
            for name, frame in frames.items():
                connection.register(name, frame)

            connection.execute("BEGIN TRANSACTION")
            try:
                connection.execute("DELETE FROM index_daily")
                connection.execute(
                    "INSERT INTO index_daily SELECT * FROM clean_index_daily"
                )
                connection.execute("DELETE FROM gov_yield_daily")
                connection.execute(
                    "INSERT INTO gov_yield_daily "
                    "SELECT * FROM clean_government_yields"
                )
                connection.execute("DELETE FROM yield_curve_snapshot")
                connection.execute(
                    "INSERT INTO yield_curve_snapshot "
                    "SELECT * FROM clean_yield_curve"
                )
                connection.execute("DELETE FROM trading_calendar")
                connection.execute(
                    "INSERT INTO trading_calendar "
                    "SELECT * FROM clean_trading_calendar"
                )
                connection.execute("COMMIT")
            except Exception:
                connection.execute("ROLLBACK")
                raise

        results = [
            index_result,
            yield_result,
            curve_result,
            calendar_result,
        ]
        CLEANING_SUMMARY_PATH.write_text(
            json.dumps(
                [asdict(result) for result in results],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return results


def main() -> None:
    """Run the Assignment 1 cleaning stage."""
    cleaner = AssignmentDataCleaner(DATABASE_PATH)
    results = cleaner.run()
    for result in results:
        print(
            f"{result.table_name}: {result.rows_before} -> "
            f"{result.rows_after} rows"
        )
    print(f"Cleaning summary written to {CLEANING_SUMMARY_PATH}")


if __name__ == "__main__":
    main()

