---
name: research-idea-pipeline
description: >-
  面向 CVPR / ICML / NeurIPS / MICCAI 投稿的研究创意全流程流水线，覆盖文献调研、idea
  发现、方案生成、多套路论文叙事生成与审稿、方案复核五个可独立调用、也可串联调用
  的子流程。文献检索先查本地文献库，并默认再做多源扩检（本地命中不是终点）；
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
  论文叙事, 叙事套路, 讲故事, 卖点, 定位, 叙事评审, 医学影像, 医学图像, 临床验证,
  MICCAI, medical image analysis, clinical validation.
argument-hint: "mode=A|B|C|D|E [领域关键词 | idea | proposal | query]"
metadata:
  author: research-idea-pipeline
  version: "1.2.0"
  upstream-spec: "顶会研究创意流水线（Research Idea Pipeline）"
---

# Research Idea Pipeline（顶会研究创意流水线）

一套面向 CVPR / ICML / NeurIPS / MICCAI 投稿的研究创意全流程辅助流水线。覆盖从文献调研、
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
| 深度 | 快筛：双评分 + 致命反驳 | 深审：八子代理 + 交叉质询 + 中位数 |

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

0. **先确认锚定点（核心目标）** —— 见 §0.1。**未确认前不得开工。**
1. **读项目根目录的 `AGENTS.md`**（若存在）—— 其布局、命名、公用部分约定优先于本
   Skill 默认约定。
2. **确定路线**（`routeA` / `routeB` / …）。用户未指定时反问；若只有一条路线则用它。
3. **读该路线的 `INDEX.md`**，了解进度、已证实/已证伪结论、TODO 与 Warnings。
4. 若路线或 `INDEX.md` 不存在，按
   [references/project-layout.md](references/project-layout.md) §7 的检查清单手工建立
   （目录 + `INDEX.md`）后再开工。

> 详细约定见 [references/project-layout.md](references/project-layout.md)。

### 0.1 锚定点（开工前必问，先于一切）

**开始任何 Mode 之前，必须先与用户确认本工作的核心目标（锚定点）。未确认前不得开工。**

用户没说就**反问**——不要猜，更不要默认成"提高性能"。用户已经讲清楚了，就复述一遍
请其确认。

| 锚点 | 核心目标 | 成功判据 | 典型会议 | 贡献类型 |
|---|---|---|---|---|
| **理论** | 提出并验证理论：定理 / 界 / 不可能性 / 统一框架 | 命题成立、证明无缺口、假设必要且紧 | ICML / NeurIPS | Theory |
| **性能** | 提高某个任务 / 指标的绝对性能 | 公平比较下超过最强基线 | CVPR / NeurIPS | 方法 |
| **现象** | 发现并解释反直觉现象 | 解释唯一且具预测力 | NeurIPS / ICML | 实证 |
| **基准** | 揭示现有评测掩盖的失败 | 基准暴露真实失败模式 | CVPR / NeurIPS | 实证 / 问题定义 |
| **可行性** | 把不可行 / 过贵的方法变可行 | 保持理论保证同时显著降本 | CVPR / ICML | Concept & Feasibility |
| **负结果** | 证明某目标在一定条件下不可能 | 不可能性成立且给出可达松弛 | NeurIPS | Negative Results |

**规则：**

1. **允许组合，但必须指定主锚点。** 例如"主锚点 = 理论，次锚点 = 可行性"。
2. **锚点必须落盘：** 写进文档 frontmatter 的 `core_goal`、`INDEX.md` 的路线概要、
   以及 `state.json` 的 `core_goal` 字段。
3. **锚点变更必须显式记录。** 中途换锚点是重大变更——老锚点下的产物（idea / 方案 /
   叙事 / 审阅结论）**必须重新审视**，并在 `INDEX.md` 变更日志留痕。
4. **锚点与产出不一致时必须当场指出。** 例如主锚点是"性能"，但 idea 是纯理论类、
   或实验设计里没有同算力公平比较——直接提示冲突，不要默默继续。

**锚点如何约束各 Mode：**

| Mode | 锚点的作用 |
|---|---|
| A | **检索边界：** 理论锚点必须查定理 / 反例 / 不可能性与负结果；性能锚点必须查 SOTA 与评测协议 |
| B | **推导与筛选：** 理论锚点优先"假设挑战"，性能锚点优先"问题重构 / 组合创新"；shortlist 只收服务主锚点的 idea |
| C | **贡献类型与实验：** 理论锚点下 C4 必须含证明 / 反例；性能锚点下必须含同算力·同数据·同调参的公平比较与显著性检验 |
| D | **叙事套路：** 见 [narrative-patterns.md](references/narrative-patterns.md) §1.2 的锚点 → 套路映射 |
| E | **评审权重：** 理论锚点首查证明正确性；性能锚点首查公平比较、指标口径与统计方案 |

**各 Mode 详细流程：**

- Mode A → [references/mode-a-literature-survey.md](references/mode-a-literature-survey.md)
- Mode B → [references/mode-b-idea-discovery.md](references/mode-b-idea-discovery.md)
- Mode C → [references/mode-c-proposal-generation.md](references/mode-c-proposal-generation.md)
- Mode D → [references/mode-d-narrative-generation.md](references/mode-d-narrative-generation.md)
- Mode E → [references/mode-e-proposal-review.md](references/mode-e-proposal-review.md)

---

## 1. 全局不变量（所有 Mode 强制遵守）

以下五条是硬约束，任何 Mode 都不得违反。执行前先确认，输出时自检。

### 1.1 文献检索：先本地，后多源 —— **但禁止只停留在本地**

```
Step 1: 搜索本地文献库 ./docs/refs/
        命中 → 纳入结果，标注 sources=["local"] —— 但流程继续，不得在此返回
Step 2: 调用全部启用源（arxiv / openalex / crossref）
        ★ 即使 Step 1 已命中，只要触发下述任一条件，本步必须执行
        ★ 单源失败【不终止】检索：该源标记 unavailable，其余源照常
        命中 → 拉取元数据与摘要，缓存到 docs/refs/cache/<source>/，标注 sources=[<source>]
Step 3: 信息不足 → 仅补充缺失字段，不重复拉取已有内容
Step 4: 饱和判定 → 未达饱和则扩大范围继续检索
```

