---
name: research-lifecycle-protocol
description: >-
  有状态的科学研究生命周期协议（Research Lifecycle Protocol，RLP）：以 Research State 为唯一
  科学事实源，运行 Discovery / Assurance 双循环（R0—R14，31 条机械硬规则），覆盖研究契约、
  文献与假设、证据资格、实验预注册与执行、对抗审查、状态回写、科研决策与长期自主探索。
  可选的 MRI Reconstruction Domain Profile 增加自监督 MRI 的物理与信息边界、平凡归因守卫
  （TAG）和机制到方法搜索（MMS）。
  A stateful scientific research lifecycle protocol centered on a Research State: a dual
  loop across R0-R14 with 31 machine-enforced rules, evidence qualification, preregistered
  experiments, adversarial review and scientific decision-making. The optional MRI
  reconstruction domain profile adds self-supervised MRI contracts, a Trivial Attribution
  Guard and Mechanism-to-Method Search. Use when the user wants to survey literature, find a
  research gap, turn an idea into a submittable proposal plus experiment plan, review paper
  narratives, audit evidence, or run a long-lived research project with explicit state and
  failure memory.
  Triggers: 科研生命周期, 研究状态, 文献调研, 相关工作, 研究缺口, 方案生成, 实验计划,
  论文叙事, 叙事套路, 故事, 卖点, 叙事评审, 方案复核, 审阅方案, 投稿方案, 研究创意,
  找 idea, 头脑风暴, 范式逃逸, 医学影像, 医学图像, 临床验证, MRI 重建, 磁共振重建,
  自监督 MRI, SSDU, 加速 MRI, 逆问题, 欠采样, 多线圈, 机制归因, 平凡归因, 方法探索,
  科研策略, research lifecycle, research state, literature survey, related work,
  research gap, research proposal, experiment plan, paper narrative, narrative review,
  proposal review, mock review, paradigm escape, MRI reconstruction, self-supervised MRI,
  inverse problem, undersampling, multi-coil, mechanism discovery, method search,
  research strategy.
argument-hint: "<start-project|continue-research|explore|audit> [phase=R0..R14] [domain=mri-reconstruction] [writing=asd-ste100] [领域关键词 | idea | proposal | query]"
metadata:
  author: research-lifecycle-protocol
  version: "2.2.0"
  abbreviation: RLP
  upstream-spec: "有状态科学研究生命周期协议（Research Lifecycle Protocol）"
  legacy-name: research-idea-pipeline
---

# Research Lifecycle Protocol（RLP）

**RLP 是有状态的科学研究生命周期协议。它不是文档流水线，也不是单领域 idea 生成器。**
它规定科研项目怎样被组织、推进、质疑、修复与决策。DSH Harness / Research Mesh 负责
Agent 生命周期、沙箱、工具执行与外部调度，两者职责分离。

**本文件是 L0 常驻核心。** 它只回答四件事：进哪道门、哪些约束不能破、这一轮加载什么、
门禁在哪里。完整科研规范在 references 里**按需加载**（§2），不在这里复述。
协议完整、上下文轻量、判断不退化：模型负责判断，机器负责机器该负责的门禁。

---

## 0. 入口：**语义入口优先**

| 身份 | 值 | 能不能改 |
|---|---|---|
| Skill 名称 | `research-lifecycle-protocol` | 只有正式发布能改 |
| 机器协议命名空间 | `research-idea-pipeline/...@1` | **永久冻结**。schema id 与历史状态的 `schema` 字段不随 Skill 改名 |
| 运行时状态根 | `<project>/.research-lifecycle-protocol/` | 唯一控制根。旧根 `.research-idea-pipeline/` 只作迁移、审计与灾难恢复来源 |

### 0.1 开工门槛：先定锚点，再定存储

**两道门都先过，未过不得进入任何 R 阶段。**

**第一道 · 锚定点。** 开工前必须与用户确认核心目标。用户没说就**反问**，不要猜，更不要默认成
「提高性能」。`core_goal` 只记主锚点，取值 `theory` / `performance` / `phenomenon` /
`benchmark` / `feasibility` / `negative`。次锚点写 `core_goal_secondary`，不得拼成
`"theory+feasibility"`。项目主锚点写根 `INDEX.md`，**未声明不得开工**。

