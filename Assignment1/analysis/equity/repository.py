"""Read stock and bond index observations from the course DuckDB."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

from config import (
    ANALYSIS_START_DATE,
    BOND_ASSETS,
    EQUITY_ASSETS,
    WARMUP_START_DATE,
)


REQUIRED_ASSETS: tuple[str, ...] = (*EQUITY_ASSETS, *BOND_ASSETS)


class MarketRepository:
    """Provide validated, read-only access to the market daily index data."""

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

    def load_price_panel(self) -> pd.DataFrame:
        """Read the close-price panel for the assets used in parts 3–4.

        The query starts in 2018 so that the 120-observation rolling
        correlations reported from 2019 onward are complete.

        Returns:
            Wide panel indexed by ``trade_date`` with one column per asset.

        Raises:
            ValueError: If a required asset, date or price is missing.
        """
        query = f"""
            SELECT asset_id, trade_date, close
            FROM index_daily
            WHERE trade_date >= DATE '{WARMUP_START_DATE}'
              AND asset_id IN ({", ".join(f"'{asset}'" for asset in REQUIRED_ASSETS)})
            ORDER BY trade_date, asset_id
        """
        with duckdb.connect(str(self.database), read_only=True) as connection:
            long_panel = connection.execute(query).fetch_df()

        if long_panel.empty:
            raise ValueError(
                "The price query returned no rows; check the DuckDB contents."
            )
        available = set(long_panel["asset_id"].unique())
        missing = [asset for asset in REQUIRED_ASSETS if asset not in available]
        if missing:
            raise ValueError(f"Missing required assets in DuckDB: {missing}.")

        panel = long_panel.pivot(
            index="trade_date",
            columns="asset_id",
            values="close",
        ).sort_index()
        panel = panel.loc[:, list(REQUIRED_ASSETS)]
        panel.index = pd.to_datetime(panel.index)
        panel.index.name = "trade_date"

        # Leading gaps are impossible for these three assets, but interior
        # gaps would silently distort correlations and the event window.
        for asset_id in REQUIRED_ASSETS:
            series = panel[asset_id]
            first_valid = series.first_valid_index()
            if first_valid is None:
                raise ValueError(f"Asset '{asset_id}' has no observations.")
            if series.loc[first_valid:].isna().any():
                raise ValueError(
                    f"Asset '{asset_id}' has interior missing closes after "
                    f"{first_valid.date().isoformat()}."
                )

        if not panel.index.max() >= pd.Timestamp(ANALYSIS_START_DATE):
            raise ValueError("The price panel does not reach the analysis window.")
        if not panel.index.min() < pd.Timestamp(ANALYSIS_START_DATE):
            raise ValueError("The price panel does not cover the 2018 warm-up rows.")
        return panel