**⚠️ 强制扩检触发条件（命中任一即必须查**全部启用源**并扩大范围）：**

| # | 触发条件 | 最低等级 |
|---|---|---|
| T1 | **创新性声明**（"首次提出 / 没人做过 / 首个 / 该方向空白"） | **L3 穷尽** |
| T2 | **理论不清**（证不出来、假设无法验证、收敛性说不清） | L2 强化 |
| T3 | **可行性不确定**（能不能做、资源够不够、是否已有不可能性结果） | L2 强化 |
| T4 | 新颖性判定（Mode C 的 C1、Mode D 的 S-Lit、Mode E 的 S-Lit/S-Nov） | **L3 穷尽**（**例外：Mode B 的 B5 概念级快筛 = L2**，只有写进文档的「首次提出」声称才回到 L3，见 §4 Mode B） |
| T5 | 本地命中不足（< 用户下限，或 < 5 条） | L2 强化 |
| T6 | 用户要求"尽可能多 / 彻底查" | **L3 穷尽** |
| T7 | 任何将写进文档的"现有工作尚未……"式论断 | L2 强化 |

**遇到卡点时第一动作是检索，不是硬推：** 理论说不清、证不出来、不确定能不能做时，
必须先检索 ① 该问题本身是否已有定理/反例/不可能性结果 ② 所用工具在其他领域的处理
③ **负结果文献**。检索后仍无解，写入 `INDEX.md` 的 Warnings 并标注待核实。

**禁止推断：** 本地未命中 ≠ 不存在；arxiv 本轮未命中 ≠ 无人研究过；429 中断 ≠ 检索完整。
未完成 L3 前，文档中只能写 **"据本次检索未见（检索式见附录）"**，
**不得**使用"首次提出"。**证据等级与措辞的权威定义见
[evidence-policy.md](references/evidence-policy.md)。**

**429 处理：** 捕获限流错误后按指数退避等待 `10s → 20s → 40s → 80s → 160s`，
最多重试 5 次；**重试期间不得发起任何新的 arxiv 请求**；5 次后仍失败则返回本地
已有结果，标注"arxiv 暂时不可用，以下结果仅来自本地库"，**并在 INDEX.md 的 Warnings
记录"检索未达饱和"**。

**代理环境识别：** 发起 arxiv 请求前，先解析 `arxiv.org` / `export.arxiv.org`。
**若解析到本地 IP**（回环 / 私有网段 / 链路本地 / `0.0.0.0`，例如 Clash 的
`198.18.x.x` fake-IP），说明**可能存在代理环境**——DNS 已被 hosts 文件或本地代理
（Clash / Surge / 镜像站）接管，你访问的不是 arxiv 官方。此时必须：

1. 在报告中**单列「代理环境提示」段**，写明解析到的**具体 IP 与判定类型**；
2. **不得**据此判定"在线源不可用"或"无人在研究"（代理缓存/镜像可能不完整）；
3. 代理链路上的 **429 未必是 arxiv 官方限流**，退避照常执行但结论中必须注明该不确定性；
4. 若本次检索用于支撑创新性声明，把"经代理环境检索"记入 INDEX.md 的 **Warnings**。

> **只告警，不阻断。** 代理环境下的结果仍可用，但**可信度需重新评估**——更应依赖
> 饱和判据（连续两轮零新增）与负检索记录来支撑结论。

完整规范（含 L1/L2/L3 尽职调查等级、饱和判据与代理环境识别）见
[references/literature-policy.md](references/literature-policy.md)（§6.1），实现见
[scripts/literature_search.py](scripts/literature_search.py)。

### 1.2 顶会标准锚定

所有创新性判定必须引用 CVPR / ICML / NeurIPS / MICCAI 的具体标准；所有贡献必须标注类型
（General / Theory / Use-Inspired / Concept & Feasibility / Negative Results 或
方法 / 理论 / 实证 / 问题定义）。
标准全文见 [references/venue-standards.md](references/venue-standards.md)。

**审稿人评价的两角度 + 会议特性（强化）：** 四个会议审稿人
（R-CVPR / R-ICML / R-NeurIPS / R-MICCAI）的**每一次评价**都必须同时给出：

1. **理论角度** —— 命题 / 假设 / 推导是否成立、形式化是否完整、理论贡献深度；
2. **应用角度** —— 能否落地、可验证性、影响面、与真实工作流的兼容性；
3. **会议特性判定** —— 按**本会议**首要标准给出一条显式判定，并引用
   [venue-standards.md](references/venue-standards.md) 的对应条目。

**三个都是必填；只写一个角度 = 评审不合格。** 两角度必须落到**具体命题 / 假设 /
实验 / 工作流环节**，不得用"理论没问题、应用有价值"充数。详见
[roles.md](references/roles.md) §1.0 与 [venue-standards.md](references/venue-standards.md) §0。

**创新性声明的额外约束（强化）：** 所有"首次提出"声称必须① 先完成 T1 的 **L3 穷尽
检索**，② 由 **S-Lit 核实**，必要时由 **S-Nov 独立复核**，③ 留存**负检索记录**
（检索式 + 命中数 + 为何不足以否定）。三项缺一，只能写"据本次检索未见"，
**不得**写"首次提出"。无法确认的标注 **"待核实"**。

### 1.3 输出规范

- 结构化报告，使用标题和表格。
- 所有引用给出具体出处，格式 `[作者, 会议/年份]`。
- 无法确认的信息标注 **"待核实"**，**不得臆造**。
  **证据等级 ↔ 允许/禁止表述的权威定义见
  [evidence-policy.md](references/evidence-policy.md)**（各 Mode 不再各自定义措辞）。