路线必须声明 `anchor_role` ∈ `primary` / `supporting` / `orthogonal`。`supporting` 必填
**可证伪的** `serves` + `serves_evidence`，要说明哪个下游决策会因此改变。答不出只能标
`orthogonal`，公开写明「不参与主锚点成功判据」，且**不得进 R12、不得作投稿主线**。
锚点与产出不一致时必须**当轮落盘**处置（重新定位或提请换方向），不得只提示后继续。

**第二道 · 存储判定。** 先解析运行根，再谈读写。

```bash
python3 scripts/rlp_paths.py resolve <project>    # 退出码 3 = 必须先迁移
```

| 判定 | 允许的动作 |
|---|---|
| `NEW_PROJECT` | 可 Bootstrap（§0.4） |
| `READY` | 正常科研 |
| `MIGRATION_REQUIRED` / `AMBIGUOUS_STORAGE_ROOT` / `INVALID_STORAGE_ROOT` | **只读**：审计、`inspect`、`plan`。执行入口一律返回 `MIGRATION_REQUIRED`，不得假装成功 |

迁移用 `scripts/migrate_project_root.py`。`--apply` **必须**带 `--assume-writers-quiesced`，
并由操作者确认外部写入者已静止。回滚是灾难恢复，不是日常操作。

> 完整锚点规则（六类锚点、三层体系、冲突处置、变更单）见
> [references/anchor-policy.md](references/anchor-policy.md)。**开工门槛不因精简而放宽。**

### 0.2 锚点变更单只有用户能授权

改项目主锚点、改路线锚点、开新路线都是**用户授权动作**。Agent 能做且只能做两件事：
**提请**（把「不可达」的证据写进根 `INDEX.md` 并明确提问）与**降级**（标 `orthogonal` 并
公开标注）。**换方向不是 Agent 能做的。**

变更单：日期 / 旧方向→新方向 / 类型（`增补` | `替换`）/ 依据 / 受影响产物。`替换` 的依据
**必须是用户显式指令原话**，且**必须**列出受影响产物，缺一即无效。append-only。

### 0.3 入口：语义入口优先，让用户不必知道 R 编号

**常态入口只有四个。** 用户描述目标即可，不选阶段。

| 入口 | 用户想要什么 | 允许做什么 | 登记预设 |
|---|---|---|---|
| `start-project` | 开一个新研究 | 只跑 Bootstrap `B0`—`B6`，**然后停** | 无 |
| `continue-research` | 继续推进既有研究 | 在既有授权内推进。区分**建议**与**执行**授权 | 11 个 |
| `explore` | 多给我一些方向 | 只扩大候选、保多样性。**不执行实验** | 2 个 |
| `audit` | 攻击一下我现在的路线 | 对抗审查、证据资格、修复。默认不改科学结论 | 2 个 |

**解析顺序固定，命中即停，不得自行调整：**

| 层 | 输入 | 处理 |
|---|---|---|
| **1. 语义入口**（常态） | `start-project` / `continue-research` / `explore` / `audit` | 按 [references/invocation-prompts.md](references/invocation-prompts.md) 的固定契约执行 |
| **2. 自然语言意图** | 「多给我一些新方向」 | 映射到上一层四个之一，并在输出开头**声明映射结果** |
| **3. 显式 `phase=`**（**专家 / 调试覆盖**入口） | `phase=R8` | 按该阶段读写契约执行。**不是常态入口** |
| **4. 兜底** | 以上都不命中 | **才**反问要跑哪些阶段。不得猜测 |

**裁决：** **不要同时给出语义入口与 `phase=`。** 两者同时出现时按语义入口执行，
并在输出开头**显式声明**该裁决。
`phase=` 不因为「更具体」就自动赢。收到旧 `mode=` **必须报错**并给出映射
（A→R2/R5、B→R3/R4/R6、C→R8、D→R12、E→R7/R10/R13），不得静默按旧模式执行。

**否定即停：** 用户说「不要审计」「先别跑」时返回 `HOLD`，不路由、不执行。

### 0.4 首次运行与恢复：三种完全不同的操作

