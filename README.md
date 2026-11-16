# Financial Data Analysis Group Assignment

本仓库为 2026 年秋《金融数据分析导论》第 12 小组作业项目。Assignment 1 研究中国权益市场、固定收益及股债配置，包含数据库快照、分析代码、回测结果、Markdown 报告和交互式 HTML 展示。

主回测以沪深 300 和上证国债指数为核心资产，比较七类策略；其他权益指数、企债指数和政金债 ETF 用于资产替换检验。数据库日频数据覆盖 2018-01-02—2026-10-16，2018 年用于主回测预热，正式主回测区间为 2019-01-02—2026-10-16。

## 成果入口

| 内容 | 入口 |
|---|---|
| 综合项目报告 | [项目报告](Assignment1/output/项目报告.md) |
| 交互式展示 | [项目展示 HTML](Assignment1/output/项目展示.html)；下载完整仓库后在本地浏览器查看 |
| 详细复现说明 | [Assignment 1 README](Assignment1/README.md) |
| 数据来源、字段与质量 | [数据说明](Assignment1/data/数据说明.md)、[数据质量报告](Assignment1/data/数据质量报告.md) |

项目报告第 6 章为稳健性检验，第 7 章为讨论与局限性。HTML 正文保留各项检验的方法和主要结论，详细表格、交互图与数值注释默认收起，点击展开。

## 小组成员

- 数学科学学院 2023 级 李彦臻
- 数学科学学院 2024 级 毛志远
- 数学科学学院 2024 级 霍彬然
- 数学科学学院 2024 级 李俊涛

## 模块与成果

| 模块 | 内容 | 成果 |
|---|---|---|
| 模块 1 | 数据获取、DuckDB 入库、清洗与质量校验 | [数据说明及表结构](Assignment1/data/数据说明.md) |
| 模块 2 | 权益收益分布、滚动指标、股债相关性与事件分析 | [第 1—2 部分报告](Assignment1/output/equity/模块2_第1-2部分_报告.md)、[第 3—4 部分报告](Assignment1/output/equity/模块2_第3-4部分_报告.md) |
| 模块 3 | Nelson–Siegel 曲线、久期凸性、压力测试与利率敏感度 | [固定收益分析报告](Assignment1/output/fixed_income/模块3_固定收益分析报告.md)、[交互仪表板](Assignment1/output/fixed_income/module3_fixed_income_dashboard.html) |
| 模块 4 | 七类配置策略、净值与回撤、五种稳健性检验 | [股债配置分析报告](Assignment1/output/asset_allocation/模块4_分析报告.md)、[净值图](Assignment1/figures/module4/nav_comparison.html)、[回撤图](Assignment1/figures/module4/drawdown_comparison.html) |
| 综合报告 | 研究方法、结果、稳健性、讨论与局限性、分工声明 | [项目报告](Assignment1/output/项目报告.md)、[项目展示](Assignment1/output/项目展示.html) |

七类策略包括全股、全债、固定 60/40、风险平价、滚动最小方差、波动率目标与目标日期；其中后五种为股债配置策略。

## 仓库结构

```text
GroupAssignment_FinancialDataAnalysis/
├── Assignment1/
│   ├── data/
│   │   ├── data.duckdb               # 数据库快照
│   │   ├── download_and_ingest.py    # 数据获取与入库
│   │   ├── clean_data.py             # 清洗与去重
│   │   ├── validate_data.py          # 数据质量校验
│   │   ├── 数据说明.md
│   │   └── 数据质量报告.md
│   ├── analysis/
│   │   ├── equity/                  # 权益分析
│   │   ├── fixed_income/            # 固定收益分析
│   │   └── asset_allocation/        # 配置策略、回测与稳健性
│   ├── figures/
│   │   ├── module2/
│   │   ├── module3/
│   │   └── module4/
│   ├── output/
│   │   ├── equity/                  # 权益结果表、图表与报告
│   │   ├── fixed_income/            # 固收结果表、图表与报告
│   │   ├── asset_allocation/        # 净值、检验结果与报告
│   │   ├── assets/                  # 本地公式、字体和交互脚本
│   │   ├── 项目报告.md
│   │   └── 项目展示.html
│   ├── README.md                    # 详细运行与复现说明
│   └── 任务说明.md
├── docs/
│   ├── GitHub协作说明.md
│   └── 技术栈说明.md
├── utils/
│   └── findata_lib.py
├── requirements.txt
└── requirements_full.txt
```

## 环境配置

使用 Python 3.11，以下命令均在仓库根目录执行。首次配置环境：

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

若上层课程目录已有统一环境，也可使用 `source ../.venv/bin/activate`。`requirements.txt` 为核心依赖，`requirements_full.txt` 为完整环境快照。重新导出静态图需要 Kaleido 及可用的 Chromium/Chrome；直接查看仓库中的现成报告无需重新导图。

