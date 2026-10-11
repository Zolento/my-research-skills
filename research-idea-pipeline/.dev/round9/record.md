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

### 1.5 基线复现证据（诚实归类）

把本轮新增/加严的测试放到**起点基线 `53ea200`** 上重跑：
`test_promotion_credentials.py` + `test_l3_trust_boundary.py` 共 **9 项失败**，逐项按异常类型归类后
**全部是真实行为复现**（5 项异常型：`KeyError`/`ValueError`/`OverflowError`；4 项断言型），
**没有一项是接口不兼容**。完整输出见 `OLD_failing_r9.txt`。

| 类别 | 数量 | 代表 |
|---|---|---|
| 真实缺口复现（异常） | 5 | `test_a_nan_unobserved_count_does_not_crash_the_evaluator`（ValueError）、`test_recomputed_level_survives_non_finite_gates` |
| 真实缺口复现（断言） | 4 | `test_a_malformed_frozen_rule_set_is_refused_at_freeze_time`、`test_a_rollback_restore_after_the_approval_expired_is_refused` |

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

---

## 附录：子代理结论与处置（Lead 逐条自行复现）

三个子代理报告已落地（`R8-A` 批准面、`R8-B` 权限管线、`R8-C` 集成/契约漂移）；
`R8-D`（测试质量）在本记录写下时仍在运行。下表只列 **Lead 已独立复现并处置** 的项。

### 子代理 A（批准面）

| 编号 | 结论 | Lead 复现 | 处置 |
|---|---|---|---|
| A-1 | `SUPERSEDED→ACTIVE` 恢复绕过人工门 | —（与本人 1.2 重复） | **已在本轮 §1.2 修复**；A 也确认 `0fad638` 后返回 INVALID |
| A-2 | 批准绑定摘要取自产物自身字段，缺失即「匹配任意批准」 | ✅ `approval_errors`（两摘要皆 None）返回 `[]`；伪造 `approval:{}` 的产物 `promote_to_active → ACTIVE` | **已修**：两摘要皆空 → `PE15`；批准绑定的凭证摘要必须能从产物保留的**凭证内容**重算；产物的 `report`/`dispatch_ref`/`task_provenance`/`execution_evidence`/`equivalence`/臂名必须与保留凭证逐字段一致（凭证为唯一事实来源）|
| A-3 | 重复批准 + 取最后一条 + 先写后判 → 孤儿产物砖化一次性派遣记录 | ✅ 0 秒重复批准导致 INVALID/PE15、留下孤儿产物、此后重试永久 PE11 | **已修**：`latest_valid_approval()` 只返回**仍然有效**的那条；`record_research_validation` 拒绝时 `_discard_artifact` 回滚；非正有效期直接在 `approve_l3` 拒绝 |
| A-4 | `policy_id` 未校验（`a/b`、NUL）→ 未捕获 FileNotFoundError/ValueError | ✅ 两者都逃逸 | **已修**：`policy_id_errors()`（单段、`[A-Za-z0-9._-]{0,63}`、禁 `..`/NUL）在 `propose` 与 `_store_artifact` 双重把关 |
| A-5 | `_read_approvals` 不校验账本 `head`，尾部删除不可检测 | ✅ 删除尾部事件后无篡改报告 | **已修**：与 `Ledger` 一致校验 `head` 提交到最后一条事件 |
| A-6 | `approve_l3(expires_in_seconds=10**400)` 抛 OverflowError | ✅ | **已修**：有效期必须为 `(0, 10 年]` 的有限秒数 |
| A-7 | 被拒绝的 `begin_bounded_trial` 写孤儿试运行产物 | ✅ 从 SHADOW 调用 → INVALID/PE10 但 `trials/` 多出一份 | **已修**：拒绝时丢弃；`attempt` 身份保留 |

A 的 NOT-BUGS（Lead 接受，未重复验证）：线程锁序无死锁、并发 `begin_bounded_trial` 单一胜出、
`attempt` 计数、两种摘要格式未混用、账本各类篡改矩阵、NaN/inf/零/负有效期、产物路径围栏。

### 子代理 B（既有权限管线 + 新依赖边）

| 编号 | 结论 | Lead 复现 | 处置 |
|---|---|---|---|
| B-1 | PE16 比较的是**映射里前两个臂**，而非声明的候选/对照臂；`sort_keys=True` 使顺序可被攻击者构造 | ✅（代码级确认） | **已修**：`_equivalence_errors` 接收 `candidate_arm`/`control_arm`，比较声明臂并拒绝与 `equivalence.arms` 不一致的臂集合（两道重叠护栏）|
| B-2 | 批准账本里「合法 JSON 但非对象」的行 → `Ledger.locked()`/读取器抛 TypeError/AttributeError（CLI traceback） | ✅ | **已修**：读取器捕获 `ValueError/TypeError/AttributeError/KeyError`；`approve_l3` 同样捕获 → `PE15` |
| B-3 | `Ledger` 崩溃窗口（events 已 fsync、head 未 rename）永久 brick（`LEDGER_TRUNCATED_OR_INCOMPLETE`） | 接受为**既有机制的可用性限制** | **未改代码**：这是复用机制的 fail-closed 设计；已在下文「仍存在的限制」如实记录（含人工恢复步骤），本轮不新增修复机制 |
| B-4 | PE16 受控轴只查「存在」，全空也能通过 | ✅ | **已修**：受控轴值不得为 `None/""/[]/{}` |
| B-5 | `scheduler_check` 对畸形 `outcome_analysis` 抛 TypeError（`strategy_memory.scheduler_verdict` 未包裹） | ✅ `RAISED: TypeError string indices must be integers` | **已修**：`actual_eig` 调用加守卫 → `EIG_SOURCE_MALFORMED` + FAIL；补 `test_execution_gate.py` 回归 |

