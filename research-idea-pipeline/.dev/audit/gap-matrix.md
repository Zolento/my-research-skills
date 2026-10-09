# Phase 1 — 架构审计与差距矩阵（Skill-RSI）

> branch-local 开发文档（根 AGENTS.md §5/§13）。基于 `origin/main` @ `ea0214e` 的实际源码，
> 不依据历史聊天或旧文档。行号均为基线提交处行号。

## 0. 审计方法

- 四路独立只读审计写入 `.dev/audit/A-strategy-memory.md`、`B-replay.md`、`C-cognition.md`、
  `D-control-plane.md`。
- 基线测试 `.dev/baseline/`：1436 tests OK(skipped=3)、`state_check --selftest` OK、
  `release_check.py` PASS（17 步）。

## 1. 审计十问（结论）

### Q1 现有 Strategy Evolution 实际能改什么？

改的是**策略记忆**，不是科学事实：

- 落盘 `<route>/cognition/model-revisions.jsonl` 中 `kind="strategy_update"` 的追加记录
  （`strategy_memory.py`；payload 只允许 `note/priors/operator/action/evidence/observations`）。
- 经 `strategy_updates()` 生成的更新，再由 `preset_router._append_strategy_revisions()` 幂等追加。
- 校验命名空间是 `SV1/SV3/SV5/SV6/SV8`（`strategy_memory.validate_strategy_revisions()`），
  与 cognition 的 `CM*` 分开。
- **不能**改锚点/契约（SV3）、不能自创算子（SV5）、不能写聚合分（SV1）、必须引用 canonical 对象（SV8）。

### Q2 Strategy Decision Adapter 如何消费策略记忆？

`strategy_memory.strategy_decision(state, index, scheduler, revisions) -> Dict`（`strategy_memory.py:1016`）：

```
advice = recommend_strategy(...)            # 菜单/算子/island/shift
legal, blocked, verdict = _legal_actions(...)  # → scheduler_verdict() → execution_gate.scheduler_check()
without      = _order_actions(state, legal, None)      # with-memory vs without-memory
with_memory  = _order_actions(state, legal, advice)
```

`_order_actions()` 先按 `EIG ÷ cost` 分层，**只在最优层内**按 `aligned` 重排，其余保持声明顺序。
结果写 `<route>/scheduler.json` 的 `strategy_decisions[]`（`record_strategy_decision():1091`，
`DECISION_LOG_LIMIT=20` 环形），读取用 `latest_strategy_decision():1125`。

**关键事实（审计 A 的 B1）**：适配器算出了 `chosen`，但生产路径**没有真正派遣它**——
`preset_router._loop_step():2042-2049` 仍然选 `scheduler.next_actions[0]`，
`_handle_research_loop():2095-2098` 只把适配器选择拼进人类可读字符串。
因此当前状态是 **L1 建议 + 部分 L2 遥测，缺真实 dispatch 消费**。

### Q3 哪些策略影响已有真实执行证据？

只有“写了遥测”这一层：`strategy_decisions[]` 记录了 `candidates_before/candidates_after/
chosen/adopted/strategy_applied/decision_changed/reason_if_not`。
`dispatch_result` 字段存在但生产路径只在 `strategy_memory.py decide --record` 手工传入。
**没有**任何路径用适配器的 `chosen` 覆盖实际派遣动作。

### Q4 哪些只是推荐、没有实际消费者？

- `p4_context()` 无调用者（审计 A：B7）。
- `value_assessment()/decision_value` 只喂 replay / release 工具。
- `after.menu` 从未持久化（`revision_payload()` 剥离），使适配器的 stagnation 分支成死代码（B2）。
- `strategy_updates()` 追加的 revision 从不被回读；`operator_priors()` 从
  `scheduler.operator_stats` + hypotheses 重算（B10）。
- `strategy_decisions[]` 持久化条目丢弃 `schema/candidates_after/chosen_without_memory`（B3）。

### Q5 当前 Discovery Replay 是否真正测量了策略选择的改善？

**没有。** 它测量的是决策与隐藏答案的相关性 + 相对 baseline 的代理增量：

- 只有单一 hard-coded `_intervention_for()` 选择（`research_replay.py:351-364`），没有候选集/排序比较；
  `decision_changed` 是 runner 自报标志（`:331`）。
- `memory_prediction` 与 `full_cie` 在全部七维上完全相同（`:696-701`）——
  即当前消融**无法隔离 strategy 层**。
- 七维 `METRIC_DIMENSIONS` 无任何“策略是否改变了实际决策”的维度。

### Q6 历史轨迹是否足以支持新的离线回放？

不足以直接支撑：replay case 是**自包含 JSON**（`load_case():161`、`load_cases():620`），
**从不读取真实 route 的** `research-state.json` / `model-revisions.jsonl` / `scheduler.json`。
`smoke` 只合成一个 route。没有把真实历史自动转成 replay case 的通道。

