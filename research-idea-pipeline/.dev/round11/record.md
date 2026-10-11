# 第十一轮：配对完整性、派遣归属、L2/L3 指标一致性与 run_id 类型安全

> 分支 `research-idea-pipeline/skill-rsi-dev`；起始 HEAD `293c7ff572c923cbd5ee894f0a5cf68135544aca`
> （= 当时的远程 HEAD；工作区干净；main 仍 `ea0214e`，未 merge/rebase/tag）。
> 流程：**先建立失败复现 → 最小实现 → 全量验收**；不新增平行状态机，不做无关重构。

## 0. 基线与结果

| 项 | 修复前 | 修复后 |
|---|---|---|
| 全量单元测试 | 1869 OK (skipped=3) | **1889 OK (skipped=3)** |
| 新增测试 | — | `test_rsi_round11.py`（20 项） |
| 新测试在 `293c7ff` 上 | **FAILED (failures=24, errors=1)**（15 个方法失败，含 subTest 展开） | **20/20 OK** |
| `release_check.py` | PASS | **PASS（18 步，含 6 个 selftest）** |
| 模块 selftest | 6/6 OK | **6/6 OK** |
| 第十轮 `test_rsi_hardening.py` 回归 | 19 OK | **19 OK** |

### 0.1 上轮计数口径的核查（任务要求）

上轮报告写「19 项测试，16 断言 + 4 异常」，**该表述有误**，原因与正确口径如下：

- `test_rsi_hardening.py` 共 **19 个测试方法**；基线运行头部为 `Ran 19 tests`，汇总为
  `FAILED (failures=16, errors=4)`。
- unittest **会把失败的 subTest 逐条计入汇总**：`test_a_non_numeric_metric_is_a_diagnosable_refusal`
  使用 6 个 subTest，产生 6 行 `FAIL/ERROR` 与 6 个汇总计数。
- 因此「16+4=20」是**子测试重复计数**（该方法 1 个方法被计 6 次，多算 5）。
- 逐方法去重后的真实口径：**基线 15/19 个方法失败**（4 个通过：两个正向测试
  `test_candidate_bound_history_backs_a_global_policy`、`test_a_scheduler_only_cached_decision_is_still_consumed`，
  另有两个当时未被基线行为违反的用例）。上轮「19/19 失败」的写法**不成立**，本报告予以更正。

## 1. P1-A 跨实验臂运行配对完整性（已复现 Bug）

- **位置**：`policy_evolution._run_distribution_errors()`（已由 `_pairing_errors()` 取代）、
  `audit_report()`、`_validation_errors()`。
- **根因**：只校验每个臂**内部**的 case 数、运行次数与 `(case,run)` 唯一性，**没有跨臂比对**。
  两臂各自「3 个 case × 2 轮、run-1/run-2」时通过了检查；但若控制臂把第 2 轮记成 `run-9`，
  两臂就**不是成对数据**，配对统计会把不同轮次错配比较。
- **复现输入**（`293c7ff`）：控制臂 run_id 由 `run-2` 改为 `run-9`（臂内仍唯一、case 数一致）
  → `evaluate_candidate` 返回 **REPLAY_EVALUATED**（被接受）。
- **修复**：新增 `_pairing_errors()`，作为 L2/L3 **共用的唯一入口**：
  ① `run_id`/`pairing_key` 类型与格式契约（见 P2-B）；② 每 case 记录数 == 声明的 `runs`；
  ③ 每 case 的配对集合必须等于整臂集合（缺轮/错配）；④ `(case_id, 配对标识)` 不得重复；
  ⑤ **跨臂配对集合必须完全一致**，否则拒绝。
  设计字段 `design` 默认 `"paired"`；显式 `"unpaired"` **拒绝**（不擅自切换统计协议）。
  `pairing_key` 可选：当执行器产出的 `run_id` 只是**臂内**执行 ID（如 `a-3` / `b-7`）时，
  用 `pairing_key` 表达配对关系；缺省时配对标识即 `run_id`。
- **测试**：`test_cross_arm_pairing_mismatch_is_refused`、`test_a_missing_pairing_across_arms_is_refused`、
  `test_a_mismatched_pairing_key_is_refused`、`test_an_explicitly_unpaired_design_is_not_promotion_evidence`、
  `test_l3_uses_the_same_pairing_rule`，以及**正向不误杀**：
  `test_a_legal_paired_experiment_is_accepted`、`test_an_explicit_independent_pairing_key_is_honoured`。

