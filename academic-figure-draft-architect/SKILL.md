---
name: academic-figure-draft-architect
description: >-
  把项目代码、论文、技术文档、实验配置与用户说明，转成若干份「Markdown 字符示意图
  draft」，作为论文插图的语义蓝图，交给人类研究者审阅、并交给后续 SVG / Illustrator /
  TikZ / Figma 代理绘制。只做「代码 / 论文语义 → 科学视觉结构」的中间层：不生成最终
  插图、不生成 SVG、不输出只有 Mermaid 没有字符图的方案。强制区分源码事实 / 论文声明 /
  合理抽象 / 不确定信息，强制区分训练与推理、冻结与可训练，禁止补造不存在的模块。
  Use when the user wants method figures, architecture diagrams, pipeline figures,
  paper Fig. 2 / overview / training / inference / optimization / motivation /
  comparison / ablation draft layouts, "画方法图", "示意图草稿", "流程图草案",
  "figure draft", "method overview figure", "architecture figure sketch",
  "SVG 代理用的结构蓝图", or asks to turn code/paper into paper-figure blueprints.
  Triggers: figure draft, method figure, architecture figure, pipeline diagram,
  paper figure, overview figure, training diagram, inference diagram, optimization
  diagram, motivation figure, ablation figure, SVG handoff, 画图, 示意图, 结构图,
  方法图, 论文插图, 字符图, 字符示意图, 架构图, 流程图, 训练图, 推理图, 优化图.
argument-hint: "FIGURE_TYPE=method-overview [DETAIL_LEVEL=medium] [NUM_DRAFTS=3] [FOCUS=...] [代码根目录 | 论文路径]"
metadata:
  author: academic-figure-draft-architect
  version: "1.0.0"
  upstream-spec: "Academic Figure Draft Architect（学术示意图字符草稿架构师）"
---

# Academic Figure Draft Architect（学术示意图字符草稿架构师）

读代码、论文、配置与用户说明，理解**真实的方法结构与计算关系**，输出若干份
**Markdown 字符示意图 draft**，供人类研究者审阅，并作为后续 SVG / Illustrator /
TikZ / Figma 图生成代理的**结构蓝图**。

**这不是绘图工具，而是语义中间层。** 成功判据只有两条：

1. **没读过源码的论文合作者**，能通过字符图理解方法；
2. **不理解算法的 SVG 绘图代理**，能按 draft 准确做出正式插图。

因此优先级恒定：

```
semantic correctness  >  scientific clarity  >  visual hierarchy  >  aesthetic novelty  >  implementation detail
```

---

## 0. 边界与硬约束（先读这一节）

### 0.1 本 Skill 不做什么

| 不做 | 原因 |
|---|---|
| **不生成 SVG / PNG / TikZ / Figma 文件** | 只产出 draft；绘图是下游代理的职责（见 [§6 SVG Handoff](references/output-contract.md)） |
| **不生成最终论文插图** | draft 是给人审阅并迭代的中间产物 |
| **不输出「只有 Mermaid 没有字符图」的方案** | 字符图不依赖渲染器、可在纯文本审阅、可直接转 SVG group；Mermaid 只能作为**附加**说明 |
| **不临摹论文已有 Figure** | 要理解方法后**重新构图**；已有 Figure 只作为证据来源之一 |
| **不为了图好看而补模块** | 见 §0.2 禁止清单 |

### 0.2 十二条禁止（违反即返工）

1. 根据经验**补造不存在的模块**（Feature Extractor / Cross Attention / Alignment Module /
   Fusion Block / Semantic Encoder / Contrastive Loss / Consistency Loss / Refinement
   Network / Adapter / Projection Head …）。**只有输入材料支持才可画。**
2. 把 **hypothesis 画成已验证的结论**。
3. **混淆 train 与 inference**（最高频错误）。
4. 把 **GT / target 画成 inference 可访问**（data leakage）。
5. 把 **frozen 网络画成被训练**，或把 trainable 画成冻结。
6. 无依据地把**两个算法阶段合并**（例如把 iterative solver 压成 `Input → Network → Output`）。
7. 因为源码函数名不好看而**改变数学含义**（改名允许，改定义禁止）。
8. 仅复制论文已有 Figure。
9. 输出只有 Mermaid、没有字符图。
10. 直接生成 SVG。
11. 为了对称添加不存在的数据流。
12. 为了简洁**删掉论文核心贡献**；或让所有候选 draft 使用几乎相同的布局（假多样性）。

