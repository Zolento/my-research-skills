# 项目组织与文档落盘规范

所有 Mode 产出的**方案**与**审阅记录**都必须落盘到项目 `docs/` 目录，**以适合人类
阅读的格式（Markdown）存储**，并按路线分开管理。本文件定义目录结构、命名、文档
ID 分配、`INDEX.md` 与 `AGENTS.md` 的规范。

---

## 0. AGENTS.md 优先原则（最高优先级）

**开工前第一件事：检查项目根目录是否存在 `AGENTS.md`。**

| 情况 | 行为 |
|---|---|
| 存在 `AGENTS.md` | **遵循它的约定**；与本文件冲突时以 `AGENTS.md` 为准（用户显式约定 > Skill 默认） |
| 不存在 | 使用本文件的默认约定 |

`AGENTS.md` 规定的典型内容：目录结构、命名规则、公用代码放哪、测试与提交规范、
哪些目录由谁写。**多代理/多人协作时，它是唯一的共享契约**——所有成员先读后写。

---

## 1. 标准项目布局

**各路线产出的文档放该路线自己的 `routeX/docs/`（扁平，不按类型再分子目录）；
根目录 `docs/` 是跨路线共享区，至少保证有 `refs/`（参考文献库）。根目录与每条路线
各自有 `README.md` 与 `INDEX.md`，分层管理各自层级的文件。**

```
<项目根目录>/
├── AGENTS.md                    # 共享契约：布局、命名、公用部分规范（最高优先级）
├── README.md                    # ★ 根级：项目总览（研究问题、路线列表、怎么跑）
├── INDEX.md                     # ★ 根级：跨路线索引（各路线状态 + 全局 TODO / Warnings）
├── docs/                        # ★ 跨路线共享区（不放路线文档）
│   ├── refs/                    # ★ 必需：参考文献库（= 本地文献库根目录）
│   │   ├── papers/              # {paper_id}.pdf + .json sidecar + 可选 .md
│   │   ├── cache/<source>/      # 查询缓存（按源分目录）
│   │   └── index.json           # ★ 必需：PDF 索引（每个 PDF 一条记录，进版本库）
│   ├── notes/                   # 可选：跨路线共享笔记（按 AGENTS.md）
│   └── latex/                   # 可选：跨路线共享 LaTeX 模板/样式（按 AGENTS.md）
├── routeA/
│   ├── README.md                # ★ 路线级：本路线说明（做什么、怎么跑、目录说明）
│   ├── INDEX.md                 # ★ 路线级：本路线索引（文档索引 + 关系图 + 进度）
│   ├── docs/                    # ★ 本路线文档（扁平；不再按类型分子目录）
│   │   ├── A001-literature-survey.md
│   │   ├── A002-ideas.md
│   │   ├── A003-proposal.md
│   │   ├── A004-experiment-plan.md
│   │   ├── A005-narrative.md
│   │   └── A003-review-r01.md
│   ├── code/                    # 该路线专属代码
│   └── experiments/
├── routeB/
│   ├── README.md
│   ├── INDEX.md
│   ├── docs/                    # B001-… 同样扁平
│   └── code/
├── shared/                      # 跨路线公用代码/笔记（按 AGENTS.md 规范）
└── .research-idea-pipeline/     # 机器状态
```

### 1.1 六条硬性规则

1. **文档按路线分离、各自扁平：** 每条路线的产出放 `routeX/docs/`，**该目录内不再按
   类型分子目录**（方案、叙事、审阅平铺在一起，靠文件名排序与识别）。
   **根目录 `docs/` 是跨路线共享区**：Skill **只保证 `refs/` 存在**，
   其他共享子目录（`notes/`、`latex/` 等）由项目与 `AGENTS.md` 决定，本 Skill
   不规定也不禁止。**唯一的硬约束是：路线文档不得放根 `docs/`。**
2. **两层 `README.md` + 两层 `INDEX.md`：** 根目录与每条路线**都必须**各有
   `README.md` 与 `INDEX.md`，**分层管理各自层级的文件**：

   | 层级 | `README.md` | `INDEX.md` |
   |---|---|---|
   | 根 | 项目总览：研究问题、路线列表、统一怎么跑 | **跨路线索引**：各路线状态、全局 TODO / Warnings |
   | `routeX/` | 本路线说明：目标、怎么跑、目录说明 | **本路线索引**：文档索引 + 关系图 + 进度 |

   **每次产出后必须更新所在路线的 `INDEX.md`**；涉及跨路线层面的变化（新增路线、
   全局风险）同步更新根 `INDEX.md`。
