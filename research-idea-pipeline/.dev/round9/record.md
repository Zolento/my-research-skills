# 第九轮：盲区核验（Lead 自查 + 子代理对抗复核）

> 分支 `research-idea-pipeline/skill-rsi-dev`；起点 HEAD `53ea200`。
> 本轮目标：核验**此前各轮没有考虑到的**可能存在 bug 的地方。
> 分工：Lead 自查「无人覆盖的输入/状态层」，同时派出 4 个子代理按互不重叠的范围独立对抗复核
> （报告见 `.dev/audit/R8-A…D-*.md`）。所有修复都遵循「先写失败复现 → 最小修复 → 变异验证」。

## 0. 结果速览

| 项 | 值 |
|---|---|
| Lead 自查确认缺陷 | **4 项**（全部已修 + 回归 + 变异验证） |
| 全量单元测试 | **1820 OK（skipped=3）** |
| `release_check.py` | **PASS（18 步）** |
| 5 个模块 selftest | 全 OK |
| 进程事故 | 并发测试再次损坏 `examples/structural-equivalence/paradigm-candidate.json`（`test_structural_equivalence` 会临时改写它）；已 `git checkout` 恢复并逐次核对 sha256 |

## 1. Lead 自查确认的 4 项缺陷

### 1.1 畸形冻结规则 → 未捕获 `KeyError`（MED）

- **复现**：`freeze_evaluation_rules(sp, {"delta_tolerance": 0.1})`（缺 `min_cases`/`min_runs`/`dimensions`）
  返回 `FROZEN`；随后 `evaluate_candidate(...)` 抛 **`KeyError: 'min_cases'`**（`ablation_verdict` 直接读
  `rules["min_cases"]`）。空 dict 同样抛 `KeyError: 'min_runs'`。
- **根因**：`freeze_evaluation_rules` 接受任意 dict；读取侧也不校验结构。
- **修复**：新增 `_rule_schema_errors()`；冻结时**先用默认值补全再校验**（部分自定义仍可用，非法值直接拒绝）；
  `frozen_rules()` 与 `evaluation_rules_errors()` 对磁盘上手工改写的残缺规则同样判定为不可信 →
  晋级路径统一得到 `PE12` 可诊断拒绝，而不是异常。
- **验证**：`test_a_malformed_frozen_rule_set_is_refused_at_freeze_time`、
  `test_a_partial_custom_rule_set_is_completed_then_frozen`、
  `test_a_hand_edited_incomplete_rule_file_cannot_reach_the_evaluator`；变异（移除 freeze 校验、移除读取校验）各被捕获。

### 1.2 回滚恢复绕过人工批准（HIGH）

- **复现**：P-1 晋升 ACTIVE（有批准）→ P-2 晋升使 P-1 变 `SUPERSEDED` → `rollback(P-2 → P-1)`
  成功恢复 P-1 为 ACTIVE，**完全不校验批准**（恢复路径曾豁免产物门）。
- **影响**：运行中的 Agent 可用回滚把策略放回 ACTIVE，而**不需要任何人工动作**，也绕过批准的有效期。
- **修复**：恢复路径不再豁免；`rollback` 把该策略已存的 L3 凭证引用放进恢复证据，`transition_errors`
  重新执行完整凭证校验（含批准有效期）。
- **验证**：`test_a_rollback_restore_after_the_approval_expired_is_refused`（时钟前跳，期望 `PE15`）、
  `test_a_rollback_restore_with_a_valid_approval_still_works`；变异（恢复重新豁免）被捕获。

### 1.3 恢复失败留下不可重试的半状态（MED）

- **复现**：修复 1.2 之前，`rollback` 先写 rollback/ROLLED_BACK 记录再尝试恢复；恢复失败时留下
  「旧策略已 ROLLED_BACK（终态）+ 目标仍 SUPERSEDED」→ **没有任何 ACTIVE 策略，且无法重试**。
- **修复**：`rollback` **先校验恢复**（`transition_errors(..., authority_ok=True)`）再落盘，整体原子。
- **验证**：同上的过期批准用例同时断言「什么都没写」（P-2 仍 ACTIVE、P-1 仍 SUPERSEDED）；
  变异（移除预校验）被捕获。

### 1.4 非有限数值逃逸为未捕获异常（MED）

- **复现**：报告 `{"unobservable_decisions": NaN}` → `evaluate_candidate` 抛
  **`ValueError: cannot convert float NaN to integer`**（`audit_report` 的 `int(... or 0)`）；
  `ablation_verdict` 对 `cases=inf`/`runs=NaN` 同样抛 `OverflowError`/`ValueError`。
- **附带**：`_numbers_differ(NaN, x)` 恒为 `False`（NaN 比较恒假）→ **声明值一致性检查对 NaN 空转**，
  声明 `mean: NaN` 曾被当作与重算结果一致。
- **修复**：新增容错 `_safe_int()`（NaN/inf/字符串/None → 默认值），用于 `audit_report`、
  `ablation_verdict`、`_recomputed_level`；`_numbers_differ` 对非有限值不再判为相等。
- **验证**：`TestMalformedNumbers`（5 项）；变异（`_safe_int` 不再容错、移除 NaN 判断）各被捕获。

## 2. Lead 自查判定「不是缺陷」的部分（已实测）

| 检查 | 结果 |
|---|---|
| 轨迹存储正文损坏（空行/非 JSON/JSON 数组/BOM/CRLF/尾随空格/超深嵌套） | 严格模式抛 `TrajectoryError`、tolerant 模式出诊断，**无未捕获异常** |
| 组件自产报告能否通过新审计 | `examples/replay/adversarial` 真实报告 `audit_report` **0 errors**，verdict `UNDIFFERENTIATED`（诚实：合成 fixture 无收益） |
| 报告/凭证的 `cases`/`runs` 为 NaN/inf/字符串/布尔 | 全部转为可诊断拒绝，不抛异常 |
| 批准绑定内容摘要（换一份凭证不可复用批准） | 拒绝（`PE15`） |
| 删除批准账本后晋级 | 拒绝（`PE15`，fail closed） |
| 批准不存在的策略 / 批准账本目录是符号链接 | 拒绝（`PE1`/`PE15`） |

## 3. 子代理对抗复核（4 个互不重叠的范围）

| 代号 | 范围 | 报告 |
|---|---|---|
| R8-A | 第八轮新增的批准账本 + 产物存储（锁序、摘要规范化、内容寻址、损坏账本、并发、过期语义、attempt 计数） | `.dev/audit/R8-A-approval-surface.md` |
| R8-B | 被复用的既有权限机制（`execution_gate` / `experiment_execute` / `evidence_outcome` / `state_check`）与新的依赖边、PE15/PE16 与既有 `human_exception`/公平性规则的一致性 | `.dev/audit/R8-B-permission-pipeline.md` |
| R8-C | 集成与契约漂移（`preset_router` 对新生命周期的消费与上报、`release_check` 各步是否仍有意义、文档/registry/schema 与 CLI 的一致性） | `.dev/audit/R8-C-integration-contract.md` |
| R8-D | 测试套件质量（变异测试、通过得「理由不对」的测试、空洞断言、确定性） | `.dev/audit/R8-D-test-quality.md` |

（子代理结论见下文「附录：子代理结论与处置」，Lead 会对每条 CONFIRMED 自行复现后再决定修复。）