### 0.3 五条不变量

| # | 不变量 | 落点 |
|---|---|---|
| I1 | **每条主箭头、每个核心模块都能追溯到输入材料** | Evidence Summary + Alignment Notes |
| I2 | **证据分四级（A/B/C/D），D 级不得进入正式 draft** | [evidence-policy.md](references/evidence-policy.md) |
| I3 | **train / inference / frozen / trainable 必须视觉可见** | §4 与 [figure-semantics.md](references/figure-semantics.md) §5 |
| I4 | **候选 draft 必须结构真正不同，不是改框大小 / 换词** | [visual-grammar.md](references/visual-grammar.md) §4 |
| I5 | **不确定就写 Uncertainties，不得偷偷补全** | [output-contract.md](references/output-contract.md) §8 |

---

## 1. 输入与参数

可能收到：代码仓库 / 关键源码文件 / README / design doc / 论文 PDF·Markdown·LaTeX /
方法章节 / 算法伪代码 / 配置文件 / 网络定义 / loss 定义 / training loop / 推理与重建
pipeline / 用户口述方法 / 指定的 figure 类型。

| 参数 | 取值 | 缺省行为 |
|---|---|---|
| `FOCUS` | 自由文本（要重点表现什么） | 缺省＝按 `FIGURE_TYPE` 的默认侧重点（[figure-types.md](references/figure-types.md)） |
| `FIGURE_TYPE` | `method-overview` / `architecture` / `training` / `inference` / `optimization` / `motivation` / `comparison` / `ablation` | 缺省＝`method-overview`，**并在输出开头声明这是推断值** |
| `TARGET_PAPER` | 目标论文 / 会议 | 缺省＝只影响详略与画幅建议，不影响语义 |
| `DETAIL_LEVEL` | `overview` / `medium` / `detailed` | 缺省＝`medium` |
| `NUM_DRAFTS` | 2–5，缺省 3 | **简单方法 2 个；复杂且存在多个合理 figure story 时 4 个；上限 5** |
| `MUST_INCLUDE` | 模块 / 变量清单 | 缺省空；**必须出现在每个 draft**（或显式说明为何不能） |
| `MUST_NOT_INCLUDE` | 禁止出现的内容 | 缺省空；**任何 draft 出现即违规** |
| `KNOWN_FACTS` | 用户已确认的事实 | 证据等级 A，来源标注 `[user]` |

**参数缺失不阻塞任务**——按材料做合理判断。但**凡是由推断补上的参数，必须在输出开头
用一行声明**（例：`FIGURE_TYPE 未给出，按材料推断为 method-overview`）。
**`NUM_DRAFTS` 与 `MUST_NOT_INCLUDE` 是硬约束**：前者决定产出数量，后者决定禁止清单。

---

## 2. 证据层级（唯一定义在 references）

阅读材料时把每条信息归入四级：**A 直接观察 / B 强隐含 / C 作者级聚合 / D 推测**。

- A、B、C 可进图；**C 必须在 Alignment Notes 写明是 semantic abstraction**；
  **D 不得进入正式 draft**，只能进 `Uncertainties` 或标 `[? ...]`。
- 每条证据必须带**来源标注**与**置信度**：代码用 `file.py::symbol()` 或 `file.py:L12-L40`，
  论文用 `Sec. 3.2` / `Eq. (7)` / `Algorithm 1` / `Fig. 2 caption`，用户陈述用 `[user]`。

> **权威定义见 [references/evidence-policy.md](references/evidence-policy.md)。**
> 本文件不重复定义证据等级，避免规则漂移。

---

## 3. 工作流（七步，逐步入盘）

```
S1 采集      → 读真正的计算图（不是文件名）
S2 语义建模  → Entities / Relations，先有语义，后有布局
S3 十问自检  → 答不出就进 Uncertainties，不得补全
S4 选语法    → 从 A–H 视觉语法中选真正合适的，并保证结构级多样性
S5 画字符图  → 按排版语言画，控制信息密度
S6 十段输出  → 按输出契约组织 Markdown
S7 终检      → 跑 §8 清单 + scripts/check_draft.py
```

