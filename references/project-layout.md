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

```
<项目根目录>/
├── AGENTS.md                    # 共享契约：布局、命名、公用部分规范
├── docs/                        # 人类可读文档（本规范管理）
│   ├── routeA/                  # 路线 A 的文档
│   │   ├── A001-idea-discovery.md
│   │   ├── A001-review.md
│   │   ├── A002-proposal.md
│   │   └── A002-review.md
│   └── routeB/
│       ├── B001-idea-discovery.md
│       └── B001-review.md
├── routeA/                      # 路线 A 的代码与实验
│   ├── INDEX.md                 # ★ 必需：文档索引 + 当前进度
│   ├── code/                    # 该路线专属代码
│   └── experiments/
├── routeB/
│   ├── INDEX.md                 # ★ 必需
│   └── code/
├── shared/                      # 跨路线公用部分（按 AGENTS.md 规范）
│   ├── code/                    # 公用工具、数据加载、评测脚本
│   ├── literature/              # 公用文献库（local_literature 落在这里）
│   └── docs/
└── local_literature/            # 若 AGENTS.md 未规定，亦可放此处
```

### 1.1 三条硬性规则

1. **路线隔离：** 每条路线 `routeX/` 自带代码与实验；**路线之间不得互相 import**，
   需要复用的一律下沉到 `shared/`。
2. **文档集中：** 所有人类可读文档放 `docs/`，按路线分子目录；**不要在路线代码目录
   里散落文档**。
3. **INDEX.md 必需：** 每条路线根目录必须有 `INDEX.md`，且**每次产出后必须更新**。

> **命名说明：** 路线目录用 `routeA` / `routeB`，其文档 ID 前缀用**大写路线字母**
> `A` / `B`。此处的 A/B 是**路线编号，与 Mode A/B/C/D 无关**；文档属于哪个 Mode
> 记录在文档 frontmatter 的 `mode` 字段里。

---

## 2. 文档命名与 ID 分配

### 2.1 命名格式

```
docs/<routeX>/<ROUTE><NNN>-<slug>.md        # 交付物文档
docs/<routeX>/<ROUTE><NNN>-review.md        # 第 1 次审阅记录
docs/<routeX>/<ROUTE><NNN>-review-2.md      # 第 2 次审阅（接续复核）
docs/<routeX>/<ROUTE><NNN>-review-3.md      # 第 3 次审阅
```

- `<ROUTE>`：路线字母（A/B/C…），与 `routeX` 对应。
- `<NNN>`：该路线内**三位递增序号**，从 `001` 开始，**只增不减、永不复用**。
- `<slug>`：kebab-case 英文短描述，如 `proposal`、`experiment-plan`、
  `idea-discovery`、`literature-survey`。
- **审阅文档不占用新序号**，永远挂在被审文档的 ID 上（`A002-review.md`）。
- 接续复核递增 `-review-2`、`-review-3`，并在 frontmatter 里写 `review_round`。

**示例（对应你给的命名）：**

| 文件 | 含义 |
|---|---|
| `docs/routeA/A001-idea-discovery.md` | 路线 A 的第 1 份文档（idea 候选清单） |
| `docs/routeA/A001-review.md` | 对 `A001` 的审阅记录 |
| `docs/routeB/B001-proposal.md` | 路线 B 的第 1 份文档（方案） |
| `docs/routeB/B001-review.md` | 对 `B001` 的审阅记录 |

> 序号按**路线独立**递增：routeA 是 A001/A002/…，routeB 是 B001/B002/…。
> 文件放进 `docs/routeX/` 子目录做物理隔离，ID 前缀保证跨路线引用时无歧义
> （INDEX.md 链接、审阅引用、git 检索都靠它）。

### 2.2 分配规则

- 分配前**扫描 `docs/<routeX>/` 中已有的最大序号**，取 `max + 1`。
- 多代理并发时，序号分配必须**串行化**（见 §5）。
- 不要手动跳号、不要复用已删除的号。

---

## 3. 文档 frontmatter（必需）

每份文档开头必须有 YAML frontmatter，便于机器检索与 INDEX 生成：

```yaml
---
id: A002
route: routeA
mode: B                     # A | B | C | D —— 产出该文档的 Mode
type: proposal              # idea-discovery | proposal | experiment-plan | review | literature-survey
status: draft               # draft | in-review | reviewed | superseded | archived
created: 2025-01-01
updated: 2025-01-02
parent: A001                # 可选：上游文档
supersedes: null            # 可选：被本文件取代的文档
review_of: null             # 仅审阅文档：被审文档 ID，如 A002
review_round: null          # 仅审阅文档：第几轮（1,2,3…）
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

> 一句话状态：当前处于 Mode B，方案 A002 已产出待审。
> 最后更新：2025-01-02

## 1. 路线概要
- 研究问题：
- 核心假设：
- 目标会议：CVPR / ICML / NeurIPS
- 当前阶段：Mode A / B / C / D
- 推荐优先级：高 / 中 / 低 / 建议放弃

## 2. 文档索引
| ID | 文件 | 类型 | Mode | 状态 | 说明 |
|---|---|---|---|---|---|
| A001 | [A001-idea-discovery.md](../docs/routeA/A001-idea-discovery.md) | idea-discovery | A | reviewed | 10 个 idea 候选 |
| A001-review | [A001-review.md](../docs/routeA/A001-review.md) | review | C | reviewed | 七子代理评分中位数 3 |
| A002 | [A002-proposal.md](../docs/routeA/A002-proposal.md) | proposal | B | in-review | 待第 1 轮审阅 |

## 3. 已证实（Confirmed）
> 有明确证据支持的结论。每条必须带证据链接。
| # | 结论 | 证据 | 日期 |
|---|---|---|---|
| C1 | 离散扩散可表示组合约束 | [A001](../docs/routeA/A001-idea-discovery.md) §2；实验 E1 | 2025-01-01 |

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
| 2025-01-02 | 新增方案 A002 | A002 |
```

