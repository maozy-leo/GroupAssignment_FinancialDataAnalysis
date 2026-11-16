"""从稳健性 CSV 更新两份报告及项目 HTML 中的对应章节。

运行：python Assignment1/analysis/asset_allocation/robustness_report.py
更新配置回测、稳健性和讨论章节，保留其他分析模块与分工记录。
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from html import escape
import json
from pathlib import Path
import re

import pandas as pd

from robustness import OUTPUT_DIR, STRATEGY_NAMES


BASE_RESULT_NOTES: tuple[str, ...] = (
    "数值注 1：全债 Sharpe 5.889、风险平价 Sharpe 4.868 来自较低的价格指数波动。"
    "本报告使用几何年化收益除以对数收益年化波动率、无风险利率取 0；"
    "全债年化收益 4.21%、波动约 0.72%，因此比率很高。该口径不同于常见的日超额收益 Sharpe。",
    "数值注 2：波动率目标的实际年化波动为 10.10%，最大回撤 26.50% 略高于 60/40 的 26.30%。"
    "10% 是基于历史窗口的风险预算，不是对未来波动或回撤的硬约束；"
    "月度更新、下一交易日收盘执行及只缩减股票敞口的实现，均会使实际风险偏离目标。",
)


@dataclass(frozen=True)
class ReportSection:
    """三种报告格式共用的文字、表头和表格记录。"""

    title: str
    introduction: str
    columns: tuple[str, ...]
    rows: list[list[str]]
    interpretation: str
    notes: tuple[str, ...] = ()
    detail_columns: tuple[str, ...] = ()
    detail_rows: list[list[str]] = field(default_factory=list)


def value_range(values: pd.Series, is_percent: bool = True) -> str:
    """格式化情景指标范围。

    Args:
        values: 同一指标的一维数值序列。
        is_percent: 是否以百分比显示，否则保留三位小数。

    Returns:
        包含最小值和最大值的可读字符串。
    """
    if is_percent:
        return f"{values.min():.2%}—{values.max():.2%}"
    return f"{values.min():.3f}—{values.max():.3f}"


def strategy_range_rows(results: pd.DataFrame) -> list[list[str]]:
    """按默认策略顺序汇总不同资产组合的指标范围。

    Args:
        results: 包含 strategy 和收益、Sharpe、回撤指标的结果表。

    Returns:
        策略名称及三个指标范围组成的表格记录。
    """
    rows: list[list[str]] = []
    for strategy, name in STRATEGY_NAMES.items():
        subset = results[results["strategy"] == strategy]
        rows.append([
            name,
            value_range(subset["年化收益率"]),
            value_range(subset["夏普比率"], is_percent=False),
            value_range(subset["最大回撤"]),
        ])
    return rows


def build_sections(output_dir: Path) -> list[ReportSection]:
    """用实际试验结果构建方法、结果表与解释。

    Args:
        output_dir: 存放三类新增 CSV 与既有稳健性 CSV 的目录。

    Returns:
        参数、长短样本替换、信号日期、频率和成本六个报告单元。
    """
    parameters = pd.read_csv(output_dir / "parameter_sensitivity.csv")
    assets = pd.read_csv(output_dir / "asset_substitution_results.csv")
    timing = pd.read_csv(output_dir / "signal_timing_results.csv")
    existing = pd.read_csv(output_dir / "robustness_results.csv")
    parameter_rows: list[list[str]] = []
    for group, subset in parameters.groupby("group", sort=False):
        parameter_rows.append([
            group,
            " / ".join(subset["label"]),
            value_range(subset["年化收益率"]),
            value_range(subset["夏普比率"], is_percent=False),
            value_range(subset["最大回撤"]),
        ])
    sections = [ReportSection(
        title="参数敏感性",
        introduction=(
            "使用沪深 300＋上证国债指数，2019-01-02—2026-10-16 共 1,887 个价格交易日。"
            "预先列出九组、28 个情景，每次仅改变一个参数，其余保持默认；"
            "2018 年作预热，最长窗口取 240 日，正式期不因历史不足使用回退权重。"
            "下表为各组情景的指标范围，各列极值未必来自同一档参数。"
        ),
        columns=("改变参数", "试验档位", "年化收益范围", "Sharpe 范围", "最大回撤范围"),
        rows=parameter_rows,
        interpretation=(
            "最小方差的 60、120、240 日窗口结果在数值精度内一致；但股票下限从 0% 提至 30% 时，"
            "平均股票权重从 0.82% 升至 29.95%，最大回撤从 0.96% 升至 9.07%，"
            "Sharpe 从 6.296 降至 0.849。窗口不敏感主要反映仓位约束持续生效，不能据此认为协方差估计稳健。"
            "波动率目标的窗口从 30 日增至 120 日时，年化收益由 5.71% 降至 4.59%，"
            "说明动态信号具有明显参数依赖。目标日期三组邻近参数的年化收益均为 5.85%—6.48%，"
            "高于默认 60/40 的 5.00%；这支持本路径下的局部稳定性，仍未改变投资起点或市场顺序。"
            "这些参数用于检验敏感性，不据此回选默认参数。"
        ),
        notes=(
            "数值注：三个最小方差窗口在正式期的 94 个生效信号上，股票目标权重均为 20%。"
            "表中相同结果来自仓位下限持续约束，差别仅为浮点数精度。股票下限为 0% 时，"
            "年化波动约 0.69%，因此 Sharpe 可达 6.296；高比率同时伴随仅 4.35% 的年化收益。",
        ),
    )]
    sections.append(ReportSection(
        title="资产替换检验：长样本",
        introduction=(
            "股票取沪深 300、中证 500、上证综指，债券取上证国债、上证企债指数，形成 3×2＝6 组股债对。"
            "每组运行全部七类策略，共 42 个情景；共同日期、2018 年预热和 2019-01-02—2026-10-16 "
            "的 1,887 个价格交易日完全一致。每次仍只持有一股一债，替换检验没有扩大组合持仓数量。"
        ),
        columns=("策略", "年化收益范围", "Sharpe 范围", "最大回撤范围"),
        rows=strategy_range_rows(assets[assets["cohort"] == "长样本"]),
        interpretation=(
            "目标日期在六组中均为七类策略里年化收益最高者，收益为 5.82%—7.20%，"
            "其长样本领先不只存在于沪深 300＋国债这一组代理。"
            "但固定 60/40 的最大回撤为 13.74%—26.48%，绝对风险指标仍明显依赖股票代理。"
            "企债价格指数的低波动使全债 Sharpe 最高达到 16.825；这提示对价格口径和零无风险利率"
            "尤其敏感，不能直接据此认定实际企债投资具有相同风险调整收益。"
        ),
        notes=(
            "数值注：全债 Sharpe 的上限 16.825 对应上证企债指数，年化收益 4.34%、"
            "年化波动约 0.258%。比率由很小的波动分母放大，按现行口径复算一致；"
            "该统计值仅反映此价格序列，实际产品的信用利差、流动性及费用影响仍需单独核验。"
            "各列范围的极值也未必对应同一资产对。",
        ),
    ))
    sections.append(ReportSection(
        title="资产替换检验：短样本",
        introduction=(
            "在上述资产中再加入科创 50 与政金债 ETF，形成 4×3＝12 组股债对、84 个策略情景。"
            "全部组合统一使用 2024-01-02—2026-10-16 的 673 个价格交易日，"
            "共同预热价格从 2023-05-17 开始。目标日期策略同步从 2024 年起滑降，"
            "只覆盖五年路径的前段；不与长样本收益直接作高低判断。"
        ),
        columns=("策略", "年化收益范围", "Sharpe 范围", "最大回撤范围"),
        rows=strategy_range_rows(assets[assets["cohort"] == "短样本"]),
        interpretation=(
            "在五种股债配置策略之间，波动率目标在十二组短样本中均取得最高年化收益，"
            "取代长样本领先的目标日期；若把全股、全债也纳入排名，则波动率目标与全股各领先六组。"
            "短样本沪深 300＋国债中，波动率目标年化 9.39%，目标日期年化 7.83%。"
            "因此，资产代理替换下相对稳定的长样本排名，仍可能随市场阶段和滑降起点改变。"
            "长短样本同时改变了区间，不能把排名变化单独归因于新增资产。ETF 前复权价格与债券指数点位"
            "口径也有差异。十二组共享大量资产和交易日，并非十二个独立样本。"
        ),
        notes=(
            "数值注：短样本企债全债的年化收益为 3.98%，波动约 0.202%，Sharpe 因而达到 19.714；"
            "最大回撤未四舍五入为 0.0240%（表中 0.02%），Calmar 达到 165.455。"
            "这些数值由当前价格序列和指标口径计算得到，极小风险分母会放大比率，"
            "仍需以可交易全收益品种复核其经济含义。",
        ),
    ))
    timing_rows: list[list[str]] = []
    for strategy, name in STRATEGY_NAMES.items():
        if strategy in ("AllStock", "AllBond"):
            continue
        pair = timing[timing["strategy"] == strategy].set_index("timing")
        timing_rows.append([
            name,
            f"{pair.loc['月末', '年化收益率']:.2%}→{pair.loc['月中', '年化收益率']:.2%}",
            f"{pair.loc['月末', '夏普比率']:.3f}→{pair.loc['月中', '夏普比率']:.3f}",
            f"{pair.loc['月末', '最大回撤']:.2%}→{pair.loc['月中', '最大回撤']:.2%}",
        ])
    sections.append(ReportSection(
        title="信号日期检验",
        introduction=(
            "月中取每月 15 日或之前最近一个共同交易日，月末取最后一个交易日，"
            "均在信号收盘后计算权重、下一交易日收盘执行。为避免末月仅含月中信号，"
            "两组统一截至 2026-09-30，从 2019-01-02 起共 1,880 个价格交易日、各 93 个执行时点。"
            "七类策略均参与；全股、全债无有效调仓，两种日期的结果相同，下表列五种配置策略。"
        ),
        columns=("策略", "年化收益（月末→月中）", "Sharpe（月末→月中）", "最大回撤（月末→月中）"),
        rows=timing_rows,
        interpretation=(
            "波动率目标年化收益从 5.48% 降至 5.00%，相差 47.8bp，"
            "Sharpe 从 0.542 降至 0.493，最大回撤几乎不变；目标日期年化收益从 6.35% 降至 6.20%，"
            "相差 15.0bp。其他配置策略收益差为 4.1—16.4bp。"
            "相比之下，波动率目标对信号落在哪一天更敏感，收益改善并非只由风险预算决定。"
            "因截止日期不同，此表的月末数值应在本表内配对比较，不与主回测表直接相减。"
            "两种日期检验不能证明月末普遍优于月中，也未同时改变交易成本或参数。"
        ),
        notes=(
            "口径注：本表截至 2026-09-30，主回测、频率与成本检验截至 2026-10-16。"
            "同一月末策略的年化收益因此可能不同，例如波动率目标为 5.48% 与 5.18%；"
            "这是统计终点差异，应在同一表、同一日期区间内比较。",
        ),
    ))
    frequency_rows: list[list[str]] = []
    frequency = existing[existing["section"] == "调仓频率"]
    for strategy in frequency["strategy"].drop_duplicates():
        pair = frequency[frequency["strategy"] == strategy].set_index("variant")
        frequency_rows.append([
            STRATEGY_NAMES[strategy],
            f"{pair.loc['月度', '年化收益率']:.2%}→{pair.loc['季度', '年化收益率']:.2%}",
            f"{pair.loc['月度', '夏普比率']:.3f}→{pair.loc['季度', '夏普比率']:.3f}",
            f"{pair.loc['月度', '最大回撤']:.2%}→{pair.loc['季度', '最大回撤']:.2%}",
        ])
    sections.append(ReportSection(
        title="调仓频率检验",
        introduction=(
            "五种配置策略分别在月末、季末收盘后形成信号，并于下一交易日收盘执行，"
            "共 10 个情景。均使用沪深 300＋国债指数、2019-01-02—2026-10-16 "
            "的 1,887 个价格交易日、2018 年预热和单边 10bp 成本。"
            "月度与季度分别有 94、32 个执行时点；目标日期保持相同的 2019 年滑降起点和 1,260 日期限。"
        ),
        columns=("策略", "年化收益（月度→季度）", "Sharpe（月度→季度）", "最大回撤（月度→季度）"),
        rows=frequency_rows,
        interpretation=(
            "60/40、风险平价和最小方差变化较小；波动率目标年化收益由 5.18% 降至 4.27%，"
            "但回撤由 26.50% 降至 24.90%。收益、波动和回撤并不同时改善。"
            "目标日期年化收益为 6.17%→6.23%，Sharpe 为 0.677→0.679，"
            "最大回撤为 17.43%→17.45%，对这两种调仓频率相对稳定。"
            "季度方案在两次执行之间仍按价格漂移，并只在季末信号后的执行日跟随同一滑降路径；"
            "滑降期限仍为 1,260 个交易日。全股、全债无再平衡需求，频率不改变其持仓。"
        ),
    ))
    costs = existing[existing["section"] == "成本敏感性"]
    cost_rows: list[list[str]] = []
    allocation_strategies = (
        "SixtyForty",
        "RiskParity",
        "RollingMinVariance",
        "VolatilityTarget",
        "TargetDate",
    )
    cost_detail_rows: list[list[str]] = []
    for strategy in allocation_strategies:
        pair = costs[costs["strategy"] == strategy].set_index("cost_bp")
        cost_rows.append([
            STRATEGY_NAMES[strategy],
            *[f"{pair.loc[cost, '年化收益率']:.2%}" for cost in (0, 10, 30)],
            f"{(pair.loc[0, '年化收益率'] - pair.loc[30, '年化收益率']) * 10000:.1f}bp",
        ])
        for cost in (0, 10, 30):
            row = pair.loc[cost]
            cost_detail_rows.append([
                STRATEGY_NAMES[strategy],
                f"{cost}bp",
                f"{row['年化收益率']:.2%}",
                f"{row['年化波动率']:.2%}",
                f"{row['夏普比率']:.3f}",
                f"{row['最大回撤']:.2%}",
                f"{row['Calmar比率']:.3f}",
                f"{row['月度胜率']:.2%}",
            ])
    sections.append(ReportSection(
        title="交易成本检验",
        introduction=(
            "五种配置策略均在单边 0、10、30bp 下进行月末调仓，共 15 个配置情景；"
            "资产、2019-01-02—2026-10-16 的报告区间及策略参数均保持不变。"
            "每次按买入和卖出金额合计扣费，即单边费率乘以双边换手金额。"
            "下表展示全部五种配置策略的年化收益与相对零成本的损耗，"
            "逐档波动、Sharpe、回撤、Calmar 和月度胜率见完整结果表。"
        ),
        columns=("策略", "0bp", "10bp", "30bp", "30bp 年化收益损耗"),
        rows=cost_rows,
        interpretation=(
            "波动率目标的损耗为 35.8bp，明显高于 60/40 的 8.4bp 和目标日期的 8.3bp；"
            "风险平价和最小方差分别损耗 5.5bp、5.6bp，成本影响较小。"
            "在 30bp 下，波动率目标的年化收益 4.95% 与 60/40 的 4.94% 已接近。"
            "全部检验均属于现有样本内的设定扰动，未形成独立样本外验证，"
            "也未联合搜索参数、资产、信号日期和成本的交互作用。"
        ),
        notes=(
            "口径注：损耗按未四舍五入的收益计算，8.4bp 表示年化收益少约 0.084 个百分点，"
            "全股、全债的三档成本结果也已保存，但因无再平衡换手而相同；"
            "这不代表实际产品交易免费，回测未计初始建仓和持有费用。",
            "数值注：成本升高时，年化波动也可能略降，因为调仓扣费改变了逐日净值收益；"
            "例如波动率目标由 10.102% 降至 10.083%。这不是风险控制改善，"
            "其 Sharpe 同时由 0.525 降至 0.490、回撤由 26.30% 升至 26.88%。",
        ),
        detail_columns=(
            "策略", "单边成本", "年化收益", "年化波动", "Sharpe",
            "最大回撤", "Calmar", "月度胜率",
        ),
        detail_rows=cost_detail_rows,
    ))
    return sections


def markdown_table(columns: tuple[str, ...], rows: list[list[str]]) -> str:
    """将格式化结果输出为标准 Markdown 表格。

    Args:
        columns: 表头。
        rows: 各行单元格字符串。

    Returns:
        表头、对齐分隔行和数据行组成的 Markdown。
    """
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join(["---"] * len(columns)) + " |",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join(lines)


def markdown_section(
    section: ReportSection,
    heading: str,
    include_details: bool = True,
) -> str:
    """生成一个标准 Markdown 报告单元。

    Args:
        section: 标题、段落和结果表。
        heading: 标题前缀，如 ``### 4.1`` 或 ``**（1）``。
        include_details: 是否同时显示逐档完整结果表。

    Returns:
        包含表格和结果解释的 Markdown 文本。
    """
    title = f"{heading} {section.title}"
    if heading.startswith("**"):
        title += "**"
    lines = [title, "", section.introduction, ""]
    lines.extend([markdown_table(section.columns, section.rows), ""])
    if include_details and section.detail_rows:
        lines.extend([
            "**逐档完整结果（五种配置策略 × 三档单边成本）**",
            "",
            markdown_table(section.detail_columns, section.detail_rows),
            "",
        ])
    for note in section.notes:
        lines.extend([note, ""])
    return "\n".join([*lines, section.interpretation, ""])


def markdown_methods(
    sections: list[ReportSection],
    chapter: int,
    include_details: bool = True,
) -> str:
    """按五种检验方法排版，并将长短样本归入资产替换小节。

    Args:
        sections: 参数、长样本、短样本、日期、频率和成本六个报告单元。
        chapter: 项目报告或模块报告中的章号。
        include_details: 是否附上成本逐档完整表。

    Returns:
        采用三级、四级标题的 Markdown 章节内容。
    """
    headings = (
        f"### {chapter}.1", f"#### {chapter}.2.1", f"#### {chapter}.2.2",
        f"### {chapter}.3", f"### {chapter}.4", f"### {chapter}.5",
    )
    blocks: list[str] = []
    for index, (section, heading) in enumerate(zip(sections, headings)):
        if index == 1:
            blocks.append(f"### {chapter}.2 资产替换检验\n")
        blocks.append(markdown_section(section, heading, include_details))
    return "\n".join(blocks)


def html_table(
    columns: tuple[str, ...],
    rows: list[list[str]],
    label: str = "稳健性检验结果",
) -> str:
    """生成可横向滚动的结果表。

    Args:
        columns: 表头。
        rows: 格式化后的单元格记录。
        label: 读屏与核验使用的表格名称。

    Returns:
        对单元格内容转义后的 HTML。
    """
    header = "".join(f"<th>{escape(column)}</th>" for column in columns)
    body = "".join(
        "<tr>" + "".join(f"<td>{escape(cell)}</td>" for cell in row) + "</tr>"
        for row in rows
    )
    return (
        '<div class="card table-wrap robustness-table">'
        f'<table aria-label="{escape(label)}">'
        f"<thead><tr>{header}</tr></thead><tbody>{body}</tbody></table></div>"
    )


def build_chart_data(output_dir: Path) -> dict[str, object]:
    """生成直接嵌入正文的参数曲线与资产比较数据。

    Args:
        output_dir: 稳健性 CSV 目录。

    Returns:
        可 JSON 序列化的参数分组和两组资产情景结果。
    """
    parameters = pd.read_csv(output_dir / "parameter_sensitivity.csv")
    assets = pd.read_csv(output_dir / "asset_substitution_results.csv")
    return {
        "parameters": {
            group: subset[["label", "年化收益率", "夏普比率", "最大回撤"]].to_dict("list")
            for group, subset in parameters.groupby("group", sort=False)
        },
        "assets": assets.to_dict("records"),
        "strategyNames": STRATEGY_NAMES,
    }


def concise_sections(sections: list[ReportSection]) -> list[ReportSection]:
    """为项目报告压缩方法与讨论，保留结果表和异常数值注释。

    Args:
        sections: 模块报告使用的六个完整结果单元。

    Returns:
        顺序与表格保持不变、正文更简短的六个单元。
    """
    introductions = (
        "九组、28 个情景逐项改变参数，其余保持默认。下表为各指标的最小—最大值，"
        "各列极值不一定对应同一档参数；不根据这些结果回选默认参数。",
        "沪深 300、中证 500、上证综指 × 国债、企债指数，六组资产对均运行七类策略（42 个情景）。"
        "共同区间为 2019-01-02—2026-10-16，共 1,887 个价格交易日。",
        "加入科创 50、政金债 ETF 后，十二组资产对均运行七类策略（84 个情景）。"
        "统一使用 2024-01-02—2026-10-16 的 673 个价格交易日，并从 2023-05-17 预热；"
        "目标日期从 2024 年起滑降，尚未覆盖完整五年。",
        "月中取每月 15 日或之前最近共同交易日，月末取最后交易日，均于下一交易日收盘执行。"
        "两组统一截至 2026-09-30，共 1,880 个价格交易日，各 93 个执行时点。全股、全债结果相同，"
        "下表列五种配置策略。",
        "五种配置策略分别按月末、季末信号调仓，共 10 个情景，分别有 94、32 个执行时点。"
        "目标日期保持相同的 2019 年起点及 1,260 个交易日滑降期限。",
        "五种配置策略均比较单边 0、10、30bp 成本，共 15 个配置情景；调仓按双边换手金额扣费。"
        "表中完整列出三档年化收益，损耗均相对零成本计算；逐档风险指标见模块报告与 HTML 展开表。",
    )
    interpretations = (
        "最小方差对窗口不敏感，但股票下限从 0% 升至 30% 时，回撤由 0.96% 升至 9.07%。"
        "波动率目标的 30 日、120 日窗口年化收益为 5.71%、4.59%，参数依赖更明显。"
        "目标日期邻近参数下收益为 5.85%—6.48%，均高于默认 60/40 的 5.00%。",
        "目标日期在六组中年化收益均居七类策略首位；60/40 的回撤则随资产对变化至 13.74%—26.48%。",
        "五种配置策略中，波动率目标在十二组中均取得最高年化收益；若包括全股、全债，"
        "则波动率目标与全股各领先六组。区间和滑降起点同时改变，不能把排名变化单独归因于资产替换。",
        "月中信号下，波动率目标年化收益少 47.8bp，目标日期少 15.0bp，其他三种策略少 4.1—16.4bp；"
        "这不能证明月末在其他样本中仍占优。",
        "目标日期收益、Sharpe 和回撤变化较小，对月度／季度相对稳定。波动率目标改为季度后收益降低，"
        "回撤也减小，体现不同指标之间的取舍；两种频率共用 1,260 个交易日的滑降路径。",
        "波动率目标损耗 35.8bp，其他四种为 5.5—8.4bp；在 30bp 下，"
        "其年化收益 4.95% 已接近 60/40 的 4.94%。",
    )
    notes = (
        (
            "数值注：三个最小方差窗口的 94 个生效信号均取 20% 股票下限，故绩效几乎相同。"
            "下限为 0% 时波动仅约 0.69%，放大了 Sharpe（6.296），并不意味着收益更高。",
        ),
        (
            "数值注：全债 Sharpe 16.825 对应企债指数的 4.34% 收益与约 0.258% 波动，"
            "主要由小分母放大，实际产品风险仍需另行核验。",
        ),
        (
            "数值注：企债全债收益 3.98%、波动约 0.202%，Sharpe 达 19.714；"
            "回撤仅 0.0240%（表中 0.02%），使 Calmar 达 165.455。"
            "这些比率按当前价格序列复算一致，经济含义仍需可交易全收益品种验证。",
        ),
        (
            "口径注：本表截止日期较早，月末收益与主回测不同；"
            "例如波动率目标为 5.48% 而非 5.18%，应在同一日期区间内比较。",
        ),
        (),
        (
            "口径注：8.4bp 损耗约为 0.084 个百分点，按未四舍五入收益计算。"
            "全股、全债无再平衡换手，三档结果相同；未计初始建仓及持有费用。",
            "数值注：费用提高可能使统计波动略降，波动率目标为 10.102%→10.083%；"
            "其 Sharpe 同时从 0.525 降至 0.490、回撤从 26.30% 升至 26.88%，并非风险改善。",
        ),
    )
    return [
        replace(
            section,
            introduction=introduction,
            interpretation=interpretation,
            notes=section_notes,
        )
        for section, introduction, interpretation, section_notes in zip(
            sections,
            introductions,
            interpretations,
            notes,
        )
    ]


def update_project_backtest(project: str, sections: list[ReportSection]) -> str:
    """保留主回测表，单列第六章稳健性及第七章讨论与局限性。

    Args:
        project: 项目报告完整 Markdown。
        sections: 六个结果单元，资产替换含长、短样本。

    Returns:
        第五章主回测、第六章按方法检验、第七章讨论与局限性的报告文本。

    Raises:
        ValueError: 第五章或第六章边界缺失。
    """
    pattern = r"(## 5\. 配置方案与回测结果\n)([\s\S]*?)(?=## 6\. )"
    match = re.search(pattern, project)
    if match is None:
        raise ValueError("Project report backtest chapter boundary is missing.")
    baseline = re.split(r"\n### 5\.2 ", match.group(2), maxsplit=1)[0].strip()
    if not baseline.startswith("### 5.1 "):
        baseline = "### 5.1 回测设定与策略绩效\n\n" + baseline
    note_pattern = r"<!-- allocation-metric-notes -->[\s\S]*?<!-- /allocation-metric-notes -->"
    baseline = re.sub(note_pattern, "", baseline).strip()
    notes = (
        "<!-- allocation-metric-notes -->\n"
        + "\n\n".join(BASE_RESULT_NOTES)
        + "\n<!-- /allocation-metric-notes -->"
    )
    baseline_chapter = (
        match.group(1) + "\n" + baseline + "\n\n" + notes + "\n\n"
    )
    discussion_match = re.search(
        r"## (?:6\. 局限性与讨论|7\. 讨论与局限性)\n([\s\S]*?)(?=## [78]\. 小组分工)",
        project,
    )
    team_match = re.search(r"## [78]\. 小组分工", project)
    if discussion_match is None or team_match is None:
        raise ValueError("Project report discussion or team chapter boundary is missing.")
    discussion = re.sub(
        r"### 6\.2 [^\n]*[\s\S]*?(?=### 6\.3 )",
        "",
        discussion_match.group(1),
    )
    discussion = re.sub(
        r"### 6\.3 [^\n]*",
        "### 6.2 策略表现与稳健性讨论",
        discussion,
    )
    discussion = re.sub(r"(?m)^### 6\.", "### 7.", discussion)
    discussion = discussion.replace("新增检验中", "参数与信号日期检验中")
    limitation = (
        "**稳健性证据仍有边界。** 参数敏感性、资产替换、信号日期、调仓频率和交易成本检验"
        "反映既定样本内的设定依赖，尚未提供独立样本外证据或多个完整五年投资周期；"
        "邻近参数、共享资产及重叠交易日也不构成独立样本。目标日期对月度／季度调仓相对稳定，"
        "但长短样本的排名差异说明其优势仍可能依赖市场阶段。Sharpe 采用几何年化收益除以"
        "对数收益年化波动率、无风险利率设为 0，低波动债券策略的高比率需要结合该口径理解。"
    )
    discussion = re.sub(
        r"\*\*稳健性证据仍有边界。\*\*[^\n]*",
        lambda matched: limitation,
        discussion,
    )
    tail = project[team_match.start():]
    tail = re.sub(r"(?m)^## [78]\. 小组分工", "## 8. 小组分工", tail)
    tail = re.sub(r"(?m)^### [78]\.", "### 8.", tail)
    tail = re.sub(r"(?m)^## [89]\. 成果索引", "## 9. 成果索引", tail)
    robustness_chapter = (
        "## 6. 稳健性检验\n\n"
        "按参数、资产替换、信号日期、调仓频率和交易成本五种方法比较。除成本检验外，"
        "均沿用单边 10bp、无杠杆和下一交易日收盘执行。参数、频率与成本检验统一使用"
        "2019-01-02—2026-10-16 的 1,887 个价格交易日，2018 年用于预热。"
        "各情景共享样本及部分默认对照，不构成独立样本外验证。\n\n"
        + markdown_methods(concise_sections(sections), chapter=6, include_details=False)
        + "\n完整逐档成本指标及回测结果见"
        "[模块四分析报告](asset_allocation/模块4_分析报告.md#四稳健性检验)。\n\n"
    )
    return (
        project[:match.start()] + baseline_chapter + robustness_chapter
        + "## 7. 讨论与局限性\n\n" + discussion.strip() + "\n\n" + tail
    )


def discussion_html(project: str) -> str:
    """将项目报告第七章的标题和段落同步为 HTML 正文章节。

    Args:
        project: 含第七章讨论与局限性的 Markdown 报告。

    Returns:
        含章节锚点、二级标题和讨论段落的 HTML。

    Raises:
        ValueError: 第七章边界缺失。

    Notes:
        此章仅包含段落和粗体，不按通用 Markdown 渲染器处理其他模块。
    """
    match = re.search(r"## 7\. 讨论与局限性\n([\s\S]*?)(?=## 8\.)", project)
    if match is None:
        raise ValueError("Project report discussion chapter is missing.")
    blocks: list[str] = []
    for block in match.group(1).strip().split("\n\n"):
        if block.startswith("### "):
            blocks.append(f'<h3>{escape(block.removeprefix("### "))}</h3>')
            continue
        paragraph = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escape(block))
        blocks.append(f"<p>{paragraph}</p>")
    return (
        '    <section id="discussion">\n'
        '<div class="section-head"><div><span class="section-no">07 · 研究讨论</span>'
        '<h2>讨论与局限性</h2></div></div>\n'
        + "\n".join(blocks) + "\n    </section>\n"
    )


def robustness_html(sections: list[ReportSection]) -> str:
    """生成精简正文，并将图表、完整结果和数值注释置于折叠区域。

    Args:
        sections: 参数、长短样本替换、信号日期、频率和成本六个结果单元。

    Returns:
        五种方法及主要结论可见、详细结果默认收起的 HTML 章节。
    """
    summaries = (
        (
            "参数敏感性",
            "逐项改变股票比例、估计窗口、仓位下限、波动率目标及滑降参数，共 28 个情景，其余设置不变。",
            "最小方差对仓位下限更敏感；波动率目标在 30 日、120 日窗口下年化收益为 5.71%、4.59%。"
            "目标日期邻近参数下收益为 5.85%—6.48%，在当前样本路径下相对稳定。",
            "展开参数敏感性图表与结果",
        ),
        (
            "资产替换检验",
            "长样本比较六组股债资产对，短样本加入科创 50、政金债 ETF 后比较十二组；"
            "每组均运行七类策略，并统一各自样本的比较区间。",
            "目标日期在六组长样本中年化收益均居首；短样本的五种配置策略中，波动率目标在十二组均居首。"
            "领先策略会随市场阶段和滑降起点变化。",
            "展开资产替换图表与长短样本结果",
        ),
        (
            "信号日期检验",
            "分别在每月 15 日或之前最近共同交易日、月末形成信号，下一交易日收盘执行。"
            "统一截至 2026-09-30，两组各有 93 个执行时点。",
            "改用月中信号后，波动率目标年化收益减少 47.8bp，目标日期减少 15.0bp；"
            "波动率目标对具体信号日期更敏感。",
            "展开月中与月末信号对照结果",
        ),
        (
            "调仓频率检验",
            "五种配置策略分别按月末、季末信号调仓，执行时点为 94 次、32 次；"
            "目标日期共用相同的起点和 1,260 个交易日滑降期限。",
            "目标日期年化收益为 6.17%→6.23%，Sharpe 为 0.677→0.679，变化较小；"
            "波动率目标年化收益由 5.18% 降至 4.27%，对频率更敏感。",
            "展开月度与季度调仓结果",
        ),
        (
            "交易成本检验",
            "五种配置策略均比较单边 0、10、30bp 成本，共 15 个情景，按调仓的双边换手金额扣费。",
            "单边成本由 0 提至 30bp 后，波动率目标年化收益损耗 35.8bp，其余四种为 5.5—8.4bp；"
            "波动率目标的成本敏感度最高。",
            "展开五种配置策略的三档成本完整结果",
        ),
    )
    charts = (
        '<label class="robustness-control">参数组 '
        '<select id="parameter-group"></select></label>'
        '<div id="parameter-sensitivity-chart" class="robustness-plot" '
        'role="img" aria-label="参数敏感性收益、Sharpe 与回撤交互图"></div>',
        '<div class="robustness-controls">'
        '<label>比较区间 <select id="asset-cohort">'
        '<option>长样本</option><option>短样本</option></select></label>'
        '<label>指标 <select id="asset-metric"><option>年化收益率</option>'
        '<option>夏普比率</option><option>最大回撤</option></select></label></div>'
        '<div id="asset-substitution-chart" class="robustness-plot" '
        'role="img" aria-label="股债资产替换策略结果热力图"></div>',
        "",
        "",
        "",
    )
    groups = (sections[:1], sections[1:3], sections[3:4], sections[4:5], sections[5:])
    blocks: list[str] = []
    for index, (summary, chart, group) in enumerate(zip(summaries, charts, groups), start=1):
        title, method, conclusion, disclosure = summary
        results = [chart]
        for section in group:
            if len(group) > 1:
                results.append(f"<h4>{escape(section.title)}</h4>")
            results.append(f'<p class="small">{escape(section.introduction)}</p>')
            results.append(html_table(section.columns, section.rows, section.title))
            if section.detail_rows:
                results.append(html_table(
                    section.detail_columns,
                    section.detail_rows,
                    "五种配置策略逐档交易成本完整结果",
                ))
            results.extend(f'<p class="small">{escape(note)}</p>' for note in section.notes)
        blocks.append(
            '<div class="chart-block">'
            f"<h3>{index}. {escape(title)}</h3>"
            f"<p><strong>方法：</strong>{escape(method)}</p>"
            f"<p><strong>主要结论：</strong>{escape(conclusion)}</p>"
            '<details class="bond-details">'
            f"<summary>{escape(disclosure)}</summary>"
            + "\n".join(results) + "</details></div>"
        )
    return (
        '    <section id="robustness">\n'
        '<div class="section-head"><div><span class="section-no">06 · 模块四深化</span>'
        '<h2>稳健性检验</h2></div></div>'
        '<p class="section-intro">通过五种方法比较策略对回测设定的敏感程度。'
        '除成本检验外均采用单边 10bp，样本区间与数值注释见展开结果。</p>'
        + "\n".join(blocks)
        + '\n    </section>'
    )


def update_reports(output_dir: Path = OUTPUT_DIR) -> None:
    """按明确章节边界更新报告并保存图表数据。

    Args:
        output_dir: 分析 CSV 和模块四报告所在目录。

    Raises:
        ValueError: 预期章节边界不存在，避免误改其他内容。
    """
    sections = build_sections(output_dir)
    project_path = output_dir.parent / "项目报告.md"
    module_path = output_dir / "模块4_分析报告.md"
    html_path = output_dir.parent / "项目展示.html"
    module = module_path.read_text()
    module_body = markdown_methods(sections, chapter=4)
    module_tail = (
        "\n## 五、检验边界与复现\n\n"
        "各试验均沿用下一交易日收盘执行、单边 10bp（成本检验除外）、不加杠杆和不填补缺失报价的口径。"
        "各表中的指标范围不是置信区间，也不是多个独立实验的统计显著性证据。Sharpe 沿用主回测的"
        "几何年化收益／对数收益年化波动率，无风险利率为 0；低波动价格指数可能产生很高的比率。"
        "指数点位与 ETF 价格并非统一的可交易全收益口径，回测也未模拟初始建仓、价差、冲击和流动性约束。\n\n"
        "复现全部检验：在项目根目录运行 "
        "`python Assignment1/analysis/asset_allocation/run_backtest.py`；"
        "运行 `python Assignment1/analysis/asset_allocation/robustness_report.py` 更新本节及项目报告、HTML。\n\n"
        "逐情景结果：[参数敏感性](parameter_sensitivity.csv) · "
        "[资产替换](asset_substitution_results.csv) · [信号日期](signal_timing_results.csv) · "
        "[调仓频率与交易成本](robustness_results.csv)。\n"
    )
    module_pattern = r"## 四、稳健性检验[^\n]*[\s\S]*\Z"
    if not re.search(module_pattern, module):
        raise ValueError("Module report robustness section boundary is missing.")
    module = re.sub(
        module_pattern,
        lambda match: "## 四、稳健性检验\n\n" + module_body + module_tail,
        module,
    )
    project = update_project_backtest(project_path.read_text(), sections)

    module_note_pattern = (
        r"<!-- allocation-metric-notes -->[\s\S]*?<!-- /allocation-metric-notes -->\n*"
    )
    module = re.sub(module_note_pattern, "", module)
    module_notes = (
        "<!-- allocation-metric-notes -->\n" + "\n\n".join(BASE_RESULT_NOTES)
        + "\n<!-- /allocation-metric-notes -->\n\n"
    )
    module = module.replace("## 三、最意外的发现", module_notes + "## 三、最意外的发现")

    html = html_path.read_text()
    html_pattern = r'    <section id="robustness">[\s\S]*?</section>'
    if not re.search(html_pattern, html):
        raise ValueError("HTML robustness section boundary is missing.")
    html = re.sub(html_pattern, lambda match: robustness_html(sections), html)
    discussion_section = discussion_html(project)
    discussion_pattern = r'    <section id="discussion">[\s\S]*?</section>\n?'
    if re.search(discussion_pattern, html):
        html = re.sub(discussion_pattern, lambda match: discussion_section, html)
    else:
        html = html.replace("  </main>", discussion_section + "  </main>")
    if 'href="#discussion"' not in html:
        html = html.replace(
            '<a href="#robustness">稳健性</a>',
            '<a href="#robustness">稳健性</a><a href="#discussion">讨论与局限性</a>',
        )
    html_notes = (
        "<!-- allocation-metric-notes -->"
        + "".join(f'<p class="small">{escape(note)}</p>' for note in BASE_RESULT_NOTES)
        + "<!-- /allocation-metric-notes -->"
    )
    if "<!-- allocation-metric-notes -->" in html:
        html = re.sub(
            r"<!-- allocation-metric-notes -->[\s\S]*?<!-- /allocation-metric-notes -->",
            lambda match: html_notes,
            html,
        )
    else:
        html = re.sub(
            r'<p class="small" style="margin-top:15px">全债与风险平价[^<]*</p>',
            lambda match: html_notes,
            html,
        )
    script_tag = '  <script defer src="assets/allocation-robustness.js"></script>'
    if script_tag not in html:
        html = html.replace(
            '  <script defer src="assets/fixed-income-report.js"></script>',
            '  <script defer src="assets/fixed-income-report.js"></script>\n'
            '  <script defer src="asset_allocation/robustness_project_figures.js"></script>\n'
            + script_tag,
        )
    module_path.write_text(module)
    project_path.write_text(project)
    html_path.write_text(html)
    chart_json = json.dumps(build_chart_data(output_dir), ensure_ascii=False, allow_nan=False)
    (output_dir / "robustness_project_figures.js").write_text(
        "// Generated by robustness_report.py from the robustness CSV files.\n"
        f"window.allocationRobustnessData = {chart_json};\n"
    )
    print("已更新三份报告的回测、稳健性与讨论章节。")


if __name__ == "__main__":
    update_reports()
