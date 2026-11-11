"""Configuration for Module 2, parts 3–4 (stock-bond correlation and the 2024 pulse).

This package deliberately contains only the code needed for part 3 (the
time-varying stock-bond correlation) and part 4 (the 2024-09-20 to 2024-10-08
pulse). Module 2 parts 1–2 (return distributions and rolling volatility) live
in the main repository and are intentionally absent here.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final

import pandas as pd


ANALYSIS_START_DATE: Final = "2019-01-01"
WARMUP_START_DATE: Final = "2018-01-01"
ROLLING_CORR_WINDOW: Final = 120
TRADING_DAYS_PER_YEAR: Final = 252

EVENT_START_DATE: Final = "2024-09-20"
EVENT_END_DATE: Final = "2024-10-08"
STABILITY_START_DATE: Final = "2022-01-01"
STABILITY_END_DATE: Final = "2024-12-31"

EQUITY_PORTFOLIO_WEIGHT: Final = 0.60
BOND_PORTFOLIO_WEIGHT: Final = 0.40
PORTFOLIO_ASSET_ID: Final = "PORTFOLIO_60_40"
PORTFOLIO_NAME: Final = "60/40股债组合"

EQUITY_ASSETS: Final[dict[str, str]] = {"CSI300": "沪深300"}
BOND_ASSETS: Final[dict[str, str]] = {
    "SSE_TREASURY": "上证国债指数",
    "SSE_ENTERPRISE_BOND": "上证企债指数",
}
ASSET_NAMES: Final[dict[str, str]] = {
    **EQUITY_ASSETS,
    **BOND_ASSETS,
    PORTFOLIO_ASSET_ID: PORTFOLIO_NAME,
}
ASSET_COLORS: Final[dict[str, str]] = {
    "CSI300": "#1f77b4",
    "SSE_TREASURY": "#6a51a3",
    "SSE_ENTERPRISE_BOND": "#8c564b",
    PORTFOLIO_ASSET_ID: "#17becf",
}
STOCK_BOND_PAIRS: Final[tuple[tuple[str, str], ...]] = (
    ("CSI300", "SSE_TREASURY"),
    ("CSI300", "SSE_ENTERPRISE_BOND"),
)
MAIN_STOCK_BOND_PAIR: Final[tuple[str, str]] = ("CSI300", "SSE_TREASURY")


def pair_id(asset_a: str, asset_b: str) -> str:
    """Build the stable identifier used for one asset pair.

    Args:
        asset_a: Left-hand asset identifier.
        asset_b: Right-hand asset identifier.

    Returns:
        Identifier of the form ``ASSET_A__ASSET_B``.
    """
    return f"{asset_a}__{asset_b}"


def pair_label(asset_a: str, asset_b: str) -> str:
    """Build the Chinese display label of one asset pair.

    Args:
        asset_a: Left-hand asset identifier.
        asset_b: Right-hand asset identifier.

    Returns:
        Display label such as ``沪深300—上证国债指数``.
    """
    return f"{ASSET_NAMES[asset_a]}—{ASSET_NAMES[asset_b]}"


@dataclass(frozen=True)
class AnalysisPaths:
    """Store input and output paths of the submission package.

    Args:
        database: DuckDB file with the course market data.
        figures: Directory for static Plotly exports (SVG and PNG).
        output: Directory for CSV result tables.
        report: Directory for the Markdown report.
    """

    database: Path
    figures: Path
    output: Path
    report: Path

    @classmethod
    def from_script(cls) -> "AnalysisPaths":
        """Build the standard Assignment 1 paths from this package.

        Returns:
            Paths rooted at the repository's ``Assignment1`` directory.
        """
        assignment_dir = Path(__file__).resolve().parents[2]
        return cls(
            database=assignment_dir / "data" / "data.duckdb",
            figures=assignment_dir / "figures" / "module2",
            output=assignment_dir / "output" / "equity",
            report=assignment_dir / "output" / "equity",
        )


@dataclass(frozen=True)
class AnalysisResults:
    """Collect all tables produced by parts 3–4 calculations.

    Args:
        stock_bond_correlations: Long 120-day stock-bond correlations.
        correlation_summary: Headline statistics for the two stock-bond pairs.
        annual_correlation: Calendar-year stock-bond correlations.
        stock_bond_period_summary: Rolling-correlation statistics inside the
            2022–2024 "see-saw" window.
        event_stats: 2024 event-window performance table.
        event_paths: 2024 event-window rebased net-value paths.
        event_daily: 2024 event-window daily returns in long format.
    """

    stock_bond_correlations: pd.DataFrame
    correlation_summary: pd.DataFrame
    annual_correlation: pd.DataFrame
    stock_bond_period_summary: pd.DataFrame
    event_stats: pd.DataFrame
    event_paths: pd.DataFrame
    event_daily: pd.DataFrame
