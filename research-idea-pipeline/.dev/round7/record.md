# 第七轮：L2/L3 凭证分离、产物来源链、冻结参数一致性

> 基线：`c810a50`。本轮**未新增架构层级、Preset 或独立评价系统**；Research State、Scheduler、
> Strategy Decision Adapter、Evidence Qualification、PEIG/AALG、Source Freeze 边界全部保留。
> 只做三件事（外加 global 作用域来源）：
> ① 合成回放不得自动获得 L3；② 评价产物必须有可重算的来源链；③ 评价必须用真正冻结的参数，
> 关键科学指标退化或收益证据不足不得晋升；④ global 作用域的跨项目引用必须有独立来源。
>
> 方法：**先建立失败复现，再做最小修复**。
> 旧版证据：`OLD_failing_r7.txt`（26 项中 24 项失败）；新版：26/26 通过。

## 0. 测试证据（供远程核验）

| 项 | 旧版（`c810a50`） | 新版（本轮） |
|---|---|---|
| `test_promotion_credentials.py` | **FAILED**（failures=11, errors=13）→ 24/26 失败 | **OK（26/26）** |
| 全量单元测试 | 1744 OK | **1771 OK（skipped=3）** |
| `release_check.py` | PASS（18 步） | **PASS（18 步）** |
| 5 个模块 `--selftest` | 全 OK | **全 OK** |

## 1. ①② 证据等级混淆与产物来源链

### 1.1 旧版缺陷

- `_recomputed_level()` 对 `SUPPORTED` 的回放报告按「可评维度≥2、runs≥2、cases≥3、runner 非空」
  自动给 **L3**，于是 `合成回放 → SUPPORTED → L3 → VALIDATED → ACTIVE` 可以一路走通。
- `evaluate_candidate()` 直接接受调用方传入的整套 `report`，只检查 schema、`results` 是否存在以及
  报告自带的 `leak_checked`/`isolation_verified` 字段；**声明的各维度均值从不与逐 case 记录比对**，
  `isolation_verified` 缺失时**默认 True**。
- `validate_candidate()` 只要求「有一个 L3 产物」，不区分它是不是回放产物。

### 1.2 新版修复

**凭证类别分离（两类凭证，不是两套架构）：**

| 凭证 | 产出入口 | schema | 等级上限 |
|---|---|---|---|
| 回放凭证 | `evaluate_candidate` | `policy-evaluation@1` | **L2（永不为 L3）** |
| 试运行派遣记录 | `begin_bounded_trial` | `policy-trial@1` | L2 |
| 真实科研验证凭证 | `record_research_validation` | `policy-research-validation@1` | **L3** |

- `_recomputed_level()` 按 `schema` 分派：回放 → 最多 L2；科研验证 → 需
  `SUPPORTED && provenance_ok && independent_ok && dispatch_bound` 才 L3。
- `TARGET_ARTIFACT_SCHEMA`：`VALIDATED`/`ACTIVE` **只接受**真实科研验证凭证；
  回放凭证出现在这两个位置直接 `PE11`（凭证类别不可互换）。
- 新增 `record_research_validation()` 与 CLI `validate-research`。

**报告来源链（从执行记录重算）：**

`audit_report()` 对报告做可重算审计，任一不满足即拒绝且不写产物：
- 各臂 `dimensions` 的 mean/min/max 必须与 `results[*].evaluation.metrics` **重算**结果一致；
- `cases`/`runs_per_case` 必须与记录数、case 集合一致；
- 每个 case 必须**显式** `leak_checked=true` 与 `isolation_verified=true`（缺失不再默认通过）；
- 必须有 schema 与非空具名 `runner`；
- 报告若声明 `policy_id`/`policy_signature`/`rules_digest`，必须与候选与冻结规则一致；
  未声明则由受控入口绑定并记录 `binding_source`。
- 晋升时对产物内嵌报告**再次重算结论**，与产物记录结论不一致即拒绝（不信任存储的结论）。

