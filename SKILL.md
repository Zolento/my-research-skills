---
name: research-idea-pipeline
description: >-
  面向 CVPR / ICML / NeurIPS 投稿的研究创意全流程流水线，覆盖文献调研、idea
  发现、方案生成、多套路论文叙事生成与审稿、方案复核五个可独立调用、也可串联调用
  的子流程。文献检索先查本地文献库，并默认再做 arxiv 扩检（本地命中不是终点）；
  遇到 429 限流自动指数退避等待。
  End-to-end research-idea pipeline for top-conference submissions: literature
  survey, idea discovery, proposal generation, multi-pattern paper narrative
  generation and review, and proposal review. Use when the user wants to
  brainstorm research ideas, find a gap in the literature, turn an idea into a
  full paper proposal plus experiment plan, find the best top-conference
  narrative/framing for an idea or proposal, or rigorously review a proposal
  before submission. Prefers the local literature library and falls back to the
  arXiv Python package with exponential backoff on HTTP 429. Triggers:
  research idea, idea discovery, brainstorm ideas, find a gap, novel idea,
  literature survey, related work, proposal, research proposal, experiment plan,
  narrative, paper narrative, storytelling, framing, positioning, narrative
  review, proposal review, mock review, reviewer critique, 找 idea, 头脑风暴,
  研究创意, 文献调研, 相关工作, 方案生成, 方案复核, 审阅方案, 投稿方案, 顶会投稿,
  论文叙事, 叙事套路, 讲故事, 卖点, 定位, 叙事评审.
argument-hint: "mode=A|B|C|D|E [领域关键词 | idea | proposal | query]"
metadata:
  author: research-idea-pipeline
  version: "1.2.0"
  upstream-spec: "顶会研究创意流水线（Research Idea Pipeline）"
---

# Research Idea Pipeline（顶会研究创意流水线）

一套面向 CVPR / ICML / NeurIPS 投稿的研究创意全流程辅助流水线。覆盖从文献调研、
idea 发现、方案生成、多套路叙事生成与审稿到方案复核的完整链路，并支持五个子流程的
独立调用与串联调用。

**本 Skill 只做编排与串联。** 子代理的角色设定、评分维度、审查视角沿用统一角色库
（见 [references/roles.md](references/roles.md)），不在各 Mode 内重新定义。

---

## 0. 入口：解析 mode 参数

用户通过 `mode` 参数指定调用哪个子流程。`$ARGUMENTS` 的第一项即 `mode`。

| Mode | 名称 | 作用 | 可独立调用 | 可被谁调用 |
|---|---|---|---|---|
| **A** | `literature-survey` | 补充文献、扩大检索范围 | 是 | 被 B/C/D/E 调用，也可单独调用 |
| **B** | `idea-discovery` | 文献调研 + 多子代理头脑风暴产出 idea 候选，**并做 idea 级创新性/可行性审核** | 是 | 接 A 之后 |
| **C** | `proposal-generation` | 基于 idea 做创新性与可行性研究，产出方案 | 是 | 接 B 之后 |
| **D** | `narrative-generation` | **基于 idea + 方案**生成多种顶会风格叙事逻辑，并拉起子代理评审，筛出最佳叙事 | 是 | 接 B（仅 idea）或接 C（推荐） |
| **E** | `proposal-review` | 复核**已成型方案**的正确性与可行性，并守创新性底线（防复现） | 是 | 接 C/D，或接上一次 E 继续复核 |

> **字母顺序 = 工作流顺序：** 文献调研 → idea 发现 → 方案生成 → 叙事生成 → 方案复核。

### 各阶段的分工（不重叠）

> **B 决定"做不做"，C 决定"做什么"，D 决定"怎么讲"，E 决定"做得对不对"。**

| 维度 | Mode B（idea 级） | Mode E（方案级） |
|---|---|---|
| 对象 | 一句话级 idea / 技术方向 | 成型的 proposal + 实验计划 |
| 可行性 | 概念可行性：路线是否成立 | 工程可行性：具体做法能否跑通、变量是否可控 |
| 正确性 | 前提是否自洽 | 方法正确性：推导/实现/指标/统计是否成立 |
| 创新性 | 方向是否已被覆盖、是否非平凡 | 方案是否**实质复现**已有工作（防复现） |
| 复现性 | 不涉及（不派 S-Repro） | 必查（S-Repro + 防复现检查） |
| 深度 | 快筛：双评分 + 致命反驳 | 深审：七子代理 + 交叉质询 + 中位数 |

