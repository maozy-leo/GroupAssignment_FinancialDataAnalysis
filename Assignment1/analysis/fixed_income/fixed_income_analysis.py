"""Command-line entry point for Assignment 1, Module 3."""

from __future__ import annotations

import plotly.graph_objects as go

from charts import (
    create_curve_figure,
    create_late_2024_figure,
    create_realized_convexity_figure,
    create_regression_figure,
    create_rolling_duration_figure,
    create_stress_figure,
    export_static_figures,
)
from config import AnalysisPaths, AnalysisResults
from curve import (
    build_curve_results,
    build_duration_convexity,
    build_realized_2024_convexity_attribution,
    build_stress_results,
    fit_nelson_siegel,
)
from market import (
    calculate_rolling_rate_duration,
    run_rate_sensitivity_regressions,
)
from html_report import write_html_report
from outputs import write_result_tables
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
    data_audit = repository.load_data_audit()
    curve_fit = fit_nelson_siegel(curve)
    curve_results = build_curve_results(curve, curve_fit)
    duration_convexity = build_duration_convexity(curve_fit)
    stress_results = build_stress_results(duration_convexity)
    regression_data, regression_results = run_rate_sensitivity_regressions(
        repository
    )
    rolling_duration = calculate_rolling_rate_duration(regression_data)
    late_period = repository.load_late_2024_period()
    realized_convexity = build_realized_2024_convexity_attribution(late_period)
    return AnalysisResults(
        curve=curve,
        data_audit=data_audit,
        curve_fit=curve_fit,
        curve_results=curve_results,
        duration_convexity=duration_convexity,
        stress_results=stress_results,
        regression_data=regression_data,
        regression_results=regression_results,
        late_period=late_period,
        realized_convexity=realized_convexity,
        rolling_duration=rolling_duration,
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
    }


def main() -> None:
    """Run Module 3 and write tables, one HTML report, and SVG figures."""
    paths = AnalysisPaths.from_script()
    results = run_calculations(paths)
    figures = build_figures(results)

    write_result_tables(results, paths.output)
    write_html_report(
        figures,
        results,
        paths.output / "module3_fixed_income_dashboard.html",
    )
    for figure_name, figure in figures.items():
        figure.write_html(
            paths.output / f"{figure_name}.html",
            include_plotlyjs="directory",
            full_html=True,
        )
    export_static_figures(figures, paths.figures)

    print(f"Module 3 outputs written to: {paths.output}")
    print(f"Module 3 figures written to: {paths.figures}")


if __name__ == "__main__":
    main()
