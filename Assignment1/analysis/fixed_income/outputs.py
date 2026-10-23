"""Write result tables and render the Markdown report from a template."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from jinja2 import Environment, StrictUndefined

from config import AnalysisResults, BOND_ASSETS, HAC_MAX_LAGS


REPORT_TEMPLATE_PATH = Path(__file__).with_name("report_template.md")


def write_result_tables(results: AnalysisResults, output_directory: Path) -> None:
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
        "yield_pca_scores.csv": results.yield_pca.scores,
        "yield_pca_explained_variance.csv": (
            results.yield_pca.explained_variance
        ),
        "yield_pca_loadings.csv": results.yield_pca.loadings,
        "yield_pca_regressions.csv": results.yield_pca.regressions,
        "yield_pca_key_rate_durations.csv": (
            results.yield_pca.key_rate_durations
        ),
        "liability_duration_matching.csv": results.liability_strategies,
        "liability_stress_results.csv": results.liability_stress,
    }
    for filename, table in tables.items():
        table.to_csv(
            output_directory / filename,
            index=False,
            encoding="utf-8-sig",
        )


def write_report(results: AnalysisResults, output_path: Path) -> None:
    """Render the report with the standalone Markdown template.

    Args:
        results: Complete calculated analysis results.
        output_path: Destination Markdown path.

    Raises:
        FileNotFoundError: If the report template is absent.
    """
    if not REPORT_TEMPLATE_PATH.is_file():
        raise FileNotFoundError(
            f"Expected report template at '{REPORT_TEMPLATE_PATH}'."
        )
    environment = Environment(
        autoescape=False,
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )
    template = environment.from_string(
        REPORT_TEMPLATE_PATH.read_text(encoding="utf-8")
    )
    output_path.write_text(
        template.render(**_build_report_context(results)),
        encoding="utf-8",
    )


def _build_report_context(results: AnalysisResults) -> dict[str, object]:
    """Convert result tables into scalar and row values for the template."""
    curve_fit = results.curve_fit
    beta_0, beta_1, beta_2, tau = curve_fit.parameters
    residuals = results.curve_results
    max_residual = residuals.iloc[residuals["residual_bp"].abs().argmax()]
    stress = results.stress_results
    late_period = results.late_period
    return {
        "hac_max_lags": HAC_MAX_LAGS,
        "curve_date": pd.Timestamp(
            results.curve["curve_date"].iloc[0]
        ).date().isoformat(),
        "beta_0": beta_0,
        "beta_1": beta_1,
        "beta_2": beta_2,
        "tau": tau,
        "rmse_bp": np.sqrt(curve_fit.objective / len(results.curve)) * 10_000,
        "max_residual": max_residual,
        "long_bond": results.duration_convexity.loc[
            results.duration_convexity["tenor_years"] == 10.0
        ].iloc[0],
        "worst_duration": stress.iloc[stress["duration_error_bp"].argmax()],
        "worst_convexity": stress.iloc[
            stress["duration_convexity_error_bp"].argmax()
        ],
        "average_error_reduction": 1.0
        - stress["duration_convexity_absolute_error"].mean()
        / stress["duration_absolute_error"].mean(),
        "regressions": results.regression_results.to_dict("records"),
        "treasury_regression": results.regression_results.loc[
            results.regression_results["asset_id"] == "SSE_TREASURY"
        ].iloc[0],
        "start_yield": float(late_period["yield_10y_decimal"].iloc[0]),
        "end_yield": float(late_period["yield_10y_decimal"].iloc[-1]),
        "yield_change_bp": (
            late_period["yield_10y_decimal"].iloc[-1]
            - late_period["yield_10y_decimal"].iloc[0]
        )
        * 10_000.0,
        "late_returns": [
            {
                "asset_name": asset_name,
                "value": late_period[f"{asset_id}_cumulative_return"].iloc[-1],
            }
            for asset_id, asset_name in BOND_ASSETS.items()
        ],
        "down_100bp": stress.loc[
            (stress["scenario_id"] == "parallel_down_100bp")
            & (stress["tenor_years"] == 10.0)
        ].iloc[0],
        "attribution": results.realized_convexity.iloc[0],
        "rolling_summaries": _rolling_summaries(results),
        "first_three_variance": results.yield_pca.explained_variance[
            "explained_variance_ratio"
        ].iloc[:3].sum(),
        "key_rate_rows": results.yield_pca.key_rate_durations.to_dict("records"),
        "barbell": results.liability_strategies.loc[
            results.liability_strategies["strategy_id"] == "barbell_3y_10y"
        ].iloc[0],
        "barbell_stress": results.liability_stress.loc[
            results.liability_stress["strategy_id"] == "barbell_3y_10y"
        ].to_dict("records"),
    }


def _rolling_summaries(results: AnalysisResults) -> list[dict[str, object]]:
    """Summarize rolling duration ranges for each bond asset."""
    summaries: list[dict[str, object]] = []
    for asset_id, asset_name in BOND_ASSETS.items():
        sample = results.rolling_duration.loc[
            results.rolling_duration["asset_id"] == asset_id
        ]
        duration = sample["implied_rate_duration_years"]
        summaries.append(
            {
                "asset_name": asset_name,
                "first_date": pd.Timestamp(
                    sample["trade_date"].iloc[0]
                ).date().isoformat(),
                "last_date": pd.Timestamp(
                    sample["trade_date"].iloc[-1]
                ).date().isoformat(),
                "minimum": duration.min(),
                "maximum": duration.max(),
                "latest": duration.iloc[-1],
            }
        )
    return summaries
