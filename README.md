# Financial Data Analysis Group Assignment

本仓库为 2026 年秋《金融数据分析导论》第 12 小组作业项目。Assignment 1 研究中国权益市场、债券市场及股债配置，以沪深 300 和上证国债指数为核心资产，其他指数用于比较和稳健性检验。

## 小组成员

- 数学科学学院 2023 级 李彦臻
- 数学科学学院 2024 级 毛志远
- 数学科学学院 2024 级 霍彬然
- 数学科学学院 2024 级 李俊涛

## 当前进度

| 模块 | 内容 | 状态 |
|---|---|---|
| 模块 1 | 数据下载、DuckDB 入库、清洗与质量校验 | 已完成 |
| 模块 2 | 权益收益分布、滚动指标、股债相关性与事件分析 | 任务口径已确定，待实现 |
| 模块 3 | Nelson–Siegel、久期凸性、压力测试与利率敏感度 | 任务口径已确定，待实现 |
| 模块 4 | 股债配置、回测、成本与稳健性 | 待实现 |
| 模块 5 | 研究报告、局限性与分工声明 | 待实现 |

## 仓库结构

```text
GroupAssignment_FinancialDataAnalysis/
├── Assignment1/
│   ├── data/
│   │   ├── data.duckdb
│   │   ├── data_config.py
│   │   ├── download_and_ingest.py
│   │   ├── clean_data.py
│   │   ├── validate_data.py
│   │   ├── cleaning_summary.json
│   │   ├── validation_results.json
│   │   ├── 数据说明.md
│   │   └── 数据质量报告.md
│   └── 任务说明.md
├── docs/
│   ├── GitHub协作说明.md
│   └── 技术栈说明.md
├── utils/
│   └── findata_lib.py
├── requirements.txt
└── requirements_full.txt
```

模块 2—4 实现后，分析代码、图表和结果分别放入 `Assignment1/analysis/`、`Assignment1/figures/` 和 `Assignment1/output/`。

## 环境

项目统一使用上层课程目录中的虚拟环境。在项目根目录执行：

```bash
source ../.venv/bin/activate
```

如需重新安装核心依赖：

```bash
python -m pip install -r requirements.txt
```

`requirements.txt` 为项目核心依赖，`requirements_full.txt` 为完整环境快照。

## 模块 1 运行方式

数据库已经生成，一般无需重复下载。需要更新数据时，在项目根目录依次执行：

```bash
python Assignment1/data/download_and_ingest.py
python Assignment1/data/clean_data.py
python Assignment1/data/validate_data.py
```

生成的数据库为 `Assignment1/data/data.duckdb`。当前数据获取日为 2026-10-18，最新交易日为 2026-10-16。

## 文档

- [Assignment 1 后续任务说明](Assignment1/任务说明.md)
- [数据说明](Assignment1/data/数据说明.md)
- [数据质量报告](Assignment1/data/数据质量报告.md)
- [技术栈说明](docs/技术栈说明.md)
- [GitHub 协作说明](docs/GitHub协作说明.md)

## 输出约定

- 数据与模型结果从 DuckDB 或可复现的分析代码生成，不手工修改结果文件。
- 所有图表使用 Plotly；交互结果输出为离线 HTML，报告静态图由 Plotly 导出。
- 日期统一使用 `YYYY-MM-DD`，收益率和利率在计算中使用小数口径，展示时转换为百分比。
- 同一资产在不同模块中使用一致的名称和颜色。
