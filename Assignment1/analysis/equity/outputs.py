"""Write the parts 3–4 result tables and render the Markdown report."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

import pandas as pd

from config import (
    ANALYSIS_START_DATE,
    BOND_PORTFOLIO_WEIGHT,
    EQUITY_PORTFOLIO_WEIGHT,
    EVENT_END_DATE,
    EVENT_START_DATE,
    MAIN_STOCK_BOND_PAIR,
    ROLLING_CORR_WINDOW,
    STABILITY_END_DATE,
    STABILITY_START_DATE,
    AnalysisResults,
    pair_id,
)

FIGURE_STEMS: tuple[str, ...] = (
    "图3-1_股债120日滚动相关",
    "图3-2_分年度股债相关",
    "图4-1_2024脉冲行情_净值与单日收益",
)


def write_result_tables(results: AnalysisResults, output_directory: Path) -> None:
    """Write every parts 3–4 result table as UTF-8 CSV.

    Args:
        results: Complete calculated analysis results.
        output_directory: Existing or creatable destination directory.
    """
    output_directory.mkdir(parents=True, exist_ok=True)
    tables = {
        "表3-1_股债相关性汇总.csv": results.correlation_summary,
        "表3-2_分年度股债相关.csv": results.annual_correlation,
        "表3-3_2022-2024滚动相关统计.csv": results.stock_bond_period_summary,
        "表4-1_2024脉冲行情指标.csv": results.event_stats,
        "明细_股债120日滚动相关.csv": results.stock_bond_correlations,
        "明细_2024脉冲净值路径.csv": results.event_paths,
        "明细_2024脉冲逐日收益.csv": results.event_daily,
    }
    for filename, table in tables.items():
        table.to_csv(
            output_directory / filename,
            index=False,
            encoding="utf-8-sig",
        )


def _pct(value: float, digits: int = 2) -> str:
    """Format a decimal rate as a percentage string."""
    return f"{value * 100:.{digits}f}%"


def _signed_pct(value: float, digits: int = 2) -> str:
    """Format a decimal rate as a signed percentage string."""
    return f"{value * 100:+.{digits}f}%"


def _number(value: float, digits: int = 3) -> str:
    """Format a plain number with fixed decimals."""
    return f"{value:.{digits}f}"


def _date(value: object) -> str:
    """Format a timestamp-like value as an ISO date."""
    return pd.Timestamp(value).date().isoformat()


def _markdown_table(
    headers: Sequence[str],
    rows: Sequence[Sequence[object]],
    alignments: Sequence[str],
) -> str:
    """Render a GitHub-flavoured Markdown table.

    Args:
        headers: Column headers.
        rows: Pre-formatted cell values.
        alignments: One of ``"l"`` or ``"r"`` per column.

    Returns:
        Markdown table text without a trailing newline.
    """
    header_line = "| " + " | ".join(headers) + " |"
    divider = (
        "|"
        + "|".join("---:" if alignment == "r" else ":---" for alignment in alignments)
        + "|"
    )
    body = [
        "| " + " | ".join(str(cell) for cell in row) + " |" for row in rows
    ]
    return "\n".join([header_line, divider, *body])


def _summary_row(results: AnalysisResults, asset_a: str, asset_b: str) -> pd.Series:
    """Return the correlation-summary row for one pair."""
    subset = results.correlation_summary.loc[
        results.correlation_summary["pair_id"] == pair_id(asset_a, asset_b)
    ]
    if subset.empty:
        raise ValueError(
            f"Missing correlation summary for {pair_id(asset_a, asset_b)}."
        )
    return subset.iloc[0]


def _correlation_cell(value: float, observed_on: object) -> str:
    """Format one rolling correlation with the date it was observed."""
    return f"{_number(value, 3)}（{_date(observed_on)}）"


def write_report(results: AnalysisResults, output_path: Path) -> None:
    """Render the parts 3–4 Markdown report.

    Args:
        results: Complete calculated analysis results.
        output_path: Destination Markdown path.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sections = [
        _report_header(),
        _section_correlation(results),
        _section_event(results),
        _section_files(),
        _section_limitations(),
    ]
    output_path.write_text("\n\n".join(sections) + "\n", encoding="utf-8")


def _report_header() -> str:
    """Build the report title and the shared-definition paragraph."""
    return f"""# 模块2（第3—4部分）：股债相关性与2024年脉冲行情

数据全部通过 SQL 从课程数据库 `数据/data.duckdb` 读取，分析区间为 **{ANALYSIS_START_DATE} 起至数据库最新共同交易日**。日收益率定义为 $r_t=\\ln(P_t/P_{{t-1}})$；年化按每年 252 个交易日换算；两个资产的相关系数在共同交易日上计算，{ROLLING_CORR_WINDOW} 日滚动窗口只有在观测完整时才输出。本报告只包含模块2的第3、4部分。"""


