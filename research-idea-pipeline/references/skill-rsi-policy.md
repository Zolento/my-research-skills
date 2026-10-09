# Skill-Level Recursive Self-Improvement（Skill-RSI）

> **渐进加载：** 只有需要「从真实科研经验改进科研策略」时才读本文件。它不替代
> [scheduler-policy.md](scheduler-policy.md)、[discovery-replay.md](discovery-replay.md)、
> [cognitive-memory-policy.md](cognitive-memory-policy.md) 或
> [scientific-value-adaptive-discovery.md](scientific-value-adaptive-discovery.md)，
> 而是在它们的既有边界内补上策略记忆、反事实回放、策略晋升与源码冻结四件事。
>
> 本文件**不是**第 16 个阶段，**不是**第九类 canonical 对象，**不是**第二个 CIE。

## 0. 一句话

科研事实仍由既有科学证据机制裁决；只有**科研策略**可以在受控、可审计、可回滚的范围内演化。

```text
Research Experience → Policy Hypothesis → Replay Evaluation → Controlled Adaptation
        → New Research Experience
```

## 1. 硬边界（优先于本文件其余全部内容）

1. **不改 Harness**：不动基础模型、推理协议、原生 Agent 调度、平台工具接口与权限模型。
2. **不改科学架构**：R0—R14、八类 canonical 对象、Discovery/Assurance 双循环、四个语义入口、
   16 个 Preset、Scheduler 八级硬优先级、PEIG/AALG、Evidence Qualification、预注册全部不变。
3. **不新增 canonical 对象或字段**：新增数据全部落 route 控制平面（telemetry / 派生存储）。
4. **运行期不得自主改 Skill 源码**：`SKILL.md`、`references/`、`presets/`、`scripts/`、
   `templates/`、`schemas/`、`preset-registry.json`、`shared-contract.md`、
   校验器、评分规则、隐藏评价数据、权限定义、发布元数据都是**只读**对象。
5. **不得伪造结果**：历史没有执行过的行动分支只有 `NO_SUPPORT`，不能用模型预测代替真实实验。
6. **不得把系统自评当能力提升**：日志数量、文档数量、状态变化、自评分数都不构成 Delta。

## 2. 三层记忆必须分开

| 层 | 载体 | 回答的问题 | 不能做什么 |
|---|---|---|---|
| Scientific Memory | canonical `research-state.json` + `cognition/` 投影 | 世界的科学事实是什么 | 不得被策略经验覆盖 |
| Decision Experience | `<route>/decision-trajectory.jsonl` | 当时可见什么、选了什么、实际发生了什么 | 不是科学证据，不得写入 `evidence[]` |
| Policy Memory | `<route>/policy/` | 哪类问题结构下哪种策略更好 | 不得否证或支持任何科学主张 |

「某探索算子在三个项目里失败」是策略经验；「某机制被实验否证」是科学事实。前者不能推出后者。

## 3. Decision Trajectory（`scripts/decision_trajectory.py`）

路径：`<route>/decision-trajectory.jsonl`，append-only、哈希链、`head` 摘要、`flock` + `fsync`。
只记录**对后续科研行为有实际影响**的重要决策。

一条轨迹由四类记录组成（同一 `trajectory_id`）：

| 记录 | 关键字段 |
|---|---|
| `decision` | `context`（state_version / contract 引用 / 科学问题 / 活跃假设 / 关键不确定性 / 可见证据 / 停止规则 / `decided_at` / `state_digest` / `scheduler_digest`）、`decision`（候选集 / 前置条件 / 优先级 / EIG÷cost / 选择 / 策略版本 / 是否改变排序 / `dispatch_status`）、`prediction`（可空，决策时冻结） |
| `outcome` | `observed_at` / `at_state_version` / `result` / `evidence_refs` / 三类 Delta / `policy_effect_observed` / 成本 / 未解决问题 / `evidence_qualification` |
| `learning` | `learning_value` / `bias_hypothesis` / `applicability` / `counterexamples` / `needs_validation` |