3. **文件名前缀 = 文档 ID，不再是路径隔离：** 文档已按路线分目录，前缀（`A` / `B`）
   不再承担"唯一的路线隔离手段"，但它**仍然是文档 ID** —— 审阅要挂靠、跨路线引用要
   唯一、`state.json` 与正文按 ID 引用。**前缀保留；序号按路线独立递增、永不复用。**
4. **路线隔离：** 每条路线 `routeX/` 自带代码与实验；**路线之间不得互相 import**，
   需要复用的一律下沉到 `shared/`。
5. **参考文献集中：** 论文元数据/笔记/缓存一律放**根目录 `docs/refs/`**，
   不要散落到 `routeX/docs/`；跨路线共享的笔记 / LaTeX 放根 `docs/` 的其他子目录。
6. **PDF 必须入索引：** `docs/refs/` 下的**每个 PDF** 都要在 **`docs/refs/index.json`**
   里有一条记录（完整字段见 [literature-policy.md](literature-policy.md) §7.1）。
   **索引进版本库，PDF 不进**（PDF 是大文件）。新增 / 替换 / 删除 PDF 后**必须重建索引**
   （`python3 scripts/refs_index.py`，校验用 `--check`）；**未入索引的 PDF 视为不存在**。

> **命名说明：** 路线目录用 `routeA` / `routeB`，其文档 ID 前缀用**大写路线字母**
> `A` / `B`。此处的 A/B 是**路线编号，与 Mode A/B/C/D/E 无关**；文档属于哪个 Mode
> 记录在文档 frontmatter 的 `mode` 字段里。

---

## 2. 文档命名与 ID 分配

> **记法：** `<routeX>` = 路线目录（如 `routeA`）；`<R>` = 该路线对应的**大写路线
> 字母**（如 `A`）；`<NNN>` = 三位序号；`<ID>` = 完整文档 ID（如 `A002`）；
> `<I<n>>` = idea 子编号（如 `I1`）。

### 2.1 文档类型与文件名（唯一权威表）

**`<slug>` 只能取下表枚举值**，不得自创。文件位于 **`<routeX>/docs/`**。

| type（frontmatter） | slug | 文件名 | 产出 Mode |
|---|---|---|---|
| `literature-survey` | `literature-survey` | `<R><NNN>-literature-survey.md` | A |
| `idea-discovery` | `ideas` | `<R><NNN>-ideas.md` | B |
| `proposal` | `proposal` | `<R><NNN>-proposal.md` | C |
| `experiment-plan` | `experiment-plan` | `<R><NNN>-experiment-plan.md` | C（独立序号） |
| `narrative` | `narrative` | `<R><NNN>-narrative.md` | D（**一次调用一份**，内含各 idea 的小节） |
| `review` | —（特殊，见 §2.3） | `<被审ID>-review-r<NN>.md` | E（或 D 的叙事审核） |

```
routeA/docs/
├── A001-literature-survey.md      # Mode A
├── A002-ideas.md                  # Mode B —— 含 I1..In 与 B5 审核结论
├── A003-proposal.md               # Mode C
├── A004-experiment-plan.md        # Mode C
├── A005-narrative.md              # Mode D —— 一次调用：I1..In 的全部叙事 + 审核 + 推荐
├── A003-review-r01.md             # Mode E —— 对 A003 的第 1 轮审阅
└── A003-review-r02.md             # Mode E —— 接续复核（第 2 轮）
```

> **为什么叙事不再每个 idea 一份？** Mode D 的产出本来就是**一份**报告：它含全部 idea 的
> 叙事、**跨 idea 的交叉质询**、**跨 idea 的最佳推荐与最终优先级建议**。硬拆成 N 份文件后，
> 这些跨 idea 的内容只能重复或随意归属，而且每个 idea 都要吃掉一个新序号。

### 2.2 子编号规范（路线内唯一，不复用）

