# 示例：多路线项目的目录与文档管理

演示一个项目同时推进多条技术路线时，代码、文档、进度如何分开管理。
**全部按约定手工建立，不需要任何脚手架脚本。**

---

## 1. 目录骨架

```
<项目根目录>/
├── AGENTS.md                    # 共享契约。存在则优先遵循
├── README.md                    # ★ 根级：项目总览
├── INDEX.md                     # ★ 根级：路线总表投影
├── docs/                        # ★ 跨路线共享区（不放路线文档）
│   ├── refs/                    # ★ 必需：参考文献库
│   │   ├── papers/              # {paper_id}.pdf（不进版本库）+ .json + 可选 .md
│   │   ├── cache/<source>/      # 查询缓存（按源分目录）
│   │   └── index.json           # ★ 必需：PDF 索引，进版本库
│   ├── decisions/               # ★ 项目级重大决策 DEC<NNN>-<slug>.md
│   ├── notes/                   # 可选：跨路线共享笔记
│   └── latex/                   # 可选：跨路线共享 LaTeX
├── routes/                      # ★ 所有科研路线集中于此
│   ├── A/
│   │   ├── README.md            # ★ 路线身份证：这条路线是什么
│   │   ├── STATUS.md            # ★ 当前状态：research-state.json 的投影
│   │   ├── INDEX.md             # ★ 资产目录 + 时间线
│   │   └── docs/                # ★ 本路线文档（扁平）
│   │       ├── A001-field-map.md
│   │       ├── A002-discovery.md
│   │       ├── A003-proposal.md
│   │       ├── A004-experiment-plan.md
│   │       ├── A005-narrative.md          # R12：一次调用一份
│   │       └── A003-review-r01.md         # 审阅挂被审 ID，轮次零填充
│   └── B/                       # 同构
├── src/                         # ★ canonical implementation（唯一）
├── configs/routes/A/            # route 差异用 config 表达
├── experiments/A/X021-identifiability/    # ★ 想做什么（pre-registration）
├── results/A/X021/              # ★ 观察到什么（observation）
├── shared/                      # 跨路线公用代码/笔记
└── .research-idea-pipeline/routes/A/research-state.json   # 机器状态（不入 docs）
```

**六条硬性规则：**

1. **文档按路线分离、各自扁平：** 产出放 `routes/<R>/docs/`，**该目录内不再按类型分子目录**。
   **根 `docs/` 是跨路线共享区**，只保证有 `refs/`。`notes/`、`latex/` 等由
   `AGENTS.md` 决定。**唯一硬约束：路线文档不得放根 `docs/`。**
2. **路线级三文件分工：** `README.md` 答"是什么"（很低频），`STATUS.md` 答"现在怎样"
   （很高频），`INDEX.md` 答"有哪些材料"（中等）。**三者都是 state 的视图。**
   `STATUS.md` 由 `render_status.py` 生成，**禁止手改**。
3. **文件名前缀 = 文档 ID**（不再是路径隔离）：前缀仍必需（审阅挂靠、跨路线引用唯一）。
   序号按路线独立递增、**永不复用**。
4. **审阅挂被审 ID、轮次零填充：** `<被审ID>-review-r01.md` / `-r02.md`，**不占新序号**。
5. **参考文献集中：** 一律放根目录 `docs/refs/`，不散落到 `routes/<R>/docs/`。
6. **PDF 必须入索引：** `docs/refs/` 下每个 PDF 都要在 `docs/refs/index.json` 里有记录。
   **索引进版本库、PDF 不进**。增删后必须重建（`scripts/refs_index.py`）。

---

## 2. 文档命名与 ID 分配

### 命名格式

```
routes/A/docs/A002-discovery.md           ← hypothesis 候选清单（含 I1..In）
routes/A/docs/A003-proposal.md            ← 方案
routes/A/docs/A005-narrative.md           ← R12 一次调用：I1 的 2—4 套 claim hierarchy + 六槽位 S1—S6 + 门禁 G1—G5
routes/A/docs/A003-review-r01.md          ← 对 A003 的第 1 轮审阅
routes/A/docs/A003-review-r02.md          ← 对 A003 的第 2 轮审阅（接续复核）
routes/B/docs/B002-discovery.md           ← routes/B 的文档在自己的 docs/ 下
```

