# 第十轮：RSI 系统性 Bug 修复与回归验证

> 分支 `research-idea-pipeline/skill-rsi-dev`；起始 HEAD `6d00e5014928192b8f4964ca3c801777d07e3e85`
> （= 远程 HEAD，工作区干净）。main 仍 `ea0214e`，未 merge/rebase/tag。
> 原则：**先复现、再最小修复、保留既有 API/CLI/持久化契约、逐项可追踪到测试**。

## 0. 基线与结果

| 项 | 修复前 | 修复后 |
|---|---|---|
| 全量单元测试 | 1850 OK (skipped=3) | **1869 OK (skipped=3)** |
| 新增对抗性测试 | — | `test_rsi_hardening.py` 19 项 |
| 新增测试在基线 `6d00e50` 的表现 | — | **19/19 失败**（16 断言 + 4 异常；**0 接口不兼容**）|
| `release_check.py` | PASS | **PASS（18 步，含 6 个 selftest）** |
| 模块 selftest | 6/6 OK | **6/6 OK** |

## 1. P1：L2/L3 运行次数校验不完整

- **位置**：`policy_evolution.audit_report()`（回放路径）、`_validation_errors()`（L3 路径）。
- **根因**：只校验「去重后的 case 数」与「记录总数 == cases×runs」，**没有校验每 case 的运行分布**，
  也没有 run 身份概念。因此 `cases=2, runs=2` 下「一个 case 跑 3 次 + 另一个跑 1 次」在结构上被接受。
- **最小复现**（基线）：把每个臂的记录改成 `[c0,c0,c0,c1]` 并令 `cases=2,runs_per_case=2`，
  `audit_report` 返回 **0 个错误**（仅因样本充分性规则才没晋升）。
- **修复**：新增 `_run_distribution_errors()`：
  ① 每 case 记录数必须等于声明的 `runs`；② `runs>1` 时每条记录必须有 `run_id`；
  ③ `(case_id, run_id)` 不得重复；④ 每 case 的 run 集合必须等于整臂的 run 集合（**配对完整性**，
  防止缺轮与跨臂错配）。`run_suite()` 现在为每条记录写 `run_id`。
- **测试**：`test_an_uneven_distribution_cannot_masquerade_as_paired_runs`、
  `test_a_repeated_run_identity_is_refused`、`test_an_unpaired_run_is_refused`、
  `test_an_l3_credential_with_an_uneven_distribution_is_refused`。

## 2. P1：Bounded Trial 派遣凭证可伪造

- **位置**：`policy_evolution.begin_bounded_trial()`、CLI `trial`、L3 门禁 `_validation_errors()`。
- **根因**：`dispatch_evidence` 是调用方自述字典；CLI 在**没有 `--dispatch`** 时自动生成
  `{"dispatched": True}`。任意字典都能成为「可信派遣证据」。
- **最小复现**（基线）：`policy_evolution.py trial --state … --policy-id P-1`（无 `--dispatch`）
  → **BOUNDED_TRIAL**，产物内 `dispatch_evidence={'dispatched': True}`。
- **修复**：新增 `dispatch_corroboration()`——派遣必须与**路由自身的调度器遥测**互相印证：
  `scheduler.strategy_decisions[]` 最后一条必须 `adopted=true`、有 `dispatch.action`、
  版本与当前一致、`advice.policy_id` 与本候选一致；调用方的声明若与遥测冲突即拒绝。
  产物记录 `dispatch_state`（`dispatched` / `simulated`）、`dispatch_record`（动作、版本、
  `scheduler_digest`、`decision_index`）。CLI 不再生成默认声明；`--simulated` 显式表达 dry-run。
  **dry-run 能力保留**：`simulated` 可进入 BOUNDED_TRIAL（L1 运行记录）但 L3 门禁拒绝
  （`dispatch_state` 必须是 dispatched/executed/completed）。