| 前缀 | 含义 | 定义处 | 示例 |
|---|---|---|---|
| `I<n>` | **idea**（由 Mode B 产出，Mode C/D 引用） | `-ideas.md` | `I1`、`I3` |
| `N<k>` | **叙事套路**（全局固定 1—10，见 [narrative-patterns.md](narrative-patterns.md) §1） | 套路库 | `N2`、`N9` |
| `K<n>` | **贡献**（方案内；**不用 C**，避免与 Mode C 章节号 C1—C7 撞） | `-proposal.md` | `K1`、`K2` |
| `E<n>` | **实验** | `-experiment-plan.md` | `E1`、`E4` |
| `H<n>` | **假设** | `-experiment-plan.md` | `H1` |

**跨文档引用写法：** `<文档ID>/<子编号>` ——
如 `A002/I3`（A002 里的第 3 个 idea）、`A003/K1`、`A004/E2`、`A005/N2`。

> 子编号**只在所属路线内唯一**，不跨路线共享。

### 2.3 审阅意见命名（Mode E / Mode D 叙事审核）

**统一规则：审阅意见永远挂在「被审文档的 ID」上，不占用新序号。**

```
<routeX>/docs/<被审ID>-review-r01.md    # 第 1 轮
<routeX>/docs/<被审ID>-review-r02.md    # 第 2 轮（接续复核）
<routeX>/docs/<被审ID>-review-r10.md    # 第 10 轮
```

**为什么用 `-r<NN>` 而不是 `-review.md` / `-review-2.md`：**

| 问题 | 旧写法 `-review.md` / `-review-2.md` | 新写法 `-review-r01.md` |
|---|---|---|
| `ls` / `sort` 顺序 | **第 1 轮排在最后**（`-` 排在 `.` 前），第 10 轮排最前 | 就是轮次顺序 |
| 轮次可读性 | 第 1 轮无编号，靠"没有后缀"推断 | `r01` / `r02` 一眼可读 |
| 歧义 | `A003-review-2` 到底是"第 2 轮"还是"被审 ID 为 A003-review-2" | 无歧义 |

**规则：**

- `<被审ID>` 是被审**文档的 ID**（不是文件名），可以是任意类型：方案 `A003`、
  实验计划 `A004`、叙事 `A005` 等。
- `r<NN>` **零填充两位**（`r01`…`r99`），保证字典序 = 轮次序。
  **边界：** 超过 99 轮时（`r100`）字典序不再等于轮次序 —— 此时改用三位
  （`r001`…`r999`）并在该路线 `INDEX.md` 的变更日志注明切换点。同一路线内
  **不得混用两种宽度**。
  同理，`<NNN>` 是三位序号，超过 999 份文档时须在 `AGENTS.md` 里另行约定。
- 文件名里**不出现** Mode 字母，避免与路线字母混淆。
- **一轮覆盖多个文档时**（如同时审 proposal + experiment-plan）：挂在**主文档**
  （proposal 或 narrative）的 ID 上，其余写进 frontmatter 的 `also_reviewed`。
- frontmatter 必须写 `review_of` 与 `review_round`。

**示例：**

| 被审对象 | 第 1 轮 | 第 2 轮 |
|---|---|---|
| 方案 `A003` | `A003-review-r01.md` | `A003-review-r02.md` |
| 实验计划 `A004` | `A004-review-r01.md` | `A004-review-r02.md` |
| 叙事 `A005` | `A005-review-r01.md` | `A005-review-r02.md` |
| 跨文档复核（A003 + A004） | `A003-review-r01.md`（frontmatter `also_reviewed: [A004]`） | `A003-review-r02.md` |

### 2.4 叙事文档的内部结构

**一次 Mode D 调用产出一份 `<R><NNN>-narrative.md`**，内含**全部 idea**的叙事，
按 idea 分节：

