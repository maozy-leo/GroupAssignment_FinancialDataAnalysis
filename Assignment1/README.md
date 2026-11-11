# Assignment 1 运行与复现说明

本目录包含第一次小组作业的完整数据、分析代码、图表和报告。项目以沪深 300 和上证国债指数为核心资产，完成数据工程、权益分析、固定收益分析以及股债配置回测。

## 1. 分析口径

- 原始数据区间：2018-01-02 至 2026-10-16；
- 正式分析与回测区间：2019-01-01 至最新共同交易日；
- 2018 年数据仅用于 60、120 和 252 日滚动窗口预热；
- 日收益率采用对数收益率 $r_t=\ln(P_t/P_{t-1})$；
- 年化收益与波动率按 252 个交易日换算；
- 跨资产分析按共同交易日内连接；
- 分析代码只读访问 `data/data.duckdb`；
- 月末配置策略在月末收盘后产生信号，并在下一交易日调仓；
- 回测默认采用单边 10bp 交易成本。

## 2. 目录与代码结构

```text
Assignment1/
├── README.md                         # 本文档
├── 任务说明.md                        # 项目内部统一口径
├── data/                             # 模块1：数据工程
│   ├── data_config.py                # 资产清单、日期和数据库路径
│   ├── download_and_ingest.py        # 下载并写入 DuckDB
│   ├── clean_data.py                 # 清洗、去重和合法性处理
│   ├── validate_data.py              # SQL 校验和异常行情检查
│   ├── data.duckdb                   # 可复现分析数据库
│   ├── cleaning_summary.json         # 清洗统计
│   ├── validation_results.json       # 自动校验明细
│   ├── 数据说明.md                    # 表结构、字段与数据来源
│   └── 数据质量报告.md                # 样本覆盖、缺失和异常核验
├── analysis/
│   ├── equity/                       # 模块2：权益市场分析
│   │   ├── part12_analysis.py        # 收益分布、JB 检验与滚动指标
│   │   ├── part34_analysis.py        # 股债相关性与2024脉冲行情入口
│   │   ├── config.py                 # 第3—4部分常量、路径和数据类
│   │   ├── repository.py             # DuckDB 只读查询
│   │   ├── market.py                 # 相关性和事件分析
│   │   ├── charts.py                 # Plotly 图表与离线 HTML
│   │   ├── outputs.py                # CSV 与 Markdown 报告
│   │   └── export_figures.py         # 第1—2部分静态图兼容导出脚本
│   ├── fixed_income/                 # 模块3：固定收益分析
│   │   ├── fixed_income_analysis.py  # 模块入口
│   │   ├── config.py                 # 参数、路径和结果数据类
│   │   ├── repository.py             # 曲线、利率和债券指数查询
│   │   ├── curve.py                  # NS、久期、凸性和压力测试
│   │   ├── market.py                 # 利率敏感度与滚动隐含久期
│   │   ├── charts.py                 # Plotly 图表与 SVG
│   │   ├── html_report.py            # 单文件交互式仪表板
│   │   └── outputs.py                # CSV 结果表
│   └── asset_allocation/             # 模块4：股债配置与回测
│       ├── run_backtest.py           # 回测、图表与稳健性入口
│       ├── data_loader.py            # 股债价格与调仓信号读取
│       ├── strategies.py             # 七类配置策略
│       ├── backtester.py             # 权重漂移、成本和绩效指标
│       ├── test_data.py              # 数据与信号检查脚本
│       └── test_strategies.py        # 策略单元测试
├── figures/
│   ├── module2/                      # 权益分析静态图
│   ├── module3/                      # 固收分析 Plotly SVG
│   └── module4/                      # 配置净值与回撤交互 HTML
└── output/
    ├── equity/                       # 权益 CSV、独立交互图和分模块报告
    ├── fixed_income/                 # 固收 CSV、独立交互图和分模块报告
    ├── asset_allocation/             # 策略净值、稳健性和报告
    ├── 项目报告.md                    # 按作业要求整合的项目报告
    └── 项目展示.html                  # 纵向滚动的交互式项目展示
```

项目根目录的 `utils/findata_lib.py` 提供课程统一数据接口；`requirements.txt` 为核心依赖，`requirements_full.txt` 为完整环境快照。