## 2. P1-B Bounded Trial 策略身份与真实派遣归属（已复现 Bug）

- **位置**：`policy_evolution.dispatch_corroboration()`、`begin_bounded_trial()`、`_validation_errors()`
  的 `dispatch_ref` 分支。
- **根因**：`advice.policy_id` 缺失时**不拒绝**（只在「存在且不匹配」时拒绝）。于是**普通
  Scheduler 派遣**（`advice=None`、`strategy_applied=False`）也能被当作某候选策略的派遣凭证。
- **复现输入**（`293c7ff`）：遥测写一条 `adopted=True, advice=None, dispatch.action="R2"` 的普通派遣
  → `begin_bounded_trial("P-1")` 返回 **BOUNDED_TRIAL**（被接受）。
- **修复**：用于候选策略的派遣**必须显式携带候选身份**：
  `advice.policy_id` 必须是非空字符串且等于候选 `policy_id`；缺失 → fail-closed
  （「普通 Scheduler 派遣不能作为策略晋升的 L3 派遣凭证」）。若遥测带 `policy_signature`
  （或 `advice.policy_signature`）则必须与候选签名一致。
  新增 **事件标识 `event_id`**（由 `policy_id + policy_signature + action + state_version +
  decision_index + scheduler_digest` 规范化摘要），并在 `begin_bounded_trial` 中做
  **事件单次使用**检查（同一 `event_id` 不得支撑第二次试运行）；L3 门禁要求
  `dispatch_ref` 具备 `event_id`、`policy_id`、动作与状态版本。
  保留 `scheduler_digest` / `dispatch_record` 与既有防重放（陈旧事件、跨策略、模拟、claim 冲突）。
  **归因只读不写**：`begin_bounded_trial` 不修改 `scheduler.json`（测试断言字节不变），
  因此不存在「验证阶段事后填入身份」。
- **测试**：`test_an_ordinary_scheduler_dispatch_is_not_a_policy_credential`、
  `test_a_dispatch_without_any_identity_is_refused`、`test_a_legitimate_policy_dispatch_is_accepted_and_bound`、
  `test_the_trial_entry_never_writes_an_identity_into_the_scheduler`、
  `test_an_event_cannot_be_replayed_for_a_second_trial`，以及第十轮既有的
  陈旧/跨策略/模拟/claim 冲突用例（全部保持通过）。

## 3. P2-A L2/L3 指标有效性统一（已复现 Bug）

- **位置**：`_metric_value_errors()`、`_recompute_arm_dimensions()`、`audit_report()`、`_validation_errors()`。
- **根因**：L2（回放）走 `_metric_value_errors()`，**L3 未调用**；L3 的非法值只被
  `_recompute_arm_dimensions()` 的防御性过滤吸收，样本量被悄悄降低后仍给出合格结论。
- **复现输入**（`293c7ff`）：L3 凭证里 `mechanistic_understanding.value="0.5"`（字符串）
  → `record_research_validation` 返回 **VALIDATED**（L2 对同一输入返回 INVALID）。
- **修复**：`_metric_value_errors()` 成为 **L2/L3 共用**的输入合法性入口，并收紧 schema：
  ① 每个 `METRIC_DIMENSIONS` 维度**必须存在**（缺键 = 结构错误，不再被当作「不可观测」）；
  ② `value` 只能是 `None`（合法不可观测）或**有限数值**（排除 bool/字符串/列表/对象/NaN/Inf）；
  ③ 聚合层不再作为唯一防线（非法值在审计层即拒绝，不会静默降低有效样本）。
- **测试**：`test_l3_rejects_every_illegal_metric_value`（string/bool/list/object/NaN/Inf）、
  `test_l2_and_l3_agree_on_illegal_metrics`、`test_a_missing_metric_key_is_a_structural_error`、
  `test_an_unobservable_value_is_legitimate_and_zero_is_a_measurement`（区分**无效数据**、
  **合法缺失**、**真实测量为零**）。

## 4. P2-B 非法 run_id 导致异常退出（已复现 Bug）

- **位置**：`_run_distribution_errors()`（及其调用链）。
- **根因**：`run_id` 直接进入 `set()`/`sorted()`；来自外部 JSON 的 list/dict 不可哈希、
  bool 与 str 混排不可比较 → 抛未捕获 `TypeError`。