**B 偏文献调研与方法研究；E 偏基于方法的正确性审核，但 E 必须显式给出复现风险等级
——做得很扎实的复现仍是拒稿理由。**（D 的定位见 [mode-d](references/mode-d-narrative-generation.md) §D0。）

**解析规则：**

1. 若 `$ARGUMENTS` 含 `mode=A|B|C|D|E`（大小写不敏感），按该 Mode 执行。
2. 若未给出 mode，**先反问用户**要调用哪个 Mode，不要猜测；只有意图极其明确时
   （如"帮我做文献调研"→ A、"帮我审一下这个方案"→ E）才可按意图推断，并在
   输出开头声明所推断的 Mode。
3. mode 之外的参数按该 Mode 的输入约定解析（见下）。
4. 若用户显式给了多个 Mode（如 `mode=B,C,D`），按 B → C → D 顺序串联执行，
   中间状态通过 `state.json` 片段传递（见 §5）。

**启动前置动作（每次调用都做）：**

1. **读项目根目录的 `AGENTS.md`**（若存在）—— 其布局、命名、公用部分约定优先于本
   Skill 默认约定。
2. **确定路线**（`routeA` / `routeB` / …）。用户未指定时反问；若只有一条路线则用它。
3. **读该路线的 `INDEX.md`**，了解进度、已证实/已证伪结论、TODO 与 Warnings。
4. 若路线或 `INDEX.md` 不存在，按
   [references/project-layout.md](references/project-layout.md) §7 的检查清单手工建立
   （目录 + `INDEX.md`）后再开工。

> 详细约定见 [references/project-layout.md](references/project-layout.md)。

**各 Mode 详细流程：**

- Mode A → [references/mode-a-literature-survey.md](references/mode-a-literature-survey.md)
- Mode B → [references/mode-b-idea-discovery.md](references/mode-b-idea-discovery.md)
- Mode C → [references/mode-c-proposal-generation.md](references/mode-c-proposal-generation.md)
- Mode D → [references/mode-d-narrative-generation.md](references/mode-d-narrative-generation.md)
- Mode E → [references/mode-e-proposal-review.md](references/mode-e-proposal-review.md)

---

## 1. 全局不变量（所有 Mode 强制遵守）

以下三条是硬约束，任何 Mode 都不得违反。执行前先确认，输出时自检。

### 1.1 文献检索：先本地，后 arxiv —— **但禁止只停留在本地**

```
Step 1: 搜索本地文献库 ./docs/refs/
        命中 → 纳入结果，标注 source="local" —— 但流程继续，不得在此返回
Step 2: 调用 Python arxiv 包
        ★ 即使 Step 1 已命中，只要触发下述任一条件，本步必须执行
        命中 → 拉取元数据与摘要，缓存到本地库，标注 source="arxiv"
Step 3: 信息不足 → 仅补充缺失字段，不重复拉取已有内容
Step 4: 饱和判定 → 未达饱和则扩大范围继续检索
```

**⚠️ 强制扩检触发条件（命中任一即必须查 arxiv 并扩大范围）：**

| # | 触发条件 | 最低等级 |
|---|---|---|
| T1 | **创新性声明**（"首次提出 / 没人做过 / 首个 / 该方向空白"） | **L3 穷尽** |
| T2 | **理论不清**（证不出来、假设无法验证、收敛性说不清） | L2 强化 |
| T3 | **可行性不确定**（能不能做、资源够不够、是否已有不可能性结果） | L2 强化 |
| T4 | 新颖性判定（Mode C 的 C1、Mode D 的 S-Lit、Mode E 的 S-Lit/S-Nov） | **L3 穷尽** |
| T5 | 本地命中不足（< 用户下限，或 < 5 条） | L2 强化 |
| T6 | 用户要求"尽可能多 / 彻底查" | **L3 穷尽** |
| T7 | 任何将写进文档的"现有工作尚未……"式论断 | L2 强化 |

**遇到卡点时第一动作是检索，不是硬推：** 理论说不清、证不出来、不确定能不能做时，
必须先检索 ① 该问题本身是否已有定理/反例/不可能性结果 ② 所用工具在其他领域的处理
③ **负结果文献**。检索后仍无解，写入 `INDEX.md` 的 Warnings 并标注待核实。

