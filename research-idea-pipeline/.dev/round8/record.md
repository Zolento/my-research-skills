# 第八轮：可信晋升与 L3 验证收口

> 分支 `research-idea-pipeline/skill-rsi-dev`；待核验基线 `995758b`（本轮起点）。
> 本轮**未新增架构层级、Preset 或科研状态类型**。
> 方法：先写失败复现 → 最小修复 → 变异测试 → 全量回归。

## 0. 交付与证据

| 项 | 值 |
|---|---|
| 新增测试 | `scripts/test_l3_trust_boundary.py`（31 项） |
| 旧版（`995758b`）运行 | **FAILED（failures=4, errors=24）** — 见 §3.2 归类 |
| 本轮修复后 | **31/31 通过** |
| 全量单元测试 | **1810 OK（skipped=3）** |
| `release_check.py` | **PASS（18 步）** |
| 5 个模块 selftest | 全 OK |
| 变异测试 | 6 项新检查各做一次“架空”，**6/6 被捕获** |

---

## 1. 任务一：L3 信任边界

### 1.1 审计的调用路径

- 直接入口：`record_research_validation()`（REPLAY_EVALUATED/BOUNDED_TRIAL → VALIDATED），
  `promote_to_active()`（VALIDATED → ACTIVE），CLI `validate-research` / `promote` / `validate`。
- 间接入口：`validate_candidate()`（读回已存凭证）、`_transition_locked(..., _AUTHORITY)`、
  `rollback()` 的 `SUPERSEDED → ACTIVE` 恢复路径。
- 全部经 `_artifact_gate_errors()`；其中 `SCHEMA_RESEARCH_VALIDATION` 分支在**每次**校验时
  重新执行 `_validation_errors()` + `approval_errors()`，所以任何路径都不能只靠一次通过。

### 1.2 三个维度必须分开（文件完整性 / 证据真实性 / 评价独立性）

| 维度 | 系统能力 |
|---|---|
| 文件完整性（来源摘要一致、凭证与账本未被改写） | **可验证** |
| 证据真实性（外部真的在真实任务上跑过） | **不可验证**：`synthetic=false`、`runner`、`executor` 都是声明 |
| 评价独立性（评价者与策略作者彼此独立） | **不可验证**：只能检查「executor 不是策略自身/自身路由」 |

### 1.3 修复：生产路径要求人工批准（复用现有权限机制）

**复用** `experiment_execute.Ledger`（本组件已有的 HMAC 密封、append-only、单次使用、
截断检测的权限账本），不新造机制：

- 新增 `approvals_dir()` / `approve_l3()` / `approval_errors()` / `approval_events()`
  与 CLI **`approve-l3 --policy-id <P> --validation <cred> --approver <human> --confirm-human`**。
- 批准事件（`l3-approval@1`）绑定：**凭证内容摘要** + 策略签名 + 冻结规则摘要 + 批准者身份
  + `attested_by: human` + 有效期 + 一条明确的 `verification_limit`（声明这不是密码学证明）。
- `VALIDATED` **要求**该批准；`ACTIVE` **重新**校验（存在、未过期、封印未破、仍绑定同一凭证）。
- **任何自动入口都不写批准**：全仓库只有 CLI 与 selftest 调用 `approve_l3`，控制面无法自我授权。
- 失败码 **`PE15`**；拒绝理由写明「没有人工批准记录 / 已过期 / 没有人类确认 / 批准账本被篡改 /
  批准针对另一个策略版本 / 目录是符号链接 / 未知 policy_id」。

### 1.4 如实声明的边界（不声称已具备自动可信晋升）

- 这是**协议级人工门**，不是密码学证明：Skill 无法独立确认批准者是人；拥有路由写权限者可伪造
  批准记录。因此本系统**不声称具备自动可信晋升**（代码、文档、`verification_limit` 三处同时写明）。
- **不得**把调用方填写的 `synthetic=false` / `executor` 名称 / `isolation_verified=true`
  当作充分真实性证明：测试 `test_flags_alone_are_never_accepted_as_authenticity` 用一份
  「所有标志位都设置、摘要自洽」的凭证证明它仍被拒绝（`PE15`）。

---

## 2. 任务二：实验对照公平性（`PE16`）

每次 L3 评价必须携带可复核的 `equivalence` 记录：

- **受控轴**（两臂必须相同）：`model`、`harness`、`tools`、`visible_data`、`budget`、`task_ids`。
- **对照轴**：必须显式声明（如 `strategy`）且**确实不同**。
- **未声明的环境差异一律拒绝** —— 与 `execution_gate._comparison_errors()` 的
  “undeclared changed variable” 规则一致（本轮实现时先漏了这一条，被自测探针抓出后补齐）。
- **区分执行实例身份与执行环境差异**：`arms[*].instance` 必须**不同**（证明是两次独立执行），
  受控环境轴必须**相同**（证明对照公平）。
- **留存**：`paired_task_ids` 必须与逐 case 执行记录一致；预算与策略版本（`policy_signature`、
  `rules_digest`）随凭证写入产物，可在 `latest_evaluation_artifact()` 中复核。

---

## 3. 任务三：对抗测试

### 3.1 覆盖的伪造路径（每条都断言**明确拒绝原因**）