def _section_correlation(results: AnalysisResults) -> str:
    """Build section 3 on the time-varying stock-bond correlation."""
    main = _summary_row(results, *MAIN_STOCK_BOND_PAIR)
    supplement = _summary_row(results, "CSI300", "SSE_ENTERPRISE_BOND")
    annual = results.annual_correlation
    treasury_column = pair_id(*MAIN_STOCK_BOND_PAIR) + "_correlation"
    enterprise_column = pair_id("CSI300", "SSE_ENTERPRISE_BOND") + "_correlation"

    summary_table = _markdown_table(
        [
            "资产对",
            "角色",
            "全样本相关",
            f"{ROLLING_CORR_WINDOW}日滚动期末",
            "滚动最低",
            "滚动最高",
            "负相关观测占比",
        ],
        [
            [
                str(row["pair_label"]),
                str(row["role"]),
                _number(row["full_sample_correlation"], 3),
                _number(row["latest_rolling_correlation"], 3),
                _correlation_cell(
                    row["minimum_rolling_correlation"], row["minimum_date"]
                ),
                _correlation_cell(
                    row["maximum_rolling_correlation"], row["maximum_date"]
                ),
                _pct(row["negative_share"], 1),
            ]
            for _, row in results.correlation_summary.iterrows()
        ],
        ["l", "l", "r", "r", "r", "r", "r"],
    )

    annual_rows = [
        [
            f"{int(row['year'])}",
            f"{int(row['common_observations'])}",
            _number(row[treasury_column], 3),
            _number(row[enterprise_column], 3),
        ]
        for _, row in annual.iterrows()
    ]
    annual_table = _markdown_table(
        ["年份", "共同交易日", "沪深300—上证国债", "沪深300—上证企债"],
        annual_rows,
        ["l", "r", "r", "r"],
    )

    period_summary = results.stock_bond_period_summary
    main_period = period_summary.set_index("pair_id").loc[
        pair_id(*MAIN_STOCK_BOND_PAIR)
    ]
    period_table = _markdown_table(
        [
            "资产对",
            "角色",
            "滚动观测数",
            "均值",
            "最低",
            "最高",
            "负相关占比",
            "低于 -0.10 占比",
        ],
        [
            [
                str(row["pair_label"]),
                str(row["role"]),
                f"{int(row['rolling_observations'])}",
                _number(row["mean_correlation"], 3),
                _number(row["minimum_correlation"], 3),
                _number(row["maximum_correlation"], 3),
                _pct(row["negative_share"], 1),
                _pct(row["strongly_negative_share"], 1),
            ]
            for _, row in period_summary.iterrows()
        ],
        ["l", "l", "r", "r", "r", "r", "r", "r"],
    )

    recent_values = {
        year: float(annual.loc[annual["year"] == year, treasury_column].iloc[0])
        for year in (2022, 2023, 2024)
    }
    closest_to_zero_year = min(
        recent_values, key=lambda year: abs(recent_values[year])
    )
    most_negative_year = min(recent_values, key=lambda year: recent_values[year])
    latest_year = annual.iloc[-1]
    latest_correlation = float(latest_year[treasury_column])

    return f"""## 3. 股债相关性时变

**表 3-1　股债相关性汇总（120 日滚动）**

{summary_table}

**表 3-2　分年度股债相关系数**

{annual_table}

**表 3-3　2022—2024 年 120 日滚动股债相关统计**

{period_table}

**图 3-1　股债120日滚动相关系数（2022—2024 区间已标注）**

![股债120日滚动相关系数](../图表/图3-1_股债120日滚动相关.svg)

**图 3-2　分年度股债相关系数与 2022—2024 稳定性检验**

![分年度股债相关系数](../图表/图3-2_分年度股债相关.svg)

**结果说明什么：** 主结果（沪深300—上证国债指数）全样本相关系数为 {_number(main['full_sample_correlation'], 3)}，{ROLLING_CORR_WINDOW} 日滚动值的期末值为 {_number(main['latest_rolling_correlation'], 3)}，区间内在 {_number(main['minimum_rolling_correlation'], 3)}（{_date(main['minimum_date'])}）与 {_number(main['maximum_rolling_correlation'], 3)}（{_date(main['maximum_date'])}）之间变动，{_pct(main['negative_share'], 1)} 的滚动观测为负，说明负相关是常态但绝非必然。补充结果（沪深300—上证企债指数）全样本仅 {_number(supplement['full_sample_correlation'], 3)}，负相关占比 {_pct(supplement['negative_share'], 1)}，明显弱于国债，说明“股债跷跷板”主要来自无风险利率与避险需求，而不是信用债。

把 2022—2024 单独看，主结果滚动相关均值为 {_number(main_period['mean_correlation'], 3)}，负相关观测占 {_pct(main_period['negative_share'], 1)}，其中 {_pct(main_period['strongly_negative_share'], 1)} 低于 -0.10；但区间内也曾出现 {_number(main_period['maximum_correlation'], 3)}（{_date(main_period['maximum_date'])}）的正相关与 {_number(main_period['minimum_correlation'], 3)}（{_date(main_period['minimum_date'])}）的深度负相关，跨度达 {_number(main_period['maximum_correlation'] - main_period['minimum_correlation'], 3)}。结合分年度系数，{closest_to_zero_year} 年最接近零（{_number(recent_values[closest_to_zero_year], 3)}）、{most_negative_year} 年最负（{_number(recent_values[most_negative_year], 3)}），说明这三年“股债跷跷板”的特征是**方向总体为负但强度不稳定**：2022 年几乎消失、2023 年显现、2024 年才显著加深。若按 2024 年的强度外推 2022—2023 年的对冲效果，会高估债券的分散能力。

分年度看，样本末端的符号已经翻转：2025 年为 {_number(float(annual.loc[annual['year'] == 2025, treasury_column].iloc[0]), 3)}，而 {int(latest_year['year'])} 年至今为 {_number(latest_correlation, 3)}（仅 {int(latest_year['common_observations'])} 个交易日，为年内部分样本）。这说明“股债跷跷板”不是长期常数，2024—2025 年的强负相关不能直接外推为配置前提。

**对资产配置有何影响：** 60/40 组合的方差为 $\\sigma_p^2=w_s^2\\sigma_s^2+w_b^2\\sigma_b^2+2w_sw_b\\rho\\sigma_s\\sigma_b$。当 $\\rho<0$ 时交叉项为负，债券既降波动又提供对冲；当 $\\rho$ 转正（如 {_date(main['last_rolling_date'])} 的滚动值为 {_number(main['latest_rolling_correlation'], 3)}），交叉项变正，60/40 的分散效果被削弱，组合波动会高于按历史负相关估计的水平。因此不能用“股债永远负相关”作为 60/40 的风险假设，配置模型应使用滚动相关或情景相关，并在相关性转正时主动下调权益敞口或引入第三个低相关资产。"""