- **复现输入**（`293c7ff`）：`run_id` 为 `["run-1"]` / `{"a":1}` / `True` / 混合 str+int
  → **ESCAPED TypeError**（`None` 恰好被旧检查拦住）。
- **修复**：新增 `_run_identity_value_errors()`：身份必须是**非空字符串**（≤64 字符、无控制字符）
  或**非负整数**；bool 拒绝；同一臂内**混用类型**拒绝；集合运算前先做类型校验；
  **不把非法值强制转成字符串**（避免 `1` 与 `"1"` 身份碰撞）；`sorted(..., key=repr)` 保证
  报错路径本身不会因混排而崩溃。
- **测试**：`test_illegal_run_id_types_are_diagnosable_refusals`（list/dict/bool/float/空串，
  并断言**不留下持久化产物**）、`test_mixed_run_id_types_are_refused_without_raising`、
  `test_a_string_and_an_integer_run_id_never_collide`、`test_valid_string_and_integer_run_ids_are_accepted`
  （正向：合法 str/int 身份仍被接受）。

## 5. 相邻路径复核（任务第三节）

| 检查 | 结论 |
|---|---|
| L2 → L3 是否绕过共同配对/指标检查 | 不绕过：两个等级都经 `_pairing_errors()` + `_metric_value_errors()`（专项一致性测试） |
| 晋升是否接受与候选无关的派遣/轨迹/outcome | 派遣需候选身份（§2）；背书轨迹需 `policy_version` 绑定（第十轮）；outcome 需 qualified |
| 缓存是否把普通派遣升级为策略能力证据 | 普通派遣只作 Scheduler 回退：`source=recorded_strategy_decision`、`level=None`、`policy_id=None`（实测）|
| 冻结规则是否贯穿执行/评估/证据/晋升 | 产物记录 `rules_digest`；门禁与 `_achieved_level` 用同一冻结快照（第十轮修复保持）|
| 错误输入是否导致部分持久化/状态污染/错误晋升 | 非法输入在审计层拒绝且**不落盘**（实测产物数量不变）|
| 新字段是否破坏历史合法数据 | 31 份出货 `per_arm` JSON 全部通过新审计（0 例误拒）；`design`/`pairing_key` 可选，不改变既有契约语义 |

**相邻复核未发现新的真实缺陷**；以上均为已 fail-closed 行为，本轮不扩大范围。

## 6. 兼容性分析

- **Research State**：无新增/修改字段或状态类型；`begin_bounded_trial` 只**读**调度器遥测。
- **CIE / Scheduler**：硬约束、EIG÷cost、AALG 预算、充分性与资源资格门禁位置未变；
  普通调度决策仍可被循环消费，但不再构成策略能力证据。
- **Policy Evolution**：`_attested_projects`（第十轮改名）与晋升链路不变；新增
  `_pairing_errors()`/`_report_design_errors()`/`_run_identity_value_errors()`，
  `dispatch_record` 增加 `event_id`/`policy_signature`（**增量字段**）；旧产物缺 `event_id`
  时按 fail-closed 拒绝，不静默降级。
- **Loop**：派遣归属由「遥测 + 事件标识」共同决定；同一事件不可复用于第二次试运行；
  模拟/普通派遣均不能进入 L3。
- **历史记录**：`design`/`pairing_key` 为可选字段；缺省语义与旧数据一致；
  出货 fixture 与既有测试数据全部兼容（实测 0 例误拒）。

## 7. 交付

- 提交与推送见最终报告；push 到 `origin/research-idea-pipeline/skill-rsi-dev`，
  本地 HEAD 与远程 HEAD 逐字一致；未 force push、未 merge/rebase main、未建 tag、未发 Release。

## 8. 仍未验证 / 风险（如实记录）

1. **L3 科研有效性仍未验证**：无真实科研 A/B，测试中的 L3 凭证是结构化夹具；
   本轮只提升「证据结构不可被误用」的软件正确性，**不等于**科研能力提升。
2. 人工批准是**协议级**门，非密码学证明；路由内遥测/策略库/产物库对有写权限者可改写；
   本轮强化的是「声明必须与遥测一致 + 事件不可复用」，不是外部信任根。
3. `run_id`/`pairing_key` 由回放运行器产生，**不是**硬件执行证明。
4. 未执行真实 GPU / 外部调度集成测试；并发仅单机多线程验证。
5. 配对设计目前**只接受 paired**；若将来需要非配对协议，必须显式扩展统计设计，
   本轮选择 fail-closed 而非静默切换。