## 查看 HTML 展示

下载完整仓库后，在根目录启动本地服务：

```bash
python -m http.server 8000 --bind 127.0.0.1 --directory Assignment1
```

浏览器访问 [项目展示](http://127.0.0.1:8000/output/项目展示.html)。页面使用本地 Plotly、KaTeX、字体及相对路径资源；查看时请保留完整目录结构。也可以直接打开 `Assignment1/output/项目展示.html`，使用本地服务可兼容浏览器对本地文件及内嵌图的访问限制。

## 复现分析

仓库已包含数据库快照，一般无需重新下载数据。基于快照校验并重算各模块：

```bash
python Assignment1/data/validate_data.py

python Assignment1/analysis/equity/part12_analysis.py
python Assignment1/analysis/equity/part34_analysis.py

python Assignment1/analysis/fixed_income/fixed_income_analysis.py

python Assignment1/analysis/asset_allocation/run_backtest.py
```

`run_backtest.py` 会生成七类策略的净值、回撤图和全部五种稳健性检验结果。随后运行：

```bash
python Assignment1/analysis/asset_allocation/robustness_report.py
```

该报告脚本同步模块四报告、项目报告的回测与讨论章节，以及 HTML 的稳健性与讨论部分。报告文字围绕当前数据库快照编写；若更新数据区间，应同时复核文字中的数值和结论。

### 稳健性检验与结果文件

| 方法 | 覆盖范围 | 结果 |
|---|---|---|
| 参数敏感性 | 九组参数、28 个情景，逐项改变窗口、权重约束、波动率目标及滑降参数 | [参数结果](Assignment1/output/asset_allocation/parameter_sensitivity.csv) |
| 资产替换 | 六组长样本资产对、十二组共同短样本资产对，均覆盖七类策略，共 126 个情景 | [资产替换结果](Assignment1/output/asset_allocation/asset_substitution_results.csv) |
| 信号日期 | 月中与月末对照，七类策略、14 个情景，统一截至 2026-09-30 | [信号日期结果](Assignment1/output/asset_allocation/signal_timing_results.csv) |
| 调仓频率 | 五种配置策略的月度／季度对照，共 10 个情景，包含目标日期策略 | [频率及成本结果](Assignment1/output/asset_allocation/robustness_results.csv) |
| 交易成本 | 七类策略分别采用单边 0／10／30bp，共 21 个情景，其中五种配置策略为 15 个 | [频率及成本结果](Assignment1/output/asset_allocation/robustness_results.csv) |

仅需重算参数、资产替换和信号日期三项时，可单独运行：

```bash
python Assignment1/analysis/asset_allocation/robustness.py
```

### 更新原始数据

需要联网重新获取数据时，依次执行：

```bash
python Assignment1/data/download_and_ingest.py
python Assignment1/data/clean_data.py
python Assignment1/data/validate_data.py
```

数据库写入 `Assignment1/data/data.duckdb`。仓库快照的数据获取日为 2026-10-18；重新下载后应再运行分析、报告脚本并核对结果。

## 测试与计算口径

运行配置策略与信号逻辑测试：

```bash
python -m unittest discover \
  -s Assignment1/analysis/asset_allocation \
  -p 'test_*.py' -v
```

- 分析模块通过只读连接访问 DuckDB；跨资产比较按共同日期对齐，不填补缺失报价。
- 资产日收益采用对数收益率，年化按 252 个交易日换算；回测年化收益按净值几何增长计算。
- 默认月末收盘后形成信号，下一交易日收盘调仓；期间权重自然漂移，默认单边成本为 10bp，不加杠杆。
- Sharpe 沿用几何年化收益除以对数收益年化波动率、无风险利率为 0 的口径。价格指数低波动可能放大 Sharpe，相关数值说明见报告。
- 资产替换使用不同长度的共同样本，月中／月末对照也单独截取完整月份；具体区间以结果表和报告说明为准。

## 文档

- [Assignment 1 任务说明](Assignment1/任务说明.md)
- [Assignment 1 运行与复现说明](Assignment1/README.md)
- [数据说明](Assignment1/data/数据说明.md)
- [数据质量报告](Assignment1/data/数据质量报告.md)
- [技术栈说明](docs/技术栈说明.md)
- [GitHub 协作说明](docs/GitHub协作说明.md)

## 输出约定

- 数据与模型结果从 DuckDB 或可复现的分析代码生成，不手工修改结果文件。
- 分析图表使用 Plotly；交互 HTML 及依赖资源随仓库提供，报告静态图保存在 `Assignment1/figures/`。
- 日期统一使用 `YYYY-MM-DD`，收益率和利率在计算中使用小数口径，展示时转换为百分比。
- 同一资产在不同模块中使用一致的名称和颜色。
