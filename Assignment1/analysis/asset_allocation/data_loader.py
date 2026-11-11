"""Module 4 数据准备：股债配置与回测的数据读取与对齐。

本模块通过 DuckDB 只读连接读取 Assignment1 数据库中的 ``index_daily``
与 ``trading_calendar`` 两张表，为模块 4（股债配置与回测）提供数据底座：

* 沪深 300 与上证国债指数日线价格的按交易日对齐（内连接）；
* 月末信号日与次日调仓执行日的提取（基于真实交易日历，防前视偏差）；
* 每日对数收益率计算。

数据访问统一通过 DuckDB 只读连接，不绕过数据库直接调用下载接口；数据库
路径基于本文件位置自动解析，因此无论从项目根目录还是任意子目录执行，
都能正确找到 ``data.duckdb``。
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

import duckdb
import numpy as np
import pandas as pd

# 数据库文件相对本模块的位置固定为 Assignment1/data/data.duckdb。
# 本文件位于 Assignment1/analysis/asset_allocation/ 下，
# 因此向上两级（parents[2]）即为 Assignment1 目录。
DATABASE_PATH: Final[Path] = (
    Path(__file__).resolve().parents[2] / "data" / "data.duckdb"
)

# 股债配置主资产：沪深 300（权益）与上证国债指数（债券）。
EQUITY_ASSET_ID: Final[str] = "CSI300"
BOND_ASSET_ID: Final[str] = "SSE_TREASURY"

# 对齐后价格表与收益率表使用的列名。
EQUITY_PRICE_COLUMN: Final[str] = "equity_close"
BOND_PRICE_COLUMN: Final[str] = "bond_close"
EQUITY_RETURN_COLUMN: Final[str] = "equity_log_return"
BOND_RETURN_COLUMN: Final[str] = "bond_log_return"


class AssetAllocationDataLoader:
    """封装股债配置模块的数据读取与对齐逻辑。

    通过 DuckDB 只读连接读取 ``index_daily`` 与 ``trading_calendar``，
    提供价格对齐、月末信号提取、对数收益率计算等方法。

    Attributes:
        db_path: 只读访问的 DuckDB 数据库路径。

    Example:
        >>> loader = AssetAllocationDataLoader()
        >>> prices = loader.load_aligned_prices()
        >>> signals = loader.extract_month_end_signals(prices)
    """

    def __init__(self, db_path: str | Path | None = None) -> None:
        """初始化数据读取器。

        Args:
            db_path: DuckDB 数据库路径。若为 None，则基于本文件位置自动解析
                到 ``Assignment1/data/data.duckdb``。
        """
        self.db_path: Path = Path(db_path) if db_path is not None else DATABASE_PATH

    # ------------------------------------------------------------------
    # 底层数据读取
    # ------------------------------------------------------------------
    def load_index_daily(self, asset_id: str) -> pd.DataFrame:
        """读取单个资产在 ``index_daily`` 表中的日线收盘价。

        Args:
            asset_id: 资产标识（如 ``CSI300``、``SSE_TREASURY``）。

        Returns:
            两列 DataFrame：``trade_date``（升序）与 ``close``。
        """
        query = """
            SELECT trade_date, close
            FROM index_daily
            WHERE asset_id = ?
            ORDER BY trade_date
        """
        with duckdb.connect(str(self.db_path), read_only=True) as conn:
            df = conn.execute(query, [asset_id]).fetchdf()
        df["trade_date"] = pd.to_datetime(df["trade_date"])
        return df

    def get_trading_calendar(self) -> pd.DataFrame:
        """读取 ``trading_calendar`` 表中的全部交易日。

        Returns:
            单列 DataFrame：``trade_date``（升序）。
        """
        query = "SELECT trade_date FROM trading_calendar ORDER BY trade_date"
        with duckdb.connect(str(self.db_path), read_only=True) as conn:
            df = conn.execute(query).fetchdf()
        df["trade_date"] = pd.to_datetime(df["trade_date"])
        return df

    # ------------------------------------------------------------------
    # 数据对齐
    # ------------------------------------------------------------------
    def load_aligned_prices(
        self,
        equity_asset_id: str = EQUITY_ASSET_ID,
        bond_asset_id: str = BOND_ASSET_ID,
    ) -> pd.DataFrame:
        """读取权益与债券资产日线并按 ``trade_date`` 内连接对齐。

        内连接确保只保留两个资产均有价格的共同交易日，供后续收益率计算与
        信号生成使用，避免因交易日不一致产生的 NaN 对齐。

        Args:
            equity_asset_id: 权益资产标识，默认 ``CSI300``。
            bond_asset_id: 债券资产标识，默认 ``SSE_TREASURY``。

        Returns:
            按 ``trade_date`` 升序的 DataFrame，包含列：
            ``trade_date``、``equity_close``、``bond_close``。
        """
        equity = self.load_index_daily(equity_asset_id).rename(
            columns={"close": EQUITY_PRICE_COLUMN}
        )
        bond = self.load_index_daily(bond_asset_id).rename(
            columns={"close": BOND_PRICE_COLUMN}
        )
        merged = (
            pd.merge(equity, bond, on="trade_date", how="inner")
            .sort_values("trade_date")
            .reset_index(drop=True)
        )
        return merged

    # ------------------------------------------------------------------
    # 收益率计算
    # ------------------------------------------------------------------
    def compute_log_returns(self, prices: pd.DataFrame) -> pd.DataFrame:
        """计算对齐价格序列的每日对数收益率。

        对数收益率定义为 :math:`r_t = \\ln(P_t / P_{t-1})`，对每个价格列独立
        计算，首行因无前值而为 NaN。

        Args:
            prices: ``load_aligned_prices`` 返回的对齐价格表，需包含
                ``equity_close`` 与 ``bond_close`` 两列。

        Returns:
            包含 ``trade_date``、``equity_log_return``、``bond_log_return``
            的 DataFrame，与输入同序。
        """
        returns = prices[["trade_date"]].copy()
        returns[EQUITY_RETURN_COLUMN] = np.log(
            prices[EQUITY_PRICE_COLUMN] / prices[EQUITY_PRICE_COLUMN].shift(1)
        )
        returns[BOND_RETURN_COLUMN] = np.log(
            prices[BOND_PRICE_COLUMN] / prices[BOND_PRICE_COLUMN].shift(1)
        )
        return returns

    # ------------------------------------------------------------------
    # 周期末信号提取（防前视偏差）
    # ------------------------------------------------------------------
    def _extract_period_end_signals(
        self,
        prices: pd.DataFrame,
        freq: str,
    ) -> pd.DataFrame:
        """提取周期末信号日与对应的次日调仓执行日（通用实现）。

        信号在每个周期的最后一个交易日收盘后生成，实际调仓在下一个交易日
        执行，从而避免前视偏差。周期末判定基于 ``trading_calendar`` 中的真实
        交易日，而非自然月末/季末（后者可能落在周末或节假日）。

        处理规则：

        * 每个周期取其日历中的最后一个交易日作为 ``signal_date``；
        * ``next_trade_date`` 为 ``signal_date`` 在日历中的下一个交易日；
        * 若 ``signal_date`` 之后不存在交易日（即数据截止于该周期），则该
          周期尚未完整，予以剔除，不生成信号。

        Args:
            prices: ``load_aligned_prices`` 返回的对齐价格表。
            freq: 周期频率，``"M"`` 表示月末、``"Q"`` 表示季末。

        Returns:
            按 ``signal_date`` 升序的 DataFrame，包含列：
            ``period``、``signal_date``、``next_trade_date``、
            ``equity_close``、``bond_close``。
        """
        calendar = self.get_trading_calendar()
        # 将日历限制在对齐价格覆盖的区间内。
        start = prices["trade_date"].min()
        end = prices["trade_date"].max()
        calendar = calendar[
            (calendar["trade_date"] >= start) & (calendar["trade_date"] <= end)
        ].copy()

        # 每个交易日对应的下一个交易日（用于确定调仓执行日）。
        calendar = calendar.sort_values("trade_date").reset_index(drop=True)
        calendar["next_trade_date"] = calendar["trade_date"].shift(-1)

        # 周期标签：月 "YYYY-MM" 或季 "YYYY-Qn"。
        if freq == "M":
            calendar["period"] = calendar["trade_date"].dt.strftime("%Y-%m")
        elif freq == "Q":
            quarter = (calendar["trade_date"].dt.month - 1) // 3 + 1
            calendar["period"] = (
                calendar["trade_date"].dt.year.astype(str)
                + "-Q"
                + quarter.astype(str)
            )
        else:
            raise ValueError(f"不支持的周期频率: {freq!r}（应为 'M' 或 'Q'）")

        # 每个周期的最后一个交易日 = 周期末信号日。
        period_ends = (
            calendar.groupby("period", as_index=False)["trade_date"]
            .max()
            .rename(columns={"trade_date": "signal_date"})
        )

        # 关联信号日的下一个交易日。
        signals = pd.merge(
            period_ends,
            calendar[["trade_date", "next_trade_date"]],
            left_on="signal_date",
            right_on="trade_date",
            how="left",
        ).drop(columns=["trade_date"])

        # 剔除无下一个交易日的周期（数据截止的最后一个不完整周期）。
        signals = signals.dropna(subset=["next_trade_date"])

        # 关联信号日的两资产收盘价。
        signals = pd.merge(
            signals,
            prices[["trade_date", EQUITY_PRICE_COLUMN, BOND_PRICE_COLUMN]],
            left_on="signal_date",
            right_on="trade_date",
            how="left",
        ).drop(columns=["trade_date"])

        return signals.sort_values("signal_date").reset_index(drop=True)

    def extract_month_end_signals(self, prices: pd.DataFrame) -> pd.DataFrame:
        """提取月末信号日与对应的次日调仓执行日。

        Args:
            prices: ``load_aligned_prices`` 返回的对齐价格表。

        Returns:
            按 ``signal_date`` 升序的 DataFrame，包含列：
            ``period``、``signal_date``、``next_trade_date``、
            ``equity_close``、``bond_close``。
        """
        return self._extract_period_end_signals(prices, freq="M")

    def extract_quarter_end_signals(self, prices: pd.DataFrame) -> pd.DataFrame:
        """提取季末信号日与对应的次日调仓执行日。

        Args:
            prices: ``load_aligned_prices`` 返回的对齐价格表。

        Returns:
            按 ``signal_date`` 升序的 DataFrame，包含列：
            ``period``、``signal_date``、``next_trade_date``、
            ``equity_close``、``bond_close``。
        """
        return self._extract_period_end_signals(prices, freq="Q")
