# 项目组织与文档落盘规范（Wave 6 目录规范）

所有 R 阶段的**方案**与**审阅记录**都必须落盘到项目，**以适合人类阅读的格式
（Markdown）存储**，并按路线分开管理。本文件定义目录结构、命名、文档 ID 分配、
`README.md` / `STATUS.md` / `INDEX.md` 三文件规范、`experiments/` 与 `results/` 的
XID 注册、`docs/decisions/` 决策记录、路由注册表与 Git 边界。

> **Wave 6 改的是「项目长什么样」。** 这是唯一一个**面向人**的规范修订：
> 机器真相集中，人类视图就近；路线独立清楚，公共资产只存一份；
> 实验可追溯，但不让实验目录淹没科研逻辑。
> **四个世界必须同时成立并互相投影：**

| 世界 | 落点 | 回答 |
|---|---|---|
| Research World | `.research-idea-pipeline/routes/<R>/research-state.json` | 我们目前认为世界是什么样 |
| Human Knowledge | `README` / `STATUS` / `INDEX` / `docs` | 人应该怎样理解现在的研究 |
| Experimental World | `experiments` / `results` / `logs` / `checkpoints` | 实际做过什么、观察到什么 |
| Implementation | `src` / `scripts` / `configs` | 怎样把实验运行出来 |

**若人进入仓库后必须连开几个 JSON 才知道「现在做到哪、为什么这么做、下一步是什么」，
这套结构就失败了。**

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

## 0.1 八条目录 invariant（**硬规则，冻结**）

**这八条是本文件的最高硬规则。** 任何布局建议、模板、示例与本表冲突时，以本表为准。

| # | invariant | 落地判据 |
|---|---|---|
| **DI-1** | **`R0`—`R14` 永远不成为目录结构。** 阶段是系统行为，不是文件树。 | `routes/` 下不得出现以 `R` 阶段命名的目录 |
| **DI-2** | **每条战略研究路线只对应一个 route**；hypothesis 不自动建 route（门槛见 §8.2）。 | 新 route 必须满足 §8.2 五条门槛中至少两条 |
| **DI-3** | **每条 route 只有一个 canonical `research-state.json`。** | 每条 route 恰好一份 `.research-idea-pipeline/routes/<R>/research-state.json` |
| **DI-4** | **`README` / `STATUS` / `INDEX` 都是人类视图，不是第二份 machine state** —— 它们必须可从 state 投影，不得独立演化出真相。 | `STATUS.md` 可由 `render_status.py` 幂等重生成 |
| **DI-5** | **所有正式实验拥有唯一 `XID`**，并贯穿 `config / result / log / checkpoint / state`。 | `rg "<XID>"` 在五处同时可查到（见 §6.3） |
| **DI-6** | **代码只维护 canonical implementation，route 不复制代码。** route 的差异用 `configs/routes/<R>/` 表达。 | 任意 `routes/*/src/` 为空或不存在 |
| **DI-7** | **`cache` / `runtime` 与 durable research provenance 严格分离。** | `.research-idea-pipeline/{cache,runtime}` 不在 Git tracked 列表 |
| **DI-8** | **任何机器状态都必须存在一个合理的人类入口**，但不要求人直接阅读机器状态。 | §13 映射表每个「人类入口」都真实存在 |

**DI-8 是本 Wave 的灵魂。** 它同时否掉两个极端：既不让人读 JSON，
也不让机器状态无处被理解。机器真相写进 `research-state.json`，
但每一个科研概念都要有一个就近的人类入口（见 §13 的映射表）。

**违反 DI-1—DI-8 的处理：** 不得「先按老结构建好再补」。
发现冲突时**当轮改正**，并在该 route 的 `INDEX.md` 变更日志记一行。

---

## 1. 标准项目布局（`routes/` 聚合）

**各路线产出的文档放该路线自己的 `routes/<R>/docs/`（扁平，
不按类型再分子目录）；根目录 `docs/` 是跨路线共享区，至少保证有 `refs/`。
根目录有 `README.md` 与 `INDEX.md`；每条路线有 `README.md` / `STATUS.md` /
`INDEX.md` 三件套。**

```text
<项目根目录>/
├── AGENTS.md                    # 共享契约：布局、命名、公用部分规范（最高优先级）
├── README.md                    # ★ 根级：项目是什么（研究问题、路线列表、怎么跑）
├── INDEX.md                     # ★ 根级：路线总表投影（Route | Goal | Status | Thesis | Blocker）
│
├── docs/                        # ★ 项目级人类知识库（跨路线）
│   ├── refs/                    # ★ 必需：参考文献库（= 本地文献库根目录）
│   │   ├── papers/              # {paper_id}.pdf + .json sidecar + 可选 .md
│   │   ├── cache/<source>/      # 查询缓存（按源分目录）
│   │   └── index.json           # ★ 必需：PDF 索引（每个 PDF 一条记录，进版本库）
│   ├── notes/                   # 可选：跨路线科研笔记（按 AGENTS.md）
│   ├── theory/                  # 可选：跨路线理论材料
│   ├── decisions/               # ★ 项目级重大决策（DEC 记录，见 §6.4）
│   ├── dev/                     # 可选：开发说明
│   └── latex/                   # 可选：跨路线共享 LaTeX 模板/样式（按 AGENTS.md）
│
├── routes/                      # ★ 所有科研路线集中于此
│   ├── A/                       # 路线目录；`<R>` = 路线字母
│   │   ├── README.md            # ★ 路线身份证（低频变更，见 §4.3）
│   │   ├── STATUS.md            # ★ 当前状态人类摘要（高频变更，见 §4.2）
│   │   ├── INDEX.md             # ★ 资产目录 + 时间线（见 §4.1）
│   │   └── docs/                # ★ 正式文档，保持扁平 + ID
│   │       ├── A000-anchor.md   # 冻结契约：路线锚点 + anchor_role + serves
│   │       ├── A001-field-map.md
│   │       ├── A002-discovery.md
│   │       ├── A003-proposal.md
│   │       ├── A004-experiment-plan.md
│   │       ├── A005-narrative.md
│   │       └── A003-review-r01.md
│   ├── B/                       # 同构
│   └── C/                       # 同构
│
├── src/                         # ★ canonical implementation（唯一，见 DI-6）
│   └── models/ methods/ solvers/ losses/ data/ utils/
├── scripts/{train/,eval/,analysis/,research/}
├── configs/{base/,datasets/,routes/<R>/}
├── dataset/
│
├── experiments/                 # ★ 实验注册表（人可浏览，回答"想做什么"）
│   ├── README.md
│   └── A/X021-identifiability/{README.md,manifest.json,config.yaml}
├── results/                     # 回答"发生了什么"（不承担科研状态）
│   └── A/X021/{summary.md,summary.json,metrics.json,tables/,figures/,artifacts/}
├── checkpoints/<R>/<XID>/
├── logs/<R>/<XID>/
├── shared/                      # 极小；只放无法归入 src/docs/configs 的多路线资产
│
└── .research-idea-pipeline/     # ★ 机器控制平面（**可忽略**，见 §11.1）
    ├── project/{contract.json,route-registry.json,constraints.json}
    ├── routes/<R>/{research-state.json,history/,actions/,populations/,
    │                assurance/,repairs/,reviews/,
    │                experiments/<XID>/{preregistration.json,state-delta.json}}
    ├── meta/{operator-stats.json,eig-calibration.json,
    │          recurring-failures.json,scheduler-history.jsonl}
    ├── cache/{literature/,retrieval/,embeddings/}
    └── runtime/{locks,tmp,tool-output}/
```