```markdown
# A005 — 多套路叙事（I1 / I3 / I5）

## 摘要

| idea | 尝试套路 | 最佳套路 | 综合中位数 | 是否否决 |
|---|---|---|---|---|
| I1 | N2/N3/N5/N9 | **N2** | 4.0 | 否 |
| I3 | N2/N3/N5/N9 | N3 | 3.0 | 否 |

## idea I1

### I1 / N2 瓶颈突破/移除假设     ← 套路编号与名称必须取自套路库 §1
#### N2.1 套路名称与适配理由
#### N2.2 五段式叙事主线（≥300 字）
#### N2.3 贡献清单（标注贡献类型 + 方法来源）
#### N2.4 为什么之前没人做
#### N2.5 该套路的弱点
#### N2.6 包装前后对照

### I1 / N3 跨域理论迁移
...

## idea I3
...

## 交叉质询（跨 idea）

## 最佳叙事推荐（跨 idea）

## 最终优先级建议（跨 idea）
```

**硬规则：**

1. **一次调用一份文档**；同一批 idea 重做叙事取**新序号**，并在 frontmatter
   `supersedes` 指向旧 ID。
2. **每个 idea 至少 4 套**套路，每套主线 **≥300 字**。
3. **跨 idea 的内容（交叉质询、最佳推荐、最终建议）集中在本文件末尾**，
   不要分散到 per-idea 小节里。
4. 套路编号 `N<k>` **必须**取自套路库；跨文档引用写 `A005/I1/N2`。

### 2.5 硬规则（不随 Mode 变化）

1. **文档 ID 前缀 = 所属路线的字母。** `routeA` 下的文档一律 `A` 开头，
   `routeB` 下一律 `B` 开头；**绝不允许** `routeB` 下出现 `A0xx`。
2. **前缀与产出该文档的 Mode 无关。** Mode C 在 `routeA` 产出的方案仍是 `A003`，
   **不是** `C003`。Mode 记在 frontmatter 的 `mode` 字段。
3. **序号按路线独立递增**，不跨路线共享：`routeA` 是 A001/A002/…，
   `routeB` 是 B001/B002/…。
4. **审阅文档不占用新序号**（见 §2.3）。
5. 文件**全部平铺在 `docs/` 下**（唯一子目录是 `docs/refs/`），ID 前缀保证跨路线引用无歧义
   （INDEX.md 链接、审阅引用、git 检索都靠它）。

### 2.6 分配规则

- 分配前**扫描 `docs/` 中已有的最大序号**，取 `max + 1`。
- 多代理并发时，序号分配必须**串行化**（见 §5）。
- 不要手动跳号、不要复用已删除的号。

---

## 3. 文档 frontmatter（必需）

每份文档开头必须有 YAML frontmatter，便于机器检索与 INDEX 生成：

```yaml
---
id: A002
route: routeA
core_goal: theory           # ★ 锚定点：theory | performance | phenomenon | benchmark | feasibility | negative
                            #   未与用户确认锚定点就开工属于违规（见 SKILL.md §0.1）
mode: C                     # A | B | C | D | E —— 产出该文档的 Mode
type: proposal              # idea-discovery | proposal | experiment-plan | narrative | review | literature-survey
status: draft               # draft | in-review | reviewed | superseded | archived
created: 2025-01-01
updated: 2025-01-02
parent: A001                # 可选：上游文档
supersedes: null            # 可选：被本文件取代的文档
review_of: null             # 仅审阅文档：被审文档 ID，如 A002
review_round: null          # 仅审阅文档：第几轮（1,2,3…）
also_reviewed: []           # 仅审阅文档：同一轮还覆盖了哪些文档 ID
reviewers: []               # 可选：参与的子代理角色
---
```

### 3.1 人类可读性要求（强制）

`docs/` 是**给人看的**：

- ✅ 用标题分层、用表格承载对比、用列表承载结论。
- ✅ 每个结论标注证据来源（文献 `[作者, 会议/年份]` 或实验编号 `E3`）。
- ✅ 关键数字给单位和口径。
- ❌ **禁止**把 `state.json`、原始 JSON、日志、traceback 直接贴进正文——
  机器状态放 `.research-idea-pipeline/`，日志放 `logs/`，正文只放结论与依据。
- ❌ 禁止只有标题没有内容的空壳文档。

---

## 4. INDEX.md 规范（每条路线必需）

`routeX/INDEX.md` 是**该路线的唯一入口**：指示文档位置 + 汇报当前进度。

**每次产出、每次实验、每次发现 bug 或风险后，必须同步更新。**

### 4.1 必需章节

