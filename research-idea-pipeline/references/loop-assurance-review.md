# R7 Post-update Assurance 审查（Loop 消费）

> **定位**：`evidence_outcome.apply()` 完成 R10/R11 迁移后，**R7 必须实际阅读 Research State、
> Outcome Analysis、实验记录、证据与适用规范，完成四项检查并给出有来源依据的结论**，再通过
> `assurance-store` 落盘。Loop 只负责发现、校验与消费审查结果，**永不自行生成审查**。
>
> 本文件是 [preset-policy.md](preset-policy.md) §5.3 的操作手册；
> 形状与门禁语义见 [evidence-outcome-contract.md](evidence-outcome-contract.md) §Post-update Assurance；
> R7 的职责边界见 [phase-r7-r10-r13-assurance-repair-review.md](phase-r7-r10-r13-assurance-repair-review.md)。

## 1. 谁写、能不能写、写完意味着什么

| 问题 | 答案 |
|---|---|
| 谁可以写 | 以 **R7 reviewer** 身份工作的 Agent（CLI `--reviewer R7`；亦接受 `CIE`/`R10`/`R11`） |
| 代码能不能替 Agent 写 | **不能**。`preset_router._loop_step()` 不生成任何 assurance；`store_assurance()` 不替 reviewer 填 PASS |
| 结论可以是 | `PASS` / `FAIL` / `UNKNOWN`（由真实审查结果决定，不预设） |
| tier | 恒为 **`T0`**（LLM reviewer 上限）：程序性审查，**不升级 Claim / Evidence / Verification Tier** |
| PASS 的效果 | 只释放该实验**已记录的** decision gate；**不启动实验、不改主锚点、不绕过 R8 预注册与 Execution Gate** |
| 格式校验通过 | **不等于**科学审查正确。CLI 只保证四项齐全、理由可追溯、摘要绑定；判断仍是 reviewer 的 |

## 2. 如何获取待审核实验与上下文

```sh
# Loop 会直接把任务与路径印出来；也可自己查：
python3 scripts/evidence_outcome.py decision --state <state> --experiment <X>
python3 scripts/preset_router.py run --preset research-loop --state <state>   # observed.assurance / assurance_pending
```

待审核 = 该实验已有**合法提交**的 `outcome_analysis` 事务（见 `evidence-outcome-contract.md`），
且 `evidence_outcome.decision_gate()` 尚未 PASS。上下文要点：

1. `experiments[X].outcome_analysis`：`{packet, analysis, audit, validation_context, audit_trail}`；
2. `analysis`：`outcome`、`claim_updates`/`hypothesis_updates`（含 `scope`/`scope_relation`/`new_status`）、
   `uncertainty_updates`、`negative_knowledge`、`stop_rules`、`decisions`、`followups`；
3. 受影响对象：`claims[]`/`hypotheses[]` 的 `status`、`supporting_evidence`/`refuting_evidence`、
   `scoped_outcomes`、`known_flaws`；`failures[]`；`uncertainties[]`；
4. `state_version`、`validation_context`（冻结策略与预注册快照）、原始结果包 `packet` 与其来源；
5. 适用规范：`evidence-outcome-contract.md`、`phase-r9-r11-experiment-loop.md`、`evidence-qualification`（`PQ1`—`PQ8`）、
   本文档。

## 3. 四项检查各自审查什么

| 检查 | 审查内容 | 典型来源 | 典型 FAIL | 典型 UNKNOWN |
|---|---|---|---|---|
| `integrity` | 事务完整性：凭证五键齐备、`analysis.id`/`packet_digest`/`audit` 摘要一致、`audit_trail.state_version == result_at_state_version`、来源未被改写 | `outcome_analysis`、`audit`、ledger 记录 | 摘要不符、来源文件被替换/缺失、版本冲突 | 来源不可访问、需外部系统核验 |
| `claim_calibration` | 状态迁移与证据强度是否相称：`supporting_evidence`/`refuting_evidence` 的 tier 与 scope、`scoped_outcomes` 是否支持新 `status`；未越界外推 | `claims[]`/`hypotheses[]`、`evidence[]`、`PQ*` 结论 | 用无效执行升级 claim、`UNKNOWN` 被当作支持、范围外推 | 缺独立校准证据、需要复现实验 |
| `reproducibility` | 可复现性：协议/种子/数据划分/配置与预注册一致；对照与容量条件成立 | `execution_protocol`、manifest/config 绑定、`preregistration` | 配置与冻结不一致、未做公平对照却声明对比 | 复现产物未归档、需重跑确认 |
| `stop_rule_compliance` | 停止规则与失败记忆：`stop_rules`、`negative_knowledge`、`failures[]`、`known_flaws` 是否被尊重；重试是否需要澄清条件 | `failures[]`、`uncertainties[]`、`repairs[]` | 违反 stop rule 重跑同一协议 | 澄清条件是否满足需进一步证据 |

