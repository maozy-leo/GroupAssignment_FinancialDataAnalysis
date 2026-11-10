"""Command-line entry point for Module 2, parts 3–4.

Running this script from the submission folder regenerates every deliverable:

    python 代码/part34_analysis.py

It writes the CSV tables into ``结果表/``, the SVG/PNG figures into ``图表/``,
the Markdown report into ``报告/`` and the offline HTML into ``交互页面/``.
"""

from __future__ import annotations

import plotly.graph_objects as go

from charts import (
    create_event_figure,
    create_stock_bond_annual_figure,
    create_stock_bond_correlation_figure,
    export_static_figures,
    write_combined_html,
)
from config import AnalysisPaths, AnalysisResults
from market import (
    build_annual_correlations,
    build_correlation_summary,
    build_event_analysis,
    build_stock_bond_period_summary,
    compute_log_returns,
    compute_stock_bond_correlations,
)
from outputs import write_report, write_result_tables
from repository import MarketRepository


def run_calculations(paths: AnalysisPaths) -> AnalysisResults:
    """Run every parts 3–4 calculation without writing artifacts.

    Args:
        paths: Standard input and output paths.

    Returns:
        Complete immutable result container.
    """
    repository = MarketRepository(paths.database)
    price_panel = repository.load_price_panel()
    returns = compute_log_returns(price_panel)
    stock_bond_correlations = compute_stock_bond_correlations(returns)
    correlation_summary = build_correlation_summary(
        returns, stock_bond_correlations
    )
    annual_correlation = build_annual_correlations(returns)
    stock_bond_period_summary = build_stock_bond_period_summary(
        stock_bond_correlations
    )
    event_stats, event_paths, event_daily = build_event_analysis(price_panel)
    return AnalysisResults(
        stock_bond_correlations=stock_bond_correlations,
        correlation_summary=correlation_summary,
        annual_correlation=annual_correlation,
        stock_bond_period_summary=stock_bond_period_summary,
        event_stats=event_stats,
        event_paths=event_paths,
        event_daily=event_daily,
    )


def build_figures(results: AnalysisResults) -> dict[str, go.Figure]:
    """Build the three core figures in report order.

    Args:
        results: Complete calculated analysis results.

    Returns:
        Ordered mapping from report figure id to Plotly figure.
    """
    return {
        "图3-1_股债120日滚动相关": create_stock_bond_correlation_figure(
            results.stock_bond_correlations,
            results.stock_bond_period_summary,
        ),
        "图3-2_分年度股债相关": create_stock_bond_annual_figure(
            results.annual_correlation,
            results.stock_bond_period_summary,
        ),
        "图4-1_2024脉冲行情_净值与单日收益": create_event_figure(
            results.event_paths,
            results.event_daily,
        ),
    }


def main() -> None:
    """Run parts 3–4 and write tables, figures, HTML and the report."""
    paths = AnalysisPaths.from_script()
    results = run_calculations(paths)
    figures = build_figures(results)

    write_result_tables(results, paths.output)
    write_report(results, paths.report / "模块2_第3-4部分_报告.md")
    write_combined_html(
        figures,
        paths.report.parent / "交互页面" / "模块2_第3-4部分_交互图.html",
    )
    export_static_figures(figures, paths.figures)

    print(f"结果表: {paths.output}")
    print(f"图表:   {paths.figures}")
    print(f"报告:   {paths.report / '模块2_第3-4部分_报告.md'}")


if __name__ == "__main__":
    main()