### Q7 Cognitive Memory 是否正确区分科学经验与系统经验？

部分区分、但**没有类型化**：

- 四个 `MEMORY_CLASSES`（mechanistic/anomaly/competition/scientific_value）都是科学类。
- 系统/决策经验分散在三处：同一份 `model-revisions.jsonl` 里的 `strategy_update`（`_Builder.fold`
  刻意跳过 `:715-722`）、`scheduler.strategy_decisions[]` 遥测、`cognition/recovery-log.jsonl`。
- 没有 decision-experience 一等记录，也没有 `experience_kind` 判别位。
- `cognition.py` 内没有决策价值/策略效果度量；`decision_impact` 是未校验 passthrough。

### Q8 Research Loop 能否持久记录决策并跨会话恢复？

半能：canonical state + scheduler telemetry + cognition 投影可跨会话恢复；
但**决策过程**只有 20 条环形遥测，没有 append-only 决策轨迹，
且**预测与结果没有和决策绑定**，无法支撑长期策略学习。

### Q9 哪些机制已能抑制无意义归因/伪进展？

已有且可复用：`structural_equivalence_check.py`（EQ/NN）、`prediction_compare.diagnosis_switch()`、
`execution_gate` 的 AALG/PEIG 有限次数、`stagnation_fingerprint()`、assurance 生命周期、
`strategy_memory` 的 `MIN_INDEPENDENT_FAILURES=2` / `STAGNANT_MENU_RUN=2`。
**不得重复实现**这些机制。

### Q10 新 RSI 是否与 Scheduler/CIE/Preset 重复？

会重复的风险点及规避：

| 风险 | 规避 |
|---|---|
| 第二套策略决策 | 复用 `strategy_decision()` / `record_strategy_decision()`，只补 dispatch 消费 |
| 第二套证据门禁 | 轨迹/replay 结论**只作策略假设**，永不写 `evidence[]` |
| 第二套评价框架 | 增强 `research_replay.py`，不新建并行评价器 |
| 第二套认知引擎 | 三层记忆靠**新增控制平面记录**分离，不新增 canonical 类、不改 CIE |
| 新增第 17 个 Preset | **不新增 preset**；用现有 `strategy-evolution` / `research-loop` 承载 |

## 2. 差距矩阵（每个拟新增模块）

### G1 Decision Trajectory（Phase 2）

| 项 | 内容 |
|---|---|
| 现有能力 | `scheduler.strategy_decisions[]`（20 条环形遥测）；`model-revisions.jsonl`（strategy_update，无预测/结果绑定） |
| 明确缺口 | 无 append-only 决策轨迹；无 Context/Prediction/Outcome/Learning 结构化绑定；20 条上限不足以长期学习；无结果泄漏防护 |
| 为何现有模块不够 | 遥测是**系统运行统计**（有界环），追加会破坏 `DECISION_LOG_LIMIT` 语义与已有测试；revision log 是科学/系统混合且 payload 受限，不能承载 prediction/outcome |
| 最小方案 | 新增 `scripts/decision_trajectory.py`，落 `<route>/decision-trajectory.jsonl`（append-only，flock + fsync），**不改** canonical state、**不改** scheduler 既有键 |
| 生产者 | `preset_router` 的决策点（strategy-evolution / research-loop）、`policy_evolution` |
| 消费者 | `policy_evolution`（候选来源）、`policy_transfer`（迁移证据）、`research_replay`（真实历史 case） |
| 验证 | 幂等/追加/过期/泄漏/来源绑定/canonical 不变性测试 |
| 接口影响 | 新增文件与 CLI，无破坏性改动 |

### G2 Counterfactual-Aware Replay（Phase 3）

| 项 | 内容 |
|---|---|
| 现有能力 | RP2 子串泄漏扫描、七维评价、四臂消融、14 个对抗 case |
| 明确缺口 | 无 OBSERVED/REPLAY_SUPPORTED/NO_SUPPORT 分级；无“未执行分支不可评价”判定；RP2 只做 ≥12 字符子串；无时间边界/文件系统/认知记忆泄漏检查；无 isolate RSI 的臂 |
| 为何现有模块不够 | 单点增强即可，无需新框架；但 `evaluate()` 返回结构必须**向后兼容**（预设与 release_check 依赖） |
| 最小方案 | 就地增强：新增 `classify_evidence_support()`、`leak_audit()`、`cases_from_trajectory()`；`evaluate()` 增加可选 `evidence_support` 块；新增 `RSI_ARMS`（不改 `ABLATION_ARMS` 四臂语义） |
| 生产者 | runner / 轨迹 |
| 消费者 | `policy_evolution` 的 REPLAY_EVALUATED 门、`release_check`、`preset_router` |
| 验证 | 不可观测返回 NO_SUPPORT；篡改 visible 含 hidden → 拒绝；时间倒挂 → 拒绝 |
| 接口影响 | 只增键、不改既有键；默认四臂行为逐字节保持 |