- **测试**：`test_a_self_issued_dispatch_claim_is_refused`、`test_the_cli_no_longer_fabricates_a_dispatch`、
  `test_a_stale_dispatch_record_is_refused`、`test_a_dispatch_record_for_another_policy_is_refused`、
  `test_a_claim_that_contradicts_the_telemetry_is_refused`、`test_a_corroborated_dispatch_is_accepted`、
  `test_a_simulated_credential_cannot_reach_l3`。

## 3. P1：Global 跨项目背书未绑定候选策略

- **位置**：`policy_evolution._attested_projects()` → 新的 `_candidate_bound_projects()`；`PE14`。
- **根因**：只要同一路由里存在「决策 + 合格 outcome」的轨迹，就计入背书项目，**与本候选无关**。
- **最小复现**（基线）：为 `PROJ-A/PROJ-B` 写入与候选无关的轨迹后，`_attested_projects` 返回
  `{'OTHER-A','OTHER-B'}` —— 数量凑够即可。
- **修复**：背书轨迹必须 `policy_version == candidate.policy_id`（策略 id 唯一且不可复用，
  因此同时锁定版本）；若轨迹带 `policy_signature` 则必须一致；按 `(project, trajectory_id)` 去重；
  仍要求 `evidence_qualification == "qualified"` 与 ≥2 个独立项目。
- **测试**：`test_unrelated_history_does_not_back_a_global_policy`（阻断）、
  `test_candidate_bound_history_backs_a_global_policy`（**正向：不误杀合法背书**）、
  `test_an_unqualified_outcome_does_not_count`。

## 4. P2：回滚后旧策略的缓存决策仍可能生效

- **位置**：`preset_router.strategy_dispatch()` 的 `recorded_strategy_decision` 回退分支。
- **根因**：有效性只看 `state_version` 与 `adopted`；回滚不改变 state_version，
  但生效策略已变，旧策略缓存（`advice.policy_id`）继续授权动作。
- **最小复现**（基线）：缓存一条 `advice.policy_id="P-ROLLED-BACK"` 的新鲜决策 → 基线**消费**它。
- **修复**：① 缓存决策的策略身份必须等于当前 ACTIVE 策略（无策略时两者都为空）；
  ② 缓存动作必须仍在 `scheduler.next_actions`（**当前合法动作集合**）内；
  否则返回 `source="stale_cached_decision"`、`reason=stale_cached_policy_decision`
  /`cached_action_not_in_legal_set`，不再授权。
- **测试**：`test_a_cached_decision_from_a_policy_no_longer_in_force_is_not_consumed`、
  `test_a_cached_action_outside_the_legal_action_set_is_not_consumed`、
  `test_a_scheduler_only_cached_decision_is_still_consumed`（不破坏既有回退）。

## 5. P2：冻结规则与证据等级计算不一致

- **位置**：`policy_evolution._achieved_level()`（`_transition_locked` 调用）。
- **根因**：`_artifact_gate_errors` 用**冻结规则**重算等级，而 `_achieved_level` 用编译期默认规则，
  于是自定义 `min_cases`/`min_runs` 时**转换记录里的等级与门禁结论不一致**。
- **最小复现**（基线）：冻结 `min_cases=1,min_runs=1`，2 case×1 run 的回放 → 产物 `level=L2`，
  但转换记录 `level=L1`。
- **修复**：`_achieved_level(..., rules=…)` 使用 `frozen_rules(state)`（缺失时回落默认），
  与门禁同一份快照；产物本身已记录 `rules_digest` 作为历史指纹。
- **测试**：`test_the_recorded_level_uses_the_frozen_rule_snapshot`。

## 6. P2：非法指标导致异常退出

- **位置**：`policy_evolution._recompute_arm_dimensions()` / `audit_report()`。
- **根因**：指标值只判 `is not None` 就进入 `sum(values)`；字符串/列表/对象直接抛 `TypeError`。
- **最小复现**（基线）：把 `search_efficiency.value` 设为 `"0.5"` / `[1,2]` / `{"a":1}`
  → `evaluate_candidate` **未捕获 TypeError**。