- 所有分析结论必须有文献依据或明确逻辑链。
- 每条"没做到 / 缺乏"必须关联**具体未建立的结构性质或未满足的理论条件**，
  禁止模糊表述。

### 1.4 项目组织与文档落盘（所有 Mode 强制）

**各路线产出的文档放该路线自己的 `routeX/docs/`（扁平）；根目录 `docs/` 是跨路线共享区，
至少保证有 `refs/`。根目录与每条路线各自有 `README.md` 与 `INDEX.md`。**

```
<项目根目录>/
├── AGENTS.md              # 共享契约；存在则优先遵循
├── README.md              # ★ 根级：项目总览（研究问题、路线列表、怎么跑）
├── INDEX.md               # ★ 根级：跨路线索引（各路线状态 + 全局 TODO/Warnings）
├── docs/                  # ★ 跨路线共享区（不放路线文档）
│   ├── refs/              # ★ 必需：参考文献库 papers/ cache/<source>/ index.json
│   ├── notes/             # 可选：跨路线共享笔记（按 AGENTS.md）
│   └── latex/             # 可选：跨路线共享 LaTeX（按 AGENTS.md）
├── routeA/
│   ├── README.md          # ★ 路线级：本路线说明
│   ├── INDEX.md           # ★ 路线级：本路线索引（文档索引 + 关系图 + 进度）
│   ├── docs/              # ★ 本路线文档（扁平）
│   │   ├── A001-literature-survey.md
│   │   ├── A002-ideas.md
│   │   ├── A003-proposal.md
│   │   ├── A004-experiment-plan.md
│   │   ├── A005-narrative.md          # Mode D：一次调用一份，内含各 idea 小节
│   │   └── A003-review-r01.md         # 审阅挂被审 ID；零填充轮次
│   └── code/
├── shared/                # 跨路线公用代码/笔记
└── .research-idea-pipeline/   # 机器状态（不入 docs）
```

**六条硬性规则：**

1. **文档按路线分离、各自扁平：** 产出放 `routeX/docs/`，**该目录内不再按类型分子目录**。
   **根 `docs/` 是跨路线共享区**——本 Skill **只保证 `refs/` 存在**，`notes/`、`latex/`
   等由项目与 `AGENTS.md` 决定。**唯一硬约束：路线文档不得放根 `docs/`。**
2. **两层 `README.md` + 两层 `INDEX.md`，分层管理：**

   | 层级 | `README.md` | `INDEX.md` |
   |---|---|---|
   | 根 | 项目总览 | **跨路线索引**（各路线状态、全局 TODO/Warnings） |
   | `routeX/` | 本路线说明 | **本路线索引**（文档索引 + **关系图** + 进度） |

   **每次产出后更新所在路线的 `INDEX.md`**；跨路线层面的变化同步更新根 `INDEX.md`。
3. **文件名前缀 = 文档 ID**（不再是路径隔离）：前缀仍**必需** —— 审阅要挂靠、跨路线
   引用要唯一。序号按路线独立递增、**永不复用**。
4. **审阅挂被审 ID、轮次零填充：** `<被审ID>-review-r01.md`、`-r02.md`（**不占新序号**）。
   用 `-r<NN>` 是因为 `-review.md`/`-review-2.md` 在 `ls`/`sort` 下**轮次顺序是反的**。
   一轮覆盖多份文档时挂主文档 ID，其余写 frontmatter 的 `also_reviewed`。
5. **参考文献集中：** 论文元数据/笔记/缓存一律放 **`docs/refs/`**（脚本默认
   `--local-dir ./docs/refs`）；机器状态放 `.research-idea-pipeline/`，日志放 `logs/`
   ——**都不进 docs 正文**。
6. **PDF 必须入索引：** `docs/refs/` 下的每个 PDF 都要在 **`docs/refs/index.json`**
   里有一条记录（字段见 [literature-policy.md](references/literature-policy.md) §7.1）。
   **索引进版本库，PDF 不进**。新增/替换/删除 PDF 后**必须重建索引**
   （`python3 scripts/refs_index.py`，校验 `--check`）；**未入索引的 PDF 视为不存在**。

> **slug 只能取：** `literature-survey` / `ideas` / `proposal` / `experiment-plan` /
> `narrative`。**Mode D 一次调用一份 `<R><NNN>-narrative.md`**（不再每个 idea 一份）。
> 完整规范见 [references/project-layout.md](references/project-layout.md)（含手工建骨架清单）。

---

### 1.5 推进纪律：理论建模是手段，不是终点（限制子代理行为）

> **禁止在「证明性工作」上停留与反复。** 数学理论的作用是**把问题建模清楚**，
> 据此找证据、提出方法、改进最终任务性能 —— **它不是交付物本身**。
> 这条规则同时约束**执行者**与**所有子代理**（尤其 S-Theory、R-ICML）。

**四步链（每个 idea / 方案都必须走得通）：**

| 步 | 内容 | 产出 |
|---|---|---|
| 1 | **数学理论建模** | 形式化问题：变量、假设、目标、结构性质 |
| 2 | **寻找证据** | 文献证据 + 实验证据（不是"我觉得"） |
| 3 | **结合机器学习领域的方法提出方法**，并**明确标注方法来源** | 可执行的方法 / 算法 + `方法来源 = 原创 / 部分原创 / 迁移` |
| 4 | **改进最终任务性能** | 有可测指标与公平比较 |

**方法来源必须显式标注（原创 / 部分原创 / 迁移）：**

| 标注 | 含义 | 判据 |
|---|---|---|
| **原创** | 方法的核心机制由本工作提出，不来自既有工作 | 必须指出最接近先前工作，并说明**机制层面**的不同 |
| **部分原创** | 核心机制部分来自既有工作，但有关键改造 / 新组合 / 新性质 | 必须写明**改了哪一条**，以及改造带来的新性质 |
| **迁移** | 把其他领域 / 任务的既有方法搬过来，机制本身不变 | 必须写明**来源领域 + 迁移合法性依据**；**迁移本身不算增量** |

