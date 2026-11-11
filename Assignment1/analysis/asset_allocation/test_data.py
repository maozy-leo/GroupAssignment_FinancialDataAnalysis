"""Module 4 数据准备测试：验证数据对齐与月末信号逻辑。

运行方式（在项目根目录执行）：

    python Assignment1/analysis/asset_allocation/test_data.py

本脚本实例化 :class:`data_loader.AssetAllocationDataLoader`，完成以下验证：

1. 打印沪深 300 与上证国债指数按交易日内连接对齐后的总行数；
2. 提取并打印最近 5 个月的月末信号日与对应次日调仓执行日，直观校验
   节假日顺延逻辑是否正确；
3. 打印两资产在信号日的对数收益率前几行。
"""

from __future__ import annotations

from data_loader import AssetAllocationDataLoader


def main() -> None:
    """执行数据对齐与月末信号逻辑的测试。"""
    loader = AssetAllocationDataLoader()

    # 1. 读取并对齐两资产价格，检查总行数。
    prices = loader.load_aligned_prices()
    print("=" * 66)
    print("1) 合并对齐后的总行数")
    print(f"   对齐后总行数: {len(prices)}")
    print(
        f"   日期范围: {prices['trade_date'].min().date()} ~ "
        f"{prices['trade_date'].max().date()}"
    )
    print()

    # 2. 计算每日对数收益率。
    returns = loader.compute_log_returns(prices)

    # 3. 提取月末信号日与次日调仓执行日。
    signals = loader.extract_month_end_signals(prices)
    print("=" * 66)
    print("2) 最近 5 个月的月末信号日与次日调仓执行日")
    print(f"   {'信号日(月末最后交易日)':<22} ->   调仓执行日(次日)")
    for _, row in signals.tail(5).iterrows():
        print(
            f"   {str(row['signal_date'].date()):<22} ->   "
            f"{row['next_trade_date'].date()}"
        )
    print()

    # 4. 打印两资产在信号日的收益率前几行。
    print("=" * 66)
    print("3) 两资产在信号日的对数收益率（前几行）")
    signal_returns = returns.merge(
        signals[["signal_date"]],
        left_on="trade_date",
        right_on="signal_date",
        how="inner",
    ).drop(columns=["signal_date"])
    print(signal_returns.head().to_string(index=False))


if __name__ == "__main__":
    main()