**每条理由必须可追溯**：写清依据对象与判据（例如 `claims[C1].scoped_outcomes` 与
`evidence[E3].verification_tier`），不要写 `TBD`/空/单字；CLI 会拒绝占位理由。

## 4. 如何提交审查

```sh
python3 scripts/evidence_outcome.py assurance-store \
  --state .research-idea-pipeline/routes/C/research-state.json \
  --experiment X-result --reviewer R7 \
  --check integrity=PASS:"audit 摘要与 source-ref 已逐项核对，来源未改写" \
  --check claim_calibration=PASS:"C1 由 T2 支持证据升级，scope 与冻结范围一致" \
  --check reproducibility=PASS:"manifest 配置与预注册 outcomes 一致，对照完整" \
  --check stop_rule_compliance=UNKNOWN:"澄清条件是否满足仍需新证据" \
  --re-review-condition "获得独立复现结果后复审"
```

行为：**校验**（四项齐全、状态合法、理由非占位、reviewer 合法）→ **绑定**（自动计算 `state_digest`/
`analysis_digest`，并绑定 `experiment_id`/`analysis_id`）→ **落盘**（`<route>/assurance/outcome/<analysis_id>.json`，
原子写 + 文件锁；默认路径受约束，任意路径被拒）→ **调用真实 `decision_gate()`** 输出结论。

覆盖规则（不静默覆盖历史）：同一 state+analysis 且内容相同 → `already_stored`；摘要已过期 → 覆盖为
`replaced_stale`；当前有效但结论不同 → **拒绝**，需显式 `--force`（复审）。退出码：PASS=0、
FAIL=3、NEEDS_REVIEW=4。

## 5. STALE / SUPERSEDED / 失败的复审规则

| 状态 | 判据 | 处理 |
|---|---|---|
| `PENDING` | 无产物 / 产物非法 | **R7 审查任务**：按 §3 完成四项检查并提交 |
| `VERIFIED` | 真实 `decision_gate()` PASS | Loop 消费并推进下一项合法动作 |
| `FAILED` | 任一检查 FAIL | `HOLD`（`assurance_failed`），按既有修复规则处置（`repairs[]`/`R10`），**不得直接继续** |
| `UNKNOWN` | 产物存在但结论未决 | **等待新信息**：Loop 报 `HOLD`（`assurance_unknown`）并记录阻断原因与复审条件，**不重复送审**。只有①摘要变化（STALE）②相关 canonical 证据/分析变化 ③用户显式 `--force` 复审，才重新进入审查任务 |
| `STALE` | `state_digest`/`analysis_digest` 与当前状态不符 | 旧审查**不得复用**；作为新的 R7 审查任务 |
| `SUPERSEDED` | `decision_gate` 判定同一 target+scope 已有更晚结果 | 跳过旧任务，不重复审核；以最新分析为准 |

## 6. Loop 如何发现并消费

`preset_router.assurance_status(state, route_dir)` 读取产物并调用**真实** `decision_gate()`；
`_loop_step()` 据此决定：依赖未审核结果的 planned 实验 `HOLD`（`assurance_pending_dependency`）、
待办审查 → R7 任务、`UNKNOWN` → 等待、`FAILED` → `HOLD`、`VERIFIED` → 下一项合法动作。
`run_preset research-loop` 的 `observed.assurance` / `decision.assurance_*` 会给出每个实验的生命周期、
reviewer、tier、检查结论与复审条件。