> **`populations/` 收两类 search artifact（都不是 `state` object）：**
> `populations/archive/` 存 QD archive 重排记录；
> `populations/intermediates/` 存 `P3` 的 `abstract_skeleton`（typed intermediate，
> 见 [phase-r3-r6-discovery.md](phase-r3-r6-discovery.md) §R3.0.1）。
> **两者都不得被当作结论引用**，也不分配 `H` / `C` / `X` ID。

**与上一版的关键差异：**

1. **`route_*` 集中进 `routes/`** —— 否则路线一多，根目录会同时混着代码、route、
   dataset、result、docs、configs，人扫一眼建立不起结构。
2. **新增 `STATUS.md`** —— 机器有 `research-state.json`，但人需要
   「30 秒理解现在发生了什么」。
3. **`experiments/` 从控制平面独立出来** —— 人常问「X021 到底做的是什么」，
   不能要求人钻隐藏目录读 JSON。

> **命名说明：** 路线目录是 `routes/<R>/`，`<R>` 是**路线字母**
> （如 `A` / `B` / `T`），其文档 ID 前缀用**同一个字母**
> （`routes/A/docs/` 下是 `A001-…`）。此处的字母是**路线编号，与 R 阶段无关**；
> 文档属于哪个 R 阶段记录在文档 frontmatter 的 `phase` 字段里。

### 1.1 六条硬性规则

1. **文档按路线分离、各自扁平：** 每条路线的产出放 `routes/<R>/docs/`，**该目录内
   不再按类型分子目录**（方案、叙事、审阅平铺在一起，靠文件名排序与识别）。
   **根目录 `docs/` 是跨路线共享区**：Skill **只保证 `refs/` 存在**，
   其他共享子目录（`notes/`、`theory/`、`latex/` 等）由项目与 `AGENTS.md` 决定，
   本 Skill 不规定也不禁止。**唯一的硬约束是：路线文档不得放根 `docs/`。**
2. **路线级三文件职责分离（根级两文件）：** 根目录必须有 `README.md` 与 `INDEX.md`；
   每条路线必须有 `README.md` / `STATUS.md` / `INDEX.md`。
   三者回答不同问题、更新频率不同（见 §1.2），**不得互相塞**。
3. **文件名前缀 = 文档 ID，不再是路径隔离：** 文档已按路线分目录，前缀（`A` / `B`）
   不再承担"唯一的路线隔离手段"，但它**仍然是文档 ID** —— 审阅文件名以 ID 为锚、
   跨路线引用要唯一、`research-state.json` 与正文按 ID 引用。
   **前缀保留；序号按路线独立递增、永不复用。**
4. **路线隔离，且 route 不复制代码：** 代码只维护 canonical implementation
   （`src/`），**route 目录内不放 `src/`**；route 之间的差异用
   `configs/routes/<R>/` 表达。**路线之间不得互相 import**，需要复用的一律下沉到
   `src/` 或 `shared/`。
5. **参考文献集中：** 论文元数据/笔记/缓存一律放**根目录 `docs/refs/`**，
   不要散落到 `routes/<R>/docs/`；跨路线共享的笔记 / LaTeX 放根 `docs/` 的其他子目录。
6. **PDF 必须入索引：** `docs/refs/` 下的**每个 PDF** 都要在 **`docs/refs/index.json`**
   里有一条记录（完整字段见 [literature-policy.md](literature-policy.md) §7.1）。
   **索引进版本库，PDF 不进**（PDF 是大文件）。新增 / 替换 / 删除 PDF 后**必须重建索引**
   （`python3 scripts/refs_index.py`，校验用 `--check`）；**未入索引的 PDF 视为不存在**。

### 1.2 `README` / `STATUS` / `INDEX` 三文件职责分离

**结论：路线级三个文件回答三个不同问题，更新频率不同，不得互相塞。**

| 文件 | 回答 | 更新频率 | 内容 | 详见 |
|---|---|---|---|---|
| `routes/<R>/README.md` | 这条路线**是什么**？为什么存在？ | **很低** | 路线身份证 | §4.3 |
| `routes/<R>/STATUS.md` | **现在做到哪了？下一步是什么？** | **很高** | `research-state.json` 的人类投影 | §4.2 |
| `routes/<R>/INDEX.md` | 这条路线**有哪些材料**？ | **中等** | 资产目录 + 时间线 | §4.1 |

**三者都是人类视图（DI-4）：** 它们**必须可从 state 投影**，不得独立演化出真相。
当三者与 `research-state.json` 冲突时，**以 state 为准**，并重新生成视图。

---

## 1.3 骨架模板索引（本规范描述的每个物件，都要有可复制的骨架）

| 物件 | 骨架 |
|---|---|
| 项目根 `README.md` / `INDEX.md` | [../templates/INDEX.root.md](../templates/INDEX.root.md) |
| 路线 `README.md`（身份证） | [../templates/README.route.md](../templates/README.route.md) |
| 路线 `INDEX.md`（资产目录 + 时间线） | [../templates/INDEX.md](../templates/INDEX.md) |
| 路线 `STATUS.md`（state 的人类投影） | [../templates/STATUS.md](../templates/STATUS.md) |
| 机器状态 `research-state.json` | [../templates/research-state.template.json](../templates/research-state.template.json) |
| 调度 telemetry `scheduler.json` | [../templates/scheduler.template.json](../templates/scheduler.template.json) |

> **为什么单列此表：** 规范里描述一个文件却指不到骨架，执行者只能自己发明结构 ——
> 那是"规范与产物脱钩"的起点。**本节列出的每个骨架都必须真实存在**，
> 由相对链接可达性检查（`SKILL.md` §8 D4）机械保证。

---

## 2. 文档命名与 ID 分配

> **记法：** `routes/<R>/` = 路线目录（`<R>` = 路线字母，如 `A` / `T`）；
> `<NNN>` = 三位序号；`<ID>` = 完整文档 ID（如 `A002`）；
> `<I<n>>` = idea 子编号（如 `I1`）。
> 旧记法中的「路线目录占位符」已退役，**一律写作 `routes/<R>/`**。

### 2.1 文档类型与文件名（唯一权威表）

**`<slug>` 只能取下表枚举值**，不得自创。文件位于 **`routes/<R>/docs/`**。
**`<slug>` 是「知识类型」，不是「流程类型」：** 它**与 `R0`—`R14` 解耦**。
同一份 `discovery` 文档可能来自 `R3 + R4 + R5 + R6`，用阶段名做 slug 无法表达这种
多阶段汇聚。

| type（frontmatter） | slug | 文件名 | 用途 | 常见来源阶段（不绑定） |
|---|---|---|---|---|
| `anchor` | `anchor` | `<R>000-anchor.md` | **—**（开工前由用户确认锚点后建立，**冻结契约**） | — |
| `field-map` | `field-map` | `<R><NNN>-field-map.md` | 领域地图 | R2 / R5 |
| `discovery` | `discovery` | `<R><NNN>-discovery.md` | hypothesis / paradigm discovery | R3—R6 |
| `theory` | `theory` | `<R><NNN>-theory.md` | 理论分析 | R8（按需） |
| `evidence` | `evidence` | `<R><NNN>-evidence.md` | evidence synthesis | R8 |
| `proposal` | `proposal` | `<R><NNN>-proposal.md` | 正式方案 | R8 |
| `experiment-plan` | `experiment-plan` | `<R><NNN>-experiment-plan.md` | 实验规划（独立序号） | R9—R11 |
| `result-analysis` | `result-analysis` | `<R><NNN>-result-analysis.md` | 实验结果分析 | R11 |
| `decision` | `decision` | `<R><NNN>-decision.md` | 科研重大决策 | R14 |
| `narrative` | `narrative` | `<R><NNN>-narrative.md` | 论文叙事（**一次调用一份**，内含各 idea 的小节） | R12 |
| `review` | —（特殊，见 §2.3） | `<被审ID>-review-r<NN>.md` | 审查 | R7 / R10 / R13（或 R12 的叙事审核） |

