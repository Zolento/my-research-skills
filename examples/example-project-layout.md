# 示例：多路线项目的目录与文档管理

演示一个项目同时推进多条技术路线时，代码、文档、进度如何分开管理。
**全部按约定手工建立，不需要任何脚手架脚本。**

---

## 1. 目录骨架

```
<项目根目录>/
├── AGENTS.md                    # 共享契约（若项目已有则优先遵循）
├── shared/
│   ├── code/                    # 跨路线公用代码
│   ├── literature/              # 公用文献库
│   └── docs/
├── routeA/
│   ├── INDEX.md                 # ★ 路线 A 的唯一入口
│   ├── code/
│   └── experiments/
├── routeB/
│   ├── INDEX.md
│   ├── code/
│   └── experiments/
├── docs/
│   ├── routeA/
│   └── routeB/
└── .research-idea-pipeline/     # 机器状态（不入 docs）
```

**四条硬性规则：**

1. 路线之间**不得互相 import**；要复用的下沉到 `shared/`。
2. 人类可读文档统一放 `docs/routeX/`，不在代码目录里散落文档。
3. 每条路线必须有 `INDEX.md`，每次产出后必须更新。
4. `state.json` / 日志不进 `docs/`。

---

## 2. 文档命名与 ID 分配

### 命名格式

```
docs/routeA/A001-idea-discovery.md
docs/routeA/A002-proposal.md
docs/routeA/A002-review.md          ← 对 A002 的第 1 轮审阅
docs/routeA/A002-review-2.md        ← 对 A002 的第 2 轮审阅（接续复核）
docs/routeB/B001-proposal.md
```

| 规则 | 说明 |
|---|---|
| 序号来源 | 扫描 `docs/<routeX>/` 中匹配 `^<路线字母>\d{3}-` 的文件名，取**最大序号 +1** |
| 递增范围 | **按路线独立**：routeA 是 A001/A002/…，routeB 是 B001/B002/… |
| 复用 | **永不复用**，也不跳号 |
| 审阅记录 | **不占新序号**，永远挂在被审文档 ID 上（`A002-review.md`） |
| 接续复核 | 递增 `-review-2`、`-review-3`，frontmatter 的 `review_round` 同步 |

> **注意：** 文档 ID 前缀 `A`/`B` 是**路线编号**，与 Mode A/B/C/D 无关。
> 产出该文档的 Mode 记在 frontmatter 的 `mode` 字段里。

### 每份文档的 frontmatter

```yaml
---
id: A002
route: routeA
mode: B                 # A | B | C | D —— 产出该文档的 Mode
type: proposal          # idea-discovery | proposal | experiment-plan | review | literature-survey
status: draft           # draft | in-review | reviewed | superseded
created: 2025-01-01
updated: 2025-01-02
parent: A001
supersedes: null
review_of: null         # 仅审阅文档
review_round: null      # 仅审阅文档
reviewers: []
---
```

---

## 3. INDEX.md 的进度结构

`routeA/INDEX.md` 是这条路线的唯一入口，章节结构与填写示例：

```markdown
# routeA — INDEX

> 一句话状态：当前处于 Mode B，方案 A002 已产出待审。
> 最后更新：2025-01-02

## 1. 路线概要
| 项 | 内容 |
|---|---|
| 研究问题 | 离散扩散如何约束组合优化搜索空间 |
| 核心假设 | 可逆性可作为硬可行性约束 |
| 目标会议 | ICML |
| 当前阶段 | Mode B |
| 推荐优先级 | 中 |

## 2. 文档索引
| ID | 文件 | 类型 | Mode | 状态 | 说明 |
|---|---|---|---|---|---|
| A001 | [A001-idea-discovery.md](../docs/routeA/A001-idea-discovery.md) | idea-discovery | A | reviewed | 12 个 idea（含审核） |
| A001-review | [A001-review.md](../docs/routeA/A001-review.md) | review | C | reviewed | 中位数 3 |
| A002 | [A002-proposal.md](../docs/routeA/A002-proposal.md) | proposal | B | in-review | 待第 1 轮审阅 |

## 3. 已证实（Confirmed）
| # | 结论 | 证据 | 日期 |
|---|---|---|---|
| C1 | 离散扩散可表示组合约束 | A001 §2；实验 E1 | 2025-01-01 |

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
| 2025-01-02 | 新增方案 A002 | A002 |
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

Mode A5 同理：被判"重叠不足"或致命反驳不可缓解而**放弃**的 idea → **§4 已证伪**。

---

## 5. 并发写入

| 资源 | 规则 |
|---|---|
| `docs/<routeX>/` | 同路线序号分配**串行化**（先读最大序号，再写入）；不同路线互不阻塞 |
| `routeX/INDEX.md` | **单写者**：同一时刻只允许一个成员改一条路线的 INDEX |
| `shared/` | 按 `AGENTS.md` 规定；无规定时默认只在明确需要时改，改前先读 |
| `local_literature/` | 追加式写入；缓存文件名由 query hash 决定，天然不冲突 |

并发下若发生写冲突，**重新读取后再提交**，不要覆盖他人的改动。
