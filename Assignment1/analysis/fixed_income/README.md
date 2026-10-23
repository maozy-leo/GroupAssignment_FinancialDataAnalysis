# 模块3：固定收益分析

从项目根目录运行：

```bash
../.venv/bin/python Assignment1/analysis/fixed_income/fixed_income_analysis.py
```

代码按七个明确职责组织：

- `config.py`：常量、路径和共享结果数据类；
- `repository.py`：所有只读 DuckDB 查询与数据边界校验；
- `curve.py`：NS 曲线、零息债风险、压力测试、凸性归因和负债匹配；
- `market.py`：单因子回归、滚动久期、收益率 PCA 和关键期限暴露；
- `charts.py`：全部 Plotly 图表、SVG 和单文件 HTML；
- `outputs.py`：CSV 表格和 Markdown 报告；
- `report_template.md`：只包含报告版式与文字，不混入计算代码；
- `fixed_income_analysis.py`：计算流程编排与命令行入口。

依赖方向固定为：入口调用数据与分析层，图表和输出层只消费结果；
分析代码不写文件，数据库访问也不会混入计算函数。

脚本只通过 SQL 读取 `Assignment1/data/data.duckdb`，并生成：

- `Assignment1/output/fixed_income/module3_fixed_income_dashboard.html`：包含全部交互图的单个离线 HTML；
- `Assignment1/output/fixed_income/`：CSV 结果表和结果解读；
- `Assignment1/figures/module3/`：模块 3 的 Plotly SVG 静态图。

Nelson–Siegel 拟合使用五组初值和 `scipy.optimize.minimize`；目标函数按常数缩放以改善数值优化，但输出 SSE、RMSE 和残差均为原始小数收益率口径。回归为带截距 OLS，标准误采用 Newey–West HAC，最大滞后阶数为 5。