> **为什么用「知识类型」而不是「流程类型」命名：** 同一份知识常常来自多个阶段
> （例如一份 `discovery` 文档可能汇聚 `R3`—`R6`）。用阶段名命名，阶段一调整文档名就失效。
> 知识类型名与 `R0`—`R14` **解耦**，因此系统阶段如何演进都不影响既有文档名与既有引用。

> **`anchor` 是「冻结契约」，必须可溯源：** frontmatter 除常规字段外**必须**带
> `anchor_version`（如 `1.7`）与 `anchor_hash`（对正文算的内容哈希，用
> `sha256sum <文件> | cut -c1-16` 即可）。**改锚点 = 开新的 §0.2 锚点变更单 +
> 升 `anchor_version`**，不得原地静默改写。

```
routes/A/docs/
├── A000-anchor.md                 # 冻结契约：路线锚点 + anchor_role + serves
├── A001-field-map.md              # R2 / R5
├── A002-discovery.md              # R3—R6 —— 含 I1..In 与审核结论
├── A003-proposal.md               # R8
├── A004-experiment-plan.md        # R9—R11
├── A005-narrative.md              # R12 —— 一次调用：I1..In 的全部叙事 + 审核 + 推荐
├── A003-review-r01.md             # R7 / R10 / R13 —— 对 A003 的第 1 轮审阅
└── A003-review-r02.md             # R7 / R10 / R13 —— 接续复核（第 2 轮）
```

> **`routes/<R>/docs/` 保持扁平。** 单路线正式文档通常几十份以内，
> 扁平 + ID 最易搜索、最易跨文档引用。**该目录内不得建子目录。**

> **为什么叙事不再每个 idea 一份？** R12 的产出本来就是**一份**报告：它含全部 idea 的
> 叙事、**跨 idea 的交叉质询**、**跨 idea 的最佳推荐与最终优先级建议**。硬拆成 N 份文件后，
> 这些跨 idea 的内容只能重复或随意归属，而且每个 idea 都要吃掉一个新序号。

> **为什么加 `anchor`？** §0.1 强制「锚点必须落盘」，但类型表原先不承认锚点文档。
> 结果是执行者只能自创 `type: mainline-anchor` / `type: anchor` 之类，**文件名越界**，
> 序列表也对不上。强制项必须与枚举表同步 —— 这正是 `SKILL.md` §8 的 A4 类漂移。

### 2.2 子编号规范（路线内唯一，不复用）

| 前缀 | 含义 | 定义处 | 示例 |
|---|---|---|---|
| `I<n>` | **idea**（由 R3—R6 产出，R8 / R12 引用） | `-discovery.md` | `I1`、`I3` |
| `N<k>` | **叙事 preset**（全局固定 1—10，见 [narrative-patterns.md](narrative-patterns.md) §1；**非互斥**） | preset 库 | `N2`、`N9` |
| `K<n>` | **贡献**（方案内；**不用 `C`**，避免与 state 的 claim `C<n>` 撞） | `-proposal.md` | `K1`、`K2` |
| `X<n>` | **实验**（与 state 的 `experiments[].id` 同一套；**不用 `E`**，避免与 evidence `E<n>` 撞） | `-experiment-plan.md` | `X1`、`X4` |
| `H<n>` | **假设** | `-experiment-plan.md` | `H1` |

**跨文档引用写法：** `<文档ID>/<子编号>` ——
如 `A002/I3`（A002 里的第 3 个 idea）、`A003/K1`、`A004/X2`、`A005/N2`。

> 子编号**只在所属路线内唯一**，不跨路线共享。
> 正式实验另有一套全局追踪 ID `XID`（见 §6.3），与 `X<n>` 并存：
> `X<n>` 是实验节点号（`research-state.json` 与实验计划书**共用同一套**），
> `XID` 是贯穿 `experiments/` 与 `results/` 目录的注册号。
> **`E<n>` 只表示 `evidence[]` 的证据编号** —— 不要用它编号实验。

### 2.3 审阅意见命名（R7 / R10 / R13 / R12 叙事审核）

**统一规则：审阅意见永远挂在「被审文档的 ID」上，不占用新序号。**

```
routes/<R>/docs/<被审ID>-review-r01.md    # 第 1 轮
routes/<R>/docs/<被审ID>-review-r02.md    # 第 2 轮（接续复核）
routes/<R>/docs/<被审ID>-review-r10.md    # 第 10 轮
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
  **不得混用两种宽度**。切换时须把该路线既有的 `r<NN>` **全部重命名为 `r<NNN>`**，
  并在变更日志记录切换点 —— 否则这条规则根本无法执行。
  同理，`<NNN>` 是三位序号，超过 999 份文档时须在 `AGENTS.md` 里另行约定。
- 文件名里**不出现** R 阶段字母，避免与路线字母混淆。
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

**一次 R12 调用产出一份 `<R><NNN>-narrative.md`**，内含**全部 idea** 的叙事。
**结构按 claim-first 排列：先证据与主张，再叙事。**

```markdown
# A005 — 叙事（I1 / I3）

## 摘要

| idea | (O, T, R) | 可辩护 anchor | 候选 preset | 最佳 preset | 门禁 G1—G5 | 六维（S/O/SM/ED/G/NC） |
|---|---|---|---|---|---|---|
| I1 | (Method, hidden-assumption, design-algorithm) | 性能 | N2/N3/N5/N9 | **N2** | 全 pass | 5/4/3/4/3/4 |
| I3 | (Phenomenon, unexplained-phenomenon, characterize) | 现象 | N1/N4/N8 | N4 | G3 fail | 不参与排序 |

## idea I1

### I1 / 证据台账与 claim graph

| E | 内容 | epistemic_status |
|---|---|---|
| E1 | … | Observed |
| E2 | … | Supported |

- `C0`（central proposition）：……
- `C1 ← E1`　`C2 ← E2, E3`　`C3 ← E2`　`C4 ← [待补]`　`C5 ← [待补]`

### I1 / N2 瓶颈突破/移除假设     ← preset 编号与名称必须取自 narrative-patterns.md §1
#### S1 Context
#### S2 Tension
#### S3 Central Proposition（可证伪）
#### S4 Resolution
#### S5 Evidence Contract（`Ci ← Ej` 对照）
#### S6 Consequence & Boundary（**含不成立的条件**）
#### 包装前后对照
#### 该 preset 的弱点（S-Devil）

### I1 / N3 跨域理论迁移（Transfer Legitimacy = L2）
...