**真实科研验证凭证的要求**（`_validation_errors`，提交时与晋升时各校验一次）：
`task_provenance.synthetic` 必须显式为 `false`；任务来源文件必须存在、摘要匹配、且不在
`examples/fixtures/replay/synthetic/.dev` 下；`execution_evidence` 必须存在且摘要匹配；
候选臂与对照臂必须有**不同** `executor`；每 case 必须显式 `isolation_verified=true`；
`candidate_arm`/`control_arm` 必须显式声明（避免把退化读成改善）；
`dispatch_ref` 必须指向该策略**实际派遣**的试运行记录（`L3 必须发生在真实试运行之后`）。

### 1.3 CLI 端到端（实测）

```text
freeze-rules → FROZEN
propose      → PROPOSED
SHADOW       → SHADOW L1
evaluate     → REPLAY_EVALUATED L2      # 回放凭证，上限 L2
trial        → BOUNDED_TRIAL L2
validate     → INVALID PE11             # 没有 L3 真实科研验证凭证
validate-research → VALIDATED L3        # 真实凭证
promote      → ACTIVE L3
```

## 2. ③ 冻结参数与科学可靠性约束

### 2.1 旧版缺陷

- `distinguishable()`、`ablation_verdict()`、`_recomputed_level()` 直接读 **编译期默认常量**
  `DEFAULT_EVALUATION_RULES`；即使自定义冻结规则的内容与 digest 完全一致，**真实评价仍用默认参数**。
- `RELIABILITY_DIMENSIONS` 缺 `mechanistic_understanding`：提高 `search_efficiency` 而削弱机制性理解
  只落进 `other_degraded`，**不触发 `REJECTED`**。
- 两臂区间重叠时只写 `caveat`，该维度**仍被标记为 BETTER 并计入晋升收益**——声明的规则没有生效。

### 2.2 新版修复

- 新增 `frozen_rules()`：**重算** digest 且返回规则内容；`distinguishable(..., rules=)`、
  `ablation_verdict(..., rules=)`、`_recomputed_level(..., rules=)` 全部使用候选绑定的那一份；
  `evaluate_candidate`/`record_research_validation` 都传入 `frozen_rules(state)`。
  → 「评价实际使用的参数 = 候选绑定的冻结规则 = 晋升时验证的规则」。
- `RELIABILITY_DIMENSIONS = (mechanistic_understanding, prediction_quality,
  intervention_quality, scientific_novelty)`：四个科学维度全部不可补偿。
- `distinguishable()` 增加 `confident = different and not overlapping`；
  收益只统计 **`direction==BETTER` 且 `confident`** 的维度；
  区间重叠的“收益”单独记为 `uncertain_benefit` 并进入理由，**不计入晋升**。
  可靠性退化即使区间重叠也按 `REJECTED` 处理（fail closed）。

## 3. ④ global 作用域的独立来源

- 旧版：`PE14` 只数候选自述 `evaluation_refs` 里的**项目名个数**（≥2 即通过）。
- 新版：`_attested_projects()` 从 `decision-trajectory.jsonl` 取「同一 trajectory 同时有
  decision 与 qualified outcome」的项目；`PE14` 要求 **≥2 个背书项目**，且候选自述的每个项目
  都必须在背书集合内。项目名不再能替代独立来源。

## 4. 变异测试（证明测试有牙齿）

对四项新保护各做一次“架空”变异，`test_promotion_credentials.py` 的捕获情况：

| 变异 | 结果 | 捕获的测试 |
|---|---|---|
| 回放凭证 L2 上限被移除（`return "L3"`） | FAILED(2) | `test_a_supported_replay_evaluation_is_L2`、`test_recomputed_level_never_returns_L3_for_a_replay_artifact` |
| 指标重算被移除（`if _numbers_differ(...)` → `if False`） | FAILED(1) | `test_declared_means_that_disagree_with_the_records_are_refused` |
| 隔离证明恢复默认放行（`row.get("isolation_verified", True)`） | FAILED(1) | `test_a_report_missing_the_isolation_proof_is_refused` |
| 冻结容差被忽略（改回 `DEFAULT_EVALUATION_RULES`） | FAILED(1) | `test_the_frozen_tolerance_is_used_not_the_default` |

## 5. 复核中发现并修复的**测试**缺陷（诚实记录）