```markdown
# routeA — INDEX

> 一句话状态：当前处于 Mode C，方案 A003 已产出待审。
> 最后更新：2025-01-02

## 1. 路线概要
- 核心目标（锚点）：theory / performance / phenomenon / benchmark / feasibility / negative
- 研究问题：
- 核心假设：
- 目标会议：CVPR / ICML / NeurIPS / MICCAI
- 当前阶段：Mode A / B / C / D / E
- 推荐优先级：高 / 中 / 低 / 建议放弃

### 2.0 文档关系图

```text
A001 文献调研
 └─▶ A002 ideas ─┬─▶ A003 方案 ─┬─▶ A004 实验计划
                 │              ├─▶ A003-review-r01
                 │              └─▶ A003-review-r02
                 └─▶ A005 narrative（含 I1 / I3）
                       └─▶ A005-review-r01
```

## 2. 文档索引
| ID | 文件 | 类型 | Mode | 状态 | 说明 |
|---|---|---|---|---|---|
| A001 | [A001-literature-survey.md](docs/A001-literature-survey.md) | literature-survey | A | reviewed | L3 达饱和 |
| A002 | [A002-ideas.md](docs/A002-ideas.md) | idea-discovery | B | reviewed | 10 个 idea（含 B5 审核） |
| A003 | [A003-proposal.md](docs/A003-proposal.md) | proposal | C | reviewed | 贡献 K1—K3 |
| A004 | [A004-experiment-plan.md](docs/A004-experiment-plan.md) | experiment-plan | C | reviewed | 实验 E1—E7 |
| A005 | [A005-narrative.md](docs/A005-narrative.md) | narrative | D | reviewed | 一次调用：I1/I3 各 4 套叙事，最佳 N2 / N3 |
| A003-review | [A003-review-r01.md](docs/A003-review-r01.md) | review | E | reviewed | 八子代理中位数 4，复现风险低 |

### 2.1 Idea 追踪（来自 A002）
| Idea | 状态 | 关联文档 | 最佳叙事 | 备注 |
|---|---|---|---|---|
| I1 | 已进方案 | A002/I1 → A003 → A005 | N2 | 复现风险低 |
| I3 | 已进方案 | A002/I3 → A006 | N3 | 理论严谨性待补 |
| I7 | **已淘汰** | A002/I7 | — | 重叠不足（[作者, 会议/年份]） |

### 2.2 叙事追踪
| Idea | 叙事文档 | 尝试套路 | 最佳套路 | 综合中位数 | 是否否决 |
|---|---|---|---|---|---|
| I1 | A005 | N2/N3/N5/N9 | **N2** | 4.0 | 否（N5 被否决） |
| I3 | A006 | N2/N3/N5/N9 | N3 | 3.0 | 否 |

### 2.3 审阅追踪
| 被审文档 | 轮次 | 文件 | 中位数 | 复现风险 | 结论 |
|---|---|---|---|---|---|
| A003 | 1 | A003-review-r01.md | 4 | 低 | 推荐优先级高 |
| A003 | 2 | A003-review-r02.md | 4 | 低 | 致命风险已缓解 |

## 3. 已证实（Confirmed）
> 有明确证据支持的结论。每条必须带证据链接，引用写作 `<文档ID>/<子编号>`。
> **行号说明：** 下列各表的 `#` 列是**表内行号**（Confirmed 用 C、Falsified 用 F、
> TODO 用 T、Bugs 用 B、Warnings 用 W），**与 Mode 章节号、触发条件 T1—T7 无关**。
| # | 结论 | 证据 | 日期 |
|---|---|---|---|
| C1 | 离散扩散可表示组合约束 | [A002/I1](docs/A002-ideas.md) §2；实验 A004/E1 | 2025-01-01 |

## 4. 已证伪（Falsified）
> 被实验或文献否定的假设。**负结果同样是要保管的资产**，不要删。
| # | 假设 | 否定证据 | 处置 | 日期 |
|---|---|---|---|---|
| F1 | 可逆性约束可无损映射到置换空间 | 实验 E2 全部失败 | 改走松弛方案 | 2025-01-01 |

## 5. TODO
| # | 任务 | 优先级 | 依赖 | 负责 | 状态 |
|---|---|---|---|---|---|
| T1 | 补齐收敛性证明 | P0 | 无 | — | 进行中 |
| T2 | 跑消融矩阵 E4—E7 | P1 | T1 | — | 待办 |

