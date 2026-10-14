# Financial Data Analysis Group Assignment

北京大学《金融数据分析导论》2026 秋季学期小组作业协作仓库。

本项目面向一笔“五年后到期、目标稳健增值”的资金，研究中国股票与债券市场的收益风险特征，并比较固定 60/40、风险平价和目标日期等股债配置方案。

## 项目结构

```text
.
├── Assignment1/              # 第一次小组作业：代码、提案和报告
├── utils/
│   └── findata_lib.py        # 仅访问真实在线数据的数据接口
├── GitHub协作说明.md          # Git/GitHub 协作流程与代码规范
├── README.md
└── requirements_full.txt
```

## 环境与数据原则

- Python 3.11；依赖版本见 `requirements_full.txt`。
- 原始数据自 2018-01-01 起获取，正式分析自 2019-01-01 起进行。
- 分析数据统一整理至 DuckDB，但数据库和原始数据不直接提交到 Git。
- 数据接口失败时必须显式报错，禁止使用模拟数据代替真实市场数据。
- 图表统一使用 Plotly。

## 主要交付物

- 可顺序运行的 Jupyter Notebook；
- 可复现的数据获取和 DuckDB 建库流程；
- Markdown/PDF 研究报告；
- 小组分工与 AI 工具使用声明。

详细研究计划见 `Assignment1/proposal.md`，协作方式见 `GitHub协作说明.md`。