**标注的硬性要求：**

- 每个方法都必须标 —— Mode B 的每个 idea、Mode C 的每条贡献、Mode D 的每套叙事。
  **不得留空，也不得模糊**（"受 X 启发"不是标注）。
- **迁移必须诚实标成迁移。** 把迁移包装成原创属于**夸大**，违反 §D2.4 的包装纪律
  （包装只允许改参照系，不允许改事实）。
- **迁移要成为贡献，必须证明迁移本身带来了新性质**（新的结构性质、理论条件或性能
  来源）。否则就只是"把 X 用到 Y 上" —— Mode B 的反模式、Mode E 的**复现风险高**。
- 标注必须**可核验**：能指向具体的先前工作与具体的机制差异。

**明令禁止：**

- ❌ 反复打磨证明（"再证一遍"不是进度）
- ❌ 把"证不出来"当成阻塞 —— 应标注 **"待补证明"** 后**继续走第 2—4 步**
- ❌ 把贡献定位成"我们证明了 X"，却没有方法、没有可验证性能
- ❌ 在证明性工作上无限迭代而不产出可执行方法与实验

**证明预算（防止无限证明）：** 证明类工作必须设**显式预算**（时间或轮次上限）。
预算用尽仍未完成 → **标注"待补证明 · 待核实"，转入第 2—4 步**，并在 `INDEX.md`
的 TODO 里留下补证任务。**不得**因此阻塞整条链路。

**唯一例外（主锚点为「理论」或「负结果」时）：** 第 4 步改为
「给出**可被实验检验的推论**或**可达到的松弛**」—— 此时"性能"指推论的可检验性，
不是 SOTA 指标。**但第 2、3 步仍然必须走通**：纯证明、无证据、无方法，依然不成立。

> ⚠️ **底线不变：** 本条约束的是**精力分配与停止条件**，不是诚实性。
> **不得**声称"已证明"却未完成证明；未完成的必须标 **"待补证明 · 待核实"**。

---

## 2. 共享资源索引

| 资源 | 位置 | 内容 |
|---|---|---|
| 子代理角色库 | [references/roles.md](references/roles.md) | R-CVPR / R-ICML / R-NeurIPS / **R-MICCAI** / A-Author / A-Experimenter / S-Lit / S-Nov / S-Theory / S-Feas / S-Devil / S-Repro |
| 顶会创新性标准 | [references/venue-standards.md](references/venue-standards.md) | CVPR / ICML / NeurIPS / MICCAI 四视角锚定标准 + 防复现标准 |
| 叙事套路库 | [references/narrative-patterns.md](references/narrative-patterns.md) | 十套顶会叙事逻辑、跨域五步升级、禁用表述、叙事自检 |
| 文献检索规范 | [references/literature-policy.md](references/literature-policy.md) | 禁止只停留在本地、T1—T7 强制扩检、L1/L2/L3 尽职调查、饱和判据、429 退避、代理环境识别、缓存 |
| 项目组织规范 | [references/project-layout.md](references/project-layout.md) | `docs/` 命名与 ID 分配、`INDEX.md` 章节、`AGENTS.md` 优先、`shared/` 公用、并发写入 |
| 评分与聚合政策 | [references/scoring-policy.md](references/scoring-policy.md) | **Mode D / E 共用**：1—5 标尺、**极性归一化**（S-Devil 反向）、门禁、逐维度中位数、**一票否决 + 带条件的推荐出口** |
| 证据等级与措辞 | [references/evidence-policy.md](references/evidence-policy.md) | **五 Mode 共用**：已核实 / 部分核实 / 据本次检索未见 / 待核实 / 待补证明 ↔ 允许与禁止表述（各 Mode 不再各自定义） |
| 检索实现脚本 | [scripts/literature_search.py](scripts/literature_search.py) | 可运行实现：**本地 + 多源**并集、每源状态、`--level`、`--exhaustive`、`--also-query`、`--venue`、`--cited-by`、退避、代理检测、`--check-env` |
| 多源适配器 | [scripts/literature_sources.py](scripts/literature_sources.py) | arxiv（新）/ openalex（关系）/ crossref（出处）+ 跨源合并层 |
| 环境自检脚本 | [scripts/env_probe.py](scripts/env_probe.py) | 发现工作解释器（已激活环境 → 项目 `.venv` → conda → PATH）；依赖缺失时退出码 4 |
| 离线测试 | [scripts/test_literature_search.py](scripts/test_literature_search.py) | stdlib unittest，全离线（环境发现 / 跨源合并 / 等级判定） |
| PDF 索引脚本 | [scripts/refs_index.py](scripts/refs_index.py) | 为 `docs/refs/` 下每个 PDF 建 `index.json` 条目；`--check` 校验（不一致退出码 3） |
| 状态传递模板 | [templates/state.template.json](templates/state.template.json) | `state.json` 片段结构 |
| 路线级索引模板 | [templates/INDEX.md](templates/INDEX.md) | `routeX/INDEX.md` 骨架（文档索引 + **关系图** + 已证实/已证伪/TODO/Bugs/Warnings） |
| 根级索引模板 | [templates/INDEX.root.md](templates/INDEX.root.md) | 根 `INDEX.md` 骨架（跨路线索引 + 全局 TODO/Warnings） |
| 路线级说明模板 | [templates/README.route.md](templates/README.route.md) | `routeX/README.md` 骨架（本路线做什么、怎么跑、目录组织） |
| 串联示例 | [examples/](examples/) | B→C→D→E 串联、接续复核、单独文献调研、多路线目录管理的示例 |

---

## 3. 子代理派遣总览

> **派遣前先定「派遣方式」（§3.1）：Team 还是默认子代理。** 方式未定不得开始派遣。

所有 Mode 共享同一角色库。按 Mode 需派遣的子代理如下（角色定义不重复，见
[references/roles.md](references/roles.md)）：