| 情形 | 操作 | 边界 |
|---|---|---|
| 无 canonical state | **Bootstrap** `B0`—`B6` | **只观察，不干预**。B6 之后必须停，等用户确认 |
| 有历史但未完成接管，或真实不兼容迁移 | **Cold Handoff**（`legacy_handoff.py take`） | 一次性。兼容性审计 + 投影重建 + 可回滚。**不伪造预注册**，canonical 无损 |
| 已有有效 state（`/loop` 唤醒、`continue-research`、会话恢复、压缩后重载） | **Research Resume** | 从磁盘读 canonical state + 认知投影 + scheduler + 已有产物，继续未完成行动 |
| state 不可读 / 证据异常 | **Recover / HOLD** | 走既有恢复链。**不得**重建 state 绕过 |

**已有 `research-state.json` ≠ 需要完整接管。** `state_version` 增长、缺少派生报告都**不**构成
重新接管的理由。**已有项目禁止重新 Bootstrap。**

Bootstrap 稀疏纪律：`State completeness is not a goal; grounded completeness is.`
首次运行结束时**每一条 state 条目都必须能指回真实来源**。指不回去的条目视为编造，
必须删除或改记为 `uncertainties[]`。**稀疏的真实状态优于编造的完整状态。**

---

## 1. 最小全局不变量

七条。任何 R 阶段、入口、子 Agent 都不得违反。输出前逐条自检。

### 1.1 科学事实与证据资格

**canonical Research State 是唯一科学事实源。** Cognitive Memory、Context Brief、Strategy
Memory、Preset 事件、决策轨迹、任何摘要都是索引、派生视图或建议，**不是**第二份真相。

**证据必须过资格门。** 一条证据能否支撑一条 claim，由既有 R8 / R9.O / R10 / R11 与
Evidence Qualification 判定。基本约束：**来源绑定**（证据要能解析到真实 Experiment /
artifact / 文献条目）、**范围约束**（结论不得超出证据覆盖的 scope，`depends_on` ≠
`supports`）、**方向单向**（claim 状态只做证据驱动的升级 `ungrounded` → `partially-supported`
→ `supported`，**降级与否决只能经 R10**）、**冻结优先**（未经事前冻结的预测不得追认，
事后解释属探索性，须用独立协议确认）。

**工程错误 ≠ 科学否证。** 崩溃、OOM、NaN、超时、进程终止、日志缺失都是工程结果，
**不得**写成机制被否证，也**不得**写成科学完成。「跑完了」的 smoke 同样**不是**有效性证据。

**科学结论必须带来源与适用范围。** 未验证的结果不得宣称机制成立。相关性不得写成因果性。
「首次提出」需要 L3 穷尽检索与负检索记录，否则只能写「据本次检索未见」。

**检索顺序不可颠倒：** Step 0: 先尝试 web search → Step 1: 本地库 → Step 2: 全部启用源。
单源失败不终止检索；网页没命中与本地没命中都不等于「没人做过」。强制扩检的
T1—T8 触发条件与 L1/L2/L3 尽职调查等级见
[references/literature-policy.md](references/literature-policy.md)。

措辞与等级的唯一权威是 [references/evidence-policy.md](references/evidence-policy.md)。

### 1.2 授权与动作分类

**用户授权不可由 Agent 自行升级。** 三件事必须分清：

| 类别 | 例子 | 谁做 |
|---|---|---|
| **A 例行维护** | 认知投影刷新、`STATUS.md` 重渲染、索引与不改变科学事实的同步 | Agent **自动做完**，不询问用户 |
| **B 科学更新** | outcome / claim / assurance / failure / decision | 必须过既有门禁（R9.O / R10 / R11 / R7） |
| **C 特权动作** | 改主锚点、破预算、改冻结协议、未授权大规模训练、推送 / 合并 / 发布 | **只由用户授权** |

**只读、建议、执行三档必须明说。** 用户只问「现在怎么样」时**不得**执行实验、**不得**写
canonical state。无法确定时按只读处理并提问。**资源与预算边界归用户**：不得自行授权 GPU、
扩大实验规模、放宽预算或延长冻结期。见
[references/operational-autonomy-policy.md](references/operational-autonomy-policy.md)。

### 1.3 存储、状态与项目根

