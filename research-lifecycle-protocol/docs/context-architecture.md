# Context Architecture（v2.2.0 架构变更报告）

本文件回答四件事：原来的上下文架构是什么、新的三级架构是什么、哪些内容常驻、哪些按需加载、
以及**为什么不需要第二套 Router 或第二套 State**。

配套文件：[context-baseline.md](context-baseline.md)（改前测量）、
[context-benchmark.md](context-benchmark.md)（前后对比）、
[rule-relocation-matrix.md](rule-relocation-matrix.md)（逐条迁移）。

---

## 1. 原来的架构

一份 156 KB 的 `SKILL.md` **每次激活都整体注入**，它同时承担十一种职责：

Skill 入口、科研哲学、权限规则、Router 说明、R0—R14 全部阶段摘要、认知记忆细则、
子 Agent 派遣、文献检索政策、写作标准、项目目录规范、开发维护清单。

后果有三个，都是可测量的：

1. **常驻成本压倒按需成本。** 12 个场景里 `SKILL.md` 占 55%—89% 的上下文
   （基线 §3.1）。真正的科研协议（选中的 Preset、当前证据）反而是小头。
2. **规则在真实 Harness 里并不完整送达。** 一次实测注入 154,495 bytes，模型可见
   84,026 bytes，省略率 45.6%（基线 §2）。规则「都在 SKILL.md 里」这个说法在 156 KB
   规模上不成立。
3. **没有「该读什么」的机器表示。** 加载顺序写在散文里，Agent 只能按自然语言推断依赖。
   于是要么全读，要么漏读，二者都不可审计。

---

## 2. 新的三级架构

| 级 | 内容 | 何时加载 | 规模 |
|---|---|---|---|
| **L0** | `SKILL.md`（27.5 KB） | 每次激活 | 固定 |
| **L1** | `shared-contract.md` + 选中的**一个** Preset + 任务必需的 references + Research Context Packet | 每次任务动作 | 按任务，实测平均 21.6 KB |
| **L2** | 完整 policy、数学推导、专项审查、异常处理、Replay 审计、维护自检 | 只在需要细节时 | 按需 |

**解析链：** `L0 → Selected Preset → State Context → Conditional Domain → Deep Reference`。

### 2.1 常驻（L0）里到底有什么

只回答四个问题：

1. **进哪道门** —— 四个语义入口、四层解析顺序、否定即停、锚点门槛、存储判定。
2. **哪些约束不能破** —— 七条最小全局不变量（含 13 条被单独盯住的硬约束）。
3. **这一轮加载什么** —— 三级加载原则、领域激活判定、条件加载的六种情形、章节级定位方法。
4. **门禁在哪里** —— 必须执行的门禁清单（模型只需知道存在，不必背实现）。

### 2.2 按需（L1/L2）里有什么

原 `SKILL.md` 的细节被**下沉到已有权威或新建的单一职责文件**，不是复制：

| 内容 | 落到哪里 |
|---|---|
| R0—R14 逐阶段读写契约 | `research-state-policy` §5（唯一权威） |
| 锚点体系 | `references/anchor-policy.md` |
| I2M | `references/insight-to-method-policy.md` |
| 完整资源目录 | `references/reference-index.md` |
| 完整输出前自检 | `references/execution-checklist.md` |
| 设计依据 | `references/design-rationale.md` |
| 维护自检 | `references/development-selfcheck.md` |
| 子 Agent 角色契约 | `references/subagent-context.md` |

### 2.3 由工具侧硬门禁执行的部分

这是整套设计的关键分工：**上下文变轻不等于约束变松。**

| 约束 | 谁执行 | 模型需要读到什么 |
|---|---|---|
| 八类对象与引用完整性（S1—S7 / V1—V24） | `state_check.py` | 只需知道它会跑，且硬违规须为 0 |
| 执行可识别性与 PEIG/AALG | `experiment_execute.py` | 只需知道正式 X3/X4 需要 PEIG PASS |
| 证据资格 | `evidence_outcome.py` | 只需知道**唯一**资格入口是它 |
| 领域边界（DP / TG / MM） | `domain_guard.py` / `domain_profile.py` / `domain_mms.py` | 只需知道「没读规则 ≠ 不受约束」 |
| 结构等价与近邻（EQ / NN） | `structural_equivalence_check.py` | 只需知道它是 Gate |
| 入口与触发 | `preset_router.py` | 四层顺序与否定即停 |
| 存储与维护锁 | `rlp_paths.py` | 只需知道 `MIGRATION_REQUIRED` 是只读 |
| 认知投影一致性 | `cognition.py` | 只需知道投影是派生视图 |
| 受控中文 | `ste_lint_zh.py` | 落盘前跑 |

