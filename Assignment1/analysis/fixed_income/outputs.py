"""Write fixed-income analysis result tables."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from config import AnalysisResults


def write_result_tables(
    results: AnalysisResults,
    output_directory: Path,
) -> None:
    """Write every Module 3 result table as UTF-8 CSV.

    Args:
        results: Complete calculated analysis results.
        output_directory: Existing or creatable destination directory.
    """
    output_directory.mkdir(parents=True, exist_ok=True)
    beta_0, beta_1, beta_2, tau = results.curve_fit.parameters
    rmse_decimal = np.sqrt(
        results.curve_fit.objective / len(results.curve)
    )
    parameter_table = pd.DataFrame(
        {
            "curve_date": [results.curve["curve_date"].iloc[0]],
            "beta_0": [beta_0],
            "beta_1": [beta_1],
            "beta_2": [beta_2],
            "tau": [tau],
            "rmse_decimal": [rmse_decimal],
            "rmse_bp": [rmse_decimal * 10_000.0],
        }
    )
    tables = {
        "nelson_siegel_parameters.csv": parameter_table,
        "nelson_siegel_start_diagnostics.csv": results.curve_fit.diagnostics,
        "nelson_siegel_residuals.csv": results.curve_results,
        "duration_convexity.csv": results.duration_convexity,
        "stress_test_results.csv": results.stress_results,
        "rate_sensitivity_regressions.csv": results.regression_results,
        "late_2024_period.csv": results.late_period,
        "realized_2024_convexity_attribution.csv": results.realized_convexity,
        "rolling_rate_duration.csv": results.rolling_duration,
    }
    for filename, table in tables.items():
        table.to_csv(
            output_directory / filename,
            index=False,
            encoding="utf-8-sig",
        )