机械规则：`DT0` 链完整性（含尾部）、`DT1` 结构、`DT2` 已记录决策不得被结果改写、
`DT3` 来源引用必须存在、`DT4` 过期状态与时间倒挂、`DT5` 事后补写预测、
`DT6` 结果泄漏进冻结上下文、`DT9` 未合格证据不得声称科学增量、`DT10` route 绑定。

命令：`open` / `outcome` / `learning` / `show` / `list` / `validate` / `--selftest`。

## 4. Counterfactual-Aware Replay（`scripts/research_replay.py`）

### 4.1 三类历史决策

| 证据等级 | 含义 | 允许的评价 |
|---|---|---|
| `OBSERVED` | 行动与其结果都被真实观测 | 可按实际结果评价 |
| `REPLAY_SUPPORTED` | 行动存在于历史已执行分支，在覆盖范围内 | 可在该范围内比较不同策略，决策时点信息必须一致 |
| `NO_SUPPORT` | 候选策略选择了历史未执行的行动 | **不得评价、不得晋升**；需要真实验证只能进入受控试验 |

### 4.2 防泄漏（在 `RP2` 之外）

- `RP6` 时间边界：可见文献不得晚于决策时间。
- `RP7` 文件系统：case 目录下可读文件、越界符号链接、项目认知投影都不得含隐藏答案。
- `RP8` 认知记忆：召回投影不得携带后续观测。
- 无法建立隔离时，`require_isolation` 直接拒绝该 case 的独立评价资格。

### 4.3 消融

原有四臂（`baseline` / `memory_only` / `memory_prediction` / `full_cie`）**语义冻结**；
Skill-RSI 追加 `rsi_full` / `rsi_shadow` / `rsi_without_trajectory` / `rsi_without_replay` /
`rsi_without_scope` / `rsi_without_promotion`，用于逐个隔离机制而不是堆叠能力。

命令：`ablate --rsi`、`support --trajectory`、`coverage --trajectory`、`validate --dir`。

## 5. Policy Candidate（`scripts/policy_evolution.py`）

### 5.1 允许调整的策略面

- 探索算子的相对偏好（`exploration_operator_preference`）
- 已定义探索菜单的选择（`menu_choice`）
- 同一合法优先级层内的动作排序（`same_tier_preference` / `same_tier_order`）
- 给定问题结构下的策略适用性（`applicability`）
- 候选探索顺序（`probe_order`）
- 保持探索下限的局部资源分配建议（`local_resource_allocation`，必须 `keep_exploration_floor: true`）

不得改变：Scheduler 八级硬优先级、`EIG ÷ cost` 固定判定、执行门禁、Evidence Qualification、
AALG 诊断预算、Research Contract、主研究锚点、GPU 授权、已冻结实验计划、核心评价标准。

### 5.2 候选结构

`policy_id` / `policy_schema_version` / `parent_policy_id` / `status` / `scope` /
`applicable_conditions` / `strategy_changes` / `supporting_trajectory_ids` / `counterexamples` /
`expected_effect` / `revalidation_conditions` / `evaluation_refs` / `rollback_target`。

机械规则：`PE1` 结构、`PE2` 越权目标、`PE3` 作用域必填且结构化、`PE4` 依据必须来自有真实
结果的轨迹、`PE5` 复杂度与 fixture 过拟合、`PE6` 可执行内容、`PE7` 自评字段、`PE8` 泛化需反例、
`PE9` 同一机制失败上限（换 `policy_id` 无效）、`PE10` 非法状态转移、`PE11` 晋升证据不足、
`PE12` 评价规则被改动、`PE13` 回滚目标非法、`PE14` 局部成功不得升级为全局策略。

策略数据不得包含可执行代码、Shell 命令、动态导入路径。自由文本只用于解释，永远不作为指令执行。

### 5.3 生命周期

```text
PROPOSED → SHADOW → REPLAY_EVALUATED → BOUNDED_TRIAL → VALIDATED → ACTIVE
失败：REJECTED / HOLD / ROLLED_BACK        取代：SUPERSEDED
```

- 这些状态只存在于策略控制记录，**不是**科学状态枚举。
- 评价规则在候选生成前冻结（`policy/evaluation-rules.json`），候选不能修改评价器、隐藏测试、
  评分定义或自己的晋升阈值。
