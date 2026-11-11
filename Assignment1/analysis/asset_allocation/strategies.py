"""Module 4 策略层：核心配置策略的目标权重计算。

本模块定义配置策略的抽象基类与多类核心策略。每个策略在给定信号日
``as_of`` 下返回目标股票权重，债券权重为 1 减去股票权重。

为避免前视偏差，策略只能使用 ``as_of`` 当日及之前的数据。
``equity_weight`` 虽然会收到完整价格表 ``prices``，但必须先切片至
``trade_date <= as_of``，严禁使用未来价格信息。
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np
import pandas as pd


TRADING_DAYS_PER_YEAR: int = 252
PRICE_COLUMNS: tuple[str, str] = ("equity_close", "bond_close")


def _compute_recent_log_returns(
    prices: pd.DataFrame,
    as_of: pd.Timestamp,
    window: int,
) -> pd.DataFrame | None:
    """计算信号日及之前指定窗口的股债对数收益率。

    Args:
        prices: 对齐后的价格表，需包含 ``trade_date``、``equity_close`` 和
            ``bond_close``。
        as_of: 信号日期；函数不会使用该日期之后的数据。
        window: 收益率窗口长度，单位为交易日。

    Returns:
        含股票和债券对数收益率的 DataFrame，shape 为 ``[window, 2]``；
        两列 dtype 均为 float64。历史价格不足 ``window + 1`` 条时
        返回 None。

    Raises:
        ValueError: 如果缺少必需列，或窗口内存在非正价格。
    """
    required_columns = {"trade_date", *PRICE_COLUMNS}
    missing_columns = required_columns.difference(prices.columns)
    if missing_columns:
        raise ValueError(
            f"Expected 'prices' to contain columns {sorted(required_columns)}, "
            f"but missing {sorted(missing_columns)}."
        )

    historical_prices = prices.loc[
        prices["trade_date"] <= as_of,
        list(PRICE_COLUMNS),
    ]
    if len(historical_prices) < window + 1:
        return None

    price_window = historical_prices.tail(window + 1)
    if (price_window <= 0.0).any().any():
        raise ValueError("Expected all values in 'prices' to be positive.")

    log_returns = np.log(price_window / price_window.shift(1)).dropna()
    return log_returns


class Strategy(ABC):
    """配置策略抽象基类。

    每个具体策略实现 :meth:`equity_weight`，返回目标股票权重。
    债券权重由引擎按 ``1 - 股票权重`` 补足。
    """

    name: str = "Strategy"

    @abstractmethod
    def equity_weight(self, as_of: pd.Timestamp, prices: pd.DataFrame) -> float:
        """计算信号日 ``as_of`` 的目标股票权重。

        Args:
            as_of: 信号日期（月末最后一个交易日）。
            prices: 对齐后的价格表，含 ``trade_date``、``equity_close``、
                ``bond_close`` 三列；策略只能使用 ``trade_date <= as_of``
                的部分。

        Returns:
            目标股票权重，取值在 [0, 1] 之间。
        """
        raise NotImplementedError


class AllStockStrategy(Strategy):
    """全股基准：固定 100% 沪深 300，债券权重恒为 0。"""

    name: str = "AllStock"

    def equity_weight(self, as_of: pd.Timestamp, prices: pd.DataFrame) -> float:
        """始终返回 1.0（全股）。"""
        return 1.0


class AllBondStrategy(Strategy):
    """全债基准：固定 100% 上证国债指数，股票权重恒为 0。"""

    name: str = "AllBond"

    def equity_weight(self, as_of: pd.Timestamp, prices: pd.DataFrame) -> float:
        """始终返回 0.0（全债）。"""
        return 0.0


class SixtyFortyStrategy(Strategy):
    """60/40 策略：固定 60% 股票 / 40% 债券，月度再平衡。

    目标权重恒定，不随时间变化。回测引擎在月末信号的次日再平衡。
    """

    name: str = "SixtyForty"

    def __init__(self, equity_weight: float = 0.60) -> None:
        """初始化 60/40 策略。

        Args:
            equity_weight: 固定股票权重，默认 0.60。
        """
        self._equity_weight = float(equity_weight)

    def equity_weight(self, as_of: pd.Timestamp, prices: pd.DataFrame) -> float:
        """返回固定的目标股票权重。"""
        return self._equity_weight


class RiskParityStrategy(Strategy):
    """风险平价策略：按滚动波动率的倒数分配权重。

    股票权重计算公式：

        w_equity = (1 / sigma_equity) / (1 / sigma_equity + 1 / sigma_bond)

    其中 ``sigma`` 为截至 ``as_of`` 的最近 ``window`` 个交易日对数
    收益率样本标准差。历史不足或波动率为 0 时回退到默认权重。
    """

    name: str = "RiskParity"

    def __init__(self, window: int = 60, fallback_weight: float = 0.60) -> None:
        """初始化风险平价策略。

        Args:
            window: 滚动波动率的窗口长度（交易日），默认 60。
            fallback_weight: 历史不足或无波动率时的回退股票权重，
                默认 0.60。
        """
        self._window = int(window)
        self._fallback_weight = float(fallback_weight)

    def equity_weight(self, as_of: pd.Timestamp, prices: pd.DataFrame) -> float:
        """基于历史滚动波动率反比计算股票权重。"""
        log_returns = _compute_recent_log_returns(
            prices,
            as_of,
            self._window,
        )
        if log_returns is None:
            return self._fallback_weight

        vol_equity = float(log_returns["equity_close"].std(ddof=1))
        vol_bond = float(log_returns["bond_close"].std(ddof=1))
        if vol_equity <= 0.0 or vol_bond <= 0.0:
            return self._fallback_weight

        inv_equity = 1.0 / vol_equity
        inv_bond = 1.0 / vol_bond
        weight = inv_equity / (inv_equity + inv_bond)
        return float(np.clip(weight, 0.0, 1.0))


class RollingMinimumVarianceStrategy(Strategy):
    """滚动最小方差策略：使用股债协方差最小化组合方差。

    策略使用最近 ``window`` 日的对数收益率估计协方差，并通过两资产
    最小方差闭式解计算股票权重。为避免估计误差导致极端仓位，
    股票权重被限制在 ``min_equity_weight`` 至 ``max_equity_weight`` 之间。
    """

    name: str = "RollingMinVariance"

    def __init__(
        self,
        window: int = 120,
        min_equity_weight: float = 0.20,
        max_equity_weight: float = 0.80,
        fallback_weight: float = 0.60,
    ) -> None:
        """初始化滚动最小方差策略。

        Args:
            window: 协方差估计窗口，单位为交易日，默认 120。
            min_equity_weight: 股票权重下限，默认 0.20。
            max_equity_weight: 股票权重上限，默认 0.80。
            fallback_weight: 历史不足或协方差退化时的股票权重，
                默认 0.60。

        Raises:
            ValueError: 如果窗口、权重边界或回退权重无效。
        """
        if window < 2:
            raise ValueError(f"Expected 'window' to be at least 2, but got {window}.")
        if not 0.0 <= min_equity_weight <= max_equity_weight <= 1.0:
            raise ValueError(
                "Expected equity weight bounds to satisfy "
                "0 <= min_equity_weight <= max_equity_weight <= 1, "
                f"but got [{min_equity_weight}, {max_equity_weight}]."
            )
        if not min_equity_weight <= fallback_weight <= max_equity_weight:
            raise ValueError(
                "Expected 'fallback_weight' to be within the equity weight bounds, "
                f"but got {fallback_weight}."
            )

        self._window = int(window)
        self._min_equity_weight = float(min_equity_weight)
        self._max_equity_weight = float(max_equity_weight)
        self._fallback_weight = float(fallback_weight)

    def equity_weight(self, as_of: pd.Timestamp, prices: pd.DataFrame) -> float:
        """计算受限的滚动最小方差股票权重。

        Args:
            as_of: 信号日期（月末最后一个交易日）。
            prices: 对齐后的股债价格表。

        Returns:
            股票目标权重，限制在构造函数给定的边界内。
        """
        log_returns = _compute_recent_log_returns(
            prices,
            as_of,
            self._window,
        )
        if log_returns is None:
            return self._fallback_weight

        covariance = log_returns.cov()
        equity_variance = float(covariance.loc["equity_close", "equity_close"])
        bond_variance = float(covariance.loc["bond_close", "bond_close"])
        equity_bond_covariance = float(
            covariance.loc["equity_close", "bond_close"]
        )
        denominator = (
            equity_variance
            + bond_variance
            - 2.0 * equity_bond_covariance
        )
        if not np.isfinite(denominator) or denominator <= np.finfo(float).eps:
            return self._fallback_weight

        unconstrained_weight = (
            bond_variance - equity_bond_covariance
        ) / denominator
        return float(
            np.clip(
                unconstrained_weight,
                self._min_equity_weight,
                self._max_equity_weight,
            )
        )


class VolatilityTargetStrategy(Strategy):
    """波动率目标策略：高波动时将 60/40 的股票风险转移至债券。

    使用最近 ``window`` 日的基础组合收益率估计年化波动率。
    当估计波动率超过目标值时，按
    ``target_volatility / estimated_volatility`` 缩减基础股票权重；
    低于目标值时保持基础权重，不使用杠杆。
    """

    name: str = "VolatilityTarget"

    def __init__(
        self,
        window: int = 60,
        target_volatility: float = 0.10,
        base_equity_weight: float = 0.60,
    ) -> None:
        """初始化波动率目标策略。

        Args:
            window: 波动率估计窗口，单位为交易日，默认 60。
            target_volatility: 目标年化波动率，默认 0.10。
            base_equity_weight: 未触发降风险时的股票权重，默认 0.60。

        Raises:
            ValueError: 如果窗口、目标波动率或基础权重无效。
        """
        if window < 2:
            raise ValueError(f"Expected 'window' to be at least 2, but got {window}.")
        if target_volatility <= 0.0:
            raise ValueError(
                "Expected 'target_volatility' to be positive, "
                f"but got {target_volatility}."
            )
        if not 0.0 <= base_equity_weight <= 1.0:
            raise ValueError(
                "Expected 'base_equity_weight' to be within [0, 1], "
                f"but got {base_equity_weight}."
            )

        self._window = int(window)
        self._target_volatility = float(target_volatility)
        self._base_equity_weight = float(base_equity_weight)

    def equity_weight(self, as_of: pd.Timestamp, prices: pd.DataFrame) -> float:
        """根据基础组合的近期波动率计算股票目标权重。

        Args:
            as_of: 信号日期（月末最后一个交易日）。
            prices: 对齐后的股债价格表。

        Returns:
            股票目标权重，取值在 0 与基础股票权重之间。
        """
        log_returns = _compute_recent_log_returns(
            prices,
            as_of,
            self._window,
        )
        if log_returns is None:
            return self._base_equity_weight

        bond_weight = 1.0 - self._base_equity_weight
        portfolio_returns = (
            self._base_equity_weight * log_returns["equity_close"]
            + bond_weight * log_returns["bond_close"]
        )
        estimated_volatility = float(
            portfolio_returns.std(ddof=1) * np.sqrt(TRADING_DAYS_PER_YEAR)
        )
        if not np.isfinite(estimated_volatility) or estimated_volatility <= 0.0:
            return self._base_equity_weight

        exposure_scale = min(
            1.0,
            self._target_volatility / estimated_volatility,
        )
        return float(self._base_equity_weight * exposure_scale)


class TargetDateStrategy(Strategy):
    """目标日期策略：股票权重随剩余期限线性下降（70% -> 30%）。

    在滑降起点（剩余期限最长），股票权重为 ``start_equity_weight``；
    随着时间推移线性降至 ``end_equity_weight``，债券补足剩余部分。

    剩余期限以交易日计。从价格序列首个交易日开始，每经过一个交易日，
    滑降 1 / ``total_days``。滑降完成后权重保持在
    ``end_equity_weight``。
    """

    name: str = "TargetDate"

    def __init__(
        self,
        start_equity_weight: float = 0.70,
        end_equity_weight: float = 0.30,
        total_days: int = 1260,
        start_date: str | pd.Timestamp | None = None,
    ) -> None:
        """初始化目标日期策略。

        Args:
            start_equity_weight: 滑降起点的股票权重，默认 0.70。
            end_equity_weight: 滑降终点的股票权重，默认 0.30（对应剩余
                期限 0 年）。
            total_days: 滑降路径的总交易日数，默认 1260，约为
                5 年 × 252 个交易日。可由外部动态传入。
            start_date: 滑降起点日期。若为 None，默认使用价格序列的
                首个交易日。
        """
        self._start_weight = float(start_equity_weight)
        self._end_weight = float(end_equity_weight)
        self._total_days = int(total_days)
        self._start_date = (
            pd.Timestamp(start_date) if start_date is not None else None
        )

    def equity_weight(self, as_of: pd.Timestamp, prices: pd.DataFrame) -> float:
        """按剩余期限线性插值计算股票权重。

        权重 = start_weight - (start_weight - end_weight) * fraction，
        其中 ``fraction`` 为自 ``start_date`` 以来经过的交易日数占
        ``total_days`` 的比例（截断到 [0, 1]）。
        """
        start_date = self._start_date
        if start_date is None:
            start_date = prices["trade_date"].min()
        # 起点当天记为第 0 日，起点之前的已过天数也按 0 处理。
        is_in_elapsed_period = (
            (prices["trade_date"] >= start_date)
            & (prices["trade_date"] <= as_of)
        )
        elapsed_days = int(is_in_elapsed_period.sum()) - 1
        elapsed_days = max(0, elapsed_days)
        fraction = min(1.0, elapsed_days / self._total_days)
        weight = self._start_weight - (self._start_weight - self._end_weight) * fraction
        return float(weight)