- 唯一运行时根是 `<project>/.research-lifecycle-protocol/`。正常运行时**绝不写入**旧根。
- 旧根的**只读**动作仍允许：`state_check`、`legacy_handoff detect`、迁移 `inspect` / `plan`。
- 迁移期间的写入入口受**协作式维护锁**保护。该锁**只**覆盖 RLP 自己的写入入口，不覆盖
  DSH Research Mesh worker、训练进程或第三方脚本。因此 `migrate --apply` 强制要求操作者
  确认外部写入者静止。
- canonical state **就地覆盖**，不按阶段切分快照。
- 历史记录（state 历史、冻结预注册、evidence、receipts、TAG 事件链、决策轨迹）**永不重写**，
  旧记录里的绝对路径**故意保留**。

### 1.4 领域协议：显式激活，不因按需加载而绕过

Domain Profile 是**可选**规则扩展，默认不激活。在 `<route|project>/domain/<profile>.json`
显式声明，未声明就是 RLP Core。

**按需加载不等于可以绕过。** 领域门禁由脚本在写入路径上强制
（`domain_guard.py` / `domain_profile.py` / `domain_mms.py`）。模型**不必**背诵实现，
但**必须**知道门禁存在，并且知道「没读规则」不是「不受规则约束」。

**MRI 的 GT-free 边界是硬约束。** 自监督训练不得使用 GT。合法的独立 `Ω_val` 可用于
GT-free 模型选择。SSL loss 改善**不等于**重建质量提高，全局 NMSE 改善**不等于**微血管恢复。
激活判定与按任务切片见 §2.2。规则本体见
[domain-profiles/mri-reconstruction/PROFILE.md](domain-profiles/mri-reconstruction/PROFILE.md)。

### 1.5 执行门禁与证据门禁

**实验必须过它自己的门。** 正式实验走 `scripts/experiment_execute.py` 的 `issue` / `run`，
要求当前 scheduler 与内容绑定的 manifest。正式 X3/X4 需要 PEIG `PASS`；前瞻性有界探索
（X1/X2/pilot）用 `PILOT_ONLY`；`HOLD` 只影响被点名的 claim 验证。

**冻结的东西不能自己改。** 预注册协议、判据、停止条件、实验预算、Anchor：Agent 不得自行
修改，只能提请用户并留变更记录。

**模型侧上下文精简与工具侧门禁执行是分离的。** 即使没读完整 R8 policy，执行器仍会跑 R8 的
机械检查。**让模型知道有哪些门禁，而不是让模型背诵每条实现。** 门禁清单见 §6。

### 1.6 修复门：critical flaw ⇒ Research State 必须改变

**检测到 critical flaw 时 State 必须改变。** 只写一份诊断报告不算闭环。

- 处置五值：`REPAIR_CLAIM` | `RUN_TEST` | `FIX_IMPLEMENTATION` | `NARROW_SCOPE` | `KILL_BRANCH`；
- 关闭两值：`RESOLVED` | `ACCEPTED_LIMITATION`；
- 落盘：`flaw` / `disposition` / `state_delta` / `closure`；`KILL_BRANCH` 归档该分支，不销毁路线。

诊断必须有界：同一 blocking condition 连续三轮不变才算 `blocked`。反复改写解释、换 ID、
加文档、加实验卡都**不是**进展。见
[references/phase-r7-r10-r13-assurance-repair-review.md](references/phase-r7-r10-r13-assurance-repair-review.md)。

### 1.7 认识论权限边界：R14 能杀研究分支，不能杀真理主张

**硬 invariant。** 三个判断互不相同，不得混用：

| 判断 | 回答什么 | 谁能给 |
|---|---|---|
| **路线终止** | 这条路还值不值得走 | R14（`continue` / `pivot` / `archive` / `submit`） |
| **claim 状态** | 现有证据支持到什么程度 | 只能经 R10（唯一例外：R8 单向升级） |
| **科学真伪** | 命题在世界里成立吗 | **没有任何 R 阶段能判定** |

**R14 不得把「路线终止」等同于「科学真理被否定」。** `archive` 的含义是「本轮不再投入」，
不是「命题为假」。叙事被淘汰不等于科学被证伪，最优叙事被选中也不等于科学被证实。