- 性能差异落在容差内或区间重叠时报告**不可区分**，不强行选胜者。
- 回滚恢复上一有效策略、保留完整失败轨迹、不改既有实验结果、不重置 AALG 或其他预算、
  不动 canonical Research State。

### 5.4 真实消费者

晋升后的策略只通过**现有 Strategy Decision Adapter**生效：

```text
policy/ 中 ACTIVE 候选 → advice_from_active_policy() → strategy_memory.strategy_decision()
    → 同一 EIG÷cost 层内重排（只重排已通过硬门禁的动作）→ research-loop 的实际派遣
```

`research-loop` 优先采用该选择；选择无法实施时如实报告 `reason_if_not`，不制造差异。
策略是否被实际派遣记录在决策轨迹与 `scheduler.strategy_decisions[]` 中。

## 6. 三类 Delta

| Delta | 含义 | 不算 Delta 的东西 |
|---|---|---|
| `scientific_delta` | 新的合格科学证据、有效认识或明确科学边界 | 日志、文档、投影刷新 |
| `decision_delta` | 真正改变了候选、实验、方法、资源或终止决定 | 主观自评提高 |
| `policy_delta` | 有来源、有作用域、带评价等级的策略变化 | 仅「提出候选策略」 |

`policy_delta` 必须携带 `level`（L1/L2/L3）；三者均可为 `none`。

## 7. 等级不得混淆

- **L1 实现有效性**：格式、权限、代码测试与不变量通过。
- **L2 运行有效性**：真实 CLI / Scheduler / Replay 能消费并产生可观测的合法行为变化。
- **L3 科研改进**：在独立、未见过的真实科研案例上取得可重复且实际有价值的改善。

L2 不能推出 L3。稳定策略的 L3 主张必须经过独立真实评价；没有该条件时明确标记 L3 未验证。

## 8. 迁移条件（`scripts/policy_transfer.py`）

迁移判断只看**声明结构**：问题结构相似性、适用假设、可用工具与资源、科学验证协议、
已知反例、历史成功的证据等级。领域关键词相似不足以判定适用。
过期经验（绑定过旧 state_version 或引用已被失效的对象）失效；被否证的机制不得再次提出。
记忆压缩不得丢失证据与停止规则。

## 9. Source Freeze 与写入白名单（`scripts/source_freeze.py`）

- 运行开始记录受保护文件的规范化路径与内容摘要；运行前后各核验一次。
- 检测覆盖符号链接、路径别名与安装副本；越界符号链接一律拒绝。
- 只读对象：Skill 源码、Preset 协议正文、系统 Prompt、科学验证器、评分规则、测试 fixture、
  隐藏评价数据、权限定义、发布元数据。
- 可写对象：已授权的策略记忆、策略候选状态、研究项目执行账本、决策轨迹、必要运行遥测、
  以及**经既有科学阶段**合法更新的 Research State。
- 写入许可按规范化后的真实路径判定，不按文件名；`../` 与符号链接逃逸一律拒绝。
- 检测到源码被修改：立即 `HOLD`、写审计事件、停止继续应用策略；**不自动修订源码**。

> **残余风险（必须如实说明）：** 本机制是**可检查的检测与策略边界**，不是操作系统级隔离。
> 具有任意文件写权限的执行者仍可绕过它。需要真正强制时，应使用只读安装目录、
> 只读挂载、独立运行用户与安装副本摘要核验。**Prompt 层面的禁令不构成安全边界。**

## 10. 自检

- [ ] 没有新增第九类 canonical 对象或字段。
- [ ] 策略只通过 `strategy_decision()` 生效，未替换硬优先级与 `EIG ÷ cost`。
- [ ] 未执行分支返回 `NO_SUPPORT`，没有被计入任何晋升证据。
- [ ] `policy_delta` 带评价等级，未把「提出候选」写成「策略已提升」。
- [ ] 运行期没有修改 Skill 源码；生产写入全部落在白名单路径内。
- [ ] 回滚不重置预算、不改实验结果、不动 canonical state。
- [ ] 合成 fixture 与单元测试未被当作 L3 证据。
