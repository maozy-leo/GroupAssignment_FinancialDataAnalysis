# 模块2：权益分析代码说明

`part12_analysis.py` 实现收益分布、正态性检验、滚动波动率和权益指数间滚动相关。其余文件按职责分层，实现股债相关性时变与 2024 年脉冲行情。

| 文件 | 职责 |
|---|---|
| `part12_analysis.py` | 模块2第1—2部分的计算、Plotly 图和 CSV 输出 |
| `config.py` | 第3—4部分的常量、资产名称、配色、路径和结果数据类 |
| `repository.py` | 只读 DuckDB 查询与数据边界校验（含 2018 年预热行） |
| `market.py` | 120 日滚动相关、分年度相关、2022—2024 区间统计、2024 脉冲行情 |
| `charts.py` | 3 张 Plotly 图（SVG + PNG）、单文件离线 HTML |
| `outputs.py` | 7 张 CSV 结果表与 Markdown 报告 |
| `part34_analysis.py` | 第3—4部分计算流程编排与命令行入口 |

依赖方向固定：入口调用数据层与分析层，图表与输出层只消费结果；分析函数不写文件，数据库访问不混入计算逻辑。

运行：

```bash
python Assignment1/analysis/equity/part12_analysis.py
python Assignment1/analysis/equity/part34_analysis.py
```

CSV、Markdown 和交互 HTML 输出到 `Assignment1/output/equity/`，静态图输出到 `Assignment1/figures/module2/`。

关键计算口径：

- 日对数收益率 $r_t=\ln(P_t/P_{t-1})$，年化按 252 个交易日；
- 滚动相关使用共同交易日样本，窗口 120 个观测，窗口不完整时不输出；
- 2022—2024 区间固定为 2022-01-01 至 2024-12-31；
- 2024 脉冲窗口为 2024-09-20 至 2024-10-08，共 8 个交易日，组合净值按 $0.6\,P/P_0+0.4\,B/B_0$ 且区间内不再平衡。