**叙事是 state 的视图，不创造科学真理。** `已证实` / `已证伪` **不得用来**描述修辞方案
或路线取舍。见 [references/evidence-policy.md](references/evidence-policy.md)。

---

## 2. 载入映射与参考索引

### 2.1 三级加载

| 级 | 内容 | 何时 |
|---|---|---|
| **L0** | 本文件 | **每次激活 RLP** |
| **L1** | `shared-contract.md` + 选中的**一个** Preset + 本任务必需 references + Research Context Packet | 每次任务动作 |
| **L2** | 完整 policy、数学推导、专项审查、异常处理、Replay 审计 | 只在需要细节时 |

**顺序：** `L0 → Selected Preset → State Context → Conditional Domain → Deep Reference`。
每条加载都要能回答：为什么需要 / 从哪里 / 是否过期 / 为什么没加载其他。机器可读计划由
`scripts/context_planner.py` 产出（`required` / `conditional` / `deep_references` /
`not_loaded` / `blocked_missing`）。**逐任务的必需集合以 `preset-registry.json` 的 `context`
块为唯一权威，不在本文件重复。** 完整资源目录见
[references/reference-index.md](references/reference-index.md)。

**禁止：** 每次加载全部 16 个 Preset；每次加载完整 references 语料；把 `scripts/*.py`
当协议全文注入；为识别阶段而读所有阶段说明；因项目属于 MRI 就一次加载全部 MRI 文档。

> **`loaded` ≠ `referenced`。** 返回一个路径列表**不等于**相应规则已进入模型上下文。
> `loaded` 只记**实际读取并返回**的内容，`referenced` 只记引用。不得用路径清单冒充已加载。

### 2.2 领域切片与条件加载

**先判激活，再只取需要的切片。** 读 `<route|project>/domain/*.json`：没有声明 ⇒ 未激活，
不加载任何领域文档；有声明 ⇒ 只加载 `PROFILE.md` 与**当前任务用得到的那一份**子协议。

MRI 子协议按任务取**一份**：自监督训练 / 模型选择 → `ssl-contract` + `acquisition-contract`；
评价与阈值冻结 → `evaluation-policy`；归因与物理限制 → `attribution-guard`（TAG）；
方法创新 → `mechanism-search`（MMS）；特定变体再加 `variants/` 对应的一份。
路径与职责见 [references/reference-index.md](references/reference-index.md)。

**六种条件加载：** 机制归因 → TAG；要提方法候选 → MMS + [skill-rsi-policy](references/skill-rsi-policy.md)；
有结果要判资格 → [evidence-outcome-analysis](references/evidence-outcome-analysis.md)；
实验失败要恢复 → [presets/experiment-failure-recovery](presets/experiment-failure-recovery.md)；
诊断不再改变决定 → [presets/stagnation-breaker](presets/stagnation-breaker.md) + I2M；
要改探索策略 → [presets/strategy-evolution](presets/strategy-evolution.md)。

**按章节加载，不整份加载。** 大文档有稳定章节索引 `references/section-index.json`
（`python3 scripts/section_index.py find <doc> <query>`）。判断引用完整性只读
`research-state-policy` 的对应章节，判断路线准入只读 `project-layout` 的准入规则，
判断结构等价只读对应检查规则。**不要因为文件长就整份读。**

### 2.3 资源目录

完整资源目录（每个 reference / template / script 的位置与职责）见
[references/reference-index.md](references/reference-index.md)。**按域查一次**，不要每次加载。

找「这件事的权威文件在哪」用它；判断某条规则归属用它；新增或改名资源后必须同步它，
并重建 `references/section-index.json`。

---

## 3. 子代理派遣

**RLP 只做编排。** 角色设定、评分维度、审查视角沿用统一角色库
[references/roles.md](references/roles.md)，不在各 R 阶段内重新定义。

**派遣方式：** 环境具备 Team 能力时**先询问用户**。用户显式要求 Team 而环境不具备时
**显式告知回退**，不得静默降级，不得假装使用了 Team。

### 3.1 最小任务契约

**子 Agent 不需要主 Agent 的全部规则与历史。** 每个子 Agent 只接收自己那份任务契约：任务、
输入证据切片、评价规则、输出 Schema、权限边界。按角色（`literature` / `theory` /
`experiment` / `assurance` / `discovery`）切片，由 `scripts/subagent_context.py` 产出。
见 [references/subagent-context.md](references/subagent-context.md)。

