"""Plotly chart construction and consolidated HTML export."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from plotly.subplots import make_subplots

from config import (
    BOND_ASSETS,
    BOND_COLORS,
    CURVE_GRID_POINTS,
    NelsonSiegelFit,
    SCENARIOS,
    YieldPcaResults,
)
from curve import nelson_siegel_yield


def create_curve_figure(
    curve: pd.DataFrame,
    curve_fit: NelsonSiegelFit,
    curve_results: pd.DataFrame,
) -> go.Figure:
    """Plot observed and fitted yields with residuals beneath.

    Args:
        curve: Observed latest curve.
        curve_fit: Selected Nelson–Siegel fit.
        curve_results: Pointwise residual table.

    Returns:
        Interactive Plotly figure.
    """
    tenor_grid = np.linspace(
        float(curve["tenor_years"].min()),
        float(curve["tenor_years"].max()),
        CURVE_GRID_POINTS,
    )
    fitted_grid = nelson_siegel_yield(tenor_grid, curve_fit.parameters) * 100.0
    figure = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.10,
        row_heights=[0.70, 0.30],
    )
    figure.add_trace(
        go.Scatter(
            x=tenor_grid,
            y=fitted_grid,
            mode="lines",
            name="Nelson–Siegel拟合",
            line={"color": "#1f77b4", "width": 3},
        ),
        row=1,
        col=1,
    )
    figure.add_trace(
        go.Scatter(
            x=curve["tenor_years"],
            y=curve["yield_decimal"] * 100.0,
            mode="markers",
            name="实际期限点",
            marker={"color": "#d62728", "size": 10},
        ),
        row=1,
        col=1,
    )
    figure.add_trace(
        go.Bar(
            x=curve_results["tenor_years"],
            y=curve_results["residual_bp"],
            name="残差（实际−拟合）",
            marker_color="#7f7f7f",
        ),
        row=2,
        col=1,
    )
    figure.add_hline(y=0.0, line_color="black", line_width=1, row=2, col=1)
    figure.update_yaxes(title_text="收益率（%）", row=1, col=1)
    figure.update_yaxes(title_text="残差（bp）", row=2, col=1)
    figure.update_xaxes(title_text="期限（年）", row=2, col=1)
    curve_date = pd.Timestamp(curve["curve_date"].iloc[0]).date().isoformat()
    figure.update_layout(
        title=(
            "最新国债收益率曲线的Nelson–Siegel拟合"
            f"（{curve_date}）"
        ),
        template="plotly_white",
        legend={"orientation": "h", "y": 1.08},
        hovermode="x unified",
    )
    return figure


def create_stress_figure(stress_results: pd.DataFrame) -> go.Figure:
    """Plot approximation errors by stress scenario.

    Args:
        stress_results: Repricing and approximation results.

    Returns:
        Two-panel error heatmap.
    """
    figure = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=("仅久期近似", "久期+凸性近似"),
        horizontal_spacing=0.15,
    )
    tenors = sorted(stress_results["tenor_years"].unique())
    for column_index, error_column in enumerate(
        ("duration_error_bp", "duration_convexity_error_bp"),
        start=1,
    ):
        pivot = stress_results.pivot(
            index="scenario",
            columns="tenor_years",
            values=error_column,
        ).reindex(index=SCENARIOS.values(), columns=tenors)
        figure.add_trace(
            go.Heatmap(
                z=pivot.to_numpy(),
                x=[f"{tenor:g}年" for tenor in tenors],
                y=list(pivot.index),
                coloraxis="coloraxis",
                text=np.round(pivot.to_numpy(), 3),
                texttemplate="%{text:.3f}",
                hovertemplate=(
                    "期限=%{x}<br>情景=%{y}<br>"
                    "绝对误差=%{z:.4f} bp<extra></extra>"
                ),
            ),
            row=1,
            col=column_index,
        )
    figure.update_layout(
        title="利率压力测试：近似方法相对精确重定价的绝对误差",
        template="plotly_white",
        coloraxis={"colorscale": "YlOrRd", "colorbar_title": "误差（bp）"},
    )
    return figure


def create_regression_figure(
    regression_data: dict[str, pd.DataFrame],
    regression_results: pd.DataFrame,
) -> go.Figure:
    """Plot yield changes against bond returns and fitted lines.

    Args:
        regression_data: Per-asset aligned regression samples.
        regression_results: Newey–West regression summary.

    Returns:
        Three-panel regression scatter figure.
    """
    figure = make_subplots(
        rows=1,
        cols=3,
        subplot_titles=tuple(BOND_ASSETS.values()),
        horizontal_spacing=0.08,
    )
    for column_index, (asset_id, asset_name) in enumerate(
        BOND_ASSETS.items(),
        start=1,
    ):
        sample = regression_data[asset_id].sort_values("yield_change_10y")
        result = regression_results.loc[
            regression_results["asset_id"] == asset_id
        ].iloc[0]
        figure.add_trace(
            go.Scattergl(
                x=sample["yield_change_10y"] * 10_000.0,
                y=sample["bond_log_return"] * 100.0,
                mode="markers",
                name=asset_name,
                showlegend=False,
                marker={
                    "color": BOND_COLORS[asset_id],
                    "size": 5,
                    "opacity": 0.35,
                },
                hovertemplate=(
                    "10Y变动=%{x:.2f} bp<br>"
                    "日对数收益=%{y:.3f}%<extra></extra>"
                ),
            ),
            row=1,
            col=column_index,
        )
        figure.add_trace(
            go.Scatter(
                x=sample["yield_change_10y"] * 10_000.0,
                y=sample["fitted_return"] * 100.0,
                mode="lines",
                name="OLS回归线",
                showlegend=column_index == 1,
                line={"color": "black", "width": 2},
                hoverinfo="skip",
            ),
            row=1,
            col=column_index,
        )
        x_reference = f"x{column_index} domain" if column_index > 1 else "x domain"
        y_reference = f"y{column_index} domain" if column_index > 1 else "y domain"
        figure.add_annotation(
            x=0.02,
            y=0.98,
            xref=x_reference,
            yref=y_reference,
            text=(
                f"β={result['beta']:.3f}<br>"
                f"隐含久期={result['implied_rate_duration_years']:.3f}年<br>"
                f"R²={result['r_squared']:.3f}, "
                f"N={int(result['n_observations'])}"
            ),
            showarrow=False,
            align="left",
            bgcolor="rgba(255,255,255,0.80)",
        )
        figure.update_xaxes(
            title_text="10年期收益率日变动（bp）",
            row=1,
            col=column_index,
        )
    figure.update_yaxes(
        title_text="债券资产日对数收益（%）",
        row=1,
        col=1,
    )
    figure.update_layout(
        title="债券资产对10年期国债收益率变动的敏感度",
        template="plotly_white",
        legend={"orientation": "h", "y": 1.10},
    )
    return figure


def create_late_2024_figure(late_period: pd.DataFrame) -> go.Figure:
    """Plot the late-2024 10-year yield and cumulative bond returns.

    Args:
        late_period: Common-date late-2024 time series.

    Returns:
        Two-panel late-2024 figure.
    """
    figure = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.10,
        subplot_titles=("10年期国债收益率", "债券资产累计收益"),
    )
    figure.add_trace(
        go.Scatter(
            x=late_period["trade_date"],
            y=late_period["yield_10y_decimal"] * 100.0,
            mode="lines+markers",
            name="10年期国债收益率",
            line={"color": "#9467bd", "width": 2.5},
        ),
        row=1,
        col=1,
    )
    for asset_id, asset_name in BOND_ASSETS.items():
        figure.add_trace(
            go.Scatter(
                x=late_period["trade_date"],
                y=late_period[f"{asset_id}_cumulative_return"] * 100.0,
                mode="lines",
                name=asset_name,
                line={"color": BOND_COLORS[asset_id], "width": 2.5},
            ),
            row=2,
            col=1,
        )
    figure.add_hline(y=0.0, line_color="black", line_width=1, row=2, col=1)
    figure.update_yaxes(title_text="收益率（%）", row=1, col=1)
    figure.update_yaxes(title_text="累计收益（%）", row=2, col=1)
    figure.update_xaxes(title_text="日期", row=2, col=1)
    figure.update_layout(
        title="2024年末利率阶段（2024-11-01至2024-12-31）",
        template="plotly_white",
        legend={"orientation": "h", "y": 1.08},
        hovermode="x unified",
    )
    return figure


def create_realized_convexity_figure(attribution: pd.DataFrame) -> go.Figure:
    """Compare exact late-2024 repricing with two approximations.

    Args:
        attribution: One-row realized convexity attribution table.

    Returns:
        Bar chart of rate-driven ten-year zero-coupon returns.
    """
    row = attribution.iloc[0]
    labels = ["精确重定价", "仅久期", "久期+凸性"]
    values = [
        row["exact_rate_driven_return"] * 100.0,
        row["duration_return"] * 100.0,
        row["duration_convexity_return"] * 100.0,
    ]
    figure = go.Figure(
        go.Bar(
            x=labels,
            y=values,
            text=[f"{value:.3f}%" for value in values],
            textposition="outside",
            marker_color=["#1f77b4", "#ff7f0e", "#2ca02c"],
            hovertemplate="%{x}<br>价格变化=%{y:.4f}%<extra></extra>",
        )
    )
    figure.update_layout(
        title=(
            "2024年末实际利率下行的凸性归因："
            f"10年期收益率变动 {row['yield_change_bp']:.2f}bp"
        ),
        template="plotly_white",
        yaxis_title="10年零息债价格变化（%）",
        showlegend=False,
    )
    return figure


def create_rolling_duration_figure(rolling_duration: pd.DataFrame) -> go.Figure:
    """Plot 252-observation rolling implied rate durations.

    Args:
        rolling_duration: Long-form rolling regression results.

    Returns:
        Multi-asset rolling duration line chart.
    """
    figure = go.Figure()
    for asset_id, asset_name in BOND_ASSETS.items():
        asset_data = rolling_duration.loc[
            rolling_duration["asset_id"] == asset_id
        ]
        figure.add_trace(
            go.Scatter(
                x=asset_data["trade_date"],
                y=asset_data["implied_rate_duration_years"],
                mode="lines",
                name=asset_name,
                line={"color": BOND_COLORS[asset_id], "width": 2},
            )
        )
    figure.add_hline(y=0.0, line_color="black", line_width=1)
    figure.update_layout(
        title="252个共同观测滚动回归隐含利率久期",
        template="plotly_white",
        xaxis_title="日期",
        yaxis_title="隐含利率久期（年）",
        hovermode="x unified",
        legend={"orientation": "h", "y": 1.08},
    )
    return figure


def create_yield_pca_figure(pca_results: YieldPcaResults) -> go.Figure:
    """Plot PCA explained variance and yield-tenor factor loadings.

    Args:
        pca_results: Yield PCA diagnostics and regression outputs.

    Returns:
        Two-panel PCA diagnostic figure.
    """
    figure = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=("各主成分解释方差", "前三个主成分的期限载荷"),
        horizontal_spacing=0.14,
    )
    variance = pca_results.explained_variance
    figure.add_trace(
        go.Bar(
            x=variance["component"],
            y=variance["explained_variance_ratio"] * 100.0,
            text=(variance["explained_variance_ratio"] * 100.0).round(2),
            texttemplate="%{text:.2f}%",
            textposition="outside",
            name="解释方差",
            marker_color="#4c78a8",
        ),
        row=1,
        col=1,
    )
    factor_labels = {
        "level": "水平因子",
        "slope": "斜率因子",
        "curvature": "曲率因子",
    }
    for factor, color in zip(
        factor_labels,
        ("#1f77b4", "#ff7f0e", "#2ca02c"),
        strict=True,
    ):
        figure.add_trace(
            go.Scatter(
                x=pca_results.loadings["tenor_years"],
                y=pca_results.loadings[f"pc_{factor}_loading"],
                mode="lines+markers",
                name=factor_labels[factor],
                line={"color": color, "width": 2.5},
            ),
            row=1,
            col=2,
        )
    figure.add_hline(y=0.0, line_color="black", line_width=1, row=1, col=2)
    figure.update_yaxes(title_text="解释方差（%）", row=1, col=1)
    figure.update_xaxes(title_text="主成分", row=1, col=1)
    figure.update_yaxes(title_text="载荷", row=1, col=2)
    figure.update_xaxes(title_text="期限（年）", row=1, col=2)
    figure.update_layout(
        title="2/5/10/30年国债收益率日变动的主成分分析",
        template="plotly_white",
        legend={"orientation": "h", "y": 1.08},
    )
    return figure


def create_liability_matching_figure(
    strategies: pd.DataFrame,
    stress_results: pd.DataFrame,
) -> go.Figure:
    """Plot five-year liability duration gaps and stressed surplus changes.

    Args:
        strategies: Strategy risk metrics and duration gaps.
        stress_results: Asset-minus-liability returns under ±100bp shocks.

    Returns:
        Two-panel liability-matching comparison.
    """
    figure = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=("相对五年负债的久期缺口", "±100bp后的资产−负债变化"),
        horizontal_spacing=0.18,
    )
    figure.add_trace(
        go.Bar(
            x=strategies["strategy_name"],
            y=strategies["duration_gap_years"],
            name="久期缺口",
            marker_color="#4c78a8",
            text=strategies["duration_gap_years"].round(3),
            textposition="outside",
        ),
        row=1,
        col=1,
    )
    for shock, color in ((-100.0, "#2ca02c"), (100.0, "#d62728")):
        subset = stress_results.loc[stress_results["yield_shock_bp"] == shock]
        figure.add_trace(
            go.Bar(
                x=subset["strategy_name"],
                y=subset["surplus_return_gap"] * 100.0,
                name=f"{shock:+.0f}bp",
                marker_color=color,
            ),
            row=1,
            col=2,
        )
    figure.add_hline(y=0.0, line_color="black", line_width=1, row=1, col=1)
    figure.add_hline(y=0.0, line_color="black", line_width=1, row=1, col=2)
    figure.update_yaxes(title_text="修正久期缺口（年）", row=1, col=1)
    figure.update_yaxes(title_text="盈余变化（百分点）", row=1, col=2)
    figure.update_xaxes(tickangle=-20, row=1, col=1)
    figure.update_xaxes(tickangle=-20, row=1, col=2)
    figure.update_layout(
        title="面向五年到期资金的久期匹配与免疫效果",
        template="plotly_white",
        barmode="group",
        legend={"orientation": "h", "y": 1.08},
    )
    return figure


def export_static_figures(
    figures: dict[str, go.Figure],
    output_directory: Path,
) -> None:
    """Export report-ready SVG files for all core figures.

    Args:
        figures: Mapping from stable file stem to Plotly figure.
        output_directory: Existing or creatable destination directory.
    """
    output_directory.mkdir(parents=True, exist_ok=True)
    output_paths = [
        output_directory / f"{stem}.svg"
        for stem in figures
    ]
    # Batch export reuses one browser process and avoids repeated Kaleido startup.
    pio.write_images(
        fig=list(figures.values()),
        file=output_paths,
        width=1_300,
        height=800,
        scale=1,
    )


def write_combined_html(
    figures: dict[str, go.Figure],
    output_path: Path,
) -> None:
    """Write all interactive figures to one self-contained offline HTML.

    Args:
        figures: Ordered mapping from section identifier to Plotly figure.
        output_path: Destination HTML path.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fragments: list[str] = []
    for figure_index, figure in enumerate(figures.values()):
        fragments.append(
            pio.to_html(
                figure,
                full_html=False,
                include_plotlyjs=figure_index == 0,
                config={"responsive": True, "displaylogo": False},
            )
        )

    sections = "\n".join(
        f'<section class="chart-card">{fragment}</section>'
        for fragment in fragments
    )
    document = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Assignment 1 模块3：固定收益分析</title>
  <style>
    body {{ margin: 0; background: #f4f6f8; color: #1f2937;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI",
            "PingFang SC", sans-serif; }}
    main {{ max-width: 1400px; margin: 0 auto; padding: 32px 20px 56px; }}
    h1 {{ margin: 0 0 8px; }}
    p {{ margin: 0 0 24px; color: #4b5563; }}
    .chart-card {{ margin: 20px 0; padding: 12px; background: white;
                   border-radius: 12px; box-shadow: 0 2px 10px #00000012; }}
  </style>
</head>
<body>
  <main>
    <h1>模块3：固定收益分析</h1>
    <p>图表可缩放、悬停查看，并可通过右上角工具栏下载。</p>
    {sections}
  </main>
</body>
</html>
"""
    output_path.write_text(document, encoding="utf-8")
