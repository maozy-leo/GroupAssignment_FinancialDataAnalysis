"""扩展模块四稳健性检验，复用既有策略、执行引擎和绩效口径。

独立运行：python Assignment1/analysis/asset_allocation/robustness.py
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from pathlib import Path

import pandas as pd

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

OUTPUT_DIR = Path(__file__).resolve().parents[2] / "output" / "asset_allocation"
REPORT_START = "2019-01-01"
SHORT_START = "2024-01-01"
ASSET_NAMES = {
    "CSI300": "沪深300",
    "CSI500": "中证500",
    "SSE_COMPOSITE": "上证综指",
    "STAR50": "科创50",
    "SSE_TREASURY": "国债指数",
    "SSE_ENTERPRISE_BOND": "企债指数",
    "POLICY_BOND_7_10_PROXY": "政金债ETF",
}
STRATEGY_NAMES = {
    "AllStock": "全股",
    "AllBond": "全债",
    "SixtyForty": "60/40",
    "RiskParity": "风险平价",
    "RollingMinVariance": "最小方差",
    "VolatilityTarget": "波动率目标",
    "TargetDate": "目标日期",
}


@dataclass(frozen=True)
class ParameterCase:
    """单因素参数试验：同组各档仅改变一个参数。"""

    group: str
    value: float
    label: str
    is_baseline: bool
    strategy: Strategy
    required_history: int = 0


def build_default_strategies(start_date: str) -> list[Strategy]:
    """构建七类默认策略，并统一目标日期策略的滑降起点。

    Args:
        start_date: 报告区间及目标日期滑降的起点，ISO 日期字符串。

    Returns:
        参数与主回测一致的七类策略实例。
    """
    return [
        AllStockStrategy(),
        AllBondStrategy(),
        SixtyFortyStrategy(),
        RiskParityStrategy(),
        RollingMinimumVarianceStrategy(),
        VolatilityTargetStrategy(),
        TargetDateStrategy(start_date=start_date),
    ]


def build_parameter_cases() -> list[ParameterCase]:
    """预先列出邻近参数网格，其他参数保持主回测默认值。

    Returns:
        九组、共 28 个参数情景；每组包含原参数作为对照。

    Notes:
        协方差长窗口用 240 日，确保 2018 年预热覆盖首个正式持仓信号。
    """
    cases: list[ParameterCase] = []
    for weight in (0.5, 0.6, 0.7):
        cases.append(ParameterCase(
            group="固定配置股票权重",
            value=weight,
            label=f"{weight:.0%}",
            is_baseline=weight == 0.6,
            strategy=SixtyFortyStrategy(equity_weight=weight),
        ))
    for window in (30, 60, 120):
        cases.append(ParameterCase(
            group="风险平价窗口",
            value=window,
            label=f"{window}日",
            is_baseline=window == 60,
            strategy=RiskParityStrategy(window=window),
            required_history=window,
        ))
    for window in (60, 120, 240):
        cases.append(ParameterCase(
            group="最小方差窗口",
            value=window,
            label=f"{window}日",
            is_baseline=window == 120,
            strategy=RollingMinimumVarianceStrategy(window=window),
            required_history=window,
        ))
    for lower_bound in (0.0, 0.1, 0.2, 0.3):
        cases.append(ParameterCase(
            group="最小方差股票下限",
            value=lower_bound,
            label=f"{lower_bound:.0%}",
            is_baseline=lower_bound == 0.2,
            strategy=RollingMinimumVarianceStrategy(min_equity_weight=lower_bound),
            required_history=120,
        ))
    for window in (30, 60, 120):
        cases.append(ParameterCase(
            group="波动率目标窗口",
            value=window,
            label=f"{window}日",
            is_baseline=window == 60,
            strategy=VolatilityTargetStrategy(window=window),
            required_history=window,
        ))
    for target in (0.08, 0.10, 0.12):
        cases.append(ParameterCase(
            group="目标年化波动率",
            value=target,
            label=f"{target:.0%}",
            is_baseline=target == 0.10,
            strategy=VolatilityTargetStrategy(target_volatility=target),
            required_history=60,
        ))
    for start_weight in (0.6, 0.7, 0.8):
        cases.append(ParameterCase(
            group="目标日期起始股票权重",
            value=start_weight,
            label=f"{start_weight:.0%}",
            is_baseline=start_weight == 0.7,
            strategy=TargetDateStrategy(
                start_equity_weight=start_weight,
                start_date=REPORT_START,
            ),
        ))
    for end_weight in (0.2, 0.3, 0.4):
        cases.append(ParameterCase(
            group="目标日期终点股票权重",
            value=end_weight,
            label=f"{end_weight:.0%}",
            is_baseline=end_weight == 0.3,
            strategy=TargetDateStrategy(
                end_equity_weight=end_weight,
                start_date=REPORT_START,
            ),
        ))
    for horizon in (1008, 1260, 1512):
        cases.append(ParameterCase(
            group="目标日期滑降期限",
            value=horizon,
            label=f"{horizon}日",
            is_baseline=horizon == 1260,
            strategy=TargetDateStrategy(
                total_days=horizon,
                start_date=REPORT_START,
            ),
        ))
    return cases


def evaluate_case(
    prices: pd.DataFrame,
    signals: pd.DataFrame,
    strategy: Strategy,
    start_date: str,
    end_date: pd.Timestamp,
    required_history: int = 0,
) -> dict[str, object]:
    """使用预热后的共同区间评估策略，并记录样本与实际股票暴露。

    Args:
        prices: 共同价格表，含日期和两资产价格三列。
        signals: 收盘信号及下一共同交易日执行日期。
        strategy: 待评估的策略实例。
        start_date: 正式绩效起点，ISO 日期字符串。
        end_date: 正式绩效终点（含当日）。
        required_history: 正式起点前生效的信号所需收益率观测数。

    Returns:
        绩效指标、样本范围、观测数、区间内执行次数及平均股票权重。

    Raises:
        ValueError: 正式样本不足、缺少已生效信号或预热历史不足。

    Notes:
        复用主引擎：下一交易日收盘调仓、单边 10bp、无杠杆，收益先计入
        旧仓位，再调仓及扣费。绩效首日归一化，不计初始建仓费用。
    """
    formal_dates = prices.loc[
        prices["trade_date"].between(pd.Timestamp(start_date), end_date),
        "trade_date",
    ]
    if len(formal_dates) < 2:
        raise ValueError(f"Fewer than two price dates in [{start_date}, {end_date}].")
    first_date = formal_dates.iloc[0]
    effective_signals = signals[signals["next_trade_date"] <= first_date]
    if effective_signals.empty:
        raise ValueError(f"No warm-up signal is effective by {first_date}.")
    latest_signal = effective_signals["signal_date"].iloc[-1]
    history_size = int((prices["trade_date"] <= latest_signal).sum()) - 1
    if history_size < required_history:
        raise ValueError(
            f"Expected at least {required_history} warm-up returns at "
            f"{latest_signal}, got {history_size}."
        )

    nav = Backtester().run(prices, strategy, signals)
    nav = nav[nav["trade_date"].isin(formal_dates)].reset_index(drop=True)
    nav["nav"] /= nav["nav"].iloc[0]
    executions = signals["next_trade_date"].between(first_date, end_date)
    return {
        "start_date": first_date.date().isoformat(),
        "end_date": nav["trade_date"].iloc[-1].date().isoformat(),
        "observations": len(nav),
        "executions": int(executions.sum()),
        "cost_bp": 10,
        "mean_equity_weight": float(nav["equity_weight"].mean()),
        **compute_metrics(nav),
    }


class RobustnessRunner:
    """缓存资产组合数据并执行三类可复现的受控比较。"""

    def __init__(self, loader: AssetAllocationDataLoader | None = None) -> None:
        """初始化只读数据读取器和价格缓存。

        Args:
            loader: 可注入的数据库读取器，默认使用项目数据库。
        """
        self.loader = loader or AssetAllocationDataLoader()
        self._prices: dict[tuple[str, str], pd.DataFrame] = {}

    def prices(self, equity_id: str, bond_id: str) -> pd.DataFrame:
        """读取并缓存指定股债的共同价格。

        Args:
            equity_id: 股票资产数据库标识。
            bond_id: 债券资产数据库标识。

        Returns:
            日期升序且价格为正的三列共同价格表。
        """
        key = (equity_id, bond_id)
        if key not in self._prices:
            prices = self.loader.load_aligned_prices(equity_id, bond_id)
            if prices.empty or (prices[["equity_close", "bond_close"]] <= 0).any().any():
                raise ValueError(f"Missing or nonpositive aligned prices for {key}.")
            self._prices[key] = prices
        return self._prices[key]

    def run_parameters(self) -> pd.DataFrame:
        """执行九组单因素参数检验。

        Returns:
            28 行参数情景、默认值标记、股票暴露与绩效指标。
        """
        prices = self.prices("CSI300", "SSE_TREASURY")
        signals = self.loader.extract_month_end_signals(prices)
        rows: list[dict[str, object]] = []
        for case in build_parameter_cases():
            rows.append({
                "group": case.group,
                "strategy": case.strategy.name,
                "value": case.value,
                "label": case.label,
                "is_baseline": case.is_baseline,
                **evaluate_case(
                    prices=prices,
                    signals=signals,
                    strategy=case.strategy,
                    start_date=REPORT_START,
                    end_date=prices["trade_date"].max(),
                    required_history=case.required_history,
                ),
            })
        return pd.DataFrame(rows)

    def run_asset_substitutions(self) -> pd.DataFrame:
        """对七类策略分别执行长样本六组及短样本十二组资产替换。

        Returns:
            126 行结果；同一 cohort 使用完全相同的价格日期与报告区间。

        Notes:
            短样本从 2024 年起，ETF 的 2023 年价格仅用于预热；目标日期
            同步重置滑降起点，短区间不构成完整五年策略验证。
        """
        rows: list[dict[str, object]] = []
        cohorts = (
            ("长样本", REPORT_START, ("CSI300", "CSI500", "SSE_COMPOSITE"),
             ("SSE_TREASURY", "SSE_ENTERPRISE_BOND")),
            ("短样本", SHORT_START, ("CSI300", "CSI500", "SSE_COMPOSITE", "STAR50"),
             ("SSE_TREASURY", "SSE_ENTERPRISE_BOND", "POLICY_BOND_7_10_PROXY")),
        )
        for cohort, start_date, equities, bonds in cohorts:
            pairs = list(product(equities, bonds))
            common_dates: pd.Index = pd.Index(self.prices(*pairs[0])["trade_date"])
            for pair in pairs[1:]:
                common_dates = common_dates.intersection(self.prices(*pair)["trade_date"])
            for equity_id, bond_id in pairs:
                prices = self.prices(equity_id, bond_id)
                prices = prices[prices["trade_date"].isin(common_dates)].reset_index(drop=True)
                signals = self.loader.extract_month_end_signals(prices)
                for strategy in build_default_strategies(start_date):
                    rows.append({
                        "cohort": cohort,
                        "equity_id": equity_id,
                        "bond_id": bond_id,
                        "pair": f"{ASSET_NAMES[equity_id]}＋{ASSET_NAMES[bond_id]}",
                        "strategy": strategy.name,
                        **evaluate_case(
                            prices=prices,
                            signals=signals,
                            strategy=strategy,
                            start_date=start_date,
                            end_date=prices["trade_date"].max(),
                            required_history=120,
                        ),
                    })
        return pd.DataFrame(rows)

    def run_signal_timing(self) -> pd.DataFrame:
        """比较月中和月末信号，统一截至最后一个完整自然月。

        Returns:
            七类策略各两种信号日期的 14 行绩效结果。

        Notes:
            截去末尾未完成月份，避免只有月中已生成信号的边界影响比较。
        """
        prices = self.prices("CSI300", "SSE_TREASURY")
        latest_date = prices["trade_date"].max()
        end_date = latest_date.to_period("M").start_time - pd.Timedelta(days=1)
        rows: list[dict[str, object]] = []
        for label, signals in (
            ("月末", self.loader.extract_month_end_signals(prices)),
            ("月中", self.loader.extract_mid_month_signals(prices)),
        ):
            for strategy in build_default_strategies(REPORT_START):
                rows.append({
                    "timing": label,
                    "strategy": strategy.name,
                    **evaluate_case(
                        prices=prices,
                        signals=signals,
                        strategy=strategy,
                        start_date=REPORT_START,
                        end_date=end_date,
                        required_history=120,
                    ),
                })
        return pd.DataFrame(rows)

    def run(self, output_dir: Path = OUTPUT_DIR) -> dict[str, pd.DataFrame]:
        """运行并保存三类结果。

        Args:
            output_dir: CSV 保存目录。

        Returns:
            以文件主名为键的结果表字典。
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        results = {
            "parameter_sensitivity": self.run_parameters(),
            "asset_substitution_results": self.run_asset_substitutions(),
            "signal_timing_results": self.run_signal_timing(),
        }
        for name, result in results.items():
            result.to_csv(output_dir / f"{name}.csv", index=False)
            print(f"已保存 {name}: {len(result)} 个情景")
        return results


if __name__ == "__main__":
    RobustnessRunner().run()