| Mode | 派遣子代理 |
|---|---|
| A | 无（执行者直接完成检索与归纳） |
| B | 头脑风暴：R-CVPR、R-ICML、R-NeurIPS、**R-MICCAI**、A-Author、A-Experimenter、S-Devil（每个至少 3 个 idea）；<br>**idea 级审核（B5）**：四审稿人（创新性）+ S-Lit、**S-Nov（按需）**、S-Feas + **S-Theory（按需，仅含理论声称时）** + S-Devil（致命反驳） |
| C | R-CVPR、R-ICML、R-NeurIPS、**R-MICCAI**（创新性）；S-Lit（先前工作核实）；**S-Nov（按需，S-Lit 判"边缘"时）**；S-Feas（可行性）；S-Theory（理论基础）；A-Author（投稿人视角展开提案）；A-Experimenter（实验设计者视角展开实验） |
| D | **叙事审核六子代理**：R-CVPR、R-ICML、R-NeurIPS、**R-MICCAI**、S-Devil、S-Lit（**六子代理全部派遣、不得裁减，S-Lit 恒派**；idea 多时可另加 S-Feas / S-Repro） |
| E | R-CVPR、R-ICML、R-NeurIPS、**R-MICCAI**、S-Devil、S-Feas、S-Lit（含**复现风险判定**）、S-Repro（**八子代理**严格审查 + 交叉质询）；**S-Nov（按需，S-Lit 判"边缘"或涉及"首次"时）** |

**职责边界：** 不派遣 S-Repro 到 Mode B（idea 阶段无代码可复现）；B5 的审核是
**概念级快筛**，不要与 Mode E 的方案级深审重复。详见
[mode-b](references/mode-b-idea-discovery.md) §B0 与
[mode-e](references/mode-e-proposal-review.md) §E0。

**派遣原则：** 子代理必须**独立产出**，不得互相抄袭结论；汇总时去重并保留来源标注。
**Mode D 与 Mode E 都要求交叉质询**：每个子代理对其余子代理的评分提出至少一条质疑
或补充；**聚合前必须先做极性归一化**（[scoring-policy.md](references/scoring-policy.md)），
综合评分取**归一化后**的中位数。**S-Devil 的「新颖性反驳」是反向维度**
（`5 = 完全无新颖性`，越低越好），归一化为 **新颖性稳健度 = 6 − 反驳分**。

### 3.1 派遣方式：Team 优先询问（强制）

**每次准备派发子代理前，先判断当前环境是否具备 Team 能力**（能创建持久、可被寻址的
teammate，例如 Agent Teams）。然后按三种情形处理：

| # | 情形 | 处理 |
|---|---|---|
| 1 | **环境具备 Team 能力** | **必须先询问用户是否使用 Team**，不得自行决定。用户要求用 → **用 Team**；用户不要或未表态 → 用默认子代理 |
| 2 | **环境不具备 Team 能力，用户也没提** | 用**默认子代理**，无需询问 |
| 3 | **用户显式要求用 Team，但环境不具备该能力** | **回退到默认子代理**，并**明确告知用户"当前环境无 Team 能力，已回退"** |

**硬约束：**

- **不得静默降级：** 回退必须显式说出来，不能让用户以为用了 Team。
- **不得假装用了 Team：** 没有该能力时，输出中不得出现"已派发 teammate"之类表述。
- **不得因为"Team 更高级"就默认启用：** Team 有持久化与并发写入成本，必须由用户选择。
- **方式不改变标准：** 无论用 Team 还是默认子代理，**角色库、派遣矩阵、评分维度、
  交叉质询与中位数规则完全一致**（见 [references/roles.md](references/roles.md)）。
  Team 只改变执行方式，**不改变审查标准**。
- **用 Team 时必须守写作用域：** 并行写者写**互不重叠**的文件；写冲突按
  "重新读取后再提交"处理（见 [project-layout.md](references/project-layout.md) §5）。

> 详见 [references/roles.md](references/roles.md) §4。

---

## 4. 各 Mode 输入 / 输出速查

### Mode A — literature-survey

- **输入：** 检索关键词或研究问题；检索范围（时间范围、会议范围、数量上限）；
  尽职调查等级（L1/L2/L3，默认按触发条件自动判定）。
- **流程：** A1 本地检索 → A2 **在线源强制补充检索**（不得因本地命中而跳过）→
  A3 范围扩大策略 → A4 饱和判定与输出。
- **交付物：** 文献列表（含来源标注）+ 检索过程记录（含 429 等待日志）+ 本地缓存
  更新记录 + 尽职调查等级达成情况。
- **落盘：** `<routeX>/docs/<R>NNN-literature-survey.md`（含负检索记录），
  并更新该路线 `INDEX.md`；**检索未达饱和必须记入 Warnings**。

### Mode B — idea-discovery

- **输入：** 研究领域关键词；已有参考文献（可选）；资源约束（可选）。
- **流程：** B1 基础文献调研（**必须走 Mode A 或等价的脚本调用，禁止内联自行实现检索**）→
  B2 深度局限性分析 →
  B3 多子代理头脑风暴 → B4 发散策略约束 →
  **B5 idea 级创新性与可行性审核（强制）** → B6 输出 → B7 落盘。
- **发散策略约束：** 每个 idea 必须通过以下**至少一种**策略推导：
  *问题重构 / 假设挑战 / 跨域迁移 / 反向思考 / 组合创新*。
- **B5 审核（不可跳过）：** 对每个候选 idea 给出 **创新性评分 + 可行性评分 +
  重叠度 + 致命反驳 + 推荐优先级**。**进入 shortlist 的门槛 = 完成 L2 检索**；
  **只有要写进文档的「首次提出」类声称才要求 L3**（并附负检索记录）。
  唯一例外是**在线源不可用**等不可控情况，此时必须标注"据本次检索未见 · 待核实"并记入
  INDEX 的 Warnings。**不派遣 S-Repro。**