第一版 `TestReportProvenance` 的 `good_report()` 用了**假的** `policy_signature="sig"`，
于是多项测试是因为「绑定不一致」被拒绝而通过，**并没有真的走到它们想验证的那一层**：

- 隔离证明缺失、泄漏证明缺失、case 计数不符 → 全部被绑定错误掩盖；
- 变异 3（隔离默认放行）第一轮**未被捕获**，正是这个原因。

修复：`good_report()` 使用真实 `policy_signature`/`rules_digest`；并把断言从
「状态不是 REPLAY_EVALUATED」收紧为**断言具体诊断文本**（`隔离`/`泄漏`/`重算`/`case`/
`policy_id`/`rules_digest`/`schema`）。修复后四项变异全部被捕获。

## 6. 源码位置

| 内容 | 文件 | 位置 |
|---|---|---|
| 凭证 schema / 类别 / 等级表 | `policy_evolution.py` | `SCHEMA_RESEARCH_VALIDATION`、`TARGET_ARTIFACT_SCHEMA`、`_recomputed_level()` |
| 冻结参数读取 | `policy_evolution.py` | `frozen_rules()`、`evaluation_rules_digest()`、`distinguishable(..., rules=)`、`ablation_verdict(..., rules=)` |
| 报告重算审计 | `policy_evolution.py` | `audit_report()`、`_recompute_arm_dimensions()`、`_numbers_differ()` |
| 真实科研验证凭证 | `policy_evolution.py` | `_validation_errors()`、`record_research_validation()`、`validate_candidate()` |
| 产物门禁（类别 + 重算） | `policy_evolution.py` | `_artifact_gate_errors()` |
| global 背书项目 | `policy_evolution.py` | `_attested_projects()`、`transition_errors()` 的 `PE14` |
| CLI | `policy_evolution.py` | `validate-research`（新增）、`validate`、`trial`、`promote` |
| 文件级摘要 | `policy_evolution.py` | `_file_digest()`（`cg.digest_of` 不接受 bytes） |
| 测试 | `scripts/test_promotion_credentials.py`（新，26 项）、`scripts/rsi_test_support.py`（共享夹具） |

## 7. 契约变更（下游需注意）

1. `validate_candidate()` 现在**只接受**已记录的 L3 科研验证凭证；旧调用会得到明确的 `PE11`。
2. 新增 `record_research_validation(state_path, policy_id, credential)` 与
   CLI `validate-research --validation <file>`。
3. 回放评价报告必须自带逐 case `evaluation.metrics`、显式隔离/泄漏证明、与记录一致的维度摘要，
   否则 `evaluate_candidate` 直接 `INVALID`。
4. `_recomputed_level(gates, verdict, *, schema, rules)` 与 `distinguishable(..., rules=)`、
   `ablation_verdict(..., rules=)` 新增参数。
5. 文档同步：`references/skill-rsi-policy.md` §5.3.1–5.3.3、`presets/strategy-evolution.md` R6–R10。

## 8. 尚未解决的限制（不假装已解决）

1. **凭证仍是「防篡改记录」，不是外部证明。** 有路由写权限者可伪造一份**内部自洽**的
   L3 凭证（真实存在的任务文件 + 日志 + 两个 executor 名 + 派遣引用）。本轮把
   「自述布尔」变成「可重算 + 必须绑定真实文件与派遣」，但没有密码学级别的第三方签名。
2. `task_provenance.synthetic=false` 是**声明**；系统只能验证来源文件存在、摘要一致、不在
   合成目录，不能独立判断该任务是否真的来自真实科研场景。
3. `executor` 的“独立性”只做到「两个臂的执行者名不同」，不是身份认证。
4. 回放评价仍由调用方提供报告（`audit_report` 只能保证报告与其自身记录自洽）。
5. **并发仍只在同机多线程验证**；跨进程/跨主机 flock 未验证。
6. L1/L2/L3 严格区分：本轮所有**自动化**结论仍是回放/合成证据，其等级上限被固定为 L2；
   L3 只有在提交真实科研验证凭证时才可能出现，本轮测试中的 L3 凭证是**测试夹具**，
   不代表本项目已获得 L3 科研能力提升。