**三条不可越过的边界：**

1. **子 Agent 不得绕过已有状态写入权限。** 上下文精简不得扩张权限。
2. **Context Packet 不是第二个授权来源。** 它描述授权，不产生授权。
3. **子 Agent 自评不得升级为科学证据。** 主 Agent 汇总，但汇总不是认证。

#### 3.1.0 DSH Research Mesh worktree 模式

<!-- 跨组件契约 dsh-research-mesh/mesh-collaboration@1：本小节与 project-layout §0.0.1、项目根 AGENTS.md §11、dsh-research-mesh 的 MESH-OPERATING-RULES.md 必须一致。 -->

派遣前检查冲突：canonical checkout 只有一个；Mesh worktree 是**临时检出，不是 route 的
第二份副本**，它**只读**项目根的 canonical `research-state.json`，不得另造同名 state。
建组前提交或 stash canonical 改动，worktree 从 HEAD 创建。单开会话与 Mesh 组不得并发占用
同一 GPU 或同一实验，以 GPU lease 与 scheduler 为准。未经用户明确同意，不创建 Mesh group、
不跑真实实验、不改 canonical state。

---

## 4. R0—R14 能力索引

**R 编号是能力，不是流水线。** 下一步由 [scheduler-policy](references/scheduler-policy.md) 的
`next_action_policy` 决定。逐阶段读写契约的唯一权威是
[research-state-policy](references/research-state-policy.md) §5，本节**不复制**它。

| Phase | 名称 | 能做什么 |
|---|---|---|
| **R0** | research-contract | 定目标、约束、资源与 provisional anchor。**不产 claim** |
| **R1** | research-state | **常驻**：维护八类一等对象。开工前读，收工前写回 |
| **R2** | field-mapping | field grammar + occupancy map + 检索纪律 |
| **R3** | dual-discovery | 隔离 Exploration Agents 产候选（含 seed claim）。执行者只编排；`P3` 只产 typed intermediate，不产 candidate |
| **R4** | isolated-populations | structural signature + QD archive，保多样性 |
| **R5** | co-evolving-retrieval | idea → 新 query → 新文献。**常驻服务** |
| **R6** | evolution | mutation / crossover / simplification / 占新 niche |
| **R7** | adversarial-assurance | 六攻击面 + 硬门禁 G1—G5。**不改 claim 状态** |
| **R8** | evidence-contract | 每张 central claim 一份证据契约 + 冻结预注册。**只做单向升级** |
| **R9** | experiment-tree | X1—X6 + EIG 选择 + provenance。**过执行门禁** |
| **R9.O** | outcome-analysis | 区分有效负证据 / mixed / 未决 / 无效执行 |
| **R10** | metacognitive-repair | **critical flaw ⇒ state 必须改变**。唯一能降级或否决 claim 的阶段 |
| **R11** | state-update | result → claim → uncertainty → EIG → next，五步缺一不可 |
| **R12** | narrative | state 的视图：六槽位 + preset + 六维。**不新增证据、不抬高状态** |
| **R13** | artifact-review | 审 artifact（code / logs / failed runs）。Integrity 是 Gate |
| **R14** | decision | `continue` / `pivot` / `archive` / `submit`。**不判科学真伪** |

**Discovery 只管扩大与保多样性，Assurance 只管会不会被推翻。** 两者都**不得**直接改
`claims[].status`。分工细则见 [scheduler-policy](references/scheduler-policy.md)。

---

## 5. 状态回写

1. **R1 是唯一状态载体。** 路径 `<project>/.research-lifecycle-protocol/routes/<R>/research-state.json`，
   就地覆盖。EIG 对照写同目录 `scheduler.json`。
2. **每阶段收尾必须跑** `python3 scripts/state_check.py --check <state.json>`，
   **硬违规须为 0**。退出码 3 = 硬违规，4 = 文件缺失或 JSON 非法。
3. **汇报前先做 operational reconciliation。** A 类投影先刷新，B 类先过门禁。维护失败保留
   `hold_reason`，不得用报告掩盖阻塞。

