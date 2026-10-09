# Loop Runtime Correctness Hotfix — Phase 1 audit（`fix/loop-runtime-correctness`）

> branch-local 开发记录（合并前 KEEP_BRANCH_ONLY）。基线 `origin/main` = `1ab5b6b`（v2.3.2）。

## 审计矩阵

| 字段 | FIX-01 | FIX-02 | FIX-03 | FIX-04 |
|---|---|---|---|---|
| Issue | Dry-run 消耗正式收据/预算 | Scheduler 全局 FAIL 仍产生 dispatch | 策略修订写者与校验者权限不一致 | post-update Assurance 不被消费 / 阶段顺序越门禁 |
| Reproduction | `test_execution_gate.resources` + `issue(now=100)` → `run(execute=False)` → 再 `run(execute=True)` | 合法 state + `scheduler.check` 仅报 `STALE_SCHEDULER` → `strategy_decision` | `run_preset('strategy-evolution', apply=True)` → 读 `cognition/model-revisions.jsonl` → `validate_strategy_revisions` / `cg.validate_revisions` | 真实 `apply()`（positive）→ `_loop_step`；再把合格 assurance 写到约定路径 → 再 `_loop_step` |
| Observed | dry-run 写入 1 条 `consume`（`dry_run: true`）；随后正式执行 `HOLD ['UNKNOWN_OR_USED_RECEIPT']` | `hard_gates.scheduler_check = PASS`、`chosen = H1`、给出 `dispatch` | 写入 `actor="R14"` → `SV6` 拒绝；`after` 含 `scope/reactivation_conditions/telemetry` → `CM1` 拒绝 | 无 Assurance 时 `Assurance`；**有合格 Assurance 落盘时仍 `Assurance`**；planned 实验先于审核被派遣 |
| Expected | 预览零副作用：无 `consume`、不扣预算、不占收据，同一收据仍可正式执行一次 | 整体 FAIL → 无合法 dispatch，且不得标记 PASS | 由授权写者（CIE/Meta-Controller）写入，且 SV/CM1 双校验通过 | 合格 Assurance 被真实 `decision_gate` 消费；依赖未审核结果的实验等待；缺失/损坏/过期不放行 |
| Root Cause | `run()` 在 `if not execute` 之前无条件 `ledger.append({'kind':'consume',...})` | `_legal_actions()` 用 `error.split(': ',1)` 解析被阻塞动作，全局错误无 `': '` → 阻塞集为空 | `_append_strategy_revisions()` 硬编码 `actor="R14"` 且直接写 `update['after']` 原文 | `_loop_step` 以 `decision_gate(state, xid)`（无 assurance）为准且从不查找产物；assurance 无约定存放位置 |
| Severity | 高（破坏一次性收据 + 错扣预算 + 阻止合法执行） | 高（在执行授权路径上 fail-open） | 中高（策略记忆写入永远非法；跨会话恢复受影响） | 高（活性 + 审核门禁顺序） |
| Decision | **FIX** | **FIX** | **FIX** | **FIX** |
| Regression | `test_loop_runtime_correctness.TestExecutionPreview`（11 项）+ `test_execution_gate` 中 3 项改为真实消费 | `TestSchedulerFailClosed`（6 项）+ 适配器测试改在**合法** scheduler 上运行 | `TestStrategyRevisionAuthority`（7 项） | `TestAssuranceLifecycle`（12 项）+ `TestEndToEndRuntime`（3 项） |

四项均为真实缺陷，无 KEEP / DEFER。

## 修复要点（最小改动）

1. `experiment_execute.run()`：预览在所有门禁复检之后、`consume` 之前返回；`consumed`/`spent` 统计
   排除 `dry_run: true`（兼容历史 Ledger，不重写任何既有事件）。
2. `strategy_memory`：新增 `scheduler_verdict()`（整体 PASS 才可派遣 + 结构化逐动作复检）、
   `SCHEDULER_GLOBAL_ERRORS`；`strategy_decision()` 全局失败时 `chosen=None`、`reason=scheduler_check_failed`、
   `hard_gates.scheduler_check=FAIL`。
3. `cognition.STRATEGY_REVISION_ACTORS` / `STRATEGY_UPDATE_ACTOR` 单点定义；`strategy_memory` 用它做
   `SV6`；`preset_router._append_strategy_revisions()` 写 `CIE`、先整组校验、事件幂等；
   `strategy_memory.revision_payload()` 把富更新投影为 `CM1` 允许的载荷。
4. `preset_router`：`assurance_status()`/`load_outcome_assurance()`/`OUTCOME_ASSURANCE_SUBDIR`/
   `_assurance_dependencies()`；`_loop_step()` 按 PENDING/VERIFIED/FAILED/STALE/SUPERSEDED 决策，
   依赖未审核结果的 planned 实验 HOLD，独立实验可推进；循环**不生成** Assurance。

## 兼容性影响

* CLI：`run` 不带 `--execute` 的输出新增 `preview`/`consumed`/`would_execute`/`budget`，并返回
  `execution_record.launch_seal = null`；`status` 仍为 `PASS`，退出码不变。
* Ledger：**不重写、不删除、不重置**任何既有事件；历史 `dry_run: true` consume 不再计入预算。
* `strategy_decisions[]` 新增 `scheduler_status`/`global_errors` 字段；`validate_strategy_revisions`
  的 `SV6` 允许集改为引用 `cognition.STRATEGY_REVISION_ACTORS`（取值与原实现相同）。
* 未改动：R0—R14、四入口、16 预设与 Intent Router、八类状态对象、证据资格/PEIG/AALG/预测冻结/
  Insight 认证门禁、canonical 语义。

## R7 Assurance 作者工具与活性（追加）

| 项 | 内容 |
|---|---|
| 需求 | R7 Agent 有权产出 T0 Assurance；Loop/CLI 不得自我认证；不得让 UNKNOWN 变成无限复审 |
| 实现 | `evidence_outcome.assurance-store`（校验→绑定→原子写+锁→真实 `decision_gate`）；`preset_router` 增加 `UNKNOWN` 生命周期与 `assurance_unknown` HOLD；PENDING 才是 R7 审查任务 |
| 权威形状 | `decision_gate` 由"恰好四键"改为"**必需四键 + 白名单可追溯字段**"，并在存在时校验 `experiment_id`/`analysis_id`/`verification_tier(T0)` 与记录一致（新增绑定校验，未放宽摘要与 checks 判据） |
| 拒绝规则 | 缺项、非法状态、空理由、占位理由（TBD/无/未知…）、过短理由、非法 reviewer、任意输出路径、错误实验/分析绑定、摘要过期保留但不复用 |
| 覆盖规则 | 同内容 → `already_stored`（不重写）；过期 → `replaced_stale`；当前有效但结论不同 → 拒绝，需 `--force` |
| 活性 | UNKNOWN → `HOLD/assurance_unknown` + 记录阻断原因与复审条件；仅摘要变化(STALE)/相关证据变化/显式 `--force` 才重新送审；PASS → 下一项合法动作；FAIL → HOLD 或既有修复协议；SUPERSEDED → 跳过 |
| 不可越权 | tier 恒 `T0`；PASS 只释放已记录决策，不启动实验、不改锚点、不绕 R8 预注册与 Execution Gate；审查工具不写 canonical |
| 文档 | 新增 `references/loop-assurance-review.md`（R7 操作手册），并从 `preset-policy.md §5.3`、`evidence-outcome-contract.md`、组件 README 链接 |