**禁止推断：** 本地未命中 ≠ 不存在；arxiv 本轮未命中 ≠ 无人研究过；429 中断 ≠ 检索完整。
未完成 L3 前，文档中只能写 **"据本次检索未见（检索式见附录）"**，
**不得**使用"首次提出"。

**429 处理：** 捕获限流错误后按指数退避等待 `10s → 20s → 40s → 80s → 160s`，
最多重试 5 次；**重试期间不得发起任何新的 arxiv 请求**；5 次后仍失败则返回本地
已有结果，标注"arxiv 暂时不可用，以下结果仅来自本地库"，**并在 INDEX.md 的 Warnings
记录"检索未达饱和"**。

完整规范（含 L1/L2/L3 尽职调查等级与饱和判据）见
[references/literature-policy.md](references/literature-policy.md)，实现见
[scripts/literature_search.py](scripts/literature_search.py)。

### 1.2 顶会标准锚定

所有创新性判定必须引用 CVPR / ICML / NeurIPS 的具体标准；所有贡献必须标注类型
（General / Theory / Use-Inspired / Concept & Feasibility / Negative Results 或
方法 / 理论 / 实证 / 问题定义）。
标准全文见 [references/venue-standards.md](references/venue-standards.md)。

**创新性声明的额外约束（强化）：** 所有"首次提出"声称必须① 先完成 T1 的 **L3 穷尽
检索**，② 由 **S-Lit 核实**，必要时由 **S-Nov 独立复核**，③ 留存**负检索记录**
（检索式 + 命中数 + 为何不足以否定）。三项缺一，只能写"据本次检索未见"，
**不得**写"首次提出"。无法确认的标注 **"待核实"**。

### 1.3 输出规范

- 结构化报告，使用标题和表格。
- 所有引用给出具体出处，格式 `[作者, 会议/年份]`。
- 无法确认的信息标注 **"待核实"**，**不得臆造**。
- 所有分析结论必须有文献依据或明确逻辑链。
- 每条"没做到 / 缺乏"必须关联**具体未建立的结构性质或未满足的理论条件**，
  禁止模糊表述。

### 1.4 项目组织与文档落盘（所有 Mode 强制）

**所有路线的方案与审阅记录必须落盘到项目根目录的 `docs/`（扁平、集中），以人类可读的
Markdown 存储；参考文献放 `docs/refs/`。**

```
<项目根目录>/
├── AGENTS.md              # 共享契约；存在则优先遵循
├── docs/                  # ★ 所有路线的文档集中于此（扁平，不分子目录）
│   ├── A001-literature-survey.md
│   ├── A002-ideas.md
│   ├── A003-proposal.md
│   ├── A004-experiment-plan.md
│   ├── A005-narrative-I1.md
│   ├── A003-review.md
│   ├── B001-literature-survey.md   # routeB 的文档同目录，靠 B 前缀区分
│   └── refs/              # ★ 参考文献（= 本地文献库根目录 papers/ cache/ index.json）
├── routeA/
│   ├── INDEX.md           # ★ 必需：索引到 ../docs/A*
│   └── code/
├── routeB/
│   └── INDEX.md
├── shared/                # 跨路线公用代码/笔记，按 AGENTS.md 规范
└── .research-idea-pipeline/   # 机器状态（不入 docs）
```

**五条硬性规则：**

1. **先读 `AGENTS.md`。** 项目根目录存在 `AGENTS.md` 时，其约定优先于本 Skill 默认。
2. **文档集中（扁平）：** 所有路线的文档都放**根目录 `docs/`**，**不再按路线分子
   目录**；路线靠**文件名前缀**（`A*` / `B*`）区分，**序号仍按路线独立递增、永不复用**。
   `slug` 只能取：`literature-survey` / `ideas` / `proposal` / `experiment-plan` /
   `narrative-I<n>`。
3. **审阅意见挂在被审 ID 上：** `<被审ID>-review.md`；接续复核 `-review-2.md`。
   **审阅记录不占新序号。**
   > 注意：文档 ID 前缀是**路线编号**，与 Mode A/B/C/D/E 无关。Mode C 在 `routeA`
   > 产出的方案是 `A003` 而**不是** `C003`；产出该文档的 Mode 记在 frontmatter 的
   > `mode` 字段。
