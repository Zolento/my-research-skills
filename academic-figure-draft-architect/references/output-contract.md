# 输出契约（十段式 + 机器可校验条件）

draft 是一份 Markdown 文档。本文件定义**段落顺序、表格列名、取值域**与
`scripts/check_draft.py` 的**校验条件**。三处必须同值：本文件 ↔ 脚本 ↔ `templates/`。

## 0. 段落总表

| # | 段落标题（H2，关键词大小写不敏感） | 必需 | 机器校验 |
|---|---|---|---|
| 1 | `Figure Understanding` | ✅ | 存在性 |
| 2 | `Evidence Summary` | ✅ | 存在性 + 表格列 + Confidence 枚举 |
| 3… | `Draft A — <visual grammar>`（`B`、`C`…，共 `NUM_DRAFTS` 份） | ✅ ≥2 份 | 每份都要有 `text` 字符图 + 合法 grammar |
| 末份前 | `Recommended Draft` | ✅ | 存在性 + 明确写出 `Recommended: Draft <X>` |
| 7 | `Alignment Notes` | ✅ | 存在性 + 每个元素表 ID 至少被提到一次 |
| 8 | `Uncertainties` | ✅（可写"无"） | 存在性 |
| 9 | `SVG Handoff Notes` | ✅ | 存在性 |
| 10 | `Figure Element Inventory` | ✅ | 表格列 + ID 唯一 + 引用可解析 + Status 枚举 |

标题允许前缀编号（`## 3. Draft A — Iterative Loop`）与中英混写，脚本按
**关键词包含**匹配；但**不建议改关键词本身**（改了脚本会判缺段）。

## 1. Figure Understanding（5–12 行）

只写：输入、输出、核心计算路径、训练关系、inference 关系、核心贡献。
**不复述整篇论文**，不写相关工作，不写实验数字。

## 2. Evidence Summary

```markdown
| Figure element | Evidence | Confidence |
|---|---|---|
| Flow prior | `models/flow.py::FlowNet` | High |
| DC update | `solver.py::dc_step()` | High |
| Alternating reconstruction | `Algorithm 1` | High |
| Structural guidance | `Sec. 3.2` | Medium |
| Encoder sharing | `[未在材料中定位]` | Low |
```

**列名（必须全部出现，顺序不限）：** `Figure element`（或 `Element`）、`Evidence`、`Confidence`。

**取值域：** `Confidence` ∈ `{High, Medium, Low}`（封闭）。首行是表头，数据行 ≥1。
**`Low` 行必须在 `Uncertainties` 里有对应条目。**

## 3. Draft `<A|B|C|D|E> — <visual grammar>`

固定结构：

```markdown
## 3. Draft A — Iterative Loop

> 设计意图：一句话说明这份 draft 想强调什么（例：强调完整 inference pipeline，
> 并把核心贡献放在视觉中心）。

```text
<字符图>
```

**Best for:** Method overview figure / 主论文 Fig. 2 / …

**Strength:** …

**Weakness:** …
```

**grammar 取值域（封闭，取自 [visual-grammar.md](visual-grammar.md)，标题里必须能匹配到其一）：**

```
Linear Pipeline
Dual / Multi Branch
Hierarchical System
Iterative Loop
Train vs Inference
Data / Model / Objective
Source / Target Domain
Temporal / Stage View
```

**校验条件：**

- 每份 draft 至少含 **1 个 `text` fenced code block**（字符图）；**Mermaid 只能作为附加**，
  不能替代字符图。
- **各 draft 的 grammar 必须互不相同**；全文不同 grammar 数 **≥2**，否则判"假多样性"。
- `Best for` / `Strength` / `Weakness` 三段应齐（缺失为警告）。

## 4. Recommended Draft

```markdown
**Recommended: Draft B**

Why:
1. 最清楚地突出论文贡献
2. training / inference 不容易混淆
3. SVG 转换后容易形成视觉层级
4. 箭头较少
5. 对双栏论文缩放更友好
```

