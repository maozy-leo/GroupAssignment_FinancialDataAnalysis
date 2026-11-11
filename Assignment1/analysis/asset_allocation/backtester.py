"""Module 4 回测引擎：每日仓位漂移、调仓执行与绩效计算。

回测引擎在给定对齐价格、月末信号与策略下，逐日模拟组合净值：

* 信号在月末最后一个交易日（``signal_date``）产生，调仓在次日
  （``next_trade_date``）收盘执行，杜绝前视偏差；
* 调仓日之间，股票与债券权重随每日涨跌自然漂移；
* 每次调仓按双边换手率扣减交易成本（单边 10bp）；
* 提供标准的绩效指标计算。
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from strategies import Strategy

# 单边交易成本：10bp = 0.1%。调仓时买卖双边各扣一次。
COST_RATE: float = 0.001

# 年化换算使用的年交易日数与无风险利率。
TRADING_DAYS_PER_YEAR: int = 252
RISK_FREE_RATE: float = 0.0


class Backtester:
    """股债配置组合的回测引擎。

    Attributes:
        cost_rate: 单边交易成本费率，默认 10bp。
    """

    def __init__(self, cost_rate: float = COST_RATE) -> None:
        """初始化回测引擎。

        Args:
            cost_rate: 单边交易成本费率（小数），默认 0.001（10bp）。
        """
        self.cost_rate = float(cost_rate)

    def run(
        self,
        prices: pd.DataFrame,
        strategy: Strategy,
        signals: pd.DataFrame,
    ) -> pd.DataFrame:
        """执行回测，返回逐日净值与权重序列。

        处理流程：

        1. 依据月末信号，构建 ``next_trade_date -> 目标股票权重`` 映射；
        2. 以首个信号日的目标权重作为初始仓位；
        3. 逐日先让仓位随当日涨跌漂移，再判断是否调仓（调仓日执行再平衡并
           扣减交易成本）。

        Args:
            prices: 对齐后的价格表（``trade_date``、``equity_close``、
                ``bond_close``）。
            strategy: 目标配置策略。
            signals: 月末信号表（``signal_date``、``next_trade_date``）。

        Returns:
            逐日 DataFrame，列含 ``trade_date``、``nav``、
            ``equity_weight``、``bond_weight``。
        """
        # 1) 构建调仓日 -> 目标股票权重映射。
        rebalance_weights: dict[pd.Timestamp, float] = {}
        for _, row in signals.iterrows():
            signal_date = pd.Timestamp(row["signal_date"])
            next_date = pd.Timestamp(row["next_trade_date"])
            rebalance_weights[next_date] = float(
                strategy.equity_weight(signal_date, prices)
            )

        # 2) 日频数据准备。
        dates = pd.to_datetime(prices["trade_date"]).tolist()
        equity_close = prices["equity_close"].to_numpy(dtype=float)
        bond_close = prices["bond_close"].to_numpy(dtype=float)
        equity_ret = np.log(equity_close[1:] / equity_close[:-1])
        bond_ret = np.log(bond_close[1:] / bond_close[:-1])

        # 3) 初始仓位：首个信号日的目标权重。
        first_signal_date = pd.Timestamp(signals["signal_date"].iloc[0])
        weight_equity = float(strategy.equity_weight(first_signal_date, prices))

        # 4) 逐日循环。
        n_days = len(dates)
        nav = 1.0
        nav_records = np.empty(n_days)
        weight_records = np.empty(n_days)

        for i in range(n_days):
            if i == 0:
                nav_records[i] = nav
                weight_records[i] = weight_equity
                continue

            # 4.1) 仓位随当日涨跌自然漂移。
            equity_gross = np.exp(equity_ret[i - 1])
            bond_gross = np.exp(bond_ret[i - 1])
            gross_return = weight_equity * equity_gross + (1.0 - weight_equity) * bond_gross
            nav *= gross_return
            weight_equity_drift = weight_equity * equity_gross / gross_return

            # 4.2) 若为调仓日，则按目标权重再平衡并扣减交易成本。
            date = dates[i]
            if date in rebalance_weights:
                target_weight = rebalance_weights[date]
                turnover = abs(target_weight - weight_equity_drift)
                transaction_cost = 2.0 * self.cost_rate * turnover
                nav *= (1.0 - transaction_cost)
                weight_equity = target_weight
            else:
                weight_equity = weight_equity_drift

            nav_records[i] = nav
            weight_records[i] = weight_equity

        return pd.DataFrame(
            {
                "trade_date": dates,
                "nav": nav_records,
                "equity_weight": weight_records,
                "bond_weight": 1.0 - weight_records,
            }
        )


def compute_metrics(
    nav_df: pd.DataFrame,
    nav_column: str = "nav",
    date_column: str = "trade_date",
) -> dict[str, float]:
    """计算组合的标准化绩效指标。

    指标包括：年化收益率、年化波动率、夏普比率（无风险利率为 0）、
    最大回撤（正值表示回撤幅度）、Calmar 比率、月度胜率。

    Args:
        nav_df: 含净值与日期的 DataFrame。
        nav_column: 净值列名，默认 ``nav``。
        date_column: 日期列名，默认 ``trade_date``。

    Returns:
        以指标中文名为键、数值为值的字典。
    """
    nav = nav_df[nav_column].to_numpy(dtype=float)
    dates = pd.to_datetime(nav_df[date_column])

    daily_ret = np.diff(np.log(nav))
    n_periods = len(daily_ret)

    # 年化收益率（几何年化）。
    annualized_return = float(
        (nav[-1] / nav[0]) ** (TRADING_DAYS_PER_YEAR / n_periods) - 1.0
    ) if n_periods > 0 else float("nan")

    # 年化波动率。
    daily_vol = float(np.std(daily_ret, ddof=1)) if n_periods > 1 else float("nan")
    annualized_vol = daily_vol * np.sqrt(TRADING_DAYS_PER_YEAR)

    # 夏普比率（无风险利率 0）。
    sharpe = annualized_return / annualized_vol if annualized_vol > 0 else float("nan")

    # 最大回撤（正值幅度）。
    cummax = np.maximum.accumulate(nav)
    drawdown = nav / cummax - 1.0
    max_drawdown = float(-np.min(drawdown))

    # Calmar 比率。
    calmar = annualized_return / max_drawdown if max_drawdown > 0 else float("nan")

    # 月度胜率：按月分组，收益为正的月份占比。
    monthly = (
        nav_df[[date_column, nav_column]]
        .assign(year_month=dates.dt.strftime("%Y-%m"))
        .groupby("year_month")[nav_column]
        .agg(["first", "last"])
    )
    monthly_returns = monthly["last"] / monthly["first"] - 1.0
    monthly_win_rate = float((monthly_returns > 0).mean())

    return {
        "年化收益率": annualized_return,
        "年化波动率": annualized_vol,
        "夏普比率": sharpe,
        "最大回撤": max_drawdown,
        "Calmar比率": calmar,
        "月度胜率": monthly_win_rate,
    }