4. **每条路线必须有 `INDEX.md`**（如 `routeA/INDEX.md`），且每次产出后必须更新。
   进度必须包含：**已证实 / 已证伪 / TODO / Bugs / Warnings**，以及文档索引
   （含 **Idea 追踪 / 叙事追踪 / 审阅追踪**）与变更日志。
   被证伪的假设**不得删除**；"检索未达饱和"必须记入 Warnings。
5. **参考文献集中：** 论文元数据/笔记/缓存一律放 **`docs/refs/`**（脚本默认
   `--local-dir ./docs/refs`）；机器状态 `state.json` 放 `.research-idea-pipeline/`，
   日志放 `logs/`——**都不进 docs 正文**。

完整规范见 [references/project-layout.md](references/project-layout.md)（含手工建立
骨架的检查清单）。

---

## 2. 共享资源索引

| 资源 | 位置 | 内容 |
|---|---|---|
| 子代理角色库 | [references/roles.md](references/roles.md) | R-CVPR / R-ICML / R-NeurIPS / A-Author / A-Experimenter / S-Lit / S-Nov / S-Theory / S-Feas / S-Devil / S-Repro |
| 顶会创新性标准 | [references/venue-standards.md](references/venue-standards.md) | CVPR / ICML / NeurIPS 三视角锚定标准 + 防复现标准 |
| 叙事套路库 | [references/narrative-patterns.md](references/narrative-patterns.md) | 十套顶会叙事逻辑、跨域五步升级、禁用表述、叙事自检 |
| 文献检索规范 | [references/literature-policy.md](references/literature-policy.md) | 禁止只停留在本地、T1—T7 强制扩检、L1/L2/L3 尽职调查、饱和判据、429 退避、缓存 |
| 项目组织规范 | [references/project-layout.md](references/project-layout.md) | `docs/` 命名与 ID 分配、`INDEX.md` 章节、`AGENTS.md` 优先、`shared/` 公用、并发写入 |
| 检索实现脚本 | [scripts/literature_search.py](scripts/literature_search.py) | 可运行实现：本地+arxiv 并集、`--level`、`--exhaustive`、`--also-query`、429 backoff |
| 状态传递模板 | [templates/state.template.json](templates/state.template.json) | `state.json` 片段结构 |
| 路线索引模板 | [templates/INDEX.md](templates/INDEX.md) | 每条路线 `INDEX.md` 的骨架（含已证实/已证伪/TODO/Bugs/Warnings） |
| 串联示例 | [examples/](examples/) | B→C→D→E 串联、接续复核、单独文献调研、多路线目录管理的示例 |

---

## 3. 子代理派遣总览

所有 Mode 共享同一角色库。按 Mode 需派遣的子代理如下（角色定义不重复，见
[references/roles.md](references/roles.md)）：

| Mode | 派遣子代理 |
|---|---|
| A | 无（执行者直接完成检索与归纳） |
| B | 头脑风暴：R-CVPR、R-ICML、R-NeurIPS、A-Author、A-Experimenter、S-Devil（每个至少 3 个 idea）；<br>**idea 级审核（B5）**：三审稿人（创新性）+ S-Lit、**S-Nov（按需）**、S-Feas + **S-Theory（按需，仅含理论声称时）** + S-Devil（致命反驳） |
| C | R-CVPR、R-ICML、R-NeurIPS（创新性）；S-Lit（先前工作核实）；**S-Nov（按需，S-Lit 判"边缘"时）**；S-Feas（可行性）；S-Theory（理论基础）；A-Author（投稿人视角展开提案）；A-Experimenter（实验设计者视角展开实验） |
| D | **叙事审核五子代理**：R-CVPR、R-ICML、R-NeurIPS、S-Devil、S-Lit（每套叙事默认 5 个，至少 3 个；idea 多时可加 S-Feas / S-Repro） |
| E | R-CVPR、R-ICML、R-NeurIPS、S-Devil、S-Feas、S-Lit（含**复现风险判定**）、S-Repro（**七子代理**严格审查 + 交叉质询）；**S-Nov（按需，S-Lit 判"边缘"或涉及"首次"时）** |