## 攻击面评审（跨 idea）
## 门禁判定 G1—G5（跨 idea）
## 六维排序与最佳叙事推荐（跨 idea）
## 缺失证据清单与最小必要实验 / 定理（跨 idea）
```

**硬规则：**

1. **一次调用一份文档**；同一批 idea 重做叙事取**新序号**，并在 frontmatter
   `supersedes` 指向旧 ID。
2. **先有证据台账与 claim graph，再有叙事。** `C0—C5` 完整，每个 `Ci` 有 `Ci ← Ej`
   或标 `[待补]`；写不出**可证伪 central proposition** 的 idea **不得进入投稿叙事**。
3. **每个 idea 2—4 套真正不同的 claim hierarchy**（不是同一主张的四种措辞），
   每套填满**六槽位 `S1—S6`**。
4. **门禁 `G1—G5` 命中的叙事不参与六维排序** —— 判定与理由仍写进文档，但不进排序表。
5. **跨 idea 的内容（攻击面评审、门禁判定、六维排序、最佳推荐、缺失证据清单）
   集中在本文件末尾**，不要分散到 per-idea 小节里。
6. preset 编号 `N<k>` **必须**取自 [narrative-patterns.md](narrative-patterns.md) §1 的
   十套表；跨文档引用写 `A005/I1/N2`。

### 2.5 硬规则（不随 R 阶段变化）

1. **文档 ID 前缀 = 所属路线的字母。** `routes/A/docs/` 下的文档一律 `A` 开头，
   `routes/B/docs/` 下一律 `B` 开头；**绝不允许** `routes/B/docs/` 下出现 `A0xx`。
2. **前缀与产出该文档的 R 阶段无关。** R8 在 `routes/A/` 产出的方案仍是 `A003`，
   **不是** `C003`。阶段记在 frontmatter 的 `phase` 字段。
3. **序号按路线独立递增**，不跨路线共享：`routes/A/` 是 A001/A002/…，
   `routes/B/` 是 B001/B002/…。
4. **审阅文档不占用新序号**（见 §2.3）。
5. 文件**在各自路线的 `routes/<R>/docs/` 内平铺**（该目录内不再分子目录）；根 `docs/`
   只放 `refs/`、`decisions/` 与 `AGENTS.md` 允许的共享子目录。ID 前缀保证
   跨路线引用无歧义（INDEX.md 链接、审阅引用、git 检索都靠它）。

### 2.6 分配规则

- 分配前**扫描 `routes/<R>/docs/` 中已有的最大序号**，取 `max + 1`。
- 多代理并发时，序号分配必须**串行化**（见 §5）。
- 不要手动跳号、不要复用已删除的号。

---

## 3. 文档 frontmatter（必需）

每份文档开头必须有 YAML frontmatter，便于机器检索与 INDEX 生成：

```yaml
---
id: A002
route: A
core_goal: theory           # ★ 锚定点【只记主锚点】：theory | performance | phenomenon | benchmark | feasibility | negative
                            #   允许"主+次"组合，但次锚点**不进本字段**（写 INDEX 概要与 state.json 的
                            #   core_goal_secondary）；写成 "theory+feasibility" 之类会被下游脚本判为非法值。
                            #   未与用户确认锚定点就开工属于违规（见 SKILL.md §0.1）
anchor_role: supporting     # ★ primary | supporting | orthogonal —— 本路线与「项目主锚点」的关系
                            #   项目主锚点在根 INDEX.md 声明（见 SKILL.md §0.1 三层锚点体系）
serves: performance         # ★ supporting 必填：服务哪条主锚点、通过什么机制
serves_evidence: A003/K1    # ★ supporting 必填：该机制落到哪条贡献/实验，须可核验
subtype: null               # 可选：自由文本，保留枚举外的原始语义（如 paper-outline /
                            #   experiment-cards / math-consolidation）。**不参与文件名**，见 §3.2
phase: R8                    # R0..R14 —— 产出该文档的阶段（单值；一次调用跨阶段时写主阶段）
type: proposal              # anchor | field-map | discovery | theory | evidence | proposal |
                            #   experiment-plan | result-analysis | decision | narrative | review
status: draft               # draft | in-review | reviewed | superseded | archived
maturity: working           # 可选：scratch | working | canonical（见 §12）；scratch 不进 route docs
created: 2025-01-01
updated: 2025-01-02
parent: A001                # 可选：上游文档
supersedes: null            # 可选：被本文件取代的文档
review_of: null             # 仅审阅文档：被审文档 ID，如 A002
review_round: null          # 仅审阅文档：第几轮（1,2,3…）
also_reviewed: []           # 仅审阅文档：同一轮还覆盖了哪些文档 ID
reviewers: []               # 可选：参与的子代理角色
anchor_version: null        # 仅 type: anchor：锚点版本号，如 1.7
anchor_hash: null           # 仅 type: anchor：正文内容哈希（sha256sum | cut -c1-16）
---
```

### 3.1 人类可读性要求（强制）

`docs/` 是**给人看的**：

- ✅ 用标题分层、用表格承载对比、用列表承载结论。
- ✅ 每个结论标注证据来源（文献 `[作者, 会议/年份]` 或实验编号 `X3`）。
- ✅ 关键数字给单位和口径。
- ✅ **句子形式遵守受控中文**（[writing-policy.md](writing-policy.md)）：一句一动作、
  句长上限（指令 ≤25 字 / 说明 ≤40 字）、不用分号连接动作、一段一主题、≥3 项用列表。
  去掉虚动词（「进行分析」→「分析」）、套话（「需要注意的是」）、营销形容词
  （「无缝」「显著提升」）、同义轮换。
- ✅ **落盘前跑 `python scripts/ste_lint_zh.py --disable synonym-rotation <文件>`，
  硬违规须为 0。** 档位见 [writing-policy.md](writing-policy.md) §1
  （实验流程计划书的步骤与命令用 **Strict**，其余正文用**中文-顺**；
  用户显式声明 **asd-ste100** 时改按该档，命令换 `--max-chars 25`，
  **Agent 不得自行升档**）。
- ❌ **正文禁令 —— 以下内容一律不得贴进 `docs/` 正文：**
  - `research-state.json`、原始 JSON、state 片段；
  - 日志、traceback、CUDA / 环境报错原文；
  - 子代理的原始评审件（原始件属中间产物，见 §6.1）。
  **机器状态放 `.research-idea-pipeline/routes/<R>/`，日志放 `logs/`，
  正文只放结论与依据。**
- ❌ 禁止只有标题没有内容的空壳文档。
- ❌ **禁止为了过 linter 而删情态**：「可能 / 初步 / 倾向于」承载置信度，是内容不是修饰
  （[writing-policy.md](writing-policy.md) §5）。句长超一点没关系，丢置信度不行。

### 3.2 `subtype`：枚举外的派生物怎么落

**`slug` 保持封闭**（§2.1 的知识类型 + `review` + `anchor`），
**派生物用 `subtype` 表达**：

- **文件名只由 `<R><NNN>-<slug>.md` 决定**，`subtype` **不参与文件名**；
- 派生物**归到最接近的枚举 `slug`**（如「论文大纲」→ `proposal`、「实验卡」→
  `experiment-plan`、「数学合并」→ `theory`、「执行方案」→ `experiment-plan`），
  原始语义写进 `subtype`；
- 路线 `INDEX.md` 的文档表**必须加一列 `subtype`**，否则语义在索引层丢失；
- **禁止**为了保留语义去自创 slug（`paper-outline` 之类）。那会让"文件名可预测"
  这条保证失效，序号也会被派生物持续吃掉。

### 3.3 `anchor_role` / `serves` / `serves_evidence`：把"服务主锚点"做成可证伪的

`core_goal` 只说"这条路线想做什么"，**不表达"它在项目里扮演什么角色"**。缺了从属字段，
「服务主锚点」与「偏离主锚点」写出来一模一样。

| 值 | 含义 | 附加要求 |
|---|---|---|
| `primary` | 本路线就是**项目主锚点**的主战场 | — |
| `supporting` | 服务主锚点，但主攻方向不同 | **`serves` + `serves_evidence` 必填**，且必须可证伪（见下） |
| `orthogonal` | 与主锚点成功判据无关 | 在根 `INDEX.md` 写明「不参与主锚点成功判据」；**不得进入 R12、不得作为投稿主线** |

**`supporting` 的可证伪要求（否则只是把"自称理论"换成"自称服务"）：**
必须说明**一个会因它而改变的下游决策**，以及该决策对主锚点成功判据的**可测影响**
（自己实测，或写明**由谁实测、用什么指标、什么判据**）。
**只写"有理论价值 / 能提供洞见"不算。** 答不出 ⇒ 只能标 `orthogonal` 并接受其后果。

---

## 4. `README` / `STATUS` / `INDEX` 的具体规范

三个文件的**职责与更新频率**见 §1.2。本节给出各自的固定结构。
**三者都是 state 的投影，不是第二份真相（DI-4）。**

### 4.1 `INDEX.md`：只做资产目录 + 时间线

**结论：`INDEX.md` 减负。** `已证实 / 已证伪 / TODO / Bugs / Warnings` 这类
**当前状态**一律交给 `STATUS.md`（§4.2），**不得在 INDEX 重复**。

`INDEX.md` 是**该路线的材料目录**：有哪些文档、有哪些实验、做过哪些决策与评审、
里程碑是什么。**它不回答"现在卡在哪"。**

**推荐节（按此顺序）：**

```
# routes/<R>/INDEX.md

