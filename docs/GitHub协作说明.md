# GitHub 协作说明

## 1. 基本流程

1. 每项任务从最新主分支创建独立分支；
2. 在自己的分支中完成代码、结果和文档；
3. 提交前运行相关脚本并检查生成结果；
4. 推送分支并创建 Pull Request；
5. 至少由另一名组员检查后合并，不直接在主分支上开发。

推荐分支名称：

- `feature/module2-equity`；
- `feature/module3-fixed-income`；
- `feature/module4-backtest`；
- `docs/report`；
- `fix/简短问题描述`。

提交信息使用简短动词开头，例如：

- `Add equity return diagnostics`；
- `Implement Nelson-Siegel fitting`；
- `Update data quality report`；
- `Fix monthly rebalance lag`。

## 2. 文件协作约定

- `Assignment1/data/data.duckdb` 是二进制文件，同一时间只由一名组员更新；其他成员只读使用，避免无法合并的二进制冲突。
- 原始数据更新必须依次运行下载、清洗和校验脚本，并同时提交对应 JSON 结果和数据文档。
- 分析代码放在 `Assignment1/analysis/`，图表放在 `Assignment1/figures/`，HTML和结果表放在 `Assignment1/output/`。
- 不提交 `.DS_Store`、`__pycache__`、虚拟环境、临时日志或 DuckDB WAL 文件。
- 不覆盖其他成员尚未合并的修改；发生冲突时先确认双方修改目的，再人工合并。
- 代码、图表和报告中的资产名称、时间区间及计算口径必须与 `Assignment1/任务说明.md` 一致。

## 3. Pull Request 检查清单

- [ ] 代码可以在课程虚拟环境中运行；
- [ ] 数据通过 SQL 从 DuckDB 读取；
- [ ] 未引入前视偏差或未说明的缺失值填充；
- [ ] 统计口径、单位和年化方法已写清；
- [ ] 图表使用 Plotly，标题、坐标轴、图例和单位完整；
- [ ] 新增函数具有必要的类型注解和 docstring；
- [ ] 结果文件可由代码重新生成；
- [ ] README 或模块文档已同步更新。

## 4. 常用 Git 命令

```bash
# 获取主分支最新修改
git switch main
git pull --ff-only

# 创建任务分支
git switch -c feature/module2-equity

# 查看和提交修改
git status --short
git diff
git add Assignment1 README.md docs
git commit -m "Add equity return diagnostics"

# 推送并建立上游分支
git push -u origin feature/module2-equity
```

合并其他修改前，先提交或暂存自己的工作。不要使用 `git reset --hard` 或强制推送处理共享分支。

## 5. Agent 提示词规范

推荐将下述内容作为 coding agent 的项目指令，以统一代码风格。不同工具的设置位置可能不同；Codex 可在项目 `AGENTS.md` 或自定义指令中配置。


当你需要编写 python 代码时，请严格遵循以下规范。优先保证代码的可读性、可维护性、可复用性和一致性。

### 5.1 逻辑规范

- 优先采用面向对象的方式组织具有明确状态、职责或生命周期的业务逻辑；简单工具逻辑无需强行封装为类。
- 遵循单一职责原则，一个函数只完成一个相对独立的语义功能，避免在单个函数中混合数据读取、预处理、计算、后处理、保存等多个复杂阶段。
- 可独立描述、重复使用或具有明确业务含义的逻辑，应抽象为独立函数、方法或类。
- 避免过度封装，不要为了减少函数行数而拆分没有独立语义的代码。
- 尽量减少深层嵌套，优先使用 early return、guard clause 等清晰的控制流。
- 优先复用已有代码，不重复实现相同逻辑，不进行与当前需求无关的重构。

### 5.2 书写规范

- 整体遵循 PEP 8，并优先采用简洁、清晰的 Pythonic 写法。
- 函数内部不同语义块之间空 **1 行**；同级函数、类之间空 **2 行**；明显独立的大型语义区域之间可空 **3 行**。
- 运算符、赋值符两侧保留一个空格；逗号后保留一个空格；括号内部不要添加无意义空格。
- 当函数定义或调用的参数 **超过 3 个**时，使用多行格式：左括号后换行，每行一个参数，右括号单独一行，并保留 trailing comma。
- 避免过长的单行表达式；复杂表达式应合理换行。
- 优先使用 f-string、comprehension、enumerate、zip、with、dataclass 等 Pythonic 写法，但不要为了简短而降低可读性。

### 5.3 类型与命名规范

- 函数参数、返回值及重要变量原则上都应提供明确的类型注解。
- 对 `Tensor`、`ndarray` 等多维数据，除数据类型外，应在类型注解、docstring 或邻近注释中明确其 **shape 及各维度含义**，例如 `[batch_size, channels, height, width]`。
- 当 shape 会发生变化时，应明确输入和输出 shape 的对应关系。
- 变量、函数使用 `snake_case`，类使用 `PascalCase`，常量使用 `UPPER_SNAKE_CASE`。
- 命名必须表达实际语义，避免 `tmp`、`data1`、`foo`、`obj`、`res` 等含义模糊的名称。
- 布尔变量优先使用 `is_`、`has_`、`can_`、`should_` 等前缀。
- 集合变量通常使用复数形式，单个对象使用单数形式。

### 5.4 函数与 Docstring 规范

除极简单的内部辅助函数外，函数应提供 docstring，至少说明：

1. **主要功能**：函数解决什么问题以及核心行为。
2. **Args**：每个输入参数的含义、类型、格式；对于 Tensor / Array，应注明 shape、dtype 以及各维度含义。
3. **Returns**：返回值的含义、类型、格式；对于 Tensor / Array，应注明输出 shape。
4. **Raises（可选）**：可能主动抛出的主要异常。
5. **Notes（可选）**：特殊约束、单位、坐标系、数值范围、算法假设、副作用等额外说明。

推荐格式：

```python
def normalize_images(
    images: torch.Tensor,
    mean: torch.Tensor,
    std: torch.Tensor,
) -> torch.Tensor:
    """Normalize a batch of images channel-wise.

    Args:
        images: Input images with shape [B, C, H, W], dtype float32.
        mean: Channel means with shape [C].
        std: Channel standard deviations with shape [C].

    Returns:
        Normalized images with shape [B, C, H, W].

    Raises:
        ValueError: If the channel dimensions do not match.

    Notes:
        Input pixel values are expected to be in [0, 1].
    """
```

函数一般应对关键输入进行必要的类型、shape、范围或合法性检查，尤其是公共接口和数据处理边界。检查应针对可能导致错误或产生隐蔽结果的条件，避免对内部已确定的数据进行大量重复检查。

错误信息应明确指出参数名称、期望条件和实际情况，例如：

```python
if images.ndim != 4:
    raise ValueError(
        f"Expected 'images' to have 4 dimensions [B, C, H, W], "
        f"but got shape {tuple(images.shape)}."
    )
```

### 5.5 注释规范

- 注释主要解释“为什么这样做”、特殊约束和非显然逻辑，而不是重复代码本身已经表达的内容。
- 复杂算法、特殊 shape 变换、数值稳定性处理、兼容性逻辑等应提供必要说明。
- 不添加无意义或显而易见的注释。

生成代码后，请自行检查上述规范并修正明显不符合要求的内容，再输出最终代码。