**职责边界：** 不派遣 S-Repro 到 Mode B（idea 阶段无代码可复现）；B5 的审核是
**概念级快筛**，不要与 Mode E 的方案级深审重复。详见
[mode-b](references/mode-b-idea-discovery.md) §B0 与
[mode-e](references/mode-e-proposal-review.md) §E0。

**派遣原则：** 子代理必须**独立产出**，不得互相抄袭结论；汇总时去重并保留来源标注。
**Mode D 与 Mode E 都要求交叉质询**：每个子代理对其余子代理的评分提出至少一条质疑
或补充，综合评分取**中位数**。

---

## 4. 各 Mode 输入 / 输出速查

### Mode A — literature-survey

- **输入：** 检索关键词或研究问题；检索范围（时间范围、会议范围、数量上限）；
  尽职调查等级（L1/L2/L3，默认按触发条件自动判定）。
- **流程：** A1 本地检索 → A2 **arxiv 强制补充检索**（不得因本地命中而跳过）→
  A3 范围扩大策略 → A4 饱和判定与输出。
- **交付物：** 文献列表（含来源标注）+ 检索过程记录（含 429 等待日志）+ 本地缓存
  更新记录 + 尽职调查等级达成情况。
- **落盘：** `docs/<R>NNN-literature-survey.md`（含负检索记录），
  并更新该路线 `INDEX.md`；**检索未达饱和必须记入 Warnings**。

### Mode B — idea-discovery

- **输入：** 研究领域关键词；已有参考文献（可选）；资源约束（可选）。
- **流程：** B1 基础文献调研（调用 Mode A 或内联执行）→ B2 深度局限性分析 →
  B3 多子代理头脑风暴 → B4 发散策略约束 →
  **B5 idea 级创新性与可行性审核（强制）** → B6 输出 → B7 落盘。
- **发散策略约束：** 每个 idea 必须通过以下**至少一种**策略推导：
  *问题重构 / 假设挑战 / 跨域迁移 / 反向思考 / 组合创新*。
- **B5 审核（不可跳过）：** 对每个候选 idea 给出 **创新性评分 + 可行性评分 +
  重叠度 + 致命反驳 + 推荐优先级**。**进入 shortlist 的 idea 必须完成 L3 穷尽检索**；
  唯一例外是 arxiv 不可用等不可控情况，此时必须标注"据本次检索未见 · 待核实"并记入
  INDEX 的 Warnings。**不派遣 S-Repro。**
- **交付物：** idea 候选清单（**不少于 10 个，每个都带审核结论**）+ 技术路线归纳表
  + 创新性边界界定 + **推荐 shortlist（3—5 个）+ 淘汰清单**。
- **落盘：** `docs/<R>NNN-ideas.md`，并更新该路线 `INDEX.md`
  （文档索引；被放弃的 idea 记入**已证伪**；未核实的无人区声称记 Warnings）。

### Mode C — proposal-generation

- **输入：** 一个或多个 idea（来自 Mode B 或用户直接提供）；关键参考文献（可选）；
  资源约束（可选）。
- **流程：** C1 创新性研究（三审稿人视角 + S-Lit 核实）→ C2 可行性研究
  （S-Feas + S-Theory）→ C3 论文格式展开 → C4 实验流程设计（0—13 共 14 节）→ C5 输出。
- **交付物：** 论文提案（1500—2000 字）+ 实验流程计划书 + 创新性判定 + 可行性评分
  + 风险清单。
- **落盘：** `docs/<R>NNN-proposal.md` + `docs/<R>NNN-experiment-plan.md`（各占独立序号），
  并更新该路线 `INDEX.md`（方案索引、TODO、依赖与风险）。

### Mode D — narrative-generation

- **输入：** **idea 清单**（来自 Mode B 或用户提供）+ **方案**（来自 Mode C，推荐）；
  关键参考文献（可选）；目标会议（可选）；资源约束（可选）。
- **定位：** **基于 idea + 方案建立多种顶会风格的叙事逻辑，并拉起子代理评审**；
  决定"怎么讲才不被判增量"。字母顺序上位于方案生成与方案复核之间。
- **流程：** D0.1 信息完整性检查 → D1 叙事套路锚定（每 idea ≥4 套）→
  D2 每套叙事的生成（含跨域五步升级、五段式、包装前后对照）→ D3 五子代理评审 →
  D4 交叉质询与共识（逐维度中位数）→ D5 最佳叙事推荐。
