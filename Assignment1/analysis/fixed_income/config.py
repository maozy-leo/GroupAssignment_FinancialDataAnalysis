"""Shared configuration and result containers for fixed-income analysis."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final

import numpy as np
import pandas as pd
from numpy.typing import NDArray


ANALYSIS_START_DATE: Final = "2019-01-01"
LATE_2024_START_DATE: Final = "2024-11-01"
LATE_2024_END_DATE: Final = "2024-12-31"
FACE_VALUE: Final = 100.0
HAC_MAX_LAGS: Final = 5
CURVE_GRID_POINTS: Final = 600

BOND_ASSETS: Final[dict[str, str]] = {
    "SSE_TREASURY": "上证国债指数",
    "SSE_ENTERPRISE_BOND": "上证企债指数",
    "POLICY_BOND_7_10_PROXY": "政金债券ETF（政金债7—10年指数代理）",
}
BOND_COLORS: Final[dict[str, str]] = {
    "SSE_TREASURY": "#1f77b4",
    "SSE_ENTERPRISE_BOND": "#ff7f0e",
    "POLICY_BOND_7_10_PROXY": "#2ca02c",
}
SCENARIOS: Final[dict[str, str]] = {
    "parallel_down_100bp": "平行下移100bp",
    "parallel_down_50bp": "平行下移50bp",
    "parallel_50bp": "平行上移50bp",
    "parallel_100bp": "平行上移100bp",
    "steepening": "陡峭化",
}
YIELD_TENORS: Final[tuple[float, ...]] = (2.0, 5.0, 10.0, 30.0)
ROLLING_REGRESSION_WINDOW: Final = 252


@dataclass(frozen=True)
class AnalysisPaths:
    """Store input and output paths for the fixed-income module.

    Args:
        database: DuckDB file containing all source observations.
        figures: Directory for static Plotly exports.
        output: Directory for tables, combined HTML, and the report.
    """

    database: Path
    figures: Path
    output: Path

    @classmethod
    def from_script(cls) -> "AnalysisPaths":
        """Build the standard Assignment 1 paths from this package.

        Returns:
            Paths rooted at the repository's ``Assignment1`` directory.
        """
        assignment_dir = Path(__file__).resolve().parents[2]
        return cls(
            database=assignment_dir / "data" / "data.duckdb",
            figures=assignment_dir / "figures" / "module3",
            output=assignment_dir / "output" / "fixed_income",
        )


@dataclass(frozen=True)
class NelsonSiegelFit:
    """Store fitted curve parameters and multi-start diagnostics.

    Args:
        parameters: Fitted ``[beta_0, beta_1, beta_2, tau]`` vector.
        objective: Residual sum of squares in decimal-yield units.
        diagnostics: One row per optimization start.
    """

    parameters: NDArray[np.float64]
    objective: float
    diagnostics: pd.DataFrame


@dataclass(frozen=True)
class YieldPcaResults:
    """Store yield PCA and key-rate sensitivity outputs.

    Args:
        scores: Daily level, slope, and curvature factor scores.
        explained_variance: Variance share explained by each factor.
        loadings: Factor loadings at the four historical tenors.
        regressions: Per-asset factor regression statistics.
        key_rate_durations: Factor-implied sensitivities by asset and tenor.
    """

    scores: pd.DataFrame
    explained_variance: pd.DataFrame
    loadings: pd.DataFrame
    regressions: pd.DataFrame
    key_rate_durations: pd.DataFrame


@dataclass(frozen=True)
class AnalysisResults:
    """Collect all tables produced by Module 3 calculations.

    Args:
        curve: Latest observed government yield curve.
        curve_fit: Selected Nelson–Siegel fit and diagnostics.
        curve_results: Pointwise fitted yields and residuals.
        duration_convexity: Zero-coupon price and risk metrics.
        stress_results: Exact and approximate stress repricing results.
        regression_data: Per-asset samples with fitted returns.
        regression_results: Newey–West regression summary.
        late_period: Aligned late-2024 rate and bond-index series.
        realized_convexity: Late-2024 constant-maturity attribution.
        rolling_duration: Rolling implied rate durations.
        yield_pca: Yield PCA and key-rate sensitivity results.
        liability_strategies: Five-year liability-matching strategies.
        liability_stress: Strategy surplus changes under ±100bp shocks.
    """

    curve: pd.DataFrame
    curve_fit: NelsonSiegelFit
    curve_results: pd.DataFrame
    duration_convexity: pd.DataFrame
    stress_results: pd.DataFrame
    regression_data: dict[str, pd.DataFrame]
    regression_results: pd.DataFrame
    late_period: pd.DataFrame
    realized_convexity: pd.DataFrame
    rolling_duration: pd.DataFrame
    yield_pca: YieldPcaResults
    liability_strategies: pd.DataFrame
    liability_stress: pd.DataFrame
