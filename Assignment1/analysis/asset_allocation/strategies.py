"""Module 4 策略层：核心配置策略的目标权重计算。

本模块定义配置策略的抽象基类与四大核心策略，每个策略在给定信号日
``as_of`` 下返回目标股票权重（债券权重 = 1 - 股票权重）。

防前视偏差约定：策略内部只能使用 ``as_of`` 当日及之前的数据。因此策略的
``equity_weight`` 方法会收到完整的对齐价格表 ``prices``，但必须自行切片到
``trade_date <= as_of`` 之后再计算，严禁使用未来价格信息。
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np
import pandas as pd


class Strategy(ABC):
    """配置策略抽象基类。

    每个具体策略实现 :meth:`equity_weight`，返回目标股票权重。债券权重由
    引擎按 ``1 - 股票权重`` 补足。
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

    目标权重恒定，不随时间变化；再平衡由回测引擎在月末信号次日执行。
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
    """风险平价策略：按过去 60 个交易日的滚动波动率反比分配权重。

    股票权重计算公式：

        w_equity = (1 / sigma_equity) / (1 / sigma_equity + 1 / sigma_bond)

    其中 ``sigma`` 为截至 ``as_of`` 的最近 ``window`` 个交易日对数收益率的
    样本标准差。历史不足或波动率为 0 时回退到默认权重。
    """

    name: str = "RiskParity"

    def __init__(self, window: int = 60, fallback_weight: float = 0.60) -> None:
        """初始化风险平价策略。

        Args:
            window: 滚动波动率的窗口长度（交易日），默认 60。
            fallback_weight: 历史不足或无波动率时的回退股票权重，默认 0.60。
        """
        self._window = int(window)
        self._fallback_weight = float(fallback_weight)

    def equity_weight(self, as_of: pd.Timestamp, prices: pd.DataFrame) -> float:
        """基于历史滚动波动率反比计算股票权重。"""
        hist = prices[prices["trade_date"] <= as_of]
        # 需要至少 window 个收益率观测，即 window + 1 个价格点。
        if len(hist) < self._window + 1:
            return self._fallback_weight

        equity = hist["equity_close"].iloc[-(self._window + 1):]
        bond = hist["bond_close"].iloc[-(self._window + 1):]
        equity_ret = np.log(equity / equity.shift(1)).dropna()
        bond_ret = np.log(bond / bond.shift(1)).dropna()

        vol_equity = float(equity_ret.std(ddof=1))
        vol_bond = float(bond_ret.std(ddof=1))
        if vol_equity <= 0.0 or vol_bond <= 0.0:
            return self._fallback_weight

        inv_equity = 1.0 / vol_equity
        inv_bond = 1.0 / vol_bond
        weight = inv_equity / (inv_equity + inv_bond)
        return float(np.clip(weight, 0.0, 1.0))


class TargetDateStrategy(Strategy):
    """目标日期策略：股票权重随剩余期限线性下降（70% -> 30%）。

    在滑降起点（剩余期限最长）股票权重为 ``start_equity_weight``，随着时间
    推移线性降至 ``end_equity_weight``，债券补足剩余部分。

    剩余期限以交易日计：从价格序列首个交易日开始，每经过一个交易日滑降
    1 / ``total_days``。滑降完成后权重保持在 ``end_equity_weight``。
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
            start_equity_weight: 滑降起点的股票权重，默认 0.70（对应剩余
                期限 5 年）。
            end_equity_weight: 滑降终点的股票权重，默认 0.30（对应剩余
                期限 0 年）。
            total_days: 滑降路径的总交易日数，默认 1260（约 5 年 × 252）。
                可由外部动态传入，例如设为回测全期长度或固定 5 年。
            start_date: 滑降起点日期（剩余期限 5 年的时点）。若为 None，
                默认使用价格序列的首个交易日。
        """
        self._start_weight = float(start_equity_weight)
        self._end_weight = float(end_equity_weight)
        self._total_days = int(total_days)
        self._start_date = pd.Timestamp(start_date) if start_date is not None else None

    def equity_weight(self, as_of: pd.Timestamp, prices: pd.DataFrame) -> float:
        """按剩余期限线性插值计算股票权重。

        权重 = start_weight - (start_weight - end_weight) * fraction，
        其中 ``fraction`` 为自 ``start_date`` 以来经过的交易日数占
        ``total_days`` 的比例（截断到 [0, 1]）。
        """
        start_date = (
            self._start_date if self._start_date is not None else prices["trade_date"].min()
        )
        # 自滑降起点以来经过的交易日数（从 0 开始计），起点之前为 0。
        elapsed_days = int(
            ((prices["trade_date"] >= start_date) & (prices["trade_date"] <= as_of)).sum()
        ) - 1
        elapsed_days = max(0, elapsed_days)
        fraction = min(1.0, elapsed_days / self._total_days)
        weight = self._start_weight - (self._start_weight - self._end_weight) * fraction
        return float(weight)