def _section_event(results: AnalysisResults) -> str:
    """Build section 4 on the 2024 equity pulse."""
    event = results.event_stats.set_index("object_id")
    equity = event.loc["CSI300"]
    bond = event.loc["SSE_TREASURY"]
    portfolio = event.loc["PORTFOLIO_60_40"]
    daily = results.event_paths["portfolio_daily_return"].dropna()
    equity_daily = results.event_daily.loc[
        results.event_daily["object_id"] == "CSI300", "daily_return"
    ]
    bond_daily = results.event_daily.loc[
        results.event_daily["object_id"] == "SSE_TREASURY", "daily_return"
    ]
    best_day_position = daily.idxmax()
    best_day_return = float(daily.max())
    best_day_date = _date(results.event_paths.loc[best_day_position, "trade_date"])
    single_day_share = best_day_return / float(portfolio["cumulative_return"])
    retained = float(portfolio["cumulative_return"]) / float(
        equity["cumulative_return"]
    )
    volatility_reduction = 1.0 - float(
        portfolio["annualized_volatility"]
    ) / float(equity["annualized_volatility"])
    down_days = int((daily < 0).sum())
    down_day_text = (
        "组合的 7 个区间日收益没有一天为负，"
        if down_days == 0
        else f"组合的 7 个区间日收益中有 {down_days} 天为负，"
    )

    stat_rows = [
        [
            str(row["object_name"]),
            f"{int(row['trading_days'])}",
            _pct(row["cumulative_return"], 2),
            f"{row['max_daily_gain'] * 100:+.2f}%（{_date(row['max_daily_gain_date'])}）",
            f"{row['max_daily_loss'] * 100:+.2f}%（{_date(row['max_daily_loss_date'])}）",
            _pct(row["daily_volatility"], 3),
            _pct(row["annualized_volatility"], 2),
            _pct(row["max_drawdown"], 2),
        ]
        for _, row in results.event_stats.iterrows()
    ]
    stat_table = _markdown_table(
        [
            "对象",
            "区间交易日",
            "区间累计收益",
            "最强单日",
            "最弱单日",
            "区间日波动率",
            "年化波动率",
            "区间最大回撤",
        ],
        stat_rows,
        ["l", "r", "r", "r", "r", "r", "r", "r"],
    )

    return f"""## 4. 极端行情案例：2024-09-20 至 2024-10-08

**表 4-1　2024 年脉冲行情区间指标（8 个交易日，7 个日收益）**

{stat_table}

**图 4-1　2024 年脉冲行情：基准化净值路径（上）与单日收益（下）**

![2024年脉冲行情净值路径与单日收益](../图表/图4-1_2024脉冲行情_净值与单日收益.svg)

**结果说明什么：** 8 个交易日内沪深300 累计上涨 {_pct(equity['cumulative_return'], 2)}，单日最大涨幅 {_pct(equity['max_daily_gain'], 2)}（{_date(equity['max_daily_gain_date'])}），区间日波动率 {_pct(equity['daily_volatility'], 3)}，折年 {_pct(equity['annualized_volatility'], 2)}，远高于权益资产的常态波动水平。同期上证国债指数下跌 {_pct(abs(float(bond['cumulative_return'])), 2)}，几乎没有提供对冲。60/40 组合（首日 60% 股票 + 40% 债券，区间内不再平衡）累计上涨 {_pct(portfolio['cumulative_return'], 2)}，保留了股票涨幅的 {_pct(retained, 1)}，年化波动率 {_pct(portfolio['annualized_volatility'], 2)}，比纯股票低 {_pct(volatility_reduction, 1)}；{down_day_text}组合的最大回撤为 {_pct(portfolio['max_drawdown'], 2)}，因为行情全程单边向上。

图 4-1 下半栏逐日拆开了这 7 个交易日：沪深300 的单日涨幅介于 {_signed_pct(equity_daily.min())} 与 {_signed_pct(equity_daily.max())} 之间、日均 {_signed_pct(equity_daily.mean())}；上证国债指数介于 {_signed_pct(bond_daily.min())} 与 {_signed_pct(bond_daily.max())}；60/40 组合介于 {_signed_pct(daily.min())} 与 {_signed_pct(daily.max())}、日均 {_signed_pct(daily.mean())}。收益高度集中在少数交易日：{_date(best_day_date)} 一天，组合就上涨 {_pct(best_day_return, 2)}，占整个区间累计收益 {_pct(portfolio['cumulative_return'], 2)} 的 {_pct(single_day_share, 1)}。

**对资产配置有何影响：** 60/40 在这次冲击中“缓冲有效、对冲失效”：债券在权益暴涨时小幅回撤，把组合收益压到纯股票的六成，波动率同步下降约四成，说明机械式 60/40 承受住了单边行情，但它的保护来自“少亏”而不是“反向”。这提醒两点：一是 60/40 的稳健性依赖债性资产的低波动，而不是负相关，一旦债券也进入高波动阶段，缓冲会迅速变薄；二是任何基于历史波动率的风险预算在这种行情里都会严重滞后，配置规则需要预设“行情突变”情景，而不是只依赖历史波动率。"""


