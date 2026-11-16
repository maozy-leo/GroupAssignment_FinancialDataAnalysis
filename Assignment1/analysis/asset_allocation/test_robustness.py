"""验证月中信号的日历边界、预热条件及扩展检验的对照设计。"""

from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from data_loader import AssetAllocationDataLoader
from robustness import build_parameter_cases, evaluate_case
from run_backtest import run_robustness_checks
from strategies import SixtyFortyStrategy


def make_prices(dates: list[str]) -> pd.DataFrame:
    """生成只用于信号和边界检查的正价格表。

    Args:
        dates: 升序 ISO 日期列表。

    Returns:
        三列价格表，两个价格列的 shape 均为 [交易日数]。
    """
    return pd.DataFrame({
        "trade_date": pd.to_datetime(dates),
        "equity_close": np.linspace(100.0, 110.0, len(dates)),
        "bond_close": np.linspace(100.0, 102.0, len(dates)),
    })


class MidMonthSignalTests(unittest.TestCase):
    """检查周末、缺失报价、未完成月份及信号执行顺序。"""

    def setUp(self) -> None:
        self.loader = AssetAllocationDataLoader()

    def test_weekend_and_missing_common_quote(self) -> None:
        """15 日为周末且 14 日无共同报价时，应选 13 日并于 17 日执行。"""
        prices = make_prices(["2025-02-12", "2025-02-13", "2025-02-17", "2025-02-18"])
        signals = self.loader.extract_mid_month_signals(prices)
        self.assertEqual(signals["signal_date"].tolist(), [pd.Timestamp("2025-02-13")])
        self.assertEqual(signals["next_trade_date"].tolist(), [pd.Timestamp("2025-02-17")])

    def test_exact_midpoint_and_incomplete_last_month(self) -> None:
        """15 日有报价时使用当日；末月仅覆盖至 10 日时不得提前生成信号。"""
        prices = make_prices([
            "2025-01-14", "2025-01-15", "2025-01-16", "2025-02-10",
        ])
        signals = self.loader.extract_mid_month_signals(prices)
        self.assertEqual(signals["period"].tolist(), ["2025-01"])
        self.assertEqual(signals["signal_date"].iloc[0], pd.Timestamp("2025-01-15"))
        self.assertEqual(signals["next_trade_date"].iloc[0], pd.Timestamp("2025-01-16"))

    def test_signal_without_execution_is_excluded(self) -> None:
        """样本终止于 15 日时，没有后续价格的信号不得执行。"""
        prices = make_prices(["2025-01-14", "2025-01-15"])
        self.assertTrue(self.loader.extract_mid_month_signals(prices).empty)

    def test_unsorted_dates_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "sorted"):
            self.loader.extract_mid_month_signals(
                make_prices(["2025-01-16", "2025-01-15"])
            )


class ExperimentDesignTests(unittest.TestCase):
    """检查默认参数对照与正式样本前的预热约束。"""

    def test_every_parameter_group_has_one_default(self) -> None:
        cases = build_parameter_cases()
        self.assertEqual(len(cases), 28)
        groups = {case.group for case in cases}
        self.assertEqual(len(groups), 9)
        for group in groups:
            self.assertEqual(sum(case.is_baseline for case in cases if case.group == group), 1)

    def test_frequency_check_covers_all_five_allocations(self) -> None:
        """月度／季度矩阵必须包含目标日期及其余四种配置策略。"""
        loader = AssetAllocationDataLoader()
        prices = loader.load_aligned_prices()
        signals = loader.extract_month_end_signals(prices)
        results = run_robustness_checks(loader, prices, signals)
        frequency = results[results["section"] == "调仓频率"]
        strategies = {
            "SixtyForty", "RiskParity", "RollingMinVariance",
            "VolatilityTarget", "TargetDate",
        }
        expected = {(strategy, period) for strategy in strategies for period in ("月度", "季度")}
        actual = set(zip(frequency["strategy"], frequency["variant"]))
        self.assertEqual(actual, expected)
        self.assertEqual(len(frequency), len(expected))
        self.assertTrue(frequency["cost_bp"].eq(10).all())

    def test_insufficient_warmup_is_rejected(self) -> None:
        prices = make_prices(["2025-01-14", "2025-01-15", "2025-01-16", "2025-01-17"])
        signals = AssetAllocationDataLoader().extract_mid_month_signals(prices)
        with self.assertRaisesRegex(ValueError, "warm-up returns"):
            evaluate_case(
                prices=prices,
                signals=signals,
                strategy=SixtyFortyStrategy(),
                start_date="2025-01-16",
                end_date=pd.Timestamp("2025-01-17"),
                required_history=120,
            )

    def test_later_prices_do_not_change_earlier_results(self) -> None:
        """扰动报告终点之后的报价，区间内绩效必须保持不变。"""
        prices = make_prices([
            "2025-01-14", "2025-01-15", "2025-01-16", "2025-01-17", "2025-01-20",
        ])
        signals = AssetAllocationDataLoader().extract_mid_month_signals(prices)
        arguments = {
            "signals": signals,
            "strategy": SixtyFortyStrategy(),
            "start_date": "2025-01-16",
            "end_date": pd.Timestamp("2025-01-17"),
        }
        original = evaluate_case(prices=prices, **arguments)
        prices.loc[4, "equity_close"] *= 5
        pd.testing.assert_series_equal(
            pd.Series(original),
            pd.Series(evaluate_case(prices=prices, **arguments)),
        )


if __name__ == "__main__":
    unittest.main()
