# 示例：多路线项目的目录与文档管理

演示一个项目同时推进多条技术路线时，代码、文档、进度如何分开管理。
**全部按约定手工建立，不需要任何脚手架脚本。**

---

## 1. 目录骨架

```
<项目根目录>/
├── AGENTS.md                    # 共享契约（若项目已有则优先遵循）
├── docs/                        # ★ 所有路线的文档集中于此（扁平，不分子目录）
│   ├── A001-literature-survey.md
│   ├── A002-ideas.md
│   ├── A003-proposal.md
│   ├── A004-experiment-plan.md
│   ├── A005-narrative-I1.md
│   ├── A003-review.md
│   ├── B001-literature-survey.md    # routeB 的文档同目录，靠 B 前缀区分
│   └── refs/                    # ★ 参考文献库（= 本地文献库根目录）
│       ├── papers/              # {paper_id}.pdf（不进版本库）+ .json + 可选 .md
│       ├── cache/               # {query_hash}.json
│       └── index.json           # ★ 必需：PDF 索引，进版本库
├── routeA/
│   ├── INDEX.md                 # ★ 路线 A 索引（文档索引 + 关系图 + 进度）
│   ├── code/
│   └── experiments/
├── routeB/
│   ├── INDEX.md                 # ★ 路线 B 索引
│   ├── code/
│   └── experiments/
├── shared/                      # 跨路线公用代码/笔记
│   ├── code/
│   └── docs/
└── .research-idea-pipeline/     # 机器状态（不入 docs）
```

**六条硬性规则：**

1. **所有路线的文档都放根目录 `docs/`（扁平）**，靠**文件名前缀**（`A*`/`B*`）区分
   路线；**不再按路线分子目录**。前缀是唯一的路线隔离手段，不可省。
2. 路线之间**不得互相 import**；要复用的下沉到 `shared/`。
3. **参考文献统一放 `docs/refs/`**（脚本默认 `--local-dir ./docs/refs`）。
4. 每条路线必须有 `INDEX.md`，每次产出后必须更新。
5. `state.json` / 日志不进 `docs/`。
6. **`docs/refs/` 下的每个 PDF 都必须在 `docs/refs/index.json` 里有索引条目**；
   **索引进版本库、PDF 不进**。新增/替换/删除 PDF 后必须重建索引：

   ```bash
   python3 scripts/refs_index.py --refs-dir docs/refs
   python3 scripts/refs_index.py --refs-dir docs/refs --check
   ```

---

## 2. 文档命名与 ID 分配

### 命名格式

```
docs/A002-ideas.md            ← idea 候选清单（含 I1..In）
docs/A003-proposal.md         ← 方案
docs/A005-narrative-I1.md     ← idea I1 的 ≥4 套叙事
docs/A003-review.md           ← 对 A003 的第 1 轮审阅
docs/A003-review-2.md         ← 对 A003 的第 2 轮审阅（接续复核）
docs/B002-ideas.md           ← routeB 的 idea 清单（同一目录，靠 B 前缀区分）
```

| 规则 | 说明 |
|---|---|
| 存放 | **所有路线共用根目录 `docs/`（扁平）**；参考文献在 `docs/refs/` |
| slug 枚举 | `literature-survey` / `ideas` / `proposal` / `experiment-plan` / `narrative-I<n>`；不得自创 |
| 序号来源 | 扫描 `docs/` 中匹配 `^<路线字母>\d{3}-` 的文件名，取**最大序号 +1** |
| 递增范围 | **按路线独立**：routeA 是 A001/A002/…，routeB 是 B001/B002/… |
| 复用 | **永不复用**，也不跳号 |
| 子编号 | `I<n>` idea、`N<k>` 套路、`K<n>` 贡献、`E<n>` 实验；引用写作 `<文档ID>/<子编号>` |
| 审阅记录 | **不占新序号**，永远挂在被审文档 ID 上（`A003-review.md`） |
| 接续复核 | 递增 `-review-2`、`-review-3`，frontmatter 的 `review_round` 同步 |

> **注意：** 文档 ID 前缀 `A`/`B` 是**路线编号**，与 Mode A/B/C/D/E 无关。
> 产出该文档的 Mode 记在 frontmatter 的 `mode` 字段里。

### 每份文档的 frontmatter

```yaml
---
id: A003
route: routeA
mode: C                 # A | B | C | D | E —— 产出该文档的 Mode
type: proposal          # idea-discovery | proposal | experiment-plan | narrative | review | literature-survey
status: draft           # draft | in-review | reviewed | superseded
created: 2025-01-01
updated: 2025-01-02
parent: A001
supersedes: null
review_of: null         # 仅审阅文档
review_round: null      # 仅审阅文档
also_reviewed: []       # 同一轮还覆盖的文档 ID
reviewers: []
---
```

---

## 3. INDEX.md 的进度结构

`routeA/INDEX.md` 是这条路线的唯一入口，章节结构与填写示例：