- **交付物：** idea 候选清单（**原始候选 ≥10、去重后 ≥6，每个都带审核结论**；
  领域过窄时可说明原因并减少）+ 技术路线归纳表
  + 创新性边界界定 + **推荐 shortlist（3—5 个）+ 淘汰清单**。
- **落盘：** `<routeX>/docs/<R>NNN-ideas.md`，并更新该路线 `INDEX.md`
  （文档索引；被放弃的 idea 记入**已证伪**；未核实的无人区声称记 Warnings）。

### Mode C — proposal-generation

- **输入：** 一个或多个 idea（来自 Mode B 或用户直接提供）；关键参考文献（可选）；
  资源约束（可选）。
- **流程：** C1 创新性研究（**对 B5 的增量复核**：只深化 B5 判"边缘/不足"的项；
  B5 判"足够"且期间无新文献的项直接引用 B5 结论，不重做 L3；四审稿人视角 + S-Lit 核实）
  → C2 可行性研究
  （S-Feas + S-Theory）→ C3 论文格式展开 → C4 实验流程设计（0—13 共 14 节）→ C5 输出。
- **交付物：** 论文提案（1500—2000 字）+ 实验流程计划书 + 创新性判定 + 可行性评分
  + 风险清单。
- **落盘：** `<routeX>/docs/<R>NNN-proposal.md` + `<routeX>/docs/<R>NNN-experiment-plan.md`（各占独立序号），
  并更新该路线 `INDEX.md`（方案索引、TODO、依赖与风险）。

### Mode D — narrative-generation

- **输入：** **idea 清单**（来自 Mode B 或用户提供）+ **方案**（来自 Mode C，推荐）；
  关键参考文献（可选）；目标会议（可选）；资源约束（可选）。
- **定位：** **基于 idea + 方案建立多种顶会风格的叙事逻辑，并拉起子代理评审**；
  决定"怎么讲才不被判增量"。**这是基于「预期贡献」的叙事预演，不是基于「实测结果」的
  包装** —— 实验完成后应**回到 Mode D 复核叙事是否仍成立**。字母顺序上位于方案生成
  与方案复核之间。
- **流程：** D0.1 信息完整性检查 → D1 叙事套路锚定（每 idea ≥4 套候选）→
  D2 每套叙事的生成（含跨域五步升级、五段式、包装前后对照；**详写最佳 2 套**）→
  D3 六子代理评审（**六子代理全部派遣、S-Lit 恒派**）→
  D4 交叉质询与共识（归一化后逐维度中位数）→ D5 最佳叙事推荐。
- **交付物：** 多套路叙事清单（每 idea **≥4 套候选**，其中**详写最佳 2 套、各 ≥300 字**，
  其余给摘要）+
  六子代理独立评审意见 + 交叉质询记录 + 最佳叙事推荐 + 横向对比表 + 最终优先级建议。
- **落盘：** `<routeX>/docs/<R>NNN-narrative.md`，并更新该路线 `INDEX.md`
  （被覆盖的叙事套路 → **已证伪**；最佳叙事 → **已证实**；综合评分 <3 → Warnings）。

### Mode E — proposal-review

- **输入：** 待复核方案（来自 Mode C 或用户提供）；上一次审阅内容（可选，用于接续
  复核）；关键参考文献（可选）。
- **定位：** 对象是**已成型方案**；主战场是**方法正确性与工程可行性**；创新性维度
  以**防复现**为核心目的（见 §0 的「各阶段的分工」）。
  **E 不是链条终点，而是反馈环**——结论可回流到 **Mode C**（重写方案 / 补实验）或
  **Mode B**（缺陷指向 idea 本身）。**三个触发点：** ① Mode C 产出后首次复核；
  ② **实验完成、有实测结果后**（"预期"变"实测"，**防复现检查必须重做**）；
  ③ 投稿被拒 / 改投时。
- **流程：** E1 判断复核类型（首次 / 接续）→ E2 八子代理严格审查（含**防复现检查**）
  → E3 交叉质询与共识形成（**先做极性归一化**，见
  [scoring-policy.md](references/scoring-policy.md)）→ E4 复核结论 → E5 接续复核规则。
- **交付物：** 八子代理评审意见 + 交叉质询记录 + 审查结论卡片（含**复现风险等级**）
  + 横向对比表 +（接续复核时）变更追踪表。
- **落盘：** `<routeX>/docs/<被审ID>-review-r01.md`（接续复核用 `-r02.md`），
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

**E 不是链条终点，而是反馈环：** E 的结论可**回流到 Mode C**（按审阅意见重写方案 /
补实验）或 **Mode B**（缺陷指向 idea 本身不成立）。三个触发点：① Mode C 产出后首次
复核；② **实验完成、有实测结果后**（"预期"变"实测"，**防复现检查必须重做**）；
③ 投稿被拒 / 改投时（详见 [mode-e](references/mode-e-proposal-review.md) §E1.1）。

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
- **人类可读产出**写入**所在路线的 `<routeX>/docs/`**（方案、审阅记录、文献报告），
  并**同步更新该路线的 `INDEX.md`**。详见 [references/project-layout.md](references/project-layout.md)。

---

## 6. 执行自检清单（每次输出前）

- [ ] mode 已明确，且与该 Mode 的输入约定一致。
- [ ] **锚定点（核心目标）已与用户确认**，并已写入 frontmatter 的 `core_goal`、
      路线 `INDEX.md` 的路线概要、以及 `state.json`；**未确认就开工属于违规**。
- [ ] **派遣方式已定**：环境有 Team 能力时**已询问用户**；用户显式要求 Team 而环境
      不具备时，已**显式告知回退**（未静默降级、未假装使用 Team）。
- [ ] **已读项目 `AGENTS.md` 与目标路线的 `INDEX.md`**，并遵循其约定。
- [ ] 文献检索：**先本地后 arxiv，且没有只停留在本地**——本地命中后仍执行了 arxiv
      检索（除非用户显式 `--local-only`）。