| 规则 | 说明 |
|---|---|
| 存放 | **路线文档放 `routes/<R>/docs/`（扁平）**。根 `docs/` 是跨路线共享区（只保证有 `refs/`） |
| slug 枚举 | `anchor` / `field-map` / `discovery` / `theory` / `evidence` / `proposal` / `experiment-plan` / `result-analysis` / `decision` / `narrative` / `review`。不得自创 |
| 序号来源 | 扫描 `routes/<R>/docs/` 中匹配 `^<路线字母>\d{3}-` 的文件名，取**最大序号 +1** |
| 递增范围 | **按路线独立**：routes/A 是 A001/A002/…，routes/B 是 B001/B002/… |
| 复用 | **永不复用**，也不跳号 |
| 子编号 | `I<n>` idea、`N<k>` 叙事 preset、`K<n>` 贡献、`E<n>` 实验。引用写作 `<文档ID>/<子编号>` |
| 审阅记录 | **不占新序号**，挂在被审文档 ID 上：`A003-review-r01.md` / `-r02.md`（轮次零填充） |
| 接续复核 | 递增 `-r02`、`-r03`（**零填充两位**），frontmatter 的 `review_round` 同步 |

> **注意：** 文档 ID 前缀 `A`/`B` 是**路线编号**，与 R 阶段 无关。
> 产出该文档的阶段记在 frontmatter 的 `phase` 字段里。
> **slug 是知识类型，不是流程类型**：同一份 `discovery` 可能来自 R3—R6 四个阶段。

### 每份文档的 frontmatter

```yaml
---
id: A003
route: A
phase: R8                 # R0..R14 —— 产出该文档的阶段
type: proposal            # anchor | field-map | discovery | theory | evidence | proposal |
                          # experiment-plan | result-analysis | decision | narrative | review
status: draft             # draft | in-review | reviewed | superseded
created: 2025-01-01
updated: 2025-01-02
parent: A001
supersedes: null
review_of: null           # 仅审阅文档
review_round: null        # 仅审阅文档
also_reviewed: []         # 同一轮还覆盖的文档 ID
reviewers: []
---
```

---

## 3. 路线级三文件

### 3.1 `INDEX.md`：只做资产目录 + 时间线

`routes/A/INDEX.md` 是这条路线的**材料目录**，不回答"现在卡在哪"。
`已证实 / 已证伪 / TODO / Bugs / Warnings` 一律交给 `STATUS.md`。

```markdown
# routes/A — INDEX

> 本文件是资产目录。当前状态见 [STATUS.md](STATUS.md)。
> 最后更新：2025-01-02

## 1. Route Overview
| 项 | 内容 |
|---|---|
| 路线锚点 `core_goal` | theory（只记主锚点） |
| `anchor_role` | primary |
| 目标会议 | ICML |

## 2. Key Documents
| ID | 文件 | 类型 | subtype | 阶段 | 状态 | 说明 |
|---|---|---|---|---|---|---|
| A002 | [A002-discovery.md](docs/A002-discovery.md) | discovery | — | R3—R6 | reviewed | 12 个 idea（含审核） |
| A003 | [A003-proposal.md](docs/A003-proposal.md) | proposal | — | R8 | reviewed | 贡献 K1..Kn |
| A004 | [A004-experiment-plan.md](docs/A004-experiment-plan.md) | experiment-plan | experiment-cards | R9—R11 | reviewed | 实验 E1..E7 |
| A005 | [A005-narrative.md](docs/A005-narrative.md) | narrative | — | R12 | reviewed | 最佳 N2 |
| A003-review | [A003-review-r01.md](docs/A003-review-r01.md) | review | — | R7 / R10 / R13 | reviewed | 中位数 4 |

### 2.1 文档关系图
A001 → A002 → A003 → A004 / A005

## 3. Experiments
| XID | Question | 状态 | 结果 | 入口 |
|---|---|---|---|---|
| X021 | 可逆性约束是否可无损映射到置换空间 | done | 全部失败 | `experiments/A/X021-identifiability/README.md` |

## 4. Decisions
| DEC | 主题 | 结论 | 日期 |
|---|---|---|---|
| DEC001 | 放弃无损映射，改走松弛方案 | 采纳 | 2025-01-01 |

## 5. Reviews
| 被审文档 | 轮次 | 文件 | 中位数 | 复现风险 | 结论 |
|---|---|---|---|---|---|
| A003 | 1 | A003-review-r01.md | 4 | 低 | 推荐优先级高 |

## 6. Milestones
| 日期 | 里程碑 | 关联文档 |
|---|---|---|
| 2025-01-01 | 方案定稿待审 | A003 |

## 7. Recent Research Changes
| 日期 | state_version | 变更摘要 | 触发阶段 |
|---|---|---|---|
| 2025-01-02 | 3 | X021 证伪无损映射，U2 升为 High | R11 |

## 8. Archive
| 日期 | 材料 | 归档原因 | 去向 |
|---|---|---|---|
| | | | |
```