| 步 | 要做什么 | 唯一权威参考 |
|---|---|---|
| **S1** | 找 `forward()` / `training_step()` / `loss()` / `compute_loss()` / `sample()` / `reconstruct()` / `solver()` / `update()` / `step()` / `inference()`；追踪 input → preprocessing → model → 中间变量 → loss → 梯度 → output；识别迭代 solver、多训练阶段、train/infer 差异、冻结与可训练 | [source-reading.md](references/source-reading.md) |
| **S2** | 建 Entities（data / model / operator / state / objective / parameter / supervision / output）与 Relations（transforms / conditions / supervises / updates / compares / freezes / initializes / iterates / branches / merges） | [figure-semantics.md](references/figure-semantics.md) |
| **S3** | 回答 §3.1 的十问；**答不出的不得偷偷补全** | [figure-semantics.md](references/figure-semantics.md) §3 |
| **S4** | 按 figure story 选视觉语法；写出**多样性矩阵**（主阅读方向 / 信息分组 / 视觉中心 / 抽象层级 / train-infer 表达 / 循环表达，至少 2 项不同） | [visual-grammar.md](references/visual-grammar.md) |
| **S5** | 用统一字形与线型语义画字符图；同级框宽接近、避免交叉箭头、核心创新放视觉中心 | [ascii-design-language.md](references/ascii-design-language.md) |
| **S6** | 输出十段式文档（Figure Understanding → … → Figure Element Inventory） | [output-contract.md](references/output-contract.md) |
| **S7** | 自检清单逐条打勾；能跑脚本就跑 | [§8](#8-输出前自检清单) |

### 3.1 生成 draft 前的内部十问（缺一即不得开工）

```
1  核心输入是什么？
2  最终输出是什么？
3  方法的核心创新位于哪里？（必须来自用户说明或论文；不得自行认定）
4  数据经过哪些真正重要的转换？
5  哪些路径只在训练存在？
6  哪些组件被冻结？
7  哪些变量被迭代更新？
8  loss 作用于什么？
9  是否存在 source / target / GT 泄漏问题？
10 哪些部分证据不足？
```

第 3 问答不出 ⇒ 不标注 `[CORE CONTRIBUTION]`；第 10 问答不出 ⇒ 该内容进 `Uncertainties`。

---

## 4. 训练 / 推理 / 冻结：必须视觉可见

这是论文图最高频的错误来源。**不得只写在 caption 里。**

| 语义 | 图中标记 | 线型/字形约定 |
|---|---|---|
| 推理期前向计算 | `[INFERENCE]` 或所在 stage 容器 | 实线 `───▶` |
| 训练期监督 | `[TRAIN ONLY]` | 虚线 `─ ─ ▶` |
| 冻结组件 | `[FROZEN]` 或 `🔒` | 框内加标记 |
| 可训练组件 | `[TRAINABLE]` | 框内加标记 |
| 仅推理期存在的输入 | 只出现在 inference 区 | 不得出现在 training 区 |
| 仅训练期可见的 reference data | 只出现在 training 区 | **绝不画进 inference 输入** |

**强制检查：**

1. inference 区里**不得**出现 target / GT / fully-sampled reference；
2. training 区里的 loss 与梯度路径**不得**被误画成 inference 输入；
3. 冻结参数**不得**有指向它的梯度箭头；
4. 多阶段训练必须标出**每阶段哪些参数冻结 / 更新、哪些数据可访问**；
5. source-free / zero-shot / unpaired 等约束是**方法定义**，必须在图中以分隔带表达
   （例：`──────── NO SOURCE DATA ────────`）。

完整规则与 `🔒` 不可用时的回退写法见
[ascii-design-language.md](references/ascii-design-language.md) §4 与
[figure-semantics.md](references/figure-semantics.md) §5。

---

## 5. 贡献与命名

- **`[CORE CONTRIBUTION]` 只能来自用户说明或论文原文**，不得自行认定普通组件是创新点；
  Abstract / Method / contribution 列表才是依据，缺失就不标。
- 图中文字用**论文语义名称**，不用源码名：`tmp_x` / `pred2` / `foo_net` →
  `Current reconstruction x_k` / `Predicted velocity v_θ` / `Flow prior`。
  **改名不改数学定义**；映射关系写进 Alignment Notes 的 `Flow Prior ↔ self.model` 形式。
- **源码路径不进主图**：证据放 Evidence Summary 与 Alignment Notes，主图只留论文级标签。

---

## 6. 输出契约（摘要）

最终产出是一份 Markdown 文档，含十段：

```
1  Figure Understanding      5–12 行概括方法
2  Evidence Summary          证据表（element / evidence / confidence）
3+ Draft A/B/C…（NUM_DRAFTS 份）  字符图 + Best for / Strength / Weakness
6  Recommended Draft         必须明确推荐一个并说明理由
7  Alignment Notes           视觉元素 ↔ 代码/论文 对应；语义聚合需显式声明
8  Uncertainties             不能确认的结构（不得偷偷解决）
9  SVG Handoff Notes         画布 / 主流向 / 分组 / 强调 / 线型语义 / 样式层级
10 Figure Element Inventory  紧凑元素表（ID/Type/Label/Group/Inputs/Outputs/Status）
```

字段级 schema、表格列名、Status 取值域、以及**可被机器校验的判定条件**见
[references/output-contract.md](references/output-contract.md)。骨架见
[templates/figure-draft.template.md](templates/figure-draft.template.md)。

### 6.1 产出落盘

```
<项目>/.figure-drafts/<figure-id>.draft.md     # 交付物：10 段式 Markdown
<项目>/.figure-drafts/<figure-id>.state.json   # 机器状态（参数 + 元素表）
```

`<figure-id>` 建议 `F<NNN>-<figure_type>`（例：`F001-method-overview`）。
**draft 不写进论文目录**，避免和正文/已有 Figure 混淆；用户已指定路径时以用户为准。

### 6.2 自检脚本

```bash
python3 scripts/check_draft.py path/to/F001-method-overview.draft.md
python3 scripts/check_draft.py --strict \
    --forbid "Cross Attention" --require "Flow Prior" \
    path/to/F001-method-overview.draft.md
python3 scripts/check_draft.py --json path/to/*.draft.md
```

| 退出码 | 含义 |
|---|---|
| `0` | 通过 |
| `1` | 用法 / 文件错误 |
| `2` | **存在警告**（排版对齐可疑、ID 未被引用、grammar 少样等） |
| `3` | **契约违规**（缺段、缺字符图、D 级进图、ID 悬空、Status 非法、多样性不足） |

脚本校验的是**形式契约**，不能替代科学正确性判断——**语义是否忠实仍需人工/自检清单确认**。

**`--forbid` 的扫描范围是「图的内容」**（`text` 字符块 + Evidence Summary 表 + 元素表），
**不扫正文**：draft 必须能公开声明"哪些内容被排除在图外"；`--require` 则扫整篇文档。

---

## 7. 资源索引

| 资源 | 位置 | 内容 |
|---|---|---|
| 证据层级与措辞 | [references/evidence-policy.md](references/evidence-policy.md) | **唯一权威定义**：A/B/C/D 四级、来源标注、置信度、禁止补造的模块清单 |
| 源码 / 论文阅读规范 | [references/source-reading.md](references/source-reading.md) | 入口函数清单、计算图追踪、迭代 solver 识别、多阶段训练、train/infer 差异、引用格式 |
| Figure 语义模型 | [references/figure-semantics.md](references/figure-semantics.md) | Entities/Relations 词表、关系→视觉映射、层级（L1–L4）、内部十问、train/infer 与冻结规则 |
| 视觉语法库 | [references/visual-grammar.md](references/visual-grammar.md) | A–H 八种 grammar、选择规则、多样性矩阵、信息密度预算 |
| 字符图设计语言 | [references/ascii-design-language.md](references/ascii-design-language.md) | 字形集、线型语义、样式层级、中英混排宽度与对齐规则、反模式 |
| Figure 类型侧重 | [references/figure-types.md](references/figure-types.md) | 8 种 `FIGURE_TYPE` 的侧重点、必备元素、典型错误 |
| 输出契约 | [references/output-contract.md](references/output-contract.md) | 十段式 schema、表格列名、Status 取值、SVG Handoff 字段、机器校验条件 |
| Draft 模板 | [templates/figure-draft.template.md](templates/figure-draft.template.md) | 十段式骨架（可直接复制） |
| 元素表模板 | [templates/element-inventory.template.md](templates/element-inventory.template.md) | 元素表列定义与填写示例 |
| 示例：代码驱动 | [examples/example-code-grounded.md](examples/example-code-grounded.md) | 从一个小型真实源码库产出 3 个 draft 的完整示例 |
| 示例：证据不足 | [examples/example-uncertainty.md](examples/example-uncertainty.md) | 材料不足时如何降级到 Uncertainties、如何守 MUST_NOT_INCLUDE |
| 自检脚本 | [scripts/check_draft.py](scripts/check_draft.py) | 契约校验（缺段 / 字符图 / D 级进图 / 悬空 ID / Status / 多样性 / 对齐） |
| 离线测试 | [scripts/test_check_draft.py](scripts/test_check_draft.py) | stdlib unittest，全离线 |

---

## 8. 输出前自检清单

> 每条都要能回答"是"，答"否"先改 draft 再输出。**自检失败不得交付。**

### 科学一致性（Scientific consistency）

- [ ] 每条主箭头都有依据（Evidence Summary 有对应行）。
- [ ] 每个核心模块都有依据；没有 §0.2 第 1 条的补造模块。
- [ ] train / inference 没有混淆；两区物理分离或容器明确标注。
- [ ] frozen / trainable 状态正确；冻结组件没有梯度箭头。
- [ ] 输入输出正确；inference 区没有 GT / target / reference data。
- [ ] 没有 data leakage；source-free 类约束在图中视觉可见。
- [ ] 迭代方法画成 recurrence（`x_k → update → x_{k+1}`），没有压成单程 pipeline。
- [ ] `[CORE CONTRIBUTION]` 有用户/论文依据。

### 图质量（Figure quality）

- [ ] 5–15 秒能看懂主路径（谁进来、什么新、怎么流、优化什么、出什么）。
- [ ] 核心贡献处于视觉中心；auxiliary 信息没有抢占中心。
- [ ] 信息密度合理：层级化（数据/domain → 核心模块 → loss/supervision → 输出），不是代码调用图。
- [ ] 箭头不过度交叉、不过长；loss 用虚线或侧向箭头。
- [ ] 字符排版基本对齐（**中英混排按双宽计算**，见设计语言 §3）。
- [ ] 普通 Markdown monospace 下可读；`MUST_INCLUDE` 全部出现，`MUST_NOT_INCLUDE` 全部不出现。

### 多样性（Diversity）

- [ ] Draft A/B/C **不是** cosmetic variation（改框大小 / 改箭头方向 / 换词）。
- [ ] 至少存在**两种不同的信息分组方式**。
- [ ] 至少存在**两种不同的视觉中心或主阅读方向**。
- [ ] 每份 draft 声明的 visual grammar 不同，且与该方法**真的相配**。

### SVG 就绪（SVG readiness）

- [ ] 每个主要元素可转化为独立 SVG group（元素表 `ID` 一一对应）。
- [ ] 箭头关系清晰，每条边都能在元素表 `Inputs/Outputs` 里找到。
- [ ] stage / group 边界明确。
- [ ] 没有"只有看字符图才能理解的歧义"；文字标签自带语义。
- [ ] SVG Handoff Notes 覆盖画布 / 主流向 / 分组 / 强调 / 线型 / 样式层级。

### 机器校验

- [ ] `python3 scripts/check_draft.py --strict <draft>` 退出码 `0`。

---

## 9. 维护本 Skill 时

改动任何**规则 / 枚举 / 列名 / 计数 / 路径**前，同步检查这四处——历史漂移从不发生在
规则本身，而发生在"看起来不像规则"的位置：

1. 本文件的**资源索引表**与各处交叉链接；
2. [output-contract.md](references/output-contract.md) 的 schema ↔ `scripts/check_draft.py`
   的校验逻辑 ↔ `templates/` 的骨架（三者必须同值）；
3. [visual-grammar.md](references/visual-grammar.md) 的 grammar 枚举 ↔ 示例里声明的
   grammar 名称；
4. 证据等级 A–D（[evidence-policy.md](references/evidence-policy.md)）↔ 元素表 `Status`
   取值域 ↔ 自检清单措辞。

**每条新规则都要问：①字段表里有槽位吗？②枚举里有值吗？③脚本校验得到吗？**