> 一句话定位（这条路线收什么材料，不写当前进度）。
> 最后更新：<YYYY-MM-DD>

## 1. Route Overview
## 2. Key Documents        （ID / Type / Title / Status）
## 3. Experiments          （XID / Question / Status / Result）
## 4. Decisions            （DEC 编号 / 主题 / 结论）
## 5. Reviews              （被审文档 / 轮次 / 文件 / 中位数 / 复现风险）
## 6. Milestones
## 7. Recent Research Changes   （state history 的人类投影）
## 8. Archive
```

**链接与表格规则：**

- 链接相对本文件（即 `routes/<R>/`）书写，指向 `docs/` 下的文件 ——
  **本路线的文档都在 `routes/<R>/docs/`（扁平）**。根目录 `docs/` 是跨路线共享区。
- **`subtype` 列必填**（枚举内写 `—`，枚举外写原义）。文件名只由 `<R><NNN>-<slug>.md`
  决定，派生物的语义**只能靠这一列保住**（见 §3.2）。
- **文档关系图**（`A001 → A002 → A003`）属于资产目录，放在 Key Documents 小节下。
- **Idea 追踪 / 叙事追踪** 属于历史资产，保留；**但当前状态列不在这里更新**，
  状态查 `STATUS.md`。
- **`Recent Research Changes` 是 `history/` 的人类投影**：每行一条，
  写 `日期 | state_version | 变更摘要 | 触发阶段`。
  它是 state history 的人类视图，**不替代** `research-state.json` 的 `history/`。
- INDEX 里的链接必须**指向真实存在的文件**，不要写占位路径。

**骨架见 [../templates/INDEX.md](../templates/INDEX.md)。**

### 4.2 `STATUS.md` = `f(research-state.json)`（**投影，不是第二份真相**）

**结论：`State = machine truth`；`STATUS = human current-state view`。
STATUS 必须自动或半自动生成，不得成为新的人工 truth source。**

- **生成入口：** `python scripts/render_status.py --route <R>`
  （读 active claims / active hypotheses / unresolved uncertainties / active experiments /
  critical attacks / latest decision）。
- **幂等是硬要求：** 同一份 `research-state.json` 连续生成两次，`STATUS.md` 必须
  内容一致。否则 `STATUS.md` 就退化成第二份人工真相（违反 DI-4）。
- **禁止手工在 `STATUS.md` 里补充 state 之外的"真相"**；要新增事实，
  先改 `research-state.json`，再重新生成。

**固定节（顺序不得改）：**

```
# routes/<R>/STATUS.md

> 本文件是 `research-state.json` 的投影，不是第二份真相。
> 应由 `scripts/render_status.py` 生成；手改无效。

## State version
## Current thesis
## Strongest supported findings
## Active hypotheses
## Critical uncertainties
## Open critical attacks
## Active experiments
## Most important negative findings
## Next recommended actions
## Current decision
```

> **这是研究者最常打开的页面。** 它必须在 30 秒内回答
> 「现在做到哪、为什么这么做、下一步是什么」。
> **骨架见 [../templates/STATUS.md](../templates/STATUS.md)。**

**刻意不写「最后更新（墙钟时间）」。** 那会破坏上文的幂等硬要求（同一份 state 两次生成不一致），
从而违反 DI-4。**时间线由 `routes/<R>/INDEX.md` 的「Recent Research Changes」承担** ——
它才是允许出现日期的那一层投影。

> **上述"固定节"与 `templates/STATUS.md`、`scripts/render_status.py` 的输出必须三者一致。**
> 这条由 `scripts/test_render_status.py` 的 `TestStatusSectionParity` **机械核对**：
> 生成物的 `## ` 节集合必须与模板声明逐项相等（名称与顺序都算）。

### 4.3 `README.md` 必须稳定（路线身份证）

`routes/<R>/README.md` 回答「**这条路线是什么？为什么存在？**」，**更新频率很低**。

**固定八节：**

1. Research Question
2. Why this route exists
3. Relation to project goal
4. Current central thesis
5. Scope / non-goals
6. Route lineage（来源、合并、分叉）
7. Key resources（数据、算力、外部依赖）
8. Entry points（→ STATUS / INDEX / Research State）

**禁止**把实验进展、今日 TODO、临时 hypothesis 塞进 README。
否则几个月后它变成历史垃圾场。

> **骨架见 [../templates/README.route.md](../templates/README.route.md)。**

### 4.4 维持规则

以下规则原先挂在 INDEX 的进度节，现已随职责迁移：
**状态类进 `STATUS.md`，材料类进 `INDEX.md`。**

- **负结果不得删除：** 被证伪的假设 / 被淘汰的 idea / null result / falsification
  进 `STATUS.md` 的 **Most important negative findings** 与 `docs/` 的正式文档，
  **不得静默丢弃**。负结果同样是要保管的资产。
- **「待核实」条数必须统计，且不得无限累积：** `STATUS.md` 的
  **Critical uncertainties** 必须给出**待核实条数**；条数**超过 5** 时，
  必须**在本轮内收敛** —— 补检索 / 补实验 / 或**明确降级措辞**
  （见 [evidence-policy.md](evidence-policy.md)），**不得继续累积**到下一轮。
- **「检索未达饱和」条目，** 只有在重跑检索达到
  [literature-policy.md](literature-policy.md) §3.3 的饱和判据后才能关闭。
- **工程失败不得污染正式 docs：** （见 §11.3）一次 CUDA OOM 只写机器 state 的
  `failures[]`（`kind: engineering_failure`）+ `logs/` 的 trace，
  **不生成**一份正式分析文档。只有**科研价值高的失败**（counterexample /
  null result / falsification / regime failure）才形成正式 route 文档。
- **Bugs 必须可复现**（给出命令或脚本路径），登记在 `STATUS.md` 的
  Next recommended actions 或该 route 的工程记录里，**不占 `docs/` 正式文档序号**。
- **`最后更新` 的范围（写死，避免歧义）：** 只有**带 frontmatter 的文档**与
  **`INDEX.md`** 有该字段（`routes/<R>/docs/*.md`、路线 `INDEX.md`、根 `INDEX.md`）。
  **`STATUS.md` 刻意没有该字段** —— 它是 `research-state.json` 的幂等投影（§4.2），
  写入墙钟时间会破坏 DI-4。本桶（工程记录 / Bugs）里出现的 `最后更新` 同样只指前者。
- **`.gitignore` 不得吞掉保留物：** `results/*/summary.*` 与
  `.research-idea-pipeline/**/research-state.json` 必须可进版本库（见 §9）。

---