### 3.2 `STATUS.md`：当前状态的投影

`routes/A/STATUS.md` 由 `research-state.json` 生成，**不是第二份真相**。
它固定十节，顺序不得改。

```markdown
# routes/A — STATUS

> 本文件是 research-state.json 的投影，不是第二份真相。
> 由 scripts/research/render_status.py 生成，手改无效。

## Last updated + State version
- 最后更新：2025-01-02
- State version：3

## Current thesis（含 status）
- 中心命题：可逆性约束需松弛后才能映射到置换空间
- status：partially-supported

## Strongest supported findings
| # | 结论 | 证据 | state 引用 |
|---|---|---|---|
| S1 | 离散扩散可表示组合约束 | A002/I1 §2 | C1 |

## Active hypotheses
| # | 假设 | 状态 | niche |
|---|---|---|---|
| H1 | 松弛后可保留可行性保证 | elite | N2 |

## Critical uncertainties
- 待核实条数：2
- 松弛方案的可行性保证在高维是否成立（等级：High）

## Open critical attacks
| # | 攻击 | 状态 | 处置 |
|---|---|---|---|
| A1 | S-Lit 判部分重叠 | open | 相关工作显式划界 |

## Active experiments
| XID | Question | 状态 | 结果 |
|---|---|---|---|
| X021 | 无损映射是否成立 | done | 否 |

## Most important negative findings
| # | 负结果 | 证据 | 处置 |
|---|---|---|---|
| F1 | 可逆性约束可无损映射到置换空间 | X021 | 改走松弛方案 |

## Next recommended actions
| # | 动作 | 优先级 | 依赖 |
|---|---|---|---|
| N1 | 补齐松弛方案的可行性证明 | P0 | — |
| N2 | 跑消融矩阵 E4—E7 | P1 | N1 |

## Current decision
- 决策：continue
- 依据：松弛方向仍有可辩护 anchor
- Revisit condition：高维反例出现即回 R14 重判
```

**维持规则：**

- 负结果**不得删除**，进 `STATUS.md` 的 Most important negative findings。
- Critical uncertainties 的"待核实"条数超过 5，必须在本轮内收敛。
- 工程失败只进机器 state 与 `logs/`，**不新增正式文档**。
- INDEX 链接必须指向真实存在的文件。
- `最后更新` 每次改动都要刷新。

---

## 4. 审阅结论 → 状态条目的映射

结论不能只停在审阅文档里，必须翻译成状态条目：

| 审阅结论 | 写入 `STATUS.md` |
|---|---|
| 某机制成立 / 已被数据支持 | **Strongest supported findings** |
| 某假设被否定 / 不可行 | **Most important negative findings** |
| 需要补实验 X | **Next recommended actions** |
| 致命风险未缓解 / **复现风险 = 高** | **Critical uncertainties** |
| 复现步骤本身有错 | **Next recommended actions**（工程项） |

R3—R6 同理：被判"重叠不足"或致命反驳不可缓解而**放弃**的 idea，
同样进 **Most important negative findings**。

---

## 5. 并发写入

| 资源 | 规则 |
|---|---|
| `routes/<R>/docs/` | 同路线序号分配**串行化**（先读最大序号，再写入）。不同路线互不阻塞 |
| `routes/<R>/INDEX.md` | **单写者**：同一时刻只允许一个成员改一条路线的资产目录 |
| `routes/<R>/STATUS.md` | **不手写**：由 `render_status.py` 从 state 生成 |
| 根 `INDEX.md` | **单写者**：路线总表投影，改动前先读 |
| `experiments/<R>/<XID>/` | 每个 XID 一个写者。创建后 manifest 与 config 冻结 |
| `shared/` | 按 `AGENTS.md` 规定。无规定时默认只在明确需要时改，改前先读 |
| `docs/refs/` | 追加式写入。缓存文件名由 query hash 决定，天然不冲突 |
| `docs/refs/index.json` | **单写者**：PDF 索引是整文件重写，同一时刻只允许一个成员重建 |

并发下若发生写冲突，**重新读取后再提交**，不要覆盖他人的改动。
