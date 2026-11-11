"""Module 4 策略单元测试。"""

from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from strategies import (
    RollingMinimumVarianceStrategy,
    VolatilityTargetStrategy,
)


def build_prices(
    equity_returns: np.ndarray,
    bond_returns: np.ndarray,
) -> pd.DataFrame:
    """根据一维对数收益率构造股债价格表。

    Args:
        equity_returns: 股票对数收益率，shape 为 ``[n_periods]``，
            numeric dtype。
        bond_returns: 债券对数收益率，shape 为 ``[n_periods]``，
            numeric dtype。

    Returns:
        股债价格表，shape 为 ``[n_periods + 1, 3]``；价格列 dtype
        为 float64。

    Raises:
        ValueError: 如果两组收益率 shape 不一致。
    """
    if equity_returns.shape != bond_returns.shape:
        raise ValueError(
            "Expected 'equity_returns' and 'bond_returns' to have the same "
            f"shape, but got {equity_returns.shape} and {bond_returns.shape}."
        )

    periods = len(equity_returns)
    dates = pd.bdate_range("2020-01-01", periods=periods + 1)
    equity_prices = 100.0 * np.exp(
        np.concatenate(([0.0], np.cumsum(equity_returns)))
    )
    bond_prices = 100.0 * np.exp(
        np.concatenate(([0.0], np.cumsum(bond_returns)))
    )
    return pd.DataFrame(
        {
            "trade_date": dates,
            "equity_close": equity_prices,
            "bond_close": bond_prices,
        }
    )


class RollingMinimumVarianceStrategyTest(unittest.TestCase):
    """验证滚动最小方差策略的边界和历史不足处理。"""

    def test_uses_lower_bound_when_stock_is_much_more_volatile(self) -> None:
        """股票波动显著更高时，权重应落在股票下限。"""
        periods = 130
        equity_returns = np.resize(np.array([0.02, -0.02]), periods)
        bond_returns = np.zeros(periods)
        prices = build_prices(equity_returns, bond_returns)
        strategy = RollingMinimumVarianceStrategy(window=120)

        weight = strategy.equity_weight(prices["trade_date"].iloc[-1], prices)

        self.assertAlmostEqual(weight, 0.20)

    def test_falls_back_when_history_is_insufficient(self) -> None:
        """窗口数据不足时应返回配置的回退权重。"""
        prices = build_prices(np.array([0.01]), np.array([0.001]))
        strategy = RollingMinimumVarianceStrategy(
            window=120,
            fallback_weight=0.55,
        )

        weight = strategy.equity_weight(prices["trade_date"].iloc[-1], prices)

        self.assertAlmostEqual(weight, 0.55)


class VolatilityTargetStrategyTest(unittest.TestCase):
    """验证波动率目标策略的降风险与无杠杆约束。"""

    def test_reduces_equity_weight_when_volatility_is_high(self) -> None:
        """基础组合波动超过目标时应降低股票权重。"""
        periods = 70
        equity_returns = np.resize(np.array([0.03, -0.03]), periods)
        bond_returns = np.zeros(periods)
        prices = build_prices(equity_returns, bond_returns)
        strategy = VolatilityTargetStrategy(window=60)

        weight = strategy.equity_weight(prices["trade_date"].iloc[-1], prices)

        self.assertGreater(weight, 0.0)
        self.assertLess(weight, 0.60)

    def test_keeps_base_weight_when_volatility_is_low(self) -> None:
        """基础组合波动低于目标时应保持 60% 股票且不加杠杆。"""
        periods = 70
        equity_returns = np.resize(np.array([0.001, -0.001]), periods)
        bond_returns = np.zeros(periods)
        prices = build_prices(equity_returns, bond_returns)
        strategy = VolatilityTargetStrategy(window=60)

        weight = strategy.equity_weight(prices["trade_date"].iloc[-1], prices)

        self.assertAlmostEqual(weight, 0.60)


if __name__ == "__main__":
    unittest.main()