## 5. 并发写入规则（写作用域）

多条路线、多个子代理并行工作时，**并行写者必须互不重叠**：

| 资源 | 规则 |
|---|---|
| `routes/<R>/docs/` | **路线内**序号分配串行化；**不同路线各自独立目录，互不阻塞** |
| `routes/<R>/INDEX.md` | **单写者**：同一时刻只允许一个成员改一条路线的 INDEX |
| `routes/<R>/README.md` | **单写者**：低频变更，改动前先读 |
| `routes/<R>/STATUS.md` | **不手写**：由 `render_status.py` 从 state 生成；同一时刻只允许一个生成者 |
| 根 `INDEX.md` | **单写者**：跨路线状态汇总，改动前先读 |
| `experiments/<R>/<XID>/` | **每个 XID 一个写者**：创建后 `manifest.json` 与 `config.yaml` 冻结 |
| `results/<R>/<XID>/` | **每个 XID 一个写者**：追加式写入，不覆盖已完成 XID 的 summary |
| `shared/` | 按 `AGENTS.md` 规定；无规定时默认**只在明确需要时改**，改前先读 |
| `docs/refs/` | 追加式写入；缓存文件名由 query hash 决定，天然不冲突 |
| `docs/refs/index.json` | **单写者**：PDF 索引是整文件重写，同一时刻只允许一个成员重建（`refs_index.py`） |
| `.research-idea-pipeline/routes/<R>/research-state.json` | **单写者**：整文件就地覆盖，改动前先读 |

> **序号分配与 INDEX 更新必须串行进行**：先读取现有最大序号 / 当前 INDEX 内容，
> 再写入新文件与新行。并发时由 Lead（或指定的单写者）统一执行这两步。
> **若发生写冲突（FS_STALE_VERSION 类），重新读取后再提交，不要覆盖他人的改动。**
> 冲突合并后必须在 `INDEX.md` 的 Recent Research Changes 留一行。

---

## 6. 各 R 阶段 的落盘职责

### 6.1 落盘三档

落盘分三档（缺了中间产物这一档，子代理原始件就只能违规塞进 `docs/`）：

| 档 | 落盘位置 | 例 | 可否删除 |
|---|---|---|---|
| **交付物** | `routes/<R>/docs/`（扁平，**不分子目录**） | anchor / field-map / discovery / proposal / experiment-plan / result-analysis / narrative / review | 否（是路线资产） |
| **中间产物** | `.research-idea-pipeline/routes/<R>/<被审ID>-r<NN>/` | 子代理**原始**评审件、草稿、检索原始结果 | 可（review 自带摘要） |
| **机器状态** | `.research-idea-pipeline/routes/<R>/research-state.json` | **R1 常驻状态**（就地覆盖，不按阶段切分） | 可 |
| **实验注册** | `experiments/<R>/<XID>/` + `results/<R>/<XID>/` | 预注册、人可读摘要、指标（见 §6.3） | experiments 否 / results 视体积 |

**所有文档产出按「交付物」列落盘；所有子代理原始件按「中间产物」列落盘。**

### 6.2 各阶段的产出与落盘路径

| R 阶段 | 产出文档（交付物） | 落盘路径 | 同时必须更新 |
|---|---|---|---|
| **R2 / R5** | 领域地图（含负检索记录） | `routes/<R>/docs/<R>NNN-field-map.md` | `STATUS.md`（Critical uncertainties：未达饱和必须记） |
| **R3—R6** | hypothesis 候选清单（**含 idea 级创新性/可行性审核评分**）+ 技术路线归纳 + 创新性边界 + population + 淘汰清单 | `routes/<R>/docs/<R>NNN-discovery.md` | `STATUS.md`（Active hypotheses；**放弃的 idea → Most important negative findings**；未核实的无人区声称 → Critical uncertainties）；`INDEX.md` 文档表 |
| **R8** | 论文提案 + 证据契约 | `routes/<R>/docs/<R>NNN-proposal.md` | `STATUS.md`、`INDEX.md` |
| **R9—R11** | 实验规划 + 结果分析 | `routes/<R>/docs/<R>NNN-experiment-plan.md`（**取其独立序号**）+ `routes/<R>/docs/<R>NNN-result-analysis.md` | `STATUS.md`（Next recommended actions、Active experiments）；`experiments/` 与 `results/` 的 XID 注册（§6.3） |
| **R12** | 证据台账 + claim graph（`C0—C5`）+ **2—4 套六槽位叙事（`S1—S6`）** + 六攻击面审稿人评审（**全部派遣，S-Lit 恒派，S-Devil 不打分**）+ **门禁 `G1—G5` 判定** + 六维排序 + 最佳叙事推荐 + **缺失证据清单与最小必要实验 / 定理** | `routes/<R>/docs/<R>NNN-narrative.md` | `STATUS.md`（被覆盖的叙事方向 → **Most important negative findings**；最佳叙事 → **Strongest supported findings**；门禁 `fail` 或六维中位 <3 → **Critical uncertainties**） |
| **R7 / R10 / R13** | 审阅记录（**含复现风险等级**） | `routes/<R>/docs/<被审ID>-review-r01.md`（接续则 `-r02.md`） | `STATUS.md`（Open critical attacks / Critical uncertainties；**复现风险高 → Critical uncertainties**） |
| **R14** | 研究决策记录 | `routes/<R>/docs/<R>NNN-decision.md` 或 `docs/decisions/DEC<NNN>-<slug>.md` | `STATUS.md`（Current decision）；路由注册表 `status` |

> **中间产物的两条硬约束：**
> 1. **正式 review 必须自带摘要**（结论 + 评分 + 关键证据 + 交叉质询记录）——
>    否则删掉原始件就等于丢结论。
> 2. **原始件不得被当作结论引用**：引用一律指向 review 正文
>    （`<被审ID>-review-rNN.md`），不得指向 `.research-idea-pipeline/` 里的原件。
>    **`routes/<R>/docs/` 内不得建子目录** —— 原始件不属于交付物，不要硬塞。

**审阅结论对状态的映射：** R7 / R10 / R13 的结论要**翻译成 `STATUS.md` 条目** ——

- 结论"某机制成立/已被数据支持" → STATUS **Strongest supported findings**
- 结论"某假设被否定/不可行" → STATUS **Most important negative findings**
- 结论"需要补 A、B" → STATUS **Next recommended actions**
- 结论"致命风险未缓解 / **复现风险高**" → STATUS **Critical uncertainties**
- 复现步骤本身有错 → STATUS **Next recommended actions**（工程项，**不新增正式文档**）

**idea 审核对状态的映射（R3—R6）：** 被判"重叠不足"或致命反驳不可缓解而**放弃**的
idea，同样写入 **Most important negative findings**——负结果是资产，不要丢。

### 6.3 `experiments/` 与 `results/` 分离，`XID` 贯穿

**`XID` 是整个目录架构最重要的工程 invariant（DI-5）。** 所有正式实验拥有唯一 `XID`，
并贯穿 `config / result / log / checkpoint / state`：

```text
X021  ⟷  experiments/A/X021-identifiability/
      ⟷  configs/routes/A/X021.yaml
      ⟷  results/A/X021/
      ⟷  logs/A/X021/
      ⟷  checkpoints/A/X021/
      ⟷  .research-idea-pipeline/routes/A/experiments/X021/
```

于是 `rg "X021"` 就把整个 provenance 找出来。

**`experiments/` 与 `results/` 语义不同，不能混在同一目录：**

| 目录 | 回答 | 对应科研概念 |
|---|---|---|
| `experiments/<R>/<XID>-<slug>/` | **想做什么？** | pre-registration |
| `results/<R>/<XID>/` | **发生了什么？** | observation |

