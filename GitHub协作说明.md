# GitHub 协作说明

本文规定本项目的 GitHub 协作流程、提交规范、代码评审方式和 Python 编码要求。三位成员开始工作前都应阅读本文。

## 1. 协作原则

1. `main` 始终保持可运行，不直接在 `main` 上开发。
2. 每项工作先建立 Issue，再建立独立分支，通过 Pull Request 合并。
3. 一个 Pull Request 只解决一个相对独立的问题，避免混入无关重构。
4. 至少由另一位成员完成代码评审后再合并。
5. 数据、图表和结论应可复现；接口失败时不得用模拟数据伪装成功。
6. 不向仓库提交口令、Token、Cookie、`.env`、大型原始数据或本地虚拟环境。

## 2. 推荐分支模型

仓库只长期保留 `main`。开发分支从最新的 `main` 创建，合并后删除。

分支命名格式：

```text
类型/简短任务名
```

推荐类型：

| 类型 | 用途 | 示例 |
|---|---|---|
| `feat` | 新功能或新分析 | `feat/data-pipeline` |
| `fix` | 修复错误 | `fix/look-ahead-bias` |
| `docs` | 文档与报告 | `docs/assignment1-report` |
| `refactor` | 不改变结果的代码整理 | `refactor/backtest-engine` |
| `test` | 测试和质量检查 | `test/data-validation` |

不要使用 `final`、`new`、`test1`、成员姓名等无法说明任务的分支名。

## 3. 标准协作流程

### 3.1 创建 Issue

Issue 至少写明：

- 背景和目标；
- 预期交付物；
- 数据口径或关键假设；
- 完成标准；
- 负责人和截止时间。

较大的任务拆成多个 Issue。例如“完成回测”应拆为回测引擎、绩效指标、交易成本和稳健性检验。

### 3.2 同步主分支并创建开发分支

```bash
git switch main
git pull --ff-only origin main
git switch -c feat/data-pipeline
```

`--ff-only` 可以避免一次普通拉取意外生成无意义的合并提交。

### 3.3 小步提交

一次提交应当能够用一句话准确描述，并尽量保持可运行。提交前执行：

```bash
git status
git diff
python -m compileall .
```

只暂存本次任务相关文件：

```bash
git add path/to/file.py path/to/notebook.ipynb
git diff --cached
git commit -m "feat: add equity index download pipeline"
```

不推荐在没有检查的情况下长期使用 `git add .`。

### 3.4 Commit message 规范

采用下面的格式：

```text
<type>: <imperative summary>
```

常用 `type`：

- `feat`：新增功能或分析；
- `fix`：修复错误；
- `docs`：文档修改；
- `refactor`：结构整理但不改变行为；
- `test`：新增或调整测试；
- `chore`：依赖、配置或其他维护工作。

示例：

```text
feat: add ChinaBond yield curve ingestion
fix: shift monthly allocation signal by one trading day
docs: document DuckDB table definitions
```

避免使用 `update`、`修改代码`、`final version` 等信息不足的提交说明。

### 3.5 推送并创建 Pull Request

```bash
git push -u origin feat/data-pipeline
```

Pull Request 应包含：

- 做了什么以及为什么；
- 数据源、样本区间和口径变化；
- 如何验证；
- 关键图表或结果截图；
- 尚未解决的问题；
- 关联 Issue，例如 `Closes #12`。

推荐使用 Squash and merge，使 `main` 上每个 Pull Request 对应一个清晰提交。

### 3.6 代码评审

评审者重点检查：

- 是否存在前视偏差、幸存者偏差或收益率单位错误；
- 月末信号是否在下一交易日执行；
- 股票和债券日期是否正确对齐；
- 是否将百分数和小数混用；
- 是否对缺失值、重复值和异常值作出明确处理；
- 图表和报告结论是否由实际结果支持；
- 公共函数是否有类型注解、docstring 和输入检查；
- Notebook 是否可以从头到尾顺序运行。

提出修改意见时说明原因和期望结果，不只写“这里不对”。作者修改后再次请求评审。

## 4. 冲突与同步

开发期间定期同步 `main`：

```bash
git fetch origin
git rebase origin/main
```

发生冲突时：

1. 打开冲突文件，理解双方改动；
2. 删除 `<<<<<<<`、`=======`、`>>>>>>>` 标记并保留正确内容；
3. 重新运行相关代码或 Notebook；
4. 执行 `git add <file>` 和 `git rebase --continue`；
5. 已推送过的个人分支使用 `git push --force-with-lease`，不要使用裸 `--force`。

不要用 `git checkout --`、`git reset --hard` 或删除文件来“解决”不理解的冲突。

## 5. Notebook 协作约定

Notebook 的 JSON 结构容易产生冲突，因此：

1. 同一 Notebook 同一时间只安排一位主要编辑者；
2. 可复用计算优先放入 `.py` 模块，Notebook 主要负责组织分析和展示；
3. 合并前重启内核并从头运行全部单元；
4. 删除调试单元、绝对路径和无关大输出；
5. 保留最终必要图表，但避免提交体积很大的交互缓存；
6. 随机算法必须固定种子并解释用途；本项目的市场数据不得模拟生成。