## 6. Bugs
| # | 现象 | 影响 | 复现 | 状态 | 处置 |
|---|---|---|---|---|---|
| B1 | E2 中 loss NaN | 阻塞消融 | `exp/e2.py` | 未解决 | 怀疑学习率 |

## 7. Warnings
> 风险、待核实项、已知未知、未达饱和的检索。
| # | 警告 | 类型 | 影响 | 处置 |
|---|---|---|---|---|
| W1 | "首次提出"声称未经 L3 穷尽检索 | 新颖性 | 投稿风险 | 待补 L3 检索 |
| W2 | arxiv 暂时不可用，检索未达饱和 | 检索 | 结论不完整 | 恢复后重跑 |

## 8. 关键依赖与风险
- 数据：…（许可、可得性）
- 算力：…（GPU·小时）
- 外部依赖：…（版本、接口）

## 9. 变更日志
| 日期 | 变更 | 文档 |
|---|---|---|
| 2025-01-02 | 新增方案 A003 | A003 |
```

### 4.2 维持规则

- **已证实 / 已证伪** 必须区分开：证伪的假设**不得删除**，留在表里并注明处置。
- **Warnings 中的"检索未达饱和"** 条目，只有在重跑检索达到 [literature-policy.md](literature-policy.md) §3.3 的饱和判据后才能关闭。
- **Bugs** 必须可复现（给出命令或脚本路径）。
- INDEX 里的链接必须**指向真实存在的文件**，不要写占位路径。
- `最后更新` 字段每次改动都要刷新。

---

## 5. 并发写入规则

多条路线、多个子代理并行工作时：

| 资源 | 规则 |
|---|---|
| `routeX/docs/` | **路线内**序号分配串行化；**不同路线各自独立目录，互不阻塞** |
| `routeX/INDEX.md` | **单写者**：同一时刻只允许一个成员改一条路线的 INDEX |
| 根 `INDEX.md` | **单写者**：跨路线状态汇总，改动前先读 |
| `shared/` | 按 `AGENTS.md` 规定；无规定时默认**只在明确需要时改**，改前先读 |
| `docs/refs/` | 追加式写入；缓存文件名由 query hash 决定，天然不冲突 |
| `docs/refs/index.json` | **单写者**：PDF 索引是整文件重写，同一时刻只允许一个成员重建（`refs_index.py`） |

> 序号分配与 INDEX 更新必须**串行进行**：先读取现有最大序号 / 当前 INDEX 内容，
> 再写入新文件与新行。并发时由 Lead（或指定的单写者）统一执行这两步。
> 若发生写冲突（FS_STALE_VERSION 类），重新读取后再提交，不要覆盖他人的改动。

---

## 6. 各 Mode 的落盘职责

| Mode | 产出文档 | 落盘路径 | 同时必须更新 |
|---|---|---|---|
| **A** | 文献调研报告（含负检索记录） | `<routeX>/docs/<R>NNN-literature-survey.md` | 对应 `INDEX.md`（§7 Warnings：未达饱和必须记） |
| **B** | idea 候选清单（**含 idea 级创新性/可行性审核评分**）+ 技术路线归纳 + 创新性边界 + shortlist + 淘汰清单 | `<routeX>/docs/<R>NNN-ideas.md` | 对应 `INDEX.md`（§2 文档索引；**放弃的 idea → §4 已证伪**；未核实的无人区声称 → §7 Warnings） |
| **C** | 论文提案 | `<routeX>/docs/<R>NNN-proposal.md` | 对应 `INDEX.md` |
| **C** | 实验流程计划书 | `<routeX>/docs/<R>NNN-experiment-plan.md`（**取其独立序号**） | 对应 `INDEX.md`（§5 TODO、§6 Bugs、§8 依赖） |
| **D** | 多套路叙事清单（≥4 套/idea）+ ≥4 子代理评审（默认 6） + 交叉质询 + 最佳叙事推荐 + 包装前后对照 | `<routeX>/docs/<R>NNN-narrative.md` | 对应 `INDEX.md`（被覆盖的套路 → **§4 已证伪**；最佳叙事 → **§3 已证实**；评分 <3 → **§7 Warnings**） |
| **E** | 审阅记录（**含复现风险等级**） | `<routeX>/docs/<被审ID>-review-r01.md`（接续则 `-r02.md`） | 对应 `INDEX.md`（§3/§4/§5/§7；**复现风险高 → §7 Warnings**） |
| 任意 | 机器状态 | `.research-idea-pipeline/state-<mode>-<ts>.json` | 不入 docs |

**审阅结论对进度的映射：** Mode E 的结论要**翻译成进度条目**——

- 结论"某机制成立/已被数据支持" → INDEX **§3 已证实**
- 结论"某假设被否定/不可行" → INDEX **§4 已证伪**
- 结论"需要补 A、B" → INDEX **§5 TODO**
- 结论"致命风险未缓解 / **复现风险高**" → INDEX **§7 Warnings**
- 复现步骤本身有错 → INDEX **§6 Bugs**

**idea 审核对进度的映射（Mode B5）：** 被判"重叠不足"或致命反驳不可缓解而**放弃**的
idea，同样写入 **§4 已证伪**——负结果是资产，不要丢。

---

## 7. 建立骨架的检查清单（手工执行）

本 Skill **不提供一键生成脚本**。执行者按下面的清单手工建立或用普通文件操作即可：

**新项目（无任何结构时）：**

1. 建 `docs/`、`docs/refs/{papers,cache}/`、`shared/{code,docs}/`、`.research-idea-pipeline/`。
2. 生成空的 PDF 索引：`python3 scripts/refs_index.py --refs-dir docs/refs`（会写出
   `docs/refs/index.json`）。之后**每次增删 PDF 都要重跑**。
3. 每条路线建 `routeX/{docs,code,experiments}/`。
4. 建两层索引与说明（**都必需**）：
   - 根 `README.md`（项目总览）与根 `INDEX.md`（跨路线索引），
     按 [../templates/INDEX.root.md](../templates/INDEX.root.md) 填写；
   - `routeX/README.md`（本路线说明）与 `routeX/INDEX.md`（本路线索引 + 关系图），
     按 [../templates/README.route.md](../templates/README.route.md) 与
     [../templates/INDEX.md](../templates/INDEX.md) 填写。
   之后**每次产出都要更新所在路线的 INDEX**；跨路线层面变化同步根 `INDEX.md`。

**每次新增 / 替换 / 删除 PDF 时：**

1. 把 PDF 放进 `docs/refs/papers/`，并在同目录写好同名 `.json` sidecar 元数据
   （字段见 [literature-policy.md](literature-policy.md) §7.2）。
2. 重建索引：`python3 scripts/refs_index.py`；校验：`python3 scripts/refs_index.py --check`。
3. 若 `--check` 报"待核实"（`needs_verification = true`），人工补齐 `title/authors/year`
   后重建；**未核实条目的文献不得用于支撑创新性声明**。

**每次产出新文档时：**

1. 扫描 `<routeX>/docs/` 里匹配 `^<路线字母>\d{3}-` 的文件名，取最大序号 +1。
2. 按 `<ID>-<slug>.md` 命名创建，文件开头写完整 frontmatter（§3）。
3. 把该行登记进 `routeX/INDEX.md` 的**文档索引**，并在**变更日志**加一行。

**每次审阅时：**

1. 审阅记录命名为 `<被审ID>-review-r01.md`；接续复核递增 `-r02.md`、`-r03.md`
   （**零填充两位**）。**审阅记录不占新序号。**
2. frontmatter 填 `review_of` 与 `review_round`。
3. 把审阅结论翻译成 INDEX 的 已证实 / 已证伪 / TODO / Warnings / Bugs（§6）。

**自检：**

- INDEX 里的每个链接都指向真实存在的文件；
- **每条路线下的文档 ID 前缀与该路线字母一致**（`routeB/docs/` 下不得出现 `A0xx`）；
- **根 `docs/` 下没有路线文档**（至少含 `refs/`；其他共享子目录按 `AGENTS.md`）；
- 每条路线都有 `README.md` + `INDEX.md`，且 `routeX/docs/` 扁平；
- 每条路线都含全部必需章节（文档索引、已证实、已证伪、TODO、Bugs、Warnings、变更日志）；
- 每份 `docs/` 文档都有完整 frontmatter，且 `最后更新` 已刷新。
