# 证据层级与措辞政策（唯一权威定义）

本 Skill **只有一个**「证据等级 ↔ 能进图什么 / 不能进图什么」的权威定义，就是本文件。
SKILL.md、各 reference、模板与脚本一律引用本文件，**不再各自重复定义**。

## 1. 四级证据

| 等级 | 名称 | 含义 | 能否进主图 | 图后必须交代什么 |
|---|---|---|---|---|
| **A** | Directly Observed | 代码 / 论文里**直接存在**：类、函数、tensor operation、loss term、equation、solver step、network block、branch、concat、skip、iterative update | ✅ 可以 | 出处（`file.py::symbol()` 或 `Sec. / Eq. / Alg.`） |
| **B** | Strongly Implied | 没有单独命名，但**从计算过程可确定存在**（例：`x = x - eta*grad; x = denoiser(x)` ⇒ Data-consistency step + Prior/denoising step） | ✅ 可以 | 出处 + **显式标注 `semantic abstraction`** |
| **C** | Author-Level Interpretation | 为论文表达，对多个底层操作做**合理聚合**（例：`FFT → mask → residual → IFFT → gradient update` 归并为 `Data Consistency`） | ✅ 可以，但必须保证**聚合不改变算法含义** | 聚合前后的逐项对应；不得隐藏关键分支 |
| **D** | Speculative | 材料不足以确认 | ❌ **不得画成确定事实** | 只能写进 `Uncertainties`，或图内以 `[? ...]` 标记并同时列入 `Uncertainties` |

**来源标注（与等级正交）：**

| 来源 | 标注格式 | 例 |
|---|---|---|
| 代码 | `<file>::<symbol>()` 或 `<file>:L<a>-L<b>` | `solver.py::dc_step()` |
| 论文 | `Sec. 3.2` / `Eq. (7)` / `Algorithm 1` / `Fig. 2 caption` / `Appendix B` | `Eq. (8)` |
| 用户 | `[user]`（对应 `KNOWN_FACTS`） | `[user] source-free 是硬约束` |
| 未能定位 | `[未在材料中定位]`（**必须同时进 `Uncertainties`**） | `[未在材料中定位]` + `(U2)` |

> **没有 `[inferred]` 这种来源标注。** D 级内容不是图中的元素，因此既没有 `Status`、
> 也不进元素表；它只能出现在 `Uncertainties`，或在图内以 `[? label]` 占位。

**置信度取值域（Evidence Summary 的 `Confidence` 列，封闭枚举）：**

| 值 | 判据 |
|---|---|
| `High` | 单一来源直接可核（A 级代码 / 论文原文） |
| `Medium` | B/C 级聚合、或需要跨多个文件/章节拼接 |
| `Low` | 单薄证据、版本不确定、或与另一来源冲突（**必须同时进 Uncertainties**） |

## 2. 使用规则（强制）

1. **先定等级，再决定画什么。** 不确定属于哪一级时，按**更保守**的一级处理。
2. **D 级不得进入正式 draft 的主结构。** 它不得出现在任何 draft 的字符图里作为确定模块；
   必须写进 `Uncertainties`。图内确有必要时只允许 `[? label]` 形式，且**同一 label 必须
   在 `Uncertainties` 出现**。
3. **C 级必须自证聚合合法性**：在 Alignment Notes 里写出被聚合的底层操作清单。
   如果聚合会掩盖"训练独有的分支"或"冻结与否"，则**不得聚合**。
4. **禁止推断式补全**：材料没写的模块不得因为"论文图通常有"而出现。典型违规清单（除非
   材料支持，一律禁止）：

   ```
   Feature Extractor     Cross Attention     Alignment Module    Fusion Block
   Semantic Encoder      Contrastive Loss    Consistency Loss    Refinement Network
   Adapter               Projection Head     Prompt Encoder      Memory Bank
   ```

   这些名字不是绝对禁止——**是"无依据时禁止"**。有依据时必须能给出出处。
5. **假设不得写成结论。** motivation / hypothesis 类内容以 `[?]` 或 "hypothesis" 标注，
   不得与 A 级事实并列成同一视觉权重。
6. **未核实内容不得进入 Evidence Summary 的 High 行**；与 `Low` 绑定的证据必须同时
   出现在 `Uncertainties`。
7. **每条证据独立可核**：Evidence Summary 的每一行都要能被第三方按出处复查。
   无法复查的（例如"我记得这篇论文是这样的"）**一律标 `Low` + `Uncertainties`**。
8. **不得臆造引用**：文件、函数、章节、公式号都必须真实存在于输入材料中；
   不确定就写 `[未在材料中定位]` 并进 Uncertainties。

## 3. 与元素表 `Status` 的对照（脚本会校验）

`Figure Element Inventory` 的 `Status` 列以**证据等级**为首字段，允许追加状态限定词：

| Status 首字段 | 对应等级 | 允许的限定词（`·` 连接） |
|---|---|---|
| `observed` | A | `frozen` / `trainable` / `train-only` / `inference-only` / `optional` |
| `abstraction` | B 或 C | 同上 + `semantic` |

例：`observed · frozen`、`observed · inference-only`、`abstraction · semantic`。
**首字段只有这两个值；非法值 = 契约违规（退出码 3）。**

**D 级不进元素表。** 它没有 Status —— 因为它**不是图中的元素**：

- 图内确有必要时，只允许 `[? label]` **占位标记**（不是框、不是箭头、不是元素），
  且 `label` 必须同时出现在 `Uncertainties`；
- 需要表达"这个模块存在但可选 / 待确认"而材料**确实支持它存在**时（即它是 A/B/C 级，
  只是是否启用不确定），用 `observed · optional`（或 `abstraction · optional`）+
  `[? 启用与否待确认]` 注释，**不要**降级成 D。

## 4. 与措辞的对照

draft 不是论文正文，但图内标签同样受证据约束：

| 材料支持程度 | 图内允许 | 图内禁止 |
|---|---|---|
| A / B | 直接作为模块名 | — |
| C | 聚合名 + Alignment Notes 逐项对应 | 把聚合说成"算法原本就是这样" |
| D | `[? label]`（并列入 Uncertainties） | 画成实线模块、画成确定箭头 |

**没有任何证据支持时：不画。** 缺一块信息不会让 draft 失败；编一块信息会让整张图不可信。