- **修复**：新增 `_finite_number()` 与 `_metric_value_errors()`：指标值必须是**有限数值**
  （bool 不算数值），否则以 `INVALID` 明确拒绝；`_recompute_arm_dimensions` 也不再让非数值进入聚合
  （防御性）。**不自动修补、不静默忽略、不把错误值转成合格证据**。
- **测试**：`test_a_non_numeric_metric_is_a_diagnosable_refusal`（string/bool/list/object/NaN/Inf 六种）。

## 7. 相邻缺陷审查（任务第三节）

| 主题 | 实测结论 |
|---|---|
| 非法跃迁 | `ACTIVE → VALIDATED/BOUNDED_TRIAL/ACTIVE/SHADOW` 全部 `PE10` 拒绝；重复 `promote` 拒绝 |
| 撤销后证据与可追溯性 | `ROLLED_BACK` 策略不能再 `promote`/`validate`；转换链保留（`rollback` + `ROLLED_BACK` + 恢复记录）|
| 并发/重复执行 | 4 线程并发晋升 → 恰好 **1 条** ACTIVE 转换记录，其余 INVALID |
| 部分写入 | 转换被拒时产物丢弃（第九轮 `_discard_artifact`），本轮不变 |
| 自签证据 | 自述派遣被拒绝（§2）；自评凭证必须有**人工批准**（第八/九轮），本轮不变 |
| 事后改判据 | 实验中/后改冻结规则 → `promote` 拒绝（`PE12`，实测） |
| 无限空转 | 策略库读取幂等；无新证据不会产生新晋升（状态机与检查点限制） |

**未发现新的真实缺陷**（以上均为已 fail-closed 行为）；本轮不引入无关重构。

## 8. 兼容性结论

- **Research State**：未新增/修改任何状态字段或类型；`begin_bounded_trial` 只是新增对既有
  `scheduler.json` 遥测的**读取**，不写入 canonical state。
- **CIE / Scheduler**：硬约束、EIG÷cost、AALG 预算、前置资格门禁位置未变；缓存建议现在必须
  属于当前 ACTIVE 策略且在当前合法动作集合内，**不绕过任何门禁**。
- **Policy Evolution**：`begin_bounded_trial` 的 `dispatch_evidence` 语义由「自述」变为「需与遥测
  互相印证」，调用签名保持兼容（默认值改为 `None`）；`_attested_projects` 由私有函数
  `_candidate_bound_projects` 取代（仅测试引用，已同步更新）。持久化契约新增字段
  （`run_id`、`dispatch_state`、`dispatch_record`），为**向后兼容的增量**：旧产物缺少这些字段时
  按 fail-closed 拒绝（不会静默降级）。
- **Loop**：派遣后写入的遥测即为下一轮缓存的权威来源；回滚后同一 state_version 的旧缓存不再生效。
- **历史记录**：产物保留 `rules_digest`、`policy_signature`；转换记录保留等级与证据引用，可追溯。

## 9. 本轮提交与推送

见最终报告（`fix(...)` 分阶段 commit + `docs(.dev): round10`），push 到
`origin/research-idea-pipeline/skill-rsi-dev`。

## 10. 仍存在的风险（如实记录）

1. 人工批准仍是**协议级门**（非密码学证明）；第八/九轮已声明。
2. 调度器遥测、策略库、产物库都在同一路由内且可被有写权限者改写；本轮收紧的是「**声明必须与
   遥测互相印证**」，不是把路由内文件变成可信外部证据。
3. `run_id` 由回放运行器生成，**不是**硬件/外部执行证明；它证明的是「同一轮运行没有被重复计数」。
4. **L3 仍未验证**：无真实科研 A/B，测试中的 L3 凭证是结构化夹具。
5. 并发仅在单机多线程验证。
6. 未执行真实 GPU/外部调度集成测试（无该环境）；不伪造执行证据。