## 3. 环境配置

推荐使用 Python 3.11。在项目根目录执行：

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

课程目录已经存在统一环境时，也可以直接使用：

```bash
source ../.venv/bin/activate
```

Plotly 静态导出依赖 Kaleido 及可用的 Chromium/Chrome。若本机无法导出 SVG 或 PNG，仍可运行全部计算并生成交互 HTML；仓库也已经包含生成好的静态图。

## 4. 推荐复现方式

以下命令均从仓库根目录 `GroupAssignment_FinancialDataAnalysis/` 执行。

### 4.1 使用仓库内数据库复现

该方式无需联网，也是最稳定的复现路径：

```bash
python Assignment1/data/validate_data.py

python Assignment1/analysis/equity/part12_analysis.py
python Assignment1/analysis/equity/part34_analysis.py

python Assignment1/analysis/fixed_income/fixed_income_analysis.py

python Assignment1/analysis/asset_allocation/run_backtest.py
```

运行顺序说明：

1. 数据校验确认数据库表、日期和异常行情满足要求；
2. 权益模块分别运行第1—2部分和第3—4部分；
3. 固收模块读取同一数据库并生成模型结果与仪表板；
4. 配置模块读取沪深 300 和上证国债指数，生成七类策略回测结果。

### 4.2 从数据获取开始完整重建

更新数据需要网络和可用的数据接口：

```bash
python Assignment1/data/download_and_ingest.py
python Assignment1/data/clean_data.py
python Assignment1/data/validate_data.py
```

数据更新完成后，再按 4.1 节顺序运行模块2—4。外部接口可能更新历史数据或暂时不可用，因此重新下载后的结果可能与仓库快照存在小幅差异。

## 5. 测试与校验

运行配置策略单元测试：

```bash
python -m unittest discover \
  -s Assignment1/analysis/asset_allocation \
  -p 'test_*.py' -v
```

运行数据与月末信号检查：

```bash
python Assignment1/analysis/asset_allocation/test_data.py
```

建议同时检查：

- `Assignment1/data/validation_results.json` 中不存在 `FAIL`；
- 生成的净值均为正，股债权重均在 $[0,1]$；
- 报告中的相对图片和结果链接均可打开；
- 更新依赖版本后重新核对数值和 Plotly 页面。

## 6. 主要输出

- 数据质量：[数据质量报告](./data/数据质量报告.md)
- 权益分析：[第1—2部分报告](./output/equity/模块2_第1-2部分_报告.md)、[第3—4部分报告](./output/equity/模块2_第3-4部分_报告.md)
- 固收分析：[模块3报告](./output/fixed_income/模块3_固定收益分析报告.md)、[交互仪表板](./output/fixed_income/module3_fixed_income_dashboard.html)
- 配置回测：[模块4报告](./output/asset_allocation/模块4_分析报告.md)、[净值对比](./figures/module4/nav_comparison.html)、[回撤对比](./figures/module4/drawdown_comparison.html)
- 综合成果：[项目报告](./output/项目报告.md)、[项目展示](./output/项目展示.html)

## 7. 查看 HTML presentation

直接双击 HTML 可以查看大部分内容。为确保浏览器允许交互图的相对路径和 `iframe` 加载，推荐从项目根目录启动本地服务器：

```bash
python -m http.server 8000 --directory Assignment1
```

然后访问：

```text
http://127.0.0.1:8000/output/项目展示.html
```

展示页面采用上下滚动阅读，顶部导航可跳转至各模块；内嵌 Plotly 图表可悬停、缩放和重置坐标。

## 8. 复现注意事项

- `data.duckdb` 是本次提交的确定性数据快照，正式结果以该文件为准；
- HTML 文件均可离线使用，但重新运行时 Plotly 可能生成不同的内部元素 ID，不影响图表数据；
- 科创 50 从 2020 年开始，政金债 ETF 从 2023 年开始，仅在各自可得区间参与分析；
- 上证国债指数和上证企债指数为指数点位，政金债使用前复权 ETF 价格代理；
- 回测没有使用未来数据，但结果仍受样本区间、资产代理和参数选择影响。