- **交付物：** 多套路叙事清单（每 idea **≥4 套**，每套主线 **≥300 字**）+
  五子代理独立评审意见 + 交叉质询记录 + 最佳叙事推荐 + 横向对比表 + 最终优先级建议。
- **落盘：** `docs/<R>NNN-narrative-I<n>.md`，并更新该路线 `INDEX.md`
  （被覆盖的叙事套路 → **已证伪**；最佳叙事 → **已证实**；综合评分 <3 → Warnings）。

### Mode E — proposal-review

- **输入：** 待复核方案（来自 Mode C 或用户提供）；上一次审阅内容（可选，用于接续
  复核）；关键参考文献（可选）。
- **定位：** 对象是**已成型方案**；主战场是**方法正确性与工程可行性**；创新性维度
  以**防复现**为核心目的（见 §0 的「各阶段的分工」）。
- **流程：** E1 判断复核类型（首次 / 接续）→ E2 七子代理严格审查（含**防复现检查**）
  → E3 交叉质询与共识形成 → E4 复核结论 → E5 接续复核规则。
- **交付物：** 七子代理评审意见 + 交叉质询记录 + 审查结论卡片（含**复现风险等级**）
  + 横向对比表 +（接续复核时）变更追踪表。
- **落盘：** `docs/<被审ID>-review.md`（接续复核用 `-review-2.md`），
  并**把审阅结论翻译成 INDEX.md 进度**：成立 → 已证实；否定 → 已证伪；
  待补 → TODO；未缓解的致命风险 / 复现风险高 → Warnings。

---

## 5. 模式衔接与状态传递

```
[用户输入]
    │
    ├─ Mode A 文献调研（被所有 Mode 调用，也可独立）──┐
    │                                                 │
    ├─ Mode B ──→ Mode C ──→ Mode D ──→ Mode E ──→ Mode E（接续复核）
    │   idea      方案        叙事        方案审查      ▲
    │    ↑          ↑           ↑                       │
    │    └── A ─────┴───── A ───┘                       │
    │                    └────── 最佳叙事回流 C / E ─────┘
    └─ 任意 Mode 可单独调用
```

**字母顺序即工作流顺序：** A 文献调研 → B idea 发现 → C 方案生成 → D 叙事生成 →
E 方案复核。

每个 Mode 输出时，附加一个 `state.json` 片段（模板见
[templates/state.template.json](templates/state.template.json)）：

```json
{
  "mode": "B",
  "timestamp": "...",
  "idea_candidates": [],
  "literature_used": [],
  "open_questions": [],
  "next_mode_suggestion": "C"
}
```

**接续规则：**

- Mode C 读取 Mode B 的 `idea_candidates`（含 B5 的 `review` 评分）。
- Mode D 读取 Mode B 的 idea 与 Mode C 的 `proposal`。
- Mode E 读取 Mode C 的 `proposal` + `experiment_plan`，以及 Mode D 的
  最佳叙事推荐。
- Mode E 接续复核时，读取上一次 Mode E 的 `review_output` 与 `open_questions`。
- 任意 Mode 调用 Mode A 时，传递 `query` 与 `scope`（并指定尽职调查等级 `level`）。

**落地约定：**

- **机器状态**写入 `.research-idea-pipeline/state-<mode>-<timestamp>.json`；串联调用时
  后一个 Mode 读取前一个 Mode 的片段。若用户未要求持久化，也在回复末尾以 JSON
  代码块给出该片段。
- **人类可读产出**写入 `docs/`（方案、审阅记录、文献报告），并**同步更新该
  路线的 `INDEX.md`**。详见 [references/project-layout.md](references/project-layout.md)。

---

## 6. 执行自检清单（每次输出前）

- [ ] mode 已明确，且与该 Mode 的输入约定一致。
- [ ] **已读项目 `AGENTS.md` 与目标路线的 `INDEX.md`**，并遵循其约定。
- [ ] 文献检索：**先本地后 arxiv，且没有只停留在本地**——本地命中后仍执行了 arxiv
      检索（除非用户显式 `--local-only`）。