**必须明确写出 `Recommended: Draft <X>`**（脚本按此模式校验）。
**不得因为某个 draft "更复杂"就推荐它。**

## 5. Alignment Notes

把图中主要视觉元素与代码 / 论文对应，用树状或表均可：

```text
┌ Flow Prior
└── models/flow.py::FlowModel

┌ Data Consistency
├── solver.py::gradient_step()
└── Eq. (8)
```

**规则：**

1. **`Figure Element Inventory` 的每个 ID 都必须在这里被提到**（形式：`N1` / `N2`…）。
2. 引用的 ID 必须存在于元素表（悬空 ID = 契约违规）。
3. **语义聚合必须显式声明**：
   `"Data Consistency" is a semantic abstraction of: Aᴴ(Ax−y) + gradient update.`
4. 源码名 → 论文名的映射也写在这里：`Flow Prior ↔ self.model`。

## 6. Uncertainties

```text
Uncertain:
- 材料不能确认 encoder 是否与 prior 共享参数（U1）。
- Eq. (9) 看起来仅用于训练，但 inference.py 尚未确认（U2）。
```

每条形如 `- <内容>（U<k>）`；`U<k>` 编号唯一。
**不得把不确定项偷偷解决掉。** 无不确定项时写 `无`。

## 7. SVG Handoff Notes

给下游绘图代理的视觉建议，**不生成 SVG**：

```text
Canvas:                  landscape
Primary flow:            left → right
Suggested visual groups: source pretraining / target adaptation / reconstruction
Visual emphasis:         Structural Post-training (中心，最重色)
Secondary elements:      measurement operator / frozen source checkpoint（弱化）
Line semantics:          solid = inference-forward；dashed = training supervision；dotted = optional/conceptual
Styling hierarchy:       Level 1 = domain/stage container；Level 2 = major module；Level 3 = operator/loss
Color grouping:          …
De-emphasize:            …
Center node:             …
Curved arrows:           …
Inset candidates:        …
```

建议覆盖 8 项：画布、主流向、视觉分组、视觉强调、次要元素、线型语义、样式层级、
可弱化 / 可放中心 / 可弯曲 / 可做 inset 的元素。

## 8. Figure Element Inventory

```markdown
| ID | Type | Label | Group | Inputs | Outputs | Status |
|---|---|---|---|---|---|---|
| N1 | data | Measurement y | Inference | — | N3 | observed |
| N2 | model | Flow Prior | Prior | z,t | v | observed · frozen |
| N3 | operator | DC Step | Solver | x,y | N4 | observed |
| N4 | operator | Prior Step | Solver | N3,N2 | N5 | observed |
```

**列名（必须全部出现，顺序不限）：** `ID`、`Type`、`Label`、`Group`、`Inputs`、`Outputs`、`Status`。

| 字段 | 取值域 | 说明 |
|---|---|---|
| `ID` | `^N\d+$`，文档内唯一 | 只登记**已经在图中出现**的节点 |
| `Type` | `data` / `model` / `operator` / `state` / `objective` / `parameter` / `supervision` / `output` | 与 [figure-semantics.md](figure-semantics.md) §1 一致 |
| `Label` | 论文语义名称 | **不得用源码变量名** |
| `Group` | stage / 视觉分组名 | 与 SVG Handoff 的分组一致 |
| `Inputs` / `Outputs` | `—`（空）或逗号分隔的 ID 列表 | 每个 ID 必须存在（悬空 = 违规） |
| `Status` | `observed` / `abstraction` + 可选 ` · frozen`、` · trainable`、` · train-only`、` · inference-only`、` · optional`、` · semantic` | 见 [evidence-policy.md](evidence-policy.md) §3 |

**校验条件：**

- 数据行 ≥1；ID 唯一；`Type` 与 `Status` 在取值域内。
- `Inputs` / `Outputs` 中的 ID 必须存在。
- **每个 ID 必须在 `Alignment Notes` 出现**（保证可追溯）。
- **D 级没有 Status**：`inferred` 之类不是合法值（契约违规）。
  材料不足的内容写成 `Uncertainties` 条目，或在图内用 `[? label]` 占位并同时列入
  `Uncertainties`——**占位标记不是元素，不占 ID、不进本表**。
