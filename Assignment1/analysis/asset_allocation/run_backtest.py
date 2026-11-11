"""Module 4 主程序：串联数据、策略与回测引擎，输出绩效与图表。

运行方式（在项目根目录执行）：

    python Assignment1/analysis/asset_allocation/run_backtest.py

主流程：

1. 从 DuckDB 读取沪深 300 与上证国债指数日线并对齐；
2. 提取月末信号（信号日 + 次日调仓执行日）；
3. 对每个策略执行回测，得到逐日净值；
4. 将净值序列保存为 CSV 到 ``output/asset_allocation/``；
5. 打印绩效对比表；
6. 生成两张 Plotly 图保存到 ``figures/module4/``。
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

from backtester import Backtester, compute_metrics
from data_loader import AssetAllocationDataLoader
from strategies import (
    AllBondStrategy,
    AllStockStrategy,
    RiskParityStrategy,
    RollingMinimumVarianceStrategy,
    SixtyFortyStrategy,
    Strategy,
    TargetDateStrategy,
    VolatilityTargetStrategy,
)

# 路径自动寻址：本文件位于 Assignment1/analysis/asset_allocation/ 下，
# 向上两级（parents[2]）即为 Assignment1 目录。
ASSIGNMENT_DIR: Path = Path(__file__).resolve().parents[2]
OUTPUT_DIR: Path = ASSIGNMENT_DIR / "output" / "asset_allocation"
FIGURES_DIR: Path = ASSIGNMENT_DIR / "figures" / "module4"

# 报告区间起点：2018 年数据用于动态策略的滚动窗口预热，
# 绩效与净值展示从 2019-01-01 开始。
REPORT_START_DATE: str = "2019-01-01"

# 绩效表列名（用于格式化打印）。
METRIC_LABELS: dict[str, str] = {
    "年化收益率": "年化收益率",
    "年化波动率": "年化波动率",
    "夏普比率": "夏普比率",
    "最大回撤": "最大回撤",
    "Calmar比率": "Calmar比率",
    "月度胜率": "月度胜率",
}
PERCENT_METRICS: frozenset[str] = frozenset(
    {"年化收益率", "年化波动率", "最大回撤", "月度胜率"}
)
STRATEGY_DISPLAY_NAMES: dict[str, str] = {
    "AllStock": "全股",
    "AllBond": "全债",
    "SixtyForty": "60/40",
    "RiskParity": "风险平价",
    "RollingMinVariance": "最小方差",
    "VolatilityTarget": "波动率目标",
    "TargetDate": "目标日期",
}


def build_strategies() -> list[Strategy]:
    """构建本次回测的全部配置策略。

    基准拆分为 ``AllStock``（100% 股票）与 ``AllBond``（100% 债券）
    两条曲线，加上 60/40、风险平价、滚动最小方差、波动率目标和
    目标日期五个配置策略，共 7 条净值曲线。

    Returns:
        策略实例列表。
    """
    return [
        AllStockStrategy(),
        AllBondStrategy(),
        SixtyFortyStrategy(),
        RiskParityStrategy(),
        RollingMinimumVarianceStrategy(),
        VolatilityTargetStrategy(),
        TargetDateStrategy(start_date=REPORT_START_DATE),
    ]


def format_metrics_table(
    results: list[tuple[str, pd.DataFrame, dict[str, float]]],
) -> pd.DataFrame:
    """将各策略绩效指标整理为 DataFrame，并对百分比指标格式化。

    Args:
        results: ``(策略名, 净值表, 指标字典)`` 的列表。

    Returns:
        以策略名为索引、指标为列的 DataFrame。
    """
    records: dict[str, dict[str, float]] = {}
    for name, _, metrics in results:
        records[name] = metrics
    table = pd.DataFrame.from_dict(records, orient="index")
    return table[METRIC_LABELS.keys()]


def print_metrics_table(table: pd.DataFrame) -> None:
    """格式化打印绩效对比表。

    Args:
        table: 以策略名为索引的绩效 DataFrame。
    """
    display = table.copy()
    for col in display.columns:
        if col in PERCENT_METRICS:
            display[col] = (display[col] * 100).round(2).astype(str) + "%"
        else:
            display[col] = display[col].round(3)
    print("=" * 72)
    print("策略绩效对比表")
    print("=" * 72)
    print(display.to_string())
    print()


def plot_nav_comparison(
    results: list[tuple[str, pd.DataFrame, dict[str, float]]],
) -> None:
    """绘制并保存各策略的对数坐标净值曲线对比图。

    Args:
        results: ``(策略名, 净值表, 指标字典)`` 的列表。
    """
    fig = go.Figure()
    for name, nav, _ in results:
        fig.add_trace(
            go.Scatter(
                x=nav["trade_date"],
                y=nav["nav"],
                mode="lines",
                name=STRATEGY_DISPLAY_NAMES.get(name, name),
            )
        )
    fig.update_layout(
        title="股债配置策略净值对比（对数坐标）",
        xaxis_title="日期",
        yaxis_title="净值（对数坐标）",
        yaxis_type="log",
        template="plotly_white",
        legend=dict(
            orientation="v",
            yanchor="top",
            y=1,
            xanchor="left",
            x=1.01,
            font=dict(size=11),
        ),
        margin=dict(l=60, r=175, t=60, b=40),
    )
    path = FIGURES_DIR / "nav_comparison.html"
    fig.write_html(path)
    print(f"已保存净值对比图: {path}")


def plot_drawdown_comparison(
    results: list[tuple[str, pd.DataFrame, dict[str, float]]],
) -> None:
    """绘制并保存各策略的回撤阴影对比图。

    Args:
        results: ``(策略名, 净值表, 指标字典)`` 的列表。
    """
    fig = go.Figure()
    for name, nav, _ in results:
        drawdown = nav["nav"] / nav["nav"].cummax() - 1.0
        fig.add_trace(
            go.Scatter(
                x=nav["trade_date"],
                y=drawdown,
                mode="lines",
                name=STRATEGY_DISPLAY_NAMES.get(name, name),
                fill="tozeroy",
            )
        )
    fig.update_layout(
        title="股债配置策略回撤阴影对比",
        xaxis_title="日期",
        yaxis_title="回撤幅度",
        yaxis_tickformat=".0%",
        template="plotly_white",
        legend=dict(
            orientation="v",
            yanchor="top",
            y=1,
            xanchor="left",
            x=1.01,
            font=dict(size=11),
        ),
        margin=dict(l=60, r=175, t=60, b=40),
    )
    path = FIGURES_DIR / "drawdown_comparison.html"
    fig.write_html(path)
    print(f"已保存回撤对比图: {path}")


def _run_strategy_nav(
    backtester: Backtester,
    prices: pd.DataFrame,
    strategy: Strategy,
    signals: pd.DataFrame,
) -> pd.DataFrame:
    """运行单个策略并返回过滤到报告区间、归一化后的净值表。

    Args:
        backtester: 回测引擎实例。
        prices: 对齐后的价格表。
        strategy: 配置策略。
        signals: 调仓信号表。

    Returns:
        归一化（净值从 1.0 起）后的逐日净值表。
    """
    nav = backtester.run(prices, strategy, signals)
    nav = nav[
        nav["trade_date"] >= pd.Timestamp(REPORT_START_DATE)
    ].reset_index(drop=True)
    nav["nav"] = nav["nav"] / nav["nav"].iloc[0]
    return nav


def run_robustness_checks(
    loader: AssetAllocationDataLoader,
    prices: pd.DataFrame,
    monthly_signals: pd.DataFrame,
) -> pd.DataFrame:
    """稳健性检验：调仓频率对比与股票代理对比。

    Args:
        loader: 数据读取器。
        prices: 沪深300 与上证国债指数对齐价格。
        monthly_signals: 月末调仓信号。

    Returns:
        含 ``section``、``strategy``、``variant`` 及绩效指标的 DataFrame。
    """
    rows: list[dict[str, object]] = []
    backtester = Backtester()
    quarterly_signals = loader.extract_quarter_end_signals(prices)

    # (1) 调仓频率：月度 vs 季度（固定配置与动态风险策略）。
    frequency_strategies: tuple[Strategy, ...] = (
        SixtyFortyStrategy(),
        RiskParityStrategy(),
        RollingMinimumVarianceStrategy(),
        VolatilityTargetStrategy(),
    )
    for strategy in frequency_strategies:
        for label, sig in (("月度", monthly_signals), ("季度", quarterly_signals)):
            nav = _run_strategy_nav(backtester, prices, strategy, sig)
            rows.append(
                {
                    "section": "调仓频率",
                    "strategy": strategy.name,
                    "variant": label,
                    **compute_metrics(nav),
                }
            )

    # (2) 股票代理：沪深300 vs 上证综指（60/40）。
    sse_prices = loader.load_aligned_prices(equity_asset_id="SSE_COMPOSITE")
    sse_signals = loader.extract_month_end_signals(sse_prices)
    for label, p, s in (
        ("沪深300(CSI300)", prices, monthly_signals),
        ("上证综指(SSE_COMPOSITE)", sse_prices, sse_signals),
    ):
        nav = _run_strategy_nav(backtester, p, SixtyFortyStrategy(), s)
        rows.append(
            {
                "section": "股票代理",
                "strategy": "SixtyForty",
                "variant": label,
                **compute_metrics(nav),
            }
        )

    return pd.DataFrame(rows)


def run_cost_sensitivity(
    prices: pd.DataFrame,
    signals: pd.DataFrame,
    cost_rates_bp: tuple[int, ...] = (0, 10, 30),
) -> pd.DataFrame:
    """交易成本敏感性：不同单边成本下的年化收益。

    Args:
        prices: 对齐后的价格表。
        signals: 月末调仓信号。
        cost_rates_bp: 单边成本档位（bp），默认 0/10/30。

    Returns:
        含 ``section``、``strategy``、``cost_bp`` 及绩效指标的 DataFrame。
    """
    rows: list[dict[str, object]] = []
    for cost_bp in cost_rates_bp:
        backtester = Backtester(cost_rate=cost_bp / 10000.0)
        for strategy in build_strategies():
            nav = _run_strategy_nav(backtester, prices, strategy, signals)
            rows.append(
                {
                    "section": "成本敏感性",
                    "strategy": strategy.name,
                    "variant": f"单边{cost_bp}bp",
                    "cost_bp": cost_bp,
                    **compute_metrics(nav),
                }
            )
    return pd.DataFrame(rows)


def print_robustness_table(robustness: pd.DataFrame) -> None:
    """格式化打印稳健性检验结果。

    Args:
        robustness: ``run_robustness_checks`` 返回的 DataFrame。
    """
    display = robustness.copy()
    for col in PERCENT_METRICS:
        display[col] = (display[col] * 100).round(2).astype(str) + "%"
    display["夏普比率"] = display["夏普比率"].round(3)
    display["Calmar比率"] = display["Calmar比率"].round(3)
    cols = ["section", "strategy", "variant", *METRIC_LABELS.keys()]
    print("=" * 72)
    print("稳健性检验结果")
    print("=" * 72)
    print(display[cols].to_string(index=False))
    print()


def print_cost_sensitivity_table(sensitivity: pd.DataFrame) -> None:
    """格式化打印交易成本敏感性对比表。

    Args:
        sensitivity: ``run_cost_sensitivity`` 返回的 DataFrame。
    """
    pivot = sensitivity.pivot_table(
        index="strategy", columns="cost_bp", values="年化收益率", aggfunc="first"
    )
    pivot.columns = [f"{int(c)}bp" for c in pivot.columns]
    pivot["10bp损耗(bp)"] = ((pivot["0bp"] - pivot["10bp"]) * 10000).round(1)
    pivot["30bp损耗(bp)"] = ((pivot["0bp"] - pivot["30bp"]) * 10000).round(1)
    for c in ("0bp", "10bp", "30bp"):
        pivot[c] = (pivot[c] * 100).round(2)
    print("=" * 72)
    print("交易成本敏感性：年化收益率(%) 与 相对0bp损耗(bp)")
    print("=" * 72)
    print(pivot.to_string())
    print()


def save_robustness_results(
    robustness: pd.DataFrame,
    sensitivity: pd.DataFrame,
) -> None:
    """将稳健性与敏感性结果合并保存为 CSV。

    Args:
        robustness: 稳健性检验 DataFrame。
        sensitivity: 成本敏感性 DataFrame。
    """
    combined = pd.concat([robustness, sensitivity], ignore_index=True)
    cols = ["section", "strategy", "variant", "cost_bp", *METRIC_LABELS.keys()]
    combined = combined.reindex(columns=cols)
    path = OUTPUT_DIR / "robustness_results.csv"
    combined.to_csv(path, index=False)
    print(f"已保存稳健性/敏感性结果 CSV: {path}")


def main() -> None:
    """执行模块 4 回测主流程。"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 72)
    print("模块 4：股债配置与回测")
    print("=" * 72)

    # 1) 数据读取与对齐。
    loader = AssetAllocationDataLoader()
    prices = loader.load_aligned_prices()
    signals = loader.extract_month_end_signals(prices)
    print(f"对齐后交易日数: {len(prices)}")
    print(f"月末信号数: {len(signals)}")

    # 2) 逐策略回测。
    backtester = Backtester()
    results: list[tuple[str, pd.DataFrame, dict[str, float]]] = []
    for strategy in build_strategies():
        nav = backtester.run(prices, strategy, signals)
        # 过滤到报告区间并归一化（净值从 1.0 起）。
        nav = nav[
            nav["trade_date"] >= pd.Timestamp(REPORT_START_DATE)
        ].reset_index(drop=True)
        nav["nav"] = nav["nav"] / nav["nav"].iloc[0]
        metrics = compute_metrics(nav)
        results.append((strategy.name, nav, metrics))

        csv_path = OUTPUT_DIR / f"nav_{strategy.name}.csv"
        nav.to_csv(csv_path, index=False)
        print(f"已保存净值 CSV: {csv_path}")

    # 3) 打印绩效对比表。
    table = format_metrics_table(results)
    print_metrics_table(table)

    # 4) 生成图表。
    plot_nav_comparison(results)
    plot_drawdown_comparison(results)

    # 5) 稳健性检验。
    robustness = run_robustness_checks(loader, prices, signals)
    print_robustness_table(robustness)

    # 6) 交易成本敏感性分析。
    sensitivity = run_cost_sensitivity(prices, signals)
    print_cost_sensitivity_table(sensitivity)

    # 7) 保存稳健性/敏感性结果。
    save_robustness_results(robustness, sensitivity)

    print("=" * 72)
    print("模块 4 回测完成")
    print("=" * 72)


if __name__ == "__main__":
    main()