- [ ] 已判定触发条件（T1—T7）并达到对应尽职调查等级（L1/L2/L3）与饱和判据。
- [ ] 每条文献结果标注了 `source`；结果集是本地 + arxiv 的并集。
- [ ] 若发生 429，输出了等待日志，且退避符合 `10→20→40→80→160s`、上限 5 次。
- [ ] arxiv 结果已写入缓存。
- [ ] 创新性判定引用了具体顶会标准；贡献标注了类型。
- [ ] **Mode B：每个 idea 都带 B5 审核结论**（创新性/可行性/重叠度/致命反驳/优先级），
      没有"只给 idea 不给审核"；且未误派 S-Repro。
- [ ] **Mode D：每个 idea 至少 4 套叙事，每套 ≥300 字**；已用**五段式**；跨域类已完成
      **五步升级**；最佳叙事**综合了全部子代理维度**（非只看创新性）；已做**叙事包装
      （重新定位，非夸大）**；无禁用表述。
- [ ] **Mode E：结论卡片给出了复现风险等级**，并回答了"设计层面贡献 vs 实现层面改进"；
      复现风险 = 高时总体判定不为"高"。
- [ ] 所有"首次提出"声称**已完成 L3 穷尽检索**、经 S-Lit 核实、附负检索记录，
      否则已降级为"据本次检索未见"或标注"待核实"。
- [ ] 理论/可行性卡点已先检索（含负结果文献），未直接假设成立。
- [ ] 无臆造引用；无法确认处标注"待核实"。
- [ ] **方案/审阅记录已落盘到 `docs/`**，命名符合 `<R><NNN>-<slug>.md` /
      `<ID>-review.md`；且**文档前缀 = 路线字母**（不随 Mode 变化）。
- [ ] **已更新路线 `INDEX.md`**：文档索引、已证实、已证伪、TODO、Bugs、Warnings、
      变更日志。
- [ ] 未达饱和的检索、未缓解的风险已记入 `INDEX.md` 的 Warnings。
- [ ] 已附 `state.json` 片段与 `next_mode_suggestion`。

---

## 7. 设计依据（为什么这样编排）

1. **为什么用 Mode 而非单一流程？** 五个能力需可独立、可串联；Mode 化让每个子流程
   有清晰输入输出，并通过 `state.json` 传递状态，避免重复劳动。**字母顺序按工作流
   排列**（调研 → idea → 方案 → 叙事 → 复核），读到 Mode X 就知道它在流程哪一段。
2. **为什么文献检索"先本地后 arxiv"，但禁止停在本地？** 顺序上先本地是为了省成本、
   省延迟、避开 429；但本地库是历史缓存的子集、天然有偏，**不能作为"不存在"的证据**。
   凡是支撑创新性声明、理论判断、可行性判断的检索，必须扩到 arxiv 并达到饱和。
   把工具的局限当成世界的性质，是本流水线要防的最主要错误。
3. **为什么 429 要指数退避？** 429 通常意味着短时限流；指数退避比固定等待更高效，
   也比立即重试更礼貌；5 次上限避免无限阻塞。失败时必须降级标注"检索未达饱和"，
   不能让不完整的检索伪装成完整结论。
4. **为什么 Mode E 支持接续复核？** 接续复核聚焦上次未解决问题与新增变更，避免
   重复完整审查，同时用"变更追踪表"保证审查连续性。
5. **为什么单设 Mode D 做叙事？** 同一 idea 在不同叙事下，审稿人的接收意愿差异显著：
   跨域迁移类 idea 在"跨域理论迁移"叙事下可能被判增量，换到"瓶颈突破/移除假设"叙事
   下可能被视为理论贡献。**多套路并行生成 + 多子代理打分，才能找到该 idea 的最优
   叙事位置。** 叙事包装不是夸大，而是**重新定位**。
6. **为什么角色不变？** 本 Skill 只做编排，角色定义、评分维度、审查视角全部沿用
   统一角色库，保证审查标准的一致性。
7. **为什么按路线分离代码、却把文档集中到根目录 `docs/`？** 代码必须隔离（避免互相
   import 与状态污染），但文档集中才方便跨路线检索、对比与交接。折中办法是：
   **代码分目录、文档扁平集中**，用**文件名前缀**（`A*` / `B*`）承担路线隔离，因此
   前缀不可省。参考文献统一放 `docs/refs/`，与检索脚本的本地库路径一致。
8. **为什么 INDEX.md 要区分"已证实"与"已证伪"？** 负结果常被丢弃，导致后人重复
   踩坑。把证伪结论与 TODO/Bugs/Warnings 一起固化为项目资产，是最省算力的做法。