def _section_files() -> str:
    """Build the deliverable inventory section."""
    table = _markdown_table(
        ["文件", "内容"],
        [
            ["`图3-1_股债120日滚动相关.svg/.png`", "图 3-1，120 日滚动相关系数"],
            ["`图3-2_分年度股债相关.svg/.png`", "图 3-2，分年度系数与稳定性检验"],
            ["`图4-1_2024脉冲行情_净值与单日收益.svg/.png`", "图 4-1，净值路径与单日收益"],
            ["`表3-1_股债相关性汇总.csv`", "表 3-1，全样本/期末/极值/负相关占比"],
            ["`表3-2_分年度股债相关.csv`", "表 3-2，逐年相关系数"],
            ["`表3-3_2022-2024滚动相关统计.csv`", "表 3-3，区间均值与负相关结构"],
            ["`表4-1_2024脉冲行情指标.csv`", "表 4-1，区间收益与波动指标"],
            ["`明细_*.csv`", "三张明细表（滚动相关序列、净值路径、逐日收益）"],
        ],
        ["l", "l"],
    )
    return f"""## 5. 提交文件清单

{table}"""


def _section_limitations() -> str:
    """Build the definitions and limitations section."""
    return f"""## 6. 口径说明与局限

- 收益率为价格指数的对数收益，不含成分股分红；这一处理对相关系数和区间比较没有方向性影响。
- {EVENT_START_DATE} 至 {EVENT_END_DATE} 共 8 个交易日，区间内日波动率与逐日收益基于首日之后的 7 个日收益计算，首日只作为净值基点。
- 60/40 组合在区间首日按 {int(EQUITY_PORTFOLIO_WEIGHT * 100)}% 股票、{int(BOND_PORTFOLIO_WEIGHT * 100)}% 债券建仓，区间内不再平衡，权重会随行情漂移。
- 滚动相关使用共同交易日样本，缺失日不填充，窗口内观测不足时不输出数值。
- 2022—2024 区间为 {STABILITY_START_DATE} 至 {STABILITY_END_DATE}；区间统计基于滚动序列，而表 3-2 的分年度系数基于当年日收益，两者口径不同、数值不可直接比较。
- 2026 年数据为年内部分样本，相关性的“翻转”结论只代表样本末端的状态。"""
