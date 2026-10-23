"""Command-line entry point for Assignment 1, Module 3."""

from __future__ import annotations

import plotly.graph_objects as go

from charts import (
    create_curve_figure,
    create_late_2024_figure,
    create_liability_matching_figure,
    create_realized_convexity_figure,
    create_regression_figure,
    create_rolling_duration_figure,
    create_stress_figure,
    create_yield_pca_figure,
    export_static_figures,
    write_combined_html,
)
from config import AnalysisPaths, AnalysisResults
from curve import (
    build_curve_results,
    build_duration_convexity,
    build_liability_matching_analysis,
    build_realized_2024_convexity_attribution,
    build_stress_results,
    fit_nelson_siegel,
)
from market import (
    calculate_rolling_rate_duration,
    run_rate_sensitivity_regressions,
    run_yield_pca,
)
from outputs import write_report, write_result_tables
from repository import FixedIncomeRepository


def run_calculations(paths: AnalysisPaths) -> AnalysisResults:
    """Run all calculations without writing presentation artifacts.

    Args:
        paths: Standard database and output paths.

    Returns:
        Complete immutable result container.
    """
    repository = FixedIncomeRepository(paths.database)
    curve = repository.load_curve_snapshot()
    curve_fit = fit_nelson_siegel(curve)
    curve_results = build_curve_results(curve, curve_fit)
    duration_convexity = build_duration_convexity(curve_fit)
    stress_results = build_stress_results(duration_convexity)
    regression_data, regression_results = run_rate_sensitivity_regressions(
        repository
    )
    rolling_duration = calculate_rolling_rate_duration(regression_data)
    yield_pca = run_yield_pca(repository)
    late_period = repository.load_late_2024_period()
    realized_convexity = build_realized_2024_convexity_attribution(late_period)
    liability_strategies, liability_stress = build_liability_matching_analysis(
        duration_convexity
    )
    return AnalysisResults(
        curve=curve,
        curve_fit=curve_fit,
        curve_results=curve_results,
        duration_convexity=duration_convexity,
        stress_results=stress_results,
        regression_data=regression_data,
        regression_results=regression_results,
        late_period=late_period,
        realized_convexity=realized_convexity,
        rolling_duration=rolling_duration,
        yield_pca=yield_pca,
        liability_strategies=liability_strategies,
        liability_stress=liability_stress,
    )


def build_figures(results: AnalysisResults) -> dict[str, go.Figure]:
    """Build all core figures in report order.

    Args:
        results: Complete calculated analysis results.

    Returns:
        Ordered mapping from stable file stem to Plotly figure.
    """
    return {
        "module3_nelson_siegel_curve": create_curve_figure(
            results.curve,
            results.curve_fit,
            results.curve_results,
        ),
        "module3_stress_test_errors": create_stress_figure(
            results.stress_results
        ),
        "module3_rate_sensitivity_regressions": create_regression_figure(
            results.regression_data,
            results.regression_results,
        ),
        "module3_late_2024_rate_stage": create_late_2024_figure(
            results.late_period
        ),
        "module3_realized_2024_convexity": create_realized_convexity_figure(
            results.realized_convexity
        ),
        "module3_rolling_rate_duration": create_rolling_duration_figure(
            results.rolling_duration
        ),
        "module3_yield_pca": create_yield_pca_figure(results.yield_pca),
        "module3_liability_matching": create_liability_matching_figure(
            results.liability_strategies,
            results.liability_stress,
        ),
    }


def main() -> None:
    """Run Module 3 and write tables, one HTML dashboard, SVGs, and report."""
    paths = AnalysisPaths.from_script()
    results = run_calculations(paths)
    figures = build_figures(results)

    write_result_tables(results, paths.output)
    write_report(results, paths.output / "fixed_income_report.md")
    write_combined_html(
        figures,
        paths.output / "module3_fixed_income_dashboard.html",
    )
    export_static_figures(figures, paths.figures)

    print(f"Module 3 outputs written to: {paths.output}")
    print(f"Module 3 figures written to: {paths.figures}")


if __name__ == "__main__":
    main()
