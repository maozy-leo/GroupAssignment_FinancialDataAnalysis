# 模块3：固定收益分析

从项目根目录运行：

```bash
../.venv/bin/python Assignment1/analysis/fixed_income/fixed_income_analysis.py
```

代码按七个明确职责组织：

- `config.py`：常量、路径和共享结果数据类；
- `repository.py`：所有只读 DuckDB 查询与数据边界校验；
- `curve.py`：NS 曲线、零息债风险、压力测试和凸性归因；
- `market.py`：单因子回归和滚动久期；
- `charts.py`：全部 Plotly 图表和 SVG；
- `html_report.py`：将方法、结果表、分析文字和交互图整合为单文件 HTML 报告；
- `outputs.py`：CSV 结果表；
- `fixed_income_analysis.py`：计算流程编排与命令行入口。

依赖方向固定为：入口调用数据与分析层，图表和输出层只消费结果；
分析代码不写文件，数据库访问也不会混入计算函数。

脚本只通过 SQL 读取 `Assignment1/data/data.duckdb`，并生成：

- `Assignment1/output/fixed_income/module3_fixed_income_dashboard.html`：包含任务流程、公式、结果表、分析文字和交互图的单文件离线报告；
- `Assignment1/output/fixed_income/`：HTML 报告和 CSV 结果表；
- `Assignment1/figures/module3/`：模块 3 的 Plotly SVG 静态图。

Nelson–Siegel 拟合使用五组初值和 `scipy.optimize.minimize`；目标函数按常数缩放以改善数值优化，但输出 SSE、RMSE 和残差均为原始小数收益率口径。回归为带截距 OLS，标准误采用 Newey–West HAC，最大滞后阶数为 5。