- [ ] 已判定触发条件（T1—T7）并达到对应尽职调查等级（L1/L2/L3）与饱和判据。
- [ ] 每条文献结果标注了 `source`；结果集是本地 + 多源 的并集。
- [ ] 若发生 429，输出了等待日志，且退避符合 `10→20→40→80→160s`、上限 5 次。
- [ ] **每个启用源都有状态**（`ok` / `partial` / `unavailable` / `skipped`）；任一源降级已在输出中显式说明，且**退出码为 2**。
- [ ] **饱和计数只在「当期可用源集合未变」时累加**；集合一变已重置计数。
- [ ] 若少用了源（`--sources`），报告中已写明理由；源覆盖不完整时结论措辞已降级。
- [ ] **已解析 `arxiv.org` / `export.arxiv.org`；若解析到本地 IP，输出了「代理环境提示」段**
      （写明具体 IP 与判定类型），且**没有**据此判定"在线源不可用 / 无人在研究"。
- [ ] arxiv 结果已写入缓存。
- [ ] 创新性判定引用了具体顶会标准；贡献标注了类型。
- [ ] **每个方法都标了「方法来源」**（`原创` / `部分原创` / `迁移`）且**可核验**；
      没有把「迁移」包装成「原创」；标为「迁移」的**已证明迁移本身带来新性质**，
      否则其复现风险按"高"处理。
- [ ] **四步链完整**（数学建模 → 证据 → 结合 ML 方法 → 任务性能）；**没有在证明性
      工作上停留或反复**；未完成的证明已标 **"待补证明 · 待核实"** 并转入后续步骤，
      而不是阻塞链路；**也没有声称"已证明"却未完成证明**。
- [ ] **四个会议审稿人的评价都含「理论角度 + 应用角度 + 会议特性判定」三段**
      （见 [roles.md](references/roles.md) §1.0）；R-MICCAI 不适用时已标 **"不适用"**
      而非硬凑临床相关性。
- [ ] **Mode B：每个 idea 都带 B5 审核结论**（创新性/可行性/重叠度/致命反驳/优先级），
      没有"只给 idea 不给审核"；且未误派 S-Repro；**进入 shortlist 的 idea 已达 L2**，
      含「首次提出」声称的已达 L3 并附负检索记录。
- [ ] **Mode D：每个 idea 至少 4 套候选，其中详写最佳 2 套（各 ≥300 字），其余给摘要**；
      已用**五段式**；跨域类已完成
      **五步升级**；最佳叙事**综合了全部子代理维度**（非只看创新性）；
      **六子代理全部派遣（S-Lit 恒派）**；已做**叙事包装
      （重新定位，非夸大）**；无禁用表述。
- [ ] **Mode E：结论卡片给出了复现风险等级**，并回答了"设计层面贡献 vs 实现层面改进"；
      复现风险 = 高时总体判定不为"高"；**S-Devil 归一化后的新颖性稳健度 ≤ 2 时总体判定
      同样不为"高"**（除非走「带条件的推荐」并写明理由、缓解路径与验证点）。
- [ ] **Mode D / E 的评分聚合前已做极性归一化**（S-Devil 反驳分 → 新颖性稳健度 =
      `6 − 反驳分`），汇总表同时给出原始分与归一化分（见
      [scoring-policy.md](references/scoring-policy.md)）。
- [ ] 所有"首次提出"声称**已完成 L3 穷尽检索**、经 S-Lit 核实、附负检索记录，
      否则已降级为"据本次检索未见"或标注"待核实"；
      **全部措辞符合 [evidence-policy.md](references/evidence-policy.md) 的证据等级表**。
- [ ] **INDEX 的 Warnings 已统计「待核实」条数**；若超过 5，已在本轮内收敛
      （补检索 / 补实验 / 明确降级措辞）。
- [ ] 理论/可行性卡点已先检索（含负结果文献），未直接假设成立。
- [ ] 无臆造引用；无法确认处标注"待核实"。
- [ ] **方案/审阅记录已落盘到所在路线的 `<routeX>/docs/`**，命名符合
      `<R><NNN>-<slug>.md` / `<ID>-review-r01.md`；且**文档前缀 = 路线字母**（不随 Mode 变化）。
- [ ] **`docs/refs/` 下每个 PDF 都在 `docs/refs/index.json` 里有条目**
      （`python3 scripts/refs_index.py --check` 通过）；索引中无绝对路径；
      `needs_verification = true` 的条目**未**用于支撑创新性声明。
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
7. **为什么文档也按路线分目录，而不是集中到根 `docs/`？** 早期设计把文档集中到根
   `docs/`，靠文件名前缀隔离路线。实际用起来有两个问题：① 每条路线都会持续产出
   （方案、叙事、多轮审阅），**文件数线性增长，"集中"很快变成"平摊"**；② 前缀成了
   唯一的隔离手段，一旦写错就无法补救。
   改为**文档随路线走**（`routeX/docs/`，目录内仍保持扁平），根 `docs/` 退为**跨路线
   共享区**（只保证有 `refs/`）。**前缀仍然保留，但身份变了**：它不再是隔离手段，
   而是**文档 ID** —— 审阅要挂靠（`A003-review-r01`）、跨路线引用要唯一（`A002/I3`）。
   两层 `README.md` / `INDEX.md` 分别管住"项目级"与"路线级"，避免根索引膨胀成流水账。
8. **为什么 INDEX.md 要区分"已证实"与"已证伪"？** 负结果常被丢弃，导致后人重复
   踩坑。把证伪结论与 TODO/Bugs/Warnings 一起固化为项目资产，是最省算力的做法。
9. **为什么把评分与证据措辞抽成共享文件？** 这两类机制被多个 Mode 复用，**复制一份
   就是多一个漂移源**：改了一处、漏了另一处，就会出现"同一条规则两个版本"。
   因此 [scoring-policy.md](references/scoring-policy.md) 与
   [evidence-policy.md](references/evidence-policy.md) 各自做**唯一权威定义**，
   各 Mode 只保留自己特有的部分（如 D 的维度向量规模、E 的八子代理分工）并引用它们。