## 6. 数据文件协作

- `data/raw/`、`data/interim/`、`*.duckdb` 和 `outputs/` 默认不进入 Git。
- 数据获取脚本、SQL 建表语句、字段字典和质量报告必须进入 Git。
- 每次数据快照记录抓取时间、来源、起止日期和记录数。
- 需要提交给课程的 DuckDB 在最终交付阶段单独生成并核验。
- 如果数据库超过 GitHub 普通文件限制，使用共享云盘或 GitHub Release，不把大文件强行写入 Git 历史。
- 任何真实密钥放入本地 `.env`，仓库只提供 `.env.example`。

## 7. 发布和版本标记

形成可讨论版本或最终提交版本时，在 `main` 上创建标签：

```bash
git switch main
git pull --ff-only origin main
git tag -a v0.1-discussion -m "Assignment 1 discussion version"
git push origin v0.1-discussion
```

最终版本可使用 `v1.0-assignment1`。标签前应确认 Notebook 可运行、数据库可复现、报告已生成且成员互相复核。

## 附录 A：Git/GitHub 基本命令

### 初次配置

```bash
git config --global user.name "Your Name"
git config --global user.email "your-email@example.com"
gh auth login
```

### 克隆和查看状态

```bash
git clone <repository-url>
cd GroupAssignment_FinancialDataAnalysis
git status
git log --oneline --graph --decorate -10
```

### 分支操作

```bash
git branch
git switch main
git switch -c feat/example
git branch -d feat/example
```

### 查看和提交修改

```bash
git diff
git diff --cached
git add path/to/file
git commit -m "feat: describe the change"
git push -u origin feat/example
```

### 撤销尚未提交的局部修改

先查看差异，再使用交互方式选择要撤销的片段：

```bash
git diff
git restore -p path/to/file
```

如果修改已经提交并进入共享分支，使用 `git revert <commit>` 创建反向提交，不改写公共历史。

### GitHub CLI 常用命令

```bash
gh issue list
gh issue create
gh pr create
gh pr view --web
gh pr checks
```

## 附录 B：推荐给代码助手的系统提示词

下面的提示词用于本项目的 Python 代码生成和审查，可复制到 Codex 或其他代码助手。具体任务要求优先于本提示词。

```text
你正在为金融数据分析课程项目编写 Python。优先保证代码的可读性、可维护性、可复用性、一致性和研究结果的可复现性。

1. 具有明确状态、职责或生命周期的业务逻辑优先使用面向对象设计；简单工具逻辑使用函数即可。遵循单一职责，数据读取、清洗、计算、后处理和保存应保持清晰边界。避免过度封装和深层嵌套，优先使用 guard clause。

2. 遵循 PEP 8。同一函数中的不同语义块空一行，同级函数和类之间空两行。运算符两侧留空格。函数定义或调用超过 3 个参数时使用多行格式，每行一个参数并保留 trailing comma。避免过长表达式和模糊缩写。

3. 函数参数、返回值和重要变量提供明确类型注解。Tensor 或 ndarray 必须在类型注解、docstring 或邻近注释中说明 dtype、shape 和各维含义，以及 shape 变化关系。函数和变量使用 snake_case，类使用 PascalCase，常量使用 UPPER_SNAKE_CASE；布尔值优先使用 is_、has_、can_ 或 should_ 前缀。

4. 除极简单的内部辅助函数外，函数必须提供 docstring，至少包含主要功能、Args 和 Returns；必要时增加 Raises 和 Notes。公共接口需要检查可能造成错误或隐蔽结果的类型、shape、范围和合法性。错误信息必须包含参数名、期望条件和实际值。

5. 注释解释原因、约束、数值稳定性、shape 变换或兼容逻辑，不重复代码本身。

6. 金融数据接口失败时显式报错，不返回模拟数据。所有收益率明确百分数、小数或 bp 单位。回测信号必须避免前视偏差，交易成本和日期对齐方式必须在代码或文档中说明。

7. 优先复用现有实现，不重复代码，不进行与当前任务无关的重构。生成代码后自行检查上述要求，运行适当的语法检查和测试，再提交结果。
```

## 附录 C：Pull Request 检查清单

- [ ] 关联了 Issue，范围单一且描述清楚；
- [ ] 没有密钥、本地路径、大型数据和临时输出；
- [ ] 代码通过语法检查和相关测试；
- [ ] Notebook 可以重启内核后顺序运行；
- [ ] 数据来源、日期和单位有记录；
- [ ] 无模拟市场数据和静默失败；
- [ ] 无前视偏差，调仓日期和交易成本实现正确；
- [ ] 图表使用 Plotly，结论与结果一致；
- [ ] 公共接口包含类型注解、docstring 和必要输入检查；
- [ ] 至少一名其他成员完成评审。