`context_planner` 的 `gates_remaining` 字段把这张表随计划一起交给调用方：
**即使没加载某条 policy，模型也知道那道门还在。**

---

## 3. 加载决策是机器可读的

### 3.1 依赖声明在注册表里

`preset-registry.json` 的每个 Preset 新增 `context` 块：

```json
"research-loop": {
  "required": ["presets/research-loop.md", "shared-contract.md"],
  "conditional": [
    {"when": "evidence_qualification",
     "load": ["references/evidence-outcome-analysis.md", "references/evidence-policy.md"]},
    {"when": "method_synthesis", "load": ["references/insight-to-method-policy.md"]}
  ],
  "deep_references": ["references/scheduler-policy.md#next_action_policy"],
  "domain_extensions": ["mri-reconstruction"],
  "forbidden": ["presets/*.md（除本预设）", "scripts/*.py 源码全文", "references/ 全语料"]
}
```

无预设的入口（`start-project`）走 `entry_context`。

**为什么把加载表放进注册表而不是 L0 散文：** 一份规则只能有一个权威。
散文里的加载表会与注册表漂移，而注册表可以被 `context_planner check` 机械校验。

### 3.2 七种加载状态

| 状态 | 含义 |
|---|---|
| `loaded` | 已**实际读取并返回正文** |
| `required` | 当前任务必须读取 |
| `conditional` | 满足 `when` 才需要（`active` 标明这次是否满足） |
| `referenced` | 只给路径，**没有**读正文 |
| `available` | 可选深层材料，允许不读 |
| `not_loaded` | 本次明确没有读取 |
| `blocked_missing` | 必需上下文缺失 ⇒ 不得继续 |

这一层修的是一个具体缺陷：旧 `load_preset_context()` 把 `scripts/*.py` 的路径名放在
`loaded_references` 里，读起来像「这些规则已加载」。现在路径与正文分开，
`execute()` 之前 `loaded` 恒为空。

### 3.3 章节级定位

`references/section-index.json`（66 份文档 / 977 个章节）由
`scripts/section_index.py build` 从正文重新生成：

- 章节 id 由**标题文本** slug 化，**不用行号** —— 插入一段正文不会让索引失效；
- 摘要是**从正文抽取**的，不存在「手写摘要过时」；
- `check` 重新生成并逐字节比对，正文改了索引没重建即判红。

依赖声明可以写成 `"references/research-state-policy.md#5. 写入时机"`。
`context_planner` 只取命中章节；**查询未命中时阻断，不退化整文件加载**。

这是把 50 KB 的 `research-state-policy` 变成可精确取用的前提。

### 3.4 预算

四类预算分开，**不合成一个长度**：

| 预算 | 默认 | 装什么 |
|---|---|---|
| `protocol_chars` | 60,000 | L0 + 契约 + 一个预设 + 必需协议 |
| `research_chars` | 12,000 | Research Context Packet |
| `evidence_chars` | 20,000 | 本轮引用的证据切片 |
| `tool_chars` | 8,000 | 单次工具返回正文 |

超预算**不静默截断**。永不截断的类别写死在代码里：安全约束、权限边界、冻结条件、
会改变本轮决定的关键反例。未覆盖项进 `uncovered`，并且当未覆盖项属于硬要求时
`can_proceed` 变假 —— 宁可停下，也不给没有依据的科学判断。

---

## 4. Research Context Packet

一次科研决策需要的是十三项，不是全部历史：项目与路线、状态版本与 digest、主锚点、
授权与关键约束、活跃机制及其证据资格、最重要的未解决问题、竞争解释、
已失败且禁止等价重试的路线、正在运行或待处理的实验、上一轮实际决策、当前合法动作、
必须审查的证据引用、必要的领域边界。

`scripts/context_packet.py` 从 canonical state **派生**这个包，并绑定五项：
`state_version`、canonical digest、相关 evidence digest、Skill 版本、Domain 配置摘要。
`verify()` 检测失效，并明确写出失效时**禁止**三件事：把旧摘要当新事实、清空 Research State、
重新 Bootstrap。

