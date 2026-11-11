"""Plotly charts for parts 3–4 and the consolidated offline HTML export."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from plotly.subplots import make_subplots

from config import (
    ASSET_COLORS,
    MAIN_STOCK_BOND_PAIR,
    PORTFOLIO_ASSET_ID,
    PORTFOLIO_NAME,
    STABILITY_END_DATE,
    STABILITY_START_DATE,
    STOCK_BOND_PAIRS,
    pair_id,
    pair_label,
)


def create_stock_bond_correlation_figure(
    stock_bond_correlations: pd.DataFrame,
    period_summary: pd.DataFrame,
) -> go.Figure:
    """Plot 120-day rolling stock-bond correlations.

    The Shanghai treasury index is the main pair; the enterprise bond index
    is shown as a supplementary comparison. The 2022–2024 window carries the
    period mean and negative share so the stability question is answered on
    the chart itself.

    Args:
        stock_bond_correlations: Long rolling-correlation table.
        period_summary: 2022–2024 rolling-correlation statistics per pair.

    Returns:
        Interactive line chart with the 2022–2024 window highlighted.
    """
    main_period = period_summary.set_index("pair_id").loc[
        pair_id(*MAIN_STOCK_BOND_PAIR)
    ]
    figure = go.Figure()
    for asset_a, asset_b in STOCK_BOND_PAIRS:
        subset = stock_bond_correlations.loc[
            stock_bond_correlations["pair_id"] == pair_id(asset_a, asset_b)
        ]
        is_main = (asset_a, asset_b) == MAIN_STOCK_BOND_PAIR
        figure.add_trace(
            go.Scatter(
                x=subset["trade_date"],
                y=subset["correlation"],
                mode="lines",
                name=(
                    pair_label(asset_a, asset_b)
                    + ("（主结果）" if is_main else "（补充）")
                ),
                line={
                    "color": ASSET_COLORS[asset_b],
                    "width": 2.4 if is_main else 1.5,
                    "dash": "solid" if is_main else "dash",
                },
                hovertemplate="%{x|%Y-%m-%d}<br>相关系数%{y:.3f}<extra></extra>",
            )
        )
    figure.add_hline(
        y=0.0,
        line_color="black",
        line_width=1.0,
        annotation_text="零相关",
        annotation_position="bottom right",
    )
    figure.add_vrect(
        x0=STABILITY_START_DATE,
        x1=STABILITY_END_DATE,
        fillcolor="#9ca3af",
        opacity=0.16,
        line_width=0,
    )
    figure.add_annotation(
        x=STABILITY_START_DATE,
        y=0.02,
        yref="paper",
        text=(
            "2022—2024 股债跷跷板区间<br>"
            f"滚动相关均值 {main_period['mean_correlation']:.3f}，"
            f"负相关占比 {main_period['negative_share']:.0%}"
        ),
        showarrow=False,
        align="left",
        xanchor="left",
        yanchor="bottom",
        font={"size": 12, "color": "#374151"},
        bgcolor="rgba(255,255,255,0.75)",
    )
    figure.update_layout(
        title="股债120日滚动相关系数：沪深300与债券指数",
        template="plotly_white",
        xaxis_title="日期",
        yaxis_title="相关系数",
        legend={"orientation": "h", "y": 1.08},
        hovermode="x unified",
    )
    return figure


def create_stock_bond_annual_figure(
    annual_correlation: pd.DataFrame,
    period_summary: pd.DataFrame,
) -> go.Figure:
    """Plot calendar-year stock-bond correlations as bars.

    Highlighting 2022–2024 makes the stability test visual: a genuine
    "see-saw" would need bars of similar, clearly negative height.

    Args:
        annual_correlation: Calendar-year correlation table.
        period_summary: 2022–2024 rolling-correlation statistics per pair.

    Returns:
        Grouped bar chart with the window highlighted and labelled.
    """
    years = [int(year) for year in annual_correlation["year"]]
    labels = [str(year) for year in years]
    main_period = period_summary.set_index("pair_id").loc[
        pair_id(*MAIN_STOCK_BOND_PAIR)
    ]
    figure = go.Figure()
    for asset_a, asset_b in STOCK_BOND_PAIRS:
        column = pair_id(asset_a, asset_b) + "_correlation"
        values = annual_correlation[column]
        is_main = (asset_a, asset_b) == MAIN_STOCK_BOND_PAIR
        figure.add_trace(
            go.Bar(
                x=labels,
                y=values,
                name=(
                    pair_label(asset_a, asset_b)
                    + ("（主结果）" if is_main else "（补充）")
                ),
                marker={
                    "color": ASSET_COLORS[asset_b],
                    "line": {"color": "white", "width": 0.5},
                },
                text=[f"{value:+.2f}" for value in values],
                textposition="outside",
                textfont={"size": 10},
                hovertemplate="%{x} 年<br>相关系数%{y:.3f}<extra></extra>",
            )
        )
    # Shade the 2022–2024 categories in paper coordinates so the bars keep
    # their series colours and the legend stays truthful.
    window_positions = [
        index for index, year in enumerate(years) if year in (2022, 2023, 2024)
    ]
    if window_positions:
        left = (min(window_positions) - 0.5) / len(labels)
        right = (max(window_positions) + 0.5) / len(labels)
        figure.add_shape(
            type="rect",
            x0=left,
            x1=right,
            y0=0.0,
            y1=1.0,
            xref="paper",
            yref="paper",
            fillcolor="rgba(156,163,175,0.10)",
            line_width=0,
            layer="below",
        )
    figure.add_hline(
        y=0.0,
        line_color="black",
        line_width=1.0,
    )
    figure.add_hline(
        y=float(main_period["mean_correlation"]),
        line_dash="dash",
        line_color=ASSET_COLORS["SSE_TREASURY"],
        line_width=1.2,
        annotation_text=(
            f"2022—2024 滚动相关均值 {main_period['mean_correlation']:.3f}"
        ),
        annotation_position="top right",
    )
    figure.add_annotation(
        x=0.01,
        y=0.98,
        xref="paper",
        yref="paper",
        text=(
            "2022—2024：三年方向均为负，但 2022 年接近零、2024 年才明显，"
            "“稳定为负”只成立于方向而非强度"
        ),
        showarrow=False,
        align="left",
        xanchor="left",
        yanchor="top",
        font={"size": 11, "color": "#374151"},
        bgcolor="rgba(255,255,255,0.75)",
    )
    figure.update_layout(
        title="分年度股债相关系数：2022—2024 年“股债跷跷板”是否稳定",
        template="plotly_white",
        barmode="group",
        bargap=0.28,
        xaxis_title="年份",
        yaxis_title="相关系数",
        legend={"orientation": "h", "y": 1.06},
    )
    return figure


def create_event_figure(
    event_paths: pd.DataFrame,
    event_daily: pd.DataFrame,
) -> go.Figure:
    """Plot the 2024 pulse with rebased paths and single-day returns.

    The upper panel shows how the three objects compounded through the
    window; the lower panel exposes each session's move, which is what the
    assignment asks to quantify as "single-day volatility".

    Args:
        event_paths: Rebased net-value path table.
        event_daily: Long daily-return table for the same window.

    Returns:
        Two-panel interactive figure.
    """
    figure = make_subplots(
        rows=2,
        cols=1,
        row_heights=[0.62, 0.38],
        vertical_spacing=0.16,
        subplot_titles=(
            "基准化净值路径（2024-09-20 = 1）",
            "区间单日收益（7 个交易日）",
        ),
    )
    series_specs = (
        ("csi300_nav", "CSI300", "沪深300"),
        ("treasury_nav", "SSE_TREASURY", "上证国债指数"),
        ("portfolio_nav", PORTFOLIO_ASSET_ID, PORTFOLIO_NAME),
    )
    for column, asset_id, display_name in series_specs:
        cumulative = float(event_paths[column].iloc[-1] - 1.0)
        figure.add_trace(
            go.Scatter(
                x=event_paths["trade_date"],
                y=event_paths[column],
                mode="lines+markers",
                name=f"{display_name}（区间 {cumulative:+.1%}）",
                line={"color": ASSET_COLORS[asset_id], "width": 2.4},
                marker={"size": 7},
                hovertemplate="%{x|%Y-%m-%d}<br>净值%{y:.4f}<extra></extra>",
            ),
            row=1,
            col=1,
        )
        subset = event_daily.loc[event_daily["object_id"] == asset_id]
        figure.add_trace(
            go.Bar(
                x=subset["trade_date"].dt.strftime("%m-%d"),
                y=subset["daily_return"] * 100.0,
                name=display_name,
                marker_color=ASSET_COLORS[asset_id],
                showlegend=False,
                hovertemplate=(
                    f"{display_name}<br>%{{x}}<br>单日收益%{{y:.2f}}%<extra></extra>"
                ),
            ),
            row=2,
            col=1,
        )
    figure.add_vrect(
        x0="2024-10-01",
        x1="2024-10-07",
        fillcolor="#d1d5db",
        opacity=0.45,
        line_width=0,
        row=1,
        col=1,
    )
    figure.add_hline(y=1.0, line_dash="dot", line_color="#6b7280", row=1, col=1)
    figure.add_hline(y=0.0, line_width=1.0, line_color="black", row=2, col=1)
    session_labels = list(
        dict.fromkeys(event_daily["trade_date"].dt.strftime("%m-%d"))
    )
    figure.update_yaxes(title_text="净值（首日 = 1）", row=1, col=1)
    figure.update_yaxes(title_text="单日收益（%）", row=2, col=1)
    figure.update_xaxes(title_text="日期", tickformat="%m-%d", row=1, col=1)
    figure.update_xaxes(
        title_text="交易日",
        type="category",
        categoryorder="array",
        categoryarray=session_labels,
        row=2,
        col=1,
    )
    figure.update_layout(
        title="2024年9—10月脉冲行情：净值路径与单日波动",
        template="plotly_white",
        barmode="group",
        legend={
            "orientation": "h",
            "x": 0,
            "y": 1.12,
            "traceorder": "normal",
        },
        margin={"l": 80, "r": 45, "t": 125, "b": 75},
        hovermode="closest",
    )
    return figure


def export_static_figures(
    figures: dict[str, go.Figure],
    output_directory: Path,
    width: int = 1_300,
    height: int = 800,
) -> None:
    """Export every core figure as SVG (report) and PNG (slides/Word).

    Args:
        figures: Mapping from stable file stem to Plotly figure.
        output_directory: Existing or creatable destination directory.
        width: Pixel width of the raster export.
        height: Pixel height of the raster export.
    """
    output_directory.mkdir(parents=True, exist_ok=True)
    stems = list(figures)
    pio.write_images(
        fig=list(figures.values()),
        file=[output_directory / f"{stem}.svg" for stem in stems],
        width=width,
        height=height,
        scale=1,
    )
    pio.write_images(
        fig=list(figures.values()),
        file=[output_directory / f"{stem}.png" for stem in stems],
        width=width,
        height=height,
        scale=2,
    )


def write_combined_html(
    figures: dict[str, go.Figure],
    output_path: Path,
    title: str = "模块2 第3—4部分：股债相关性与2024脉冲行情",
) -> None:
    """Write all interactive figures to one self-contained offline HTML.

    Args:
        figures: Ordered mapping from section identifier to Plotly figure.
        output_path: Destination HTML path.
        title: Page title shown in the browser tab and heading.
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
  <title>{title}</title>
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
    <h1>{title}</h1>
    <p>图表可缩放、悬停查看，并可通过右上角工具栏下载。数据区间 2019-01-01 起，滚动窗口 120 个交易日。</p>
    {sections}
  </main>
</body>
</html>
"""
    output_path.write_text(document, encoding="utf-8")
