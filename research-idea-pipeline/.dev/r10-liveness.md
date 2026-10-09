# R9.O → R10/R11 → Consolidate Loop Liveness（`fix/r10-outcome-loop-liveness`）

> branch-local 开发记录（合并前 KEEP_BRANCH_ONLY）。

## 1. 根因

`preset_router.r10_pending()` 用 `repairs[].outcome_analysis_id` 作为 R10/R11 完成收据。真实事务语义
（`evidence_outcome._apply()`）里 Repair **只在"更新把证据挂到 claim/hypothesis 上"的分支**写入；
`NEGATIVE_EVIDENCE`、`INVALID_EXPERIMENT`、hypothesis-only、partial-scope 等合法事务提交后
`repairs == []`（只写 `failures[]` 或 `scoped_outcomes`）。这些实验因此永远被判为待处理 → 反复 `Revise`。

同一根因另有两处：
1. `_loop_step()` 用全局存在性（`if analysis` / `done and not analysis`）代替实验级状态：一个历史分析
   掩盖所有未分析实验（case B），且缺少 Consolidate 之后的推进路径。
2. `signal_snapshot` 的 `engineering_failure` 用 `_repair_covers()` 判定"未处理失败"，已合法提交的
   `INVALID_EXPERIMENT` 被反复重新触发 `experiment-failure-recovery`。

## 2. 真实事务证据（实测）

| fixture | outcome | apply | repairs | failures | evidence | state_errors |
|---|---|---|---|---|---|---|
| positive | POSITIVE_EVIDENCE | PASS | **1** | 0 | 3 | 0 |
| negative | NEGATIVE_EVIDENCE | PASS | **0** | 1 | 3 | 0 |
| invalid | INVALID_EXPERIMENT | PASS | **0** | 1 | 1 | 0 |

凭证 = `{packet, analysis, audit, validation_context, audit_trail}`；权威校验器 =
`evidence_outcome.state_errors()`（键集/摘要/audit checks/冻结策略/历史复验/结果未被改写/
`audit_trail` 版本与 decision 一致）。

## 3. 修复

* 新增 `r10_status()`：逐实验 `COMMITTED` / `NEEDS_ANALYSIS` / `BLOCKED` / `PENDING_EXECUTION`，
  以 `state_errors()` 的逐实验归因为准（未归因的全局错误 → BLOCKED）；额外校验五键凭证、
  `audit_trail.state_version == result_at_state_version`、版本不晚于当前 state。
* `r10_pending()` 保留兼容包装（只返回 `NEEDS_ANALYSIS`）；新增 `r10_blocked()`。
* `_loop_step()` 重写为实验级待办：契约 → 候选 → 凭证受损(HOLD) → 缺失分析(R9.O) → planned/running
  → 投影过期(Consolidate 一次) → Assurance/Decision Gate → Scheduler 合法动作 → HOLD（不伪造进展）。
* `signal_snapshot`：`engineering_failure` 视 `COMMITTED` 凭证为已覆盖。
* `_handle_research_loop()`：映射 HOLD(exit 4)/BLOCKED(exit 3)，透传 `hold_reason`。
* 未新增字段、对象或阶段；未放宽任何 Validator。

## 4. 修复前后对比（同一状态）

| 场景 | 修复前 | 修复后 |
|---|---|---|
| 合法 NEGATIVE_EVIDENCE（无 Repair） | `Revise` 无限重复 | `COMMITTED`，不重复 |
| 合法 INVALID_EXPERIMENT（无 Repair） | `Revise` 无限重复 | `COMMITTED`，不重复 |
| X1 已提交、X2 未分析 | 有历史分析时被掩盖 | 逐实验：X2 → R9.O Verify |
| 凭证缺 `audit_trail` / 版本冲突 | 可能被当作待处理并重试 | `HOLD` + 实验 ID + 原因 |
| 全部已提交、投影过期 | `Consolidate` 后无推进 | `Consolidate` 一次 → Assurance → Discover |
| 已提交的 INVALID_EXPERIMENT 信号 | 反复触发工程恢复 | 不再触发 |

## 5. 测试

* 新增 `scripts/test_r10_liveness.py`（29 项），全部基于真实 `apply()` 事务；修复前 22/27 失败。
* 更新 `test_preset_router.py`：手写假凭证用例改为"真实事务 COMMITTED + 假凭证必须 BLOCKED"。
* 全量 `unittest discover`：**1382 项 OK**（skipped 3）；`release_check.py` 16/16 PASS；6 个 selftest PASS。

## 6. 旧项目兼容性（3D_ZS_SSL，state_version 86）

| 项 | 结果 |
|---|---|
| 实验 | 32（22 终态、10 非终态） |
| 分类 | `NEEDS_ANALYSIS` 22、`PENDING_EXECUTION` 10、`BLOCKED` 0 |
| `state_errors` | 0（该项目无 `contract.outcome_policy`，附加门禁未启用） |
| Loop 步骤 | R9.O → Verify（列出 22 个实验 ID），无 HOLD |
| canonical | sha256 前后逐字节一致（只读判定） |

**未补造任何凭证**：22 个历史实验确实从未走过 outcome 事务，按"保守报告、不事后补造"处理。

## 7. 未解决风险

1. 旧项目若长期不补齐历史分析，Loop 会停在 R9.O（真实未完成工作，不是死循环）；需研究者用 contract
   的 `outcome_policy` 明确范围或逐个提交分析，工具不代劳。
2. `READY_TO_COMMIT` 未实现：当前架构没有可信的"暂存未提交"分析产物（分析由调用方在命令行给出），
   扫描未核验 JSON 会违反"不得据未核验文件推定已提交"。若未来引入正式暂存区，应作为独立设计。
3. `decision_gate()` 需绑定当前 state 的 Assurance 才能 PASS，因此"分析完成 → 下一项动作"是
   Assurance → Discover 两步；这是既有门禁语义，本次未改动。