- **`experiments/<R>/<XID>-<slug>/` 只放：** `README.md` + `manifest.json` + `config.yaml`。
  **不放**：checkpoint、巨型 output、raw logs。
  每个实验目录必须有**人类 README**，固定节：
  Question / Targets（Claim、Hypothesis、Uncertainty）/ Motivation / Setup /
  Expected outcomes（O1…）/ Result / Interpretation /
  Links（config、manifest、results、logs、state delta）。
- **`results/<R>/<XID>/` 同时有人类摘要与机器摘要：**
  `summary.md` 给人；`summary.json` 给 Agent；另有 `metrics.json`、
  `tables/`、`figures/`、`artifacts/`。
  人打开 `summary.md` 应直接看到：Result / Main observation / Unexpected / Limitations /
  **State impact**（如 `C7: Hypothesized → Supported`、`U4: High → Medium`）。
  **不应该先翻 TensorBoard。**

> 几个月后最不想遇到的问题是「`exp_final_v3_fix2` 到底做了什么」。
> **用 `XID` 彻底解决。**

### 6.4 决策记录：`docs/decisions/DEC<NNN>-<slug>.md`

借软件 ADR 的思想。**命名用 `DEC`，避免与 route ID 字母 `D` 冲突。**

**固定节：** Context / Evidence / Alternatives / Decision / Consequences /
**Revisit condition**。

- **项目级重大决策**放根 `docs/decisions/`；**路线内决策**可放
  `routes/<R>/docs/<R>NNN-decision.md`，并在 `docs/decisions/` 留一行索引。
- **append-only：** 已定决策不原地改写；要改就开新的 `DEC` 并在
  `Revisit condition` 写明触发条件。

> 半年后最难回答的是「**我们当初为什么没走另一条路**」。
> **Failure Memory 告诉机器；Decision Record 告诉人。**

---

## 7. 建立骨架的检查清单（手工执行）

本 Skill **不提供一键生成脚本**。执行者按下面的清单手工建立或用普通文件操作即可：

**新项目（无任何结构时）：**

1. 建 `docs/{refs/{papers,cache/<source>}/,decisions/}`、`routes/`、`experiments/`、
   `results/`、`src/`、`scripts/`、`configs/`、`shared/`、
   `.research-idea-pipeline/{project,cache,runtime}/`
   （后者还要放**中间产物**：`.research-idea-pipeline/routes/<R>/<被审ID>-r<NN>/`）。
2. 生成空的 PDF 索引：`python3 scripts/refs_index.py --refs-dir docs/refs`（会写出
   `docs/refs/index.json`）。之后**每次增删 PDF 都要重跑**。
   若已有旧索引而 `--check` 报「缺少 pdfs 数组」→ 用 `--migrate`，**不要直接重建**（会丢旧字段）。
3. 每条路线建 `routes/<R>/docs/`，并在 `.research-idea-pipeline/routes/<R>/` 放
   **唯一** `research-state.json`（DI-3）。**`routes/<R>/` 内不建 `src/`**（DI-6）。
4. 建三件套与根级两文件（**都必需**）：
   - 根 `README.md`（项目总览）与根 `INDEX.md`（**路线总表投影**：
     `Route | Goal | Status | Thesis | Blocker`）。
     **必须在根 `INDEX.md` 声明「项目主锚点」** —— 未声明不得开工（`SKILL.md` §0.1 规则 0）。
   - `routes/<R>/README.md`、`routes/<R>/STATUS.md`、`routes/<R>/INDEX.md`，
     分别按 [../templates/README.route.md](../templates/README.route.md)、
     [../templates/STATUS.md](../templates/STATUS.md) 与
     [../templates/INDEX.md](../templates/INDEX.md) 填写。
     每条路线还要建 **`<R>000-anchor.md`**（`type: anchor`，冻结契约，带
     `anchor_version` + `anchor_hash`）。
   之后**每次产出都要更新所在路线的 `INDEX.md`**；**当前状态只更新 `STATUS.md`**；
   跨路线层面变化同步根 `INDEX.md`。
5. 写 `.research-idea-pipeline/project/route-registry.json`（见 §8.1），
   每条路线记 `{name, path, status, primary, parent, forked_from}`。

**每次开工前的契约检查（`AGENTS.md`）：**

1. 读根 `AGENTS.md`（若存在）—— 布局 / 命名 / 公用约定优先于本 Skill 默认约定。
2. **校验它引用的文件是否都存在**：逐个确认 `AGENTS.md` 里提到的路径。
   **缺失项记入根 `INDEX.md` 的 Warnings**（悬空引用会让"按 AGENTS.md 办"直接失效）。
3. 若 `AGENTS.md` 的**纪律性条款**与本路线锚定契约冲突，按 `SKILL.md` §0 的裁决规则处理：
   **纪律性条款优先**，冲突走锚点变更单或重新定位，**不得用路线自述的 `core_goal` 抵消它**。

**每次新增 / 替换 / 删除 PDF 时：**

1. 把 PDF 放进 `docs/refs/papers/`，并在同目录写好同名 `.json` sidecar 元数据
   （字段见 [literature-policy.md](literature-policy.md) §7.2）。
2. 重建索引：`python3 scripts/refs_index.py`；校验：`python3 scripts/refs_index.py --check`。
3. 若 `--check` 报"待核实"（`needs_verification = true`），人工补齐 `title/authors/year`
   后重建；**未核实条目的文献不得用于支撑创新性声明**。

**每次产出新文档时：**

0. **判断它属于哪一档**（§6.1）：交付物 → `routes/<R>/docs/`；
   **中间产物 → `.research-idea-pipeline/routes/<R>/`**；
   机器状态 → `.research-idea-pipeline/routes/<R>/research-state.json`。
   **不要为了塞中间产物而在 `docs/` 下建子目录。**
1. 扫描 `routes/<R>/docs/` 里匹配 `^<路线字母>\d{3}-` 的文件名，取最大序号 +1。
2. 按 `<ID>-<slug>.md` 命名创建（**`slug` 只取 §2.1 封闭枚举**；枚举外的派生物写
   frontmatter 的 `subtype`，**不改文件名**），文件开头写完整 frontmatter（§3）。
3. 把该行登记进 `routes/<R>/INDEX.md` 的**文档索引**（**含 `subtype` 列**），
   并在 **Recent Research Changes** 加一行。
4. **若该产出改变了当前状态**（新证据、新负结果、新不确定性），
   **先写回 `research-state.json`，再重新生成 `STATUS.md`**（不得手改 STATUS）。

**每次审阅时：**

1. 审阅记录命名为 `<被审ID>-review-r01.md`；接续复核递增 `-r02.md`、`-r03.md`
   （**零填充两位**）。**审阅记录不占新序号。**
2. frontmatter 填 `review_of` 与 `review_round`。
3. 把审阅结论翻译成 `STATUS.md` 的状态节（§6.2 的映射表）。

**每次新增 / 改名正式实验时：**

1. 分配唯一 `XID`（`X021` 形式），并在五处同时建立映射（§6.3）。
2. 建 `experiments/<R>/<XID>-<slug>/`（README + manifest + config）。
3. 结果落 `results/<R>/<XID>/`（`summary.md` + `summary.json` + `metrics.json`）。
4. **预注册必须早于观察：** `experiments/` 与
   `.research-idea-pipeline/routes/<R>/experiments/<XID>/preregistration.json` 冻结
   `Outcome → state_delta`，之后不得追改。

**自检：**