10. **为什么 Mode E 也必须做极性归一化？** E 与 D 同样使用 S-Devil 的**反向**「新颖性
   反驳」分（`5 = 完全无新颖性`）。不归一化就直接取中位数，会把**最没新颖性的方案
   算成高分**——与 D 的极性错误同类。归一化（`稳健度 = 6 − 反驳分`）是聚合的前置条件。

---

## 8. 规则变更自检清单（维护本 Skill 时用）

> **与 §6 的区别：** §6 是**执行时**的输出自检；本节是**改本 Skill 自身**时的自检。
> 触发条件：改动任何**规则、命名、枚举、计数、路径**。

**为什么需要它：** 本仓库的实际漂移记录显示，改了规则后**漏掉的从来不是规则本身**，
而是下面 A 组这三类"看起来不像规则"的位置。

### A. 三类高危位置（历史上反复漏）

| # | 位置 | 为什么危险 | 必做动作 |
|---|---|---|---|
| A1 | **设计依据 / 理由段**（§7、各文件开头的"为什么"） | 它在**论证旧设计**，读起来像权威依据。改规则后最容易整条漏掉，且在有人质疑设计时被当成正确论点引用 | **逐条读一遍 §7 与各"为什么"，问："这条还在支持当前规则吗？"** |
| A2 | **速查 / 汇总表**（§4 各 Mode 速查、`project-layout` §6 落盘职责表、`roles` §4.2 派遣矩阵、`mode-d` D3.3 汇总表） | 汇总表是规则的**复制品**。改规则不改它 = 仓库里有两份互相矛盾的规则 | **所有"表格式汇总"逐个核对** |
| A3 | **示例与模板**（`examples/*`、`templates/*`） | 示例会**示范旧写法**，且比正文更容易被照抄 | **示例里的文件名、路径、计数、命令逐个核对** |

### B. 计数与枚举（每轮都漏）

| # | 对象 | 历史改动 | 分布位置 |
|---|---|---|---|
| B1 | **子代理数** | 会议审稿人 `3→4`；B3 头脑风暴 `6→7`；Mode D `5→6`；Mode E `7→8` | 标题、正文、汇总表、速查节、`roles` 矩阵 |
| B2 | **规则条数** | §1 `四→五`；§1.4 布局规则 `四→五→六` | **标题里的"N 条"必须与该节实际条目数一致** |
| B3 | **会议枚举** | `CVPR/ICML/NeurIPS` → `+MICCAI` | 约 13 处 |
| B4 | **源枚举** | `local\|arxiv` → `+openalex\|crossref` | 约 15 处（注意 `index.json` 的 `source` 是**另一种含义**，不要改） |
| B5 | **slug 枚举** | 叙事从「每个 idea 一个后缀式 slug」改为单一 slug | 类型表、规则表、示例、模板 |
| B6 | **退出码** | `0/1/2` → `0/1/2/4` | CLI 表、退出码表、各 Mode 输出说明 |

### C. 路径与命名

| # | 对象 | 历史改动 |
|---|---|---|
| C1 | **落盘路径** | `docs/` → `routeX/docs/`（**含 §4 速查节** —— 曾漏 5 处） |
| C2 | **审阅命名** | `<ID>-review.md` → `<ID>-review-r01.md` |
| C3 | **标题里的旧词** | 曾漏 `mode-a` 的 A2 标题（正文早已改为多源，标题仍写旧源名） |

### D. 机械校验（先跑，再人工）

```bash
# 1) 相对链接可达（排除代码围栏内的示例路径与模板占位路径）
# 2) §X<n> 与 §<数字> 引用可解析
# 3) JSON 文件与 md 内 ```json 围栏块合法
python3 scripts/refs_index.py --check
python3 -m unittest discover -s scripts -p "test_*.py"

# 4) 陈旧措辞扫描 —— 必须为 0
# 废弃词清单在 references/deprecated-terms.txt（.txt 天然被 --include=*.md 排除，
# 因此扫描结果才能真的为 0）；以后新增废弃表述就追加到那个文件。
PAT=$(grep -vhE '^\s*(#|$)' references/deprecated-terms.txt | paste -sd'|')
grep -rnE "$PAT" --include=*.md .          # 期望：0 命中（exit 1）

# 5) 落盘路径必须带 routeX/ 前缀 —— 正确的写法以 `<routeX>/docs/ 开头，
#    所以「反引号紧跟 docs/」就是缺前缀
grep -rnE '`docs/<' --include=*.md . | grep -vE 'templates/INDEX\.md|grep -rnE'
#    ↑ 排除 templates/INDEX.md：该模板本身就在 routeX/ 内，其 `docs/` 是相对路径，正确
```

> **D4 的"已废弃措辞"清单要持续维护**：每次改规则时，把**被替换掉的旧表述**
> 追加进来。这份 grep 清单是防漂移最省力的一道闸。

### D5. **内容丢失检查（本次真实教训）**

用「按区间替换」改动大段文本时，很容易**把夹在区间内的其它章节整节吞掉**。
本次真实发生过：重写 §1.4 时替换区间取到 `## 2.`，**把夹在中间的 §1.5 整节删除**
（一个用户明确要求的规则）——而当时的链接/引用检查**完全测不出来**，
因为引用处写的是 `§1.5` 这个**字符串**，字符串还在。

**必做：** 任何按区间替换的编辑，都要检查被替换区间内是否含其它标题：

```bash
git diff -U0 -- SKILL.md | grep -E '^[-+]## '     # 标题增删一眼可见
git log --oneline -S"<被删章节的关键词>" -- SKILL.md
```

### E. 清单自身

**改完后问一句：这次漏掉的位置，属于 A/B/C 里的哪一类？**
如果是**新的一类**，把它加进上表 —— 否则下一轮还会漏在同一处。