```markdown
# routeA — INDEX

> 一句话状态：当前处于 Mode C，方案 A003 已产出待审。
> 最后更新：2025-01-02

## 1. 路线概要
| 项 | 内容 |
|---|---|
| **核心目标（锚点）** | theory（主）+ performance（次） |
| 研究问题 | 离散扩散如何约束组合优化搜索空间 |
| 核心假设 | 可逆性可作为硬可行性约束 |
| 目标会议 | ICML |
| 当前阶段 | Mode D |
| 推荐优先级 | 中 |

## 2. 文档索引
| ID | 文件 | 类型 | Mode | 状态 | 说明 |
|---|---|---|---|---|---|
| A002 | [A002-ideas.md](docs/A002-ideas.md) | idea-discovery | B | reviewed | 12 个 idea（含 B5 审核） |
| A003 | [A003-proposal.md](docs/A003-proposal.md) | proposal | C | reviewed | 贡献 K1..Kn |
| A004 | [A004-experiment-plan.md](docs/A004-experiment-plan.md) | experiment-plan | C | reviewed | 实验 E1..E7 |
| A005 | [A005-narrative.md](docs/A005-narrative.md) | narrative | D | reviewed | 一次调用：I1 的 4 套叙事，最佳 N2 |
| A003-review | [A003-review-r01.md](docs/A003-review-r01.md) | review | E | reviewed | 中位数 4 |

### 2.1 Idea 追踪
| Idea | 状态 | 关联文档 | 最佳叙事 | 备注 |
|---|---|---|---|---|
| I1 | 已进方案 | A002/I1 → A003 | N2 | 复现风险低 |
| I7 | **已淘汰** | A002/I7 | — | 重叠不足（[作者, 会议/年份]） |

### 2.2 叙事追踪
| Idea | 叙事文档 | 尝试套路 | 最佳套路 | 综合中位数 | 是否否决 |
|---|---|---|---|---|---|
| I1 | A005 | N2/N3/N5/N9 | **N2** | 4.0 | 否（N5 被否决） |

### 2.3 审阅追踪
| 被审文档 | 轮次 | 文件 | 中位数 | 复现风险 | 结论 |
|---|---|---|---|---|---|
| A003 | 1 | A003-review.md | 4 | 低 | 推荐优先级高 |

## 3. 已证实（Confirmed）

> 下表 `#` 列为**表内行号**（Confirmed 的 C1、Falsified 的 F1、TODO 的 T1、Bugs 的 B1、
> Warnings 的 W1），**与 Mode 章节号 / 触发条件 T1—T7 无关**。

| # | 结论 | 证据 | 日期 |
|---|---|---|---|
| C1 | 离散扩散可表示组合约束 | A002/I1 §2；实验 A004/E1 | 2025-01-01 |

## 4. 已证伪（Falsified）
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
| B1 | E2 中 loss NaN | 阻塞消融 | exp/e2.py | 未解决 | 怀疑学习率 |

## 7. Warnings
| # | 警告 | 类型 | 影响 | 处置 |
|---|---|---|---|---|
| W1 | "首次提出"声称仅达 L2，未达 L3 | 新颖性 | 投稿风险 | 补 L3 穷尽检索 |
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

**维持规则：**

- 已证实与已证伪**必须分开**；证伪的假设**不得删除**，留在表里并注明处置。
- Warnings 里的"检索未达饱和"条目，只有在重跑检索达到饱和判据后才能关闭。
- Bugs 必须可复现（给出命令或脚本路径）。
- INDEX 链接必须指向真实存在的文件。
- `最后更新` 每次改动都要刷新。

---

## 4. 审阅结论 → 进度条目的映射

结论不能只停在审阅文档里，必须翻译成 INDEX 条目：

| 审阅结论 | 写入 INDEX |
|---|---|
| 某机制成立 / 已被数据支持 | **§3 已证实** |
| 某假设被否定 / 不可行 | **§4 已证伪** |
| 需要补实验 X | **§5 TODO** |
| 致命风险未缓解 / **复现风险 = 高** | **§7 Warnings** |
| 复现步骤本身有错 | **§6 Bugs** |

Mode B5 同理：被判"重叠不足"或致命反驳不可缓解而**放弃**的 idea → **§4 已证伪**。

---

## 5. 并发写入

| 资源 | 规则 |
|---|---|
| `docs/` | 同路线序号分配**串行化**（先读最大序号，再写入）；不同路线互不阻塞 |
| `routeX/INDEX.md` | **单写者**：同一时刻只允许一个成员改一条路线的 INDEX |
| `shared/` | 按 `AGENTS.md` 规定；无规定时默认只在明确需要时改，改前先读 |
| `docs/refs/` | 追加式写入；缓存文件名由 query hash 决定，天然不冲突 |
| `docs/refs/index.json` | **单写者**：PDF 索引是整文件重写，同一时刻只允许一个成员重建 |

并发下若发生写冲突，**重新读取后再提交**，不要覆盖他人的改动。