- INDEX 里的每个链接都指向真实存在的文件；
- **每条路线下的文档 ID 前缀与该路线字母一致**（`routes/B/docs/` 下不得出现 `A0xx`）；
- **根 `docs/` 下没有路线文档**（至少含 `refs/`、`decisions/`；其他共享子目录按 `AGENTS.md`）；
- 每条路线都有 `README.md` + `STATUS.md` + `INDEX.md`，且 `routes/<R>/docs/` 扁平；
- **`STATUS.md` 可由 `render_status.py` 幂等重生成**（DI-4）；
- **每条 route 恰好一份 canonical `research-state.json`**（DI-3）；
- **`routes/*/src/` 为空或不存在**（DI-6）；
- 每份 `docs/` 文档都有完整 frontmatter，且 `最后更新` 已刷新（**范围见 §4.2：`STATUS.md`
  刻意没有该字段**）；
- **锚点体系完整**：根 `INDEX.md` 声明了**项目主锚点**；每条路线有 `<R>000-anchor.md`，
  frontmatter 含 `core_goal` / `anchor_role` / `serves` / `serves_evidence`
  （`supporting` 时后两者必填且可证伪）；路线锚点与本路线 INDEX 一致；
- **文档名没越界**：所有 `<R><NNN>-<slug>.md` 的 `slug` 都在 §2.1 封闭枚举内；
  枚举外的派生物写的是 `subtype`，且路线 INDEX 文档表**有 `subtype` 列**；
- **中间产物没混进 `docs/`**：`routes/<R>/docs/` 内**没有子目录**；
  `routes/<R>/docs/` 里**没有**子代理原始评审件；正式 review **自带摘要**，
  且没有引用指向原始件；
- **XID 贯穿**：每个 `XID` 在 `configs/` / `results/` / `logs/` / `checkpoints/` /
  state 中**同时可查到**（DI-5）；
- **`AGENTS.md` 引用可达**：它提到的路径都存在；缺失项已记入根 `INDEX.md` 的 Warnings；
- **refs 索引一致且已清点待核实**：`python3 scripts/refs_index.py --check` 通过；
  `needs_verification` 条数已计入 `STATUS.md` 的 Critical uncertainties。

---

## 8. 路由注册表与 route fork 门槛

### 8.1 route-registry：`.research-idea-pipeline/project/route-registry.json`

**它是路线管理的核心。** 每条约 `{name, path, status, primary, parent, forked_from}`。

**根 `INDEX.md` 投影成：** `Route | Goal | Status | Thesis | Blocker`。

**`status` 用小而稳定的枚举（冻结六值）：**

| 值 | 含义 |
|---|---|
| `candidate` | 候选路线，尚未投入 |
| `active` | 正在推进 |
| `supporting` | 服务主锚点，但非主战场 |
| `dormant` | 暂停，材料保留 |
| `archived` | 封存，不再推进 |
| `merged` | 已并入其他路线 |

**禁止** `almost done` / `maybe` / `low priority` / `temporarily paused` 这类自然语言状态
—— 说明写单独字段。

### 8.2 Route fork 门槛（**不得 hypothesis 一多就 fork**）

**满足下列至少两项**才考虑新 route：

| 条件 | 含义 |
|---|---|
| 独立 central question | 已不是原路线的子问题 |
| 独立 claim graph | 核心 claim 明显分叉 |
| 独立 experiment tree | 大部分实验不再共享 |
| 独立论文 thesis | 可单独成稿 |
| 长期资源投入 | 需要持续维护 |

否则保留为 `H<n>`，不开 route。（DI-2 的落地判据。）

---

## 9. Git 版本控制边界

| 版本控制 ✅ | 不版本控制 ❌ |
|---|---|
| `AGENTS.md` / `README.md` / `INDEX.md` / `routes/**` / `docs/**` | `checkpoints/` |
| `src/**` / `scripts/**` / `configs/**` | `logs/` |
| `experiments/**/{README.md,manifest.json,config.yaml}` | `dataset/` |
| `.research-idea-pipeline/**/research-state.json`、`history/*`、`experiments/*/preregistration.json`、`meta/*` | `.research-idea-pipeline/cache/`、`.research-idea-pipeline/runtime/` |

`results/` 视体积决定，但**至少 `summary.md` / `summary.json` / `metrics.json` 应保留**。

> **DI-7 落地：** `cache` / `runtime` 与 durable research provenance 严格分离。
> `.gitignore` 不得把 `routes/**`、`docs/**`、`research-state.json` 一起忽略掉。

---

## 10. 人类导航只有 3 层

```text
项目级:  README.md → INDEX.md
路线级:  routes/<R>/README.md → STATUS.md → INDEX.md
任务级:  experiments/<R>/<XID>/README.md
```

**研究者应该永远不需要想「R8 的文件在哪里」** —— 因为 R8 是系统行为（DI-1）。
他只需要想「我要看路线 A」或「我要看实验 X021」。这就是好的系统设计。

---

## 11. 两条内容过滤原则

### 11.1 机器目录必须「可忽略」

普通研究者只看 `README` / `INDEX` / `routes/` / `experiments/` / `results/` / `src/`
就能正常工作，**完全不知道 `.research-idea-pipeline/` 内部细节也没关系**。

### 11.2 反过来说：控制平面内部不追求人类漂亮

它追求：`schema 清晰` / `ID 稳定` / `mutation safe` / `validator friendly` /
`append-only provenance`。`research-state.json`、`actions.jsonl`、`operator-stats.json`
完全没问题。**不要为了"人看起来方便"破坏机器状态一致性** ——
人需要的内容通过 `STATUS` / `INDEX` 投影。

### 11.3 失败不得污染正式 docs

一次 CUDA OOM：机器写 `failures[]`（`kind: engineering_failure`）+ `logs/` 有 trace；
**但不生成** `T047-cuda-oom-analysis.md`。

只有**科研价值高的失败**（counterexample / null result / falsification /
regime failure）才形成正式 route 文档。

```text
machine memory has everything;
human docs contain knowledge-worthy events.
```

---

## 12. 文档成熟度（**不新增状态，用位置表达**）

| 位置 | 成熟度 |
|---|---|
| `.research-idea-pipeline/runtime/` | `scratch` |
| `routes/<R>/docs/` | `working` / `canonical` |

**`scratch` 不进 `routes/<R>/docs/`。** 若确需在 frontmatter 标注，只用三值
`scratch` / `working` / `canonical`，**不要再增加状态**。

---

## 13. 概念 → 人类入口 → canonical 机器源

**每个科研概念都有一个人类入口，也都有一个唯一的机器真相源；两者之间是投影关系，不是两份真相。**

| 科研概念 | 人类入口 | Canonical machine source |
|---|---|---|
| 项目 | `/README.md` | project contract |
| 路线 | `routes/<R>/README.md` | route registry |
| 当前状态 | `routes/<R>/STATUS.md` | `research-state.json` |
| 文档 | `routes/<R>/docs/` | 文档本身 |
| Claim | STATUS / docs | `claims[]` |
| Hypothesis | STATUS | `hypotheses[]` |
| Experiment | `experiments/<R>/<XID>/README.md` | `experiments[]` + manifest |
| Result | `results/<R>/<XID>/summary.md` | metrics + `evidence[]` |
| Literature | `docs/refs/` | refs index + `literature[]` |
| Failure | STATUS / result docs | `failures[]` |
| Decision | `docs/decisions/` | `decision` + history |
| Narrative | route docs | `narrative_view` |
| Agent telemetry | 通常不展示 | `.research-idea-pipeline/meta/` |

> **DI-8 的验收：** 本表每个「人类入口」都必须真实存在。
> 机器状态可以复杂，但**每一个都必须有一个合理的人类入口**，且**不要求人直接阅读**。