| 攻击 | 期望原因 |
|---|---|
| 伪造任务来源（摘要取好后替换文件） | 「摘要…不一致」 |
| 内部自洽的假执行凭证 | `PE15` 无人工批准 |
| 旧派遣记录复用（新一轮试运行后复活旧记录） | 「派遣记录…不是最近一次」 |
| 派遣记录已被另一份凭证使用（白盒） | 「已被另一份…使用」 |
| 派遣记录指向另一个策略 / 不存在 | 「派遣…」 |
| 伪造 executor 身份（用策略自身路由名） | 「executor…就是策略自身」 |
| 两臂同一执行实例 | 「执行实例 identity 相同」 |
| 受控轴差异 / 未声明额外轴 / 对照轴无差异 / 缺必需轴 / 配对任务不符 | `PE16` 具体轴名 |
| 篡改策略绑定 / 规则绑定 | 「策略版本…」「凭证绑定的评价规则…」 |
| 批准绑定到另一份凭证 / 已过期 / 无人类确认 / 批准者身份为空 | `PE15` 对应原因 |
| 篡改批准账本（改 approver / 改 expires_at） | `PE15` 账本被篡改 |
| 篡改已存凭证后再晋升 | 摘要不匹配 → 拒绝 |
| 批准不存在的策略 / 批准账本目录是符号链接 | `PE1` / `PE15` |
| CLI 无批准直接 `validate-research` | `PE15`，且无 traceback |

### 3.2 第七轮旧版复现中 13 个 error 的重新归类（诚实修正）

`.dev/round7/OLD_failing_r7.txt`（第七轮测试跑在 `c810a50` 上）共 24 项失败：11 FAIL + 13 ERROR。
逐项按异常类型归类（脚本：`.dev/round8/error_classification.json`）：

| 类别 | 数量 | 说明 |
|---|---|---|
| **接口不兼容**（`AttributeError: module has no attribute …`） | **12** | 第七轮新引入的 API/schema 在旧版根本不存在（`SCHEMA_RESEARCH_VALIDATION`、`record_research_validation`、`frozen_rules`、`RELIABILITY_DIMENSIONS`、`_file_digest` 等）。**这些不是漏洞复现**，只能证明「新接口带来了新检查」。 |
| **真实行为缺口**（`KeyError: 'binding_source'`） | **1** | `test_the_entry_binds_an_unbound_report_and_records_that_it_did`：旧版产物没有 `binding_source` 字段。 |
| 真实缺口复现（11 项 `AssertionError`） | 11 | 失败的**断言**（旧版行为确实不符合新契约）——这些才是真正的行为复现。 |

**结论（修正第七轮的表述）**：第七轮「24/26 失败」的说法在数字上正确，但其中 **12 项是接口不兼容**，
只有 **11 项 FAIL + 1 项 KeyError = 12 项**是真实行为复现。以后应把两者分列。

同样地，第八轮测试跑在**基线 `995758b`** 上：`FAILED (failures=4, errors=24)` ——
4 项 FAIL 是真实信任边界缺口（无人工批准即可自授 L3、CLI 未拦截），
24 项 ERROR 是接口不兼容（`approve_l3` / `approval_events` / `approvals_dir` 等尚不存在）。

---

## 4. 任务四：最终回归与等级

| 检查 | 结果 |
|---|---|
| 单元测试 | **1810 OK（skipped=3）** |
| 端到端（`test_skill_rsi_e2e.py`） | OK（含 research-loop 真实消费） |
| 源码冻结（`source_freeze` selftest + `release_check` 的 .dev 扫描） | OK / PASS |
| 策略晋升与回滚（`test_policy_evolution` + `test_promotion_integrity`） | OK |
| `release_check.py` | **PASS（18 步）** |

**等级严格区分：** 合成回放证据上限 **L2**（`_recomputed_level` 对 `policy-evaluation@1`
永不返回 L3）；`VALIDATED`/`ACTIVE` 需要 **L3 真实科研验证凭证 + 人工批准 + 对照公平记录 +
派遣记录绑定**。

> **L3 现状：未验证。** 本分支**没有真实科研 A/B 评价**；测试中的 L3 凭证是结构化夹具。
> 系统能保证的是「合成证据不得冒充 L3、且 L3 需要人工批准与可复核的对照记录」；
> 系统**不能**证明批准者是人、也不能证明外部真的执行过。**不得把本轮结果宣称为 L3 科研能力提升。**

---

## 5. 源码位置

| 内容 | 位置（`scripts/policy_evolution.py` 除非注明） |
|---|---|
| 人工批准账本（复用 `experiment_execute.Ledger`） | `approvals_dir`、`_approval_seal`、`_read_approvals`、`approval_events` |
| 批准入口与校验 | `approve_l3`、`approval_errors` |
| 公平性校验 | `_equivalence_errors`、`_REQUIRED_EQUIVALENCE_AXES` |
| 派遣记录复用/时效 | `_dispatch_reuse_errors` |
| executor 自身身份 | `_validation_errors` 的 `self_names` 检查 |
| 试运行尝试序号（使两次试运行产物不再折叠） | `begin_bounded_trial` 的 `attempt` 字段 |
| 接入点 | `record_research_validation`、`_artifact_gate_errors`（`SCHEMA_RESEARCH_VALIDATION` 分支） |
| CLI | `approve-l3`（新增）、`validate-research`、`promote`、`validate` |
| 文档 | `references/skill-rsi-policy.md` §5.3.1.1/§5.3.1.2、`presets/strategy-evolution.md` R7 |
| 测试 | `scripts/test_l3_trust_boundary.py`、`scripts/rsi_test_support.py` |

## 6. 仍存在的限制（不假装已解决）

1. **人工批准是协议级门，不是密码学证明**：Skill 无法确认批准者是人；有路由写权限者可伪造批准记录
   与账本密钥。本系统因此**明确不声称自动可信晋升**。
2. `synthetic=false`、`executor` 名称、`isolation_verified=true` 仍是**声明**；系统只能检查
   「不是策略自身」与「两臂名字不同」。
3. 任务真实性与「任务确实来自真实科研场景」不可验证。
4. **L3 未验证**：无真实科研 A/B；测试夹具不代表科研能力。
5. 并发仍只在同机多线程验证；跨进程/跨主机 flock 未验证。