B 的 SUSPECTED：`head` 未校验（= A-5，已修）、key 权限/长度未校验（与文档化限制 #1 相邻，未改）、
`eo.digest` 非类型单射（未观察到可利用路径）。

### 子代理 C（集成与契约漂移）

| 编号 | 结论 | 处置 |
|---|---|---|
| C-1 | `research-loop` 对**所有**已应用策略硬编码 `policy_delta.level="L2"`，丢弃记录到的 L3 与人工批准 | **已修**：新增 `active_policy_standing()`（ACTIVE 策略记录到的最高等级 + 是否有人工批准 + 批准者），`preset_router` 上报真实等级与 `policy_approved`；`recorded_strategy_decision` 分支不再谎称 L2（无策略 → level None）；e2e 断言从 L2 改为 L3 并加批准断言 |
| C-2 | 删除 `test_l3_trust_boundary.py` + `test_promotion_credentials.py` 后闸门仍 PASS | **已修**：`EXPECTED_TEST_SUITES` 清单 + `MIN_TESTS` 下限；Skill-RSI 步骤补上三个新套件。实测：删除两个套件 → **FAIL** |
| C-3 | README 仍写旧晋升规则，完全没提 `validate-research`/`approve-l3`/PE15/PE16 | **已修** |
| C-4 | `policy_evolution --help` 的模块 docstring 仍写「没有独立 replay 评价就到不了 ACTIVE」 | **已修** |
| C-5 | `references/skill-rsi-policy.md` §5.1 规则索引止于 PE14；§5.3.1 只提「四个受控入口」 | **已修**（补 PE15/PE16 与 `validate-research`/`approve-l3`）|
| C-6 | `SKILL.md` 与 `presets/strategy-evolution.md` 仍写 `PE1`—`PE14` | **已修** → `PE1`—`PE16` |
| C-7 | `rsi_ablation.py` 仍输出「晋升需要独立 replay 评价」 | **已修** |
| C-8 | registry↔protocol 的 `trigger` 漂移不被检出 | **已修**：`step_preset_library` 增加 16 个预设的 `registry trigger` 逐项比对。实测：把 `strategy-evolution` 改为 `manual` → 步骤 FAIL |
| C-9 | 文档化的 R4→R5→R6 在出货 fixture 上会先 HOLD 再 PE10，文档没有 HOLD 分支 | **已修（文档）**：`presets/strategy-evolution.md` 增加「HOLD 是正常出口」说明；代码行为本身正确（诚实不晋升）|

C 的 SUSPECTED 中「变异测试写真实仓库文件导致并发互相破坏」已在第九轮**两次真实发生**；
**已修**：`test_structural_equivalence._mutate` 用系统临时目录的 flock 串行化（本记录 §0 已记录事故与恢复）。

### 第九轮回归与验证

| 项 | 值 |
|---|---|
| 全量单元测试 | **1841 OK（skipped=3）** |
| `release_check.py` | **PASS（18 步）** |
| 5 个模块 selftest | 全 OK |
| 新增测试 | `test_round9_findings.py`（19 项）+ `test_execution_gate.py` 1 项 + 上一段 4 项 |
| 变异验证 | A-2(批准绑定/内容重算/报告比对)、A-3(丢弃产物)、A-4、A-5、A-6、A-7、B-2、B-4 **各自被捕获**；B-1 的两道护栏互为重点（单独移除任一道仍被另一道拒绝，属纵深防御，非缺陷） |

### 仍存在的限制（不假装已解决）

1. **人工批准是协议级门**，不是密码学证明；有路由写权限者可伪造批准账本与其密钥（第八轮已声明）。
2. **`Ledger` 崩溃窗口**：`events.jsonl` 与 `head` 之间断电会让批准账本进入
   `LEDGER_TRUNCATED_OR_INCOMPLETE`（fail-closed）。恢复需人工核对链完整性后重建 head；
   本轮**不新增自动修复机制**，以免削弱篡改检测。
3. PE16 的受控轴与既有 `execution_gate.FAIR`（`compute_hours`/`data_split`/
   `optimization.tuning_trials`）仍是两套字段：前者面向策略评价，后者面向实验臂；
   未合并（不同域），但因此**没有**互相覆盖。
4. 任务真实性与「外部确实执行过」仍不可验证；**L3 仍未验证**（无真实科研 A/B）。
5. 并发仍只在同机多线程/多进程验证。