- 不为完整性虚构节点：**只登记图中已有的元素**。

---

## 9. 机器校验：`scripts/check_draft.py`

```bash
python3 scripts/check_draft.py <draft.md> [<draft2.md> ...]
python3 scripts/check_draft.py --strict --forbid "Cross Attention" --require "Flow Prior" <draft.md>
python3 scripts/check_draft.py --json <draft.md>
```

| 检查 | 级别 |
|---|---|
| 必需段落缺失；`Recommended: Draft X` 缺失 | 错误 |
| Draft 段缺 `text` 字符图；grammar 无法匹配 | 错误 |
| 各 draft grammar 重复 / 不同 grammar < 2 | 错误 |
| Evidence Summary 列缺失 / Confidence 非枚举 | 错误 |
| 元素表列缺失 / ID 非法或重复 / Type、Status 非法 / 悬空 ID | 错误 |
| 元素表 ID 未出现在 Alignment Notes | 错误 |
| `Status` 首字段为 `inferred`（D 级不得进入正式 draft） | 错误 |
| `--forbid` 命中 / `--require` 未命中 | 错误 |
| 字符图 `[? ...]` 未在 Uncertainties 出现 | 警告 |
| 框上下边界显示宽度不一致（含**并排框**）/ 框右边界不齐 / `┌` 同行缺 `┐` / 找不到闭合的 `└` | 警告（`--strict` 下为错误） |
| Draft 缺 `Best for` / `Strength` / `Weakness`；Evidence Summary 无数据行 | 警告 |

**`--forbid` 的扫描范围 = 「图的内容」，不是整篇文档：**
只扫 **`text` fenced 字符块** + **Evidence Summary 表** + **Figure Element Inventory 表**。
**正文段落不扫**——draft 必须能公开声明"我把哪些内容排除在图外"
（`MUST_NOT_INCLUDE` 声明、`Uncertainties` 里点名被排除的模块），
否则"声明不画"和"偷偷画了"无法区分。
`--require` 则相反：扫**整篇文档**（它检查的是"该出现的东西有没有被覆盖到"）。

**关于并排框：** 左右并排的两个框必须**各自**闭合，不得共用一个 `└`。
框**内部**用于树状分叉的 `└`（如 `├ [n]` / `└ [n]`）不是角字符，不参与配对。

**对齐校验算法（供实现者照做，避免误报）：**

1. 显示宽度：`unicodedata.east_asian_width(ch) in ("W","F")` → 2，否则 1。
   先把每行转成 `{显示列: 字符}` 的映射，后续一律按列比较。
2. 对每个含 `┌` 的行 `i`：取 `c1` = `┌` 的显示列；取 `c2` = **`c1` 右侧最近的** `┐`
   的显示列（不是整行最后一个 `┐`——否则并排框会互相干扰）。缺 `┐` ⇒ 警告。
3. 向下的第一个 `└` 显示列等于 `c1` 的行 `j` 即该框的闭合行（找不到 ⇒ 警告），
   且要求该行在显示列 `c2` 上的字符是 `┘`。
4. 对 `i < k < j` 的每一行：若该行在列 `c1` 是 `│`，则**必须**在列 `c2` 也是 `│`，
   否则警告"框右边界不齐"。列 `c1` 不是 `│` 的行是分叉 / 箭头行，跳过。
5. **不要**用「整行角字符计数配平」做判断——并排框与框内树状 `└` 都会误报。

| 退出码 | 含义 |
|---|---|
| `0` | 通过 |
| `1` | 用法 / 文件错误 |
| `2` | 仅有警告 |
| `3` | 存在契约违规 |

**脚本只校验形式契约，不校验科学正确性。** 语义忠实性由
[SKILL.md §8](../SKILL.md) 自检清单负责。