它复用 `cognition.py` 的 `CanonicalView` / `failure_constraints` / `digest_of`，
**不新建第二套研究记忆**，也**不新增第九类对象**。

---

## 5. 子 Agent：按角色裁剪，权限不扩张

`scripts/subagent_context.py` 给五个角色（`literature` / `theory` / `experiment` /
`assurance` / `discovery`）各一份最小任务契约，并机械校验五条不变量：

1. 角色的能力集合必须是父级权限的**子集**；
2. `write_canonical` 只属于主 Agent，或被用户显式授权的角色；
3. 任何角色都不得获得 `modify_anchor`；
4. `execute_experiment` 为真时必须同时要求 manifest 与批准；
5. `never` 列表必须非空 —— 「什么都给它」等于没有裁剪。

**三条设计判断：**

- 子 Agent 拿到的是**任务**，不是主 Agent 的对话历史；
- 证据以**切片引用**形式传入，切片必须带原始 id，子 Agent 不得重写；
- 子 Agent 的 `supported` / `novel` 判断不进入 canonical `status`，只能作为 R7 / R10 的输入。

实测子 Agent 上下文从 123,449 字符降到 16,881 字符（−86%），且没有任何角色获得写权限。

---

## 6. 为什么不需要第二套 Router 和 State

这是本轮最容易被误解的一点，所以写清楚边界。

| 已有组件 | 它已经决定什么 | 本轮加了什么 | 有没有再造一个 |
|---|---|---|---|
| `preset_router.py` | 入口解析、预设选择、否定守卫、触发与冷却 | **没有加**。`context_planner` 消费它的 `entry` / `preset_id` / `execution_scope` | 没有 |
| `cognition.py` | 认知投影、Context Brief、hot/warm/cold、失效过滤 | `context_packet` **调用**它，不复制 | 没有 |
| `research-state.json` | 唯一科学事实源 | 没有任何新字段；Packet 是派生视图 | 没有 |
| `scheduler.json` | 下一步动作与 EIG telemetry | 没有改 | 没有 |
| `research-state-policy` §5 | 逐阶段读写契约 | 成为**唯一**权威（原先 SKILL 也有一份） | 没有 |

**为什么 Context Planner 不并进 Router：** Router 回答「用户想干什么」，
Planner 回答「因此该读什么」。两者的输入、输出、失败模式都不同：Router 的失败是
「路由错」，Planner 的失败是「上下文不全」。合在一起会让「路由正确但上下文不全」这种
情况没有独立的表达方式，而那恰恰是最危险的一种失败。

**为什么 Packet 不是第二套 State：** 它不可写、可重建、删除后可从 canonical state 重新生成，
且 `verify()` 会因为 state 变化而判定它失效。它没有自己的持久化位置。

---

## 7. 失败模式与处置

| 失败 | 检测 | 处置 |
|---|---|---|
| 必需上下文缺失 | `execute()` 的 `blocked_missing` | `can_proceed=false`，不继续 |
| 章节查询未命中 | 同上（`section query 未命中`） | 阻断，**不**退化为整文件 |
| 存储需要迁移 | `rlp_paths.resolve` + `blockers` | 只读审计，执行入口返回 `MIGRATION_REQUIRED` |
| 计划超预算 | `budget.over_budget` + `uncovered` | 列出未覆盖项；硬要求未覆盖则阻断 |
| 子 Agent 权限越界 | `subagent_context.build/check` | 返回 `FAIL`，不生成上下文 |
| Packet 过期 | `context_packet.verify` | 重新 build，禁止清空 state 或重新 Bootstrap |
| L0 重新膨胀 | `release_check` 的 `L0_BUDGET_BYTES` | 发布闸门 FAIL |
| 硬约束被删 | 13 个标记串 | 发布闸门 FAIL |

---

## 8. 这轮没有做的事

1. **没有验证 Prompt Cache。** `plan_digest` 只用于检测计划变化，不声称缓存命中。
2. **没有真实 tokenizer 与 Harness 请求记录。** 所有 token 数字是估算。
3. **没有 L3（真实科研 A/B）。** 行为回归与 Replay 只支持 L1/L2 结论。
4. **没有改科研规则。** 阶段数、对象类、ID、Preset 身份、门禁语义全部不变。
5. **没有修已知的规范冲突。** 攻击面数量、读写契约内部矛盾、约 20 处旧运行时根路径
   都登记在 [rule-relocation-matrix.md](rule-relocation-matrix.md) §5，留待单独一轮。