### 4.2 维持规则

- **已证实 / 已证伪** 必须区分开：证伪的假设**不得删除**，留在表里并注明处置。
- **Warnings 中的"检索未达饱和"** 条目，只有在重跑检索达到 §3.3 饱和判据后才能关闭。
- **Bugs** 必须可复现（给出命令或脚本路径）。
- INDEX 里的链接必须**指向真实存在的文件**，不要写占位路径。
- `最后更新` 字段每次改动都要刷新。

---

## 5. 并发写入规则

多条路线、多个子代理并行工作时：

| 资源 | 规则 |
|---|---|
| `docs/<routeX>/` | 同一路线内序号分配**串行化**；不同路线互不阻塞 |
| `routeX/INDEX.md` | **单写者**：同一时刻只允许一个成员改一条路线的 INDEX |
| `shared/` | 按 `AGENTS.md` 规定；无规定时默认**只在明确需要时改**，改前先读 |
| `local_literature/` | 追加式写入；缓存文件名由 query hash 决定，天然不冲突 |

> 序号分配与 INDEX 更新必须**串行进行**：先读取现有最大序号 / 当前 INDEX 内容，
> 再写入新文件与新行。并发时由 Lead（或指定的单写者）统一执行这两步。
> 若发生写冲突（FS_STALE_VERSION 类），重新读取后再提交，不要覆盖他人的改动。

---

## 6. 各 Mode 的落盘职责

| Mode | 产出文档 | 落盘路径 | 同时必须更新 |
|---|---|---|---|
| **A** | idea 候选清单（**含 idea 级创新性/可行性审核评分**）+ 技术路线归纳 + 创新性边界 + shortlist + 淘汰清单 | `docs/<routeD>/<R>001-idea-discovery.md` | 对应 `INDEX.md`（§2 文档索引；**放弃的 idea → §4 已证伪**；未核实的无人区声称 → §7 Warnings） |
| **B** | 论文提案 | `docs/<routeD>/<R>00N-proposal.md` | 对应 `INDEX.md` |
| **B** | 实验流程计划书 | `docs/<routeD>/<R>00N-experiment-plan.md` | 对应 `INDEX.md`（§5 TODO、§6 Bugs、§8 依赖） |
| **C** | 审阅记录（**含复现风险等级**） | `docs/<routeD>/<被审ID>-review.md`（接续则 `-review-2.md`） | 对应 `INDEX.md`（§3/§4/§5/§7；**复现风险高 → §7 Warnings**） |
| **D** | 文献调研报告（含负检索记录） | `docs/<routeD>/<R>00N-literature-survey.md` | 对应 `INDEX.md`（§7 Warnings：未达饱和必须记） |
| 任意 | 机器状态 | `.research-idea-pipeline/state-<mode>-<ts>.json` | 不入 docs |

**审阅结论对进度的映射：** Mode C 的结论要**翻译成进度条目**——

- 结论"某机制成立/已被数据支持" → INDEX **§3 已证实**
- 结论"某假设被否定/不可行" → INDEX **§4 已证伪**
- 结论"需要补 A、B" → INDEX **§5 TODO**
- 结论"致命风险未缓解 / **复现风险高**" → INDEX **§7 Warnings**
- 复现步骤本身有错 → INDEX **§6 Bugs**

**idea 审核对进度的映射（Mode A5）：** 被判"重叠不足"或致命反驳不可缓解而**放弃**的
idea，同样写入 **§4 已证伪**——负结果是资产，不要丢。

---

## 7. 建立骨架的检查清单（手工执行）

本 Skill **不提供一键生成脚本**。执行者按下面的清单手工建立或用普通文件操作即可：

**新项目（无任何结构时）：**

1. 建 `docs/`、`shared/{code,literature,docs}/`、`.research-idea-pipeline/`。
2. 每条路线建 `routeX/{code,experiments}/`、`docs/routeX/`。
3. 每条路线建 `routeX/INDEX.md`，按 [../templates/INDEX.md](../templates/INDEX.md) 的
   章节结构填写（**必需**，且之后每次产出都要更新）。

**每次产出新文档时：**

1. 扫描 `docs/<routeX>/` 里匹配 `^<路线字母>\d{3}-` 的文件名，取最大序号 +1。
2. 按 `<ID>-<slug>.md` 命名创建，文件开头写完整 frontmatter（§3）。
3. 把该行登记进 `routeX/INDEX.md` 的**文档索引**，并在**变更日志**加一行。

**每次审阅时：**

1. 审阅记录命名为 `<被审ID>-review.md`；已是审阅则递增 `-review-2.md`、`-review-3.md`。
   **审阅记录不占新序号。**
2. frontmatter 填 `review_of` 与 `review_round`。
3. 把审阅结论翻译成 INDEX 的 已证实 / 已证伪 / TODO / Warnings / Bugs（§6）。

**自检：**

- INDEX 里的每个链接都指向真实存在的文件；
- 每条路线都含全部必需章节（文档索引、已证实、已证伪、TODO、Bugs、Warnings、变更日志）；
- 每份 `docs/` 文档都有完整 frontmatter，且 `最后更新` 已刷新。