**R12 的落盘映射：** 被淘汰的叙事方向 → `STATUS.md` 的 Most important negative findings；
最佳叙事 → Strongest supported findings 的叙事表述；门禁 `fail` 或六维中位 <3 →
Critical uncertainties（**不是**根 `INDEX.md` 的 Warnings）。

**默认汇报形态五段：** `Problem → Insight → Method → Evidence → Next Decision`，先结论后细节。
PID、GPU UUID、长路径、内部版本号默认隐藏。R12 是论文叙事机制，日常科研汇报**不得**改造成
R12 流程。汇报顺序与操作分类见
[references/scientific-communication-policy.md](references/scientific-communication-policy.md)
与 [scripts/operational_reconcile.py](scripts/operational_reconcile.py)（协调脚本）。

---

## 6. 输出前自检（最小集）

完整清单见 [references/execution-checklist.md](references/execution-checklist.md)。至少过这十条。

- [ ] 入口与阶段明确，与该阶段输入契约一致。
- [ ] 只读请求没被升级成执行。没执行未授权实验。
- [ ] 锚点已确认并落盘。**没有自行换方向、换主锚点、开新路线。**
- [ ] 每条 state 条目都能指回真实来源。没有为「看起来完整」而编造。
- [ ] 工程错误没写成科学否证，进程终止没写成科学完成。
- [ ] claim 状态变更走了 R10（R8 单向升级除外）。
- [ ] 结论没超出证据范围。措辞符合 [evidence-policy](references/evidence-policy.md)。
- [ ] 跑过真正的门禁：`state_check.py` 硬违规 0。没因「没读规则」跳过门禁。
- [ ] A 类维护已实际做完，没向用户询问是否维护。
- [ ] 负结果、阻塞与 `hold_reason` 仍可见，没被简洁性掩盖。
- [ ] 只有 R12 / R13 的 venue calibration 与投稿评估**引用具体顶会标准**；
      R3—R6 用顶会口味判断候选属于违规。

**必须执行的门禁（模型只需知道存在，不必背诵实现）：**
`state_check.py`（S1—S7 + V1—V24）、`experiment_execute.py`（PEIG/AALG）、
`evidence_outcome.py`、`prediction_compare.py`、`domain_guard.py` / `domain_profile.py` /
`domain_mms.py`（DP/TG/MM）、`structural_equivalence_check.py`（EQ/NN）、
`preset_router.py`、`rlp_paths.py`、`cognition.py`、`ste_lint_zh.py`。

---

## 7. 设计依据

完整论证见 [references/design-rationale.md](references/design-rationale.md)。三条最常被误读的：

- **为什么用 R 阶段而非流水线？** Discovery 与 Assurance 必须并行且互相牵制。
- **为什么上下文分三级？** 协议完整与上下文轻量能同时成立，前提是**按需加载 + 机器门禁**。
  模型上下文是工作集，不是事实数据库。
- **为什么精简不改科研规则？** 减的是加载量，不是约束。一条规则若必须加载才能避免错误
  科研决策，就应该加载。

---

## 8. 规则变更自检（维护本 Skill 时用）

**改任何规则、命名、枚举、计数、路径时必读**，完整清单见
[references/development-selfcheck.md](references/development-selfcheck.md)。

**五类历史高频漏点：** ① 设计依据与「为什么」段；② 速查 / 汇总表（规则的复制品）；
③ 示例与模板；④ 语义字段与枚举（规则要求落盘的东西，schema 里有没有槽位）；
⑤ 跨层漂移（claim 层 / 叙事层 / 评审层必须同改）。

**唯一发布判据是 `python3 scripts/release_check.py` 的最后一行（`PASS` / `FAIL`）。**
逐条命令只用于诊断，不能替代它。改规则后必跑：

```bash
python3 scripts/release_check.py            # 唯一发布判据
python3 scripts/section_index.py check      # 章节索引与正文一致
python3 scripts/context_planner.py check    # 载入依赖声明合法
```

**内容丢失检查：** 按区间替换时必须确认被替换区间里没有别的标题。链接与引用检查**测不出**
这种丢失，因为引用处写的是字符串。用 `git diff -U0 -- SKILL.md | grep -E '^[-+]## '`。