### G3 Scoped Policy Evolution（Phase 4）

| 项 | 内容 |
|---|---|
| 现有能力 | `strategy_updates()` 生成有 provenance 的更新；SV 校验；exploration floor |
| 明确缺口 | 更新是“先验/菜单调整”，无候选结构（scope/counterexamples/revalidation/rollback）；无生命周期；无复杂度正则；无失败上限防改名规避 |
| 为何现有模块不够 | revision payload 受 `STRATEGY_FIELDS` 限制，塞入会触发 CM1；需要独立控制平面存储 |
| 最小方案 | 新增 `scripts/policy_evolution.py`，落 `<route>/policy/*.jsonl`；策略只能影响**已有授权策略面** |
| 生产者 | `decision_trajectory` + `research_replay` |
| 消费者 | `preset_router._loop_step` 的派遣决策、`strategy_decision()` |
| 验证 | 禁止字段/可执行内容/越权目标拒绝；作用域必填；复杂度上限；失败签名上限 |
| 接口影响 | 只经 `strategy_decision()` 的 `advice` 输入，不改其签名 |

### G4 Independent Policy Evaluation & Promotion（Phase 5）

| 项 | 内容 |
|---|---|
| 现有能力 | replay 七维、L1/L2/L3 概念（`preset-policy.md §7`） |
| 明确缺口 | 无策略生命周期状态机；无 shadow 评价；无冻结评价规则；无 rollback；无“测试过拟合”拒绝 |
| 最小方案 | 在 `policy_evolution.py` 内实现状态机 + `evaluation-rules` 冻结摘要 + rollback；晋升必须携带独立评价引用 |
| 验证 | 非法转移拒绝；无独立评价不得 ACTIVE；rollback 保留失败历史；跨会话重建一致 |
| 接口影响 | 新增 CLI/API |

### G5 Research Loop Integration（Phase 6）

| 项 | 内容 |
|---|---|
| 现有能力 | `_loop_step()` 选 `next_actions[0]`；`_handle_research_loop()` 只做 guidance 文本 |
| 明确缺口 | 适配器/POLICY 选择未真正进入 dispatch；无 Scientific/Decision/Policy 三类 Delta |
| 最小方案 | 就地改 `_loop_step()`/`_handle_research_loop()`：当存在**未过期且合法**的有效策略决策时，用它作为派遣动作；补齐 `decision_delta/policy_delta` |
| 验证 | 已有 `test_preset_router` 消费/过期测试保持通过；新增“策略改变实际派遣”测试 |
| 接口影响 | `next_action` 语义增强（向后兼容：无策略时行为不变）|

### G6 Research Memory & Policy Transfer（Phase 7）

| 项 | 内容 |
|---|---|
| 现有能力 | cognition 投影 + revision log；无 decision-experience 层 |
| 明确缺口 | 三层未类型化；无结构相似性迁移门；无过期经验/负向发现拒绝 |
| 最小方案 | 新增 `scripts/policy_transfer.py`：三层分离视图 + 迁移条件（结构签名而非关键词）+ 过期/反例拒绝 |
| 验证 | 关键词相似但结构不同 → 拒绝；过期经验 → 拒绝；被否证机制不得再现 |
| 接口影响 | 只读视图 + 校验函数 |

### G7 Source Freeze & Write Guard（Phase 8）

| 项 | 内容 |
|---|---|
| 现有能力 | `experiment_execute.manifest_binding()` 对**实验**文件做 sha256 绑定 |
| 明确缺口 | 无 Skill 源码清单/摘要；无运行时源码写入白名单；无违规 HOLD 审计；无 symlink/路径穿越防护 |
| 最小方案 | 新增 `scripts/source_freeze.py`：清单、规范化路径、symlink 越界检测、运行前后核验、`guard_write()`、HOLD 审计事件 |
| 验证 | 14 类对抗测试（改 SKILL.md / 改校验器 / 改阈值 / shell 命令 / `../` / symlink / 安装副本 / 隐藏答案 / 旧 state_version / 重置预算 / 子代理注入 / 伪造证据 / 重放晋升凭证 / 换 ID 规避上限）|
| 接口影响 | 新增模块；`preset_router` 在 apply 路径调用前后核验 |

## 3. 明确不做（防止过度工程）

- 不新增 preset（保持 16）。
- 不新增 canonical 对象/字段（保持八类）。
- 不替换 Scheduler、CIE、Evidence Qualification、AALG。
- 不做模型权重更新、Harness 自修改、无限制 Agent 自进化。
- 不用 LLM 预测代替真实实验结果。
