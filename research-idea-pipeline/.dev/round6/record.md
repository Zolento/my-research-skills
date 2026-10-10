# 第六轮：晋升证据可信性与评价正确性修复

> 基线：`198a420e162062576994269f7e5a958174c4fc8d`（该提交之后仅 `AGENTS.md` 增加 §21，代码一致）。
> 本轮**未新增**架构层级、Preset 或独立评价系统；Research State、Scheduler、
> Strategy Decision Adapter、Evidence Qualification、PEIG/AALG、Source Freeze 边界全部保留。
>
> 方法：**先建立旧版失败复现，再做最小修复**。
> 旧版结果：`OLD_failing.txt`（31 项中 23 项失败）；新版结果：`NEW_passing.txt`（31/31 通过）。

## 0. 测试证据

| 项 | 旧版（`198a420`） | 新版（本轮） |
|---|---|---|
| `test_promotion_integrity.py` | **FAILED**（failures=15, errors=8）→ 23/31 失败 | **OK**（31/31） |
| 全量单元测试 | 1695 OK | **1739 OK（skipped=3）** |
| `release_check.py` | PASS（18 步） | **PASS（18 步）** |
| 5 个模块 `--selftest` | 全 OK | **全 OK** |

新增 `scripts/test_promotion_integrity.py` 的 31 项里，23 项在旧版真实失败，逐项对应下文缺陷；
其余 8 项为新受控入口的验收测试（旧版对应 API 不存在，其等价伪造路径由 23 项中的
「整梯只用布尔」一项覆盖）。

---

## 1. P0-A Policy Promotion 绕过

**旧版复现**（`OLD_failing.txt`）：
- `test_all_true_booleans_cannot_reach_replay_evaluated`：SHADOW 之后直接
  `transition(... "REPLAY_EVALUATED", evidence={全部字段 True})` → 旧版返回 `REPLAY_EVALUATED`。
- `test_the_whole_ladder_cannot_climb_on_booleans_alone`：`REPLAY_EVALUATED → BOUNDED_TRIAL →
  VALIDATED → ACTIVE` 整梯只用调用方自述布尔即可走通，旧版写出 ACTIVE。
- `test_a_missing_evaluation_record_blocks_validated`：**完全没有评价产物**也能到 `VALIDATED`。
- `test_a_fabricated_report_is_not_an_execution_record` / `..._without_the_ablation_schema_...`：
  手写报告（无逐 case 结果、无 schema）→ 旧版 `REPLAY_EVALUATED`。
- `test_the_cli_cannot_forge_a_promotion`：`policy_evolution.py transition --to ACTIVE --reason
  '{...全 True...}'` → 旧版直接晋升。
- 旧版根因：`transition_errors()` 只做 `key not in evidence` 的**字段存在性**检查，
  数值只看 `is False`；`level` 由调用方传入；没有任何产物、来源、摘要或绑定校验。

**新版修复**（`scripts/policy_evolution.py`）：
- `GATED_TARGETS`（`:762`）+ 模块私有 `_AUTHORITY`：`transition()`（`:1042`）对
  `REPLAY_EVALUATED/BOUNDED_TRIAL/VALIDATED/ACTIVE` 一律拒绝，除非来自受控入口；
  `transition_errors()`（`:938`）对无授权调用返回 `PE11`，**不再读取自述布尔**。
- 四个受控入口：`evaluate_candidate()`（`:1234`）、`begin_bounded_trial()`（`:1324`）、
  `validate_candidate()`（`:1371`）、`promote_to_active()`（`:1392`）。
- 评价产物：`_store_artifact()` / `_read_artifact()`（`:824`）写入
  `<route>/policy/evaluations|trials/<policy>.<digest>.json`，转换记录只存**引用**；
  `_artifact_gate_errors()`（`:882`）逐项核验：
  | 要素 | 实现 |
  |---|---|
  | 明确来源 | realpath 必须落在策略存储目录内，越界/符号链接逃逸拒绝 |
  | 完整性摘要 | 内容重算 digest 比对；引用声明的 digest 也必须一致 |
  | 策略版本绑定 | `policy_id` + `policy_signature` + `policy_schema_version` 必须匹配候选 |
  | 冻结评价规则 | 产物 `rules_digest` == 当前重算 digest == 候选绑定 digest |
  | 可信执行记录 | 报告必须有 `schema`、逐 case `results`（含 `leak_checked`/`isolation_verified`）、具名 `runner` |
  | 证据等级 | `_recomputed_level()`（`:854`）从门与结论**重算**，不接受自报；`TARGET_LEVEL`（`:764`）核验目标等级 |
- CLI：`transition --to <受控目标>` 直接拒绝并指向 `evaluate/trial/validate/promote`；
  新增 `trial` / `validate` / `promote` 子命令。

**测试**：31 项中的 10 项（`TestNoBooleanPromotion`、`TestEvaluationArtifactBinding`），
覆盖伪造全 True、伪造报告、缺失评价记录、错误候选绑定、评价结果替换、越界产物路径、
评价规则篡改、整梯布尔旁路、CLI 旁路、受控全流程可走通。

---

## 2. P0-B Replay 收益方向错误

**旧版复现**：
- `test_only_efficiency_degradation_is_not_supported`：效率维度**退化**（0.1 vs 0.9）而其他维度持平
  → 旧版 `SUPPORTED`（只看「有差异」，不看方向）。
- `test_only_a_non_critical_dimension_improves_is_not_supported`：只有非收益维度改善 → 旧版 `SUPPORTED`。
- `test_unobserved_decisions_block_support`：4 个 `NO_SUPPORT` → 旧版仍 `SUPPORTED`（只加一句 reason）。
- `test_an_insufficient_sample_is_never_supported`：`cases=2, runs=1` 且 `sufficient_sample=true`
  → 旧版 `SUPPORTED`（直接信任报告字段）。
- `test_better_is_distinguished_from_merely_different`：旧版没有方向概念。
- 旧版根因：`ablation_verdict()` 把「超出容差」当成「有收益」；样本充分性直接读报告字段；
  未观测只记 reason 不改结论。

**新版修复**：
- `distinguishable()`（`:1108`）为每个维度给出 `direction = BETTER | WORSE | NONE`，
  容差取自冻结规则；`DIFFERENT` 与 `BETTER` 彻底分离。
- `ablation_verdict()`（`:1147`）：
  - 结构非法 / 缺对照臂 / schema 非 `replay-ablation@1` / 无逐 case 执行记录 → `INVALID`；
  - 隔离未通过或**科学可靠性维度**（`RELIABILITY_DIMENSIONS`, `:758`）`WORSE` → `REJECTED`；
  - 样本不足（`cases`/`runs`/可评维度按冻结规则**重算**，不信 `sufficient_sample`）
    → `INSUFFICIENT_SAMPLE`；未观测 → `INSUFFICIENT_COVERAGE`；
  - 无任何**收益维度**（`BENEFIT_DIMENSIONS`, `:756`）`BETTER` → `UNDIFFERENTIATED`；
  - 仅当「≥1 收益维度正向改善 且 可靠性未退化 且 样本充分 且 无未观测」→ `SUPPORTED`。
- 报告必须带 `schema`；`evaluate_candidate` 的门全部由结论重算，忽略兼容参数。

**测试**：`TestBenefitDirection` 9 项（仅效率退化、仅非关键改善、无正向、可靠性退化压过效率收益、
样本不足、未观测、伪造报告、方向判定、真实收益受支持）。

---

## 3. P1-A PT9 引用验证

**旧版复现**：`test_every_reference_must_be_backed_not_just_one`——
`independent_evaluation_refs=["DT-a","DT-ghost"]`，只有第一个有来源 → 旧版 `ALLOW`
（`independent_backed = any(...)`）。

**新版修复**（`scripts/policy_transfer.py:1411`）：改为**逐项**核验，
`unbacked_refs` 列出每个没有来源支持的引用，`PT9` 说明每一项为何不成立，并区分：
- 引用为空 / 无 id；
- 「只是项目名」——该项目没有「决策 + 合格 outcome」的轨迹，**不能替代独立评价证明**；
- 既非背书轨迹也非背书项目。
跨项目数量门槛仍要求 ≥2 个**背书**项目，自述 `evidence_projects` 不得代替。

**测试**：`TestPT9PerReference` 2 项（其中 1 项旧版失败、1 项为回归保护）。

---

## 4. P1-B 评价规则冻结与并发转换

**旧版复现**：
- `test_a_stale_digest_field_cannot_mask_edited_rules`：改写 `rules.delta_tolerance` 而**保留旧
  `digest` 字段** → 旧版 `evaluation_rules_digest()` 原样返回旧 digest，判为「未变」。
- `test_evaluation_refuses_a_candidate_bound_to_other_rules`：候选绑定规则 A，随后替换规则为 B
  → 旧版仍 `REPLAY_EVALUATED`（评价只读当前文件，不比候选绑定）。
- `test_concurrent_promotions_yield_one_active_policy`：4 线程同时 `promote_to_active`
  → 旧版追加 **4 条** ACTIVE 转换记录（快照在锁外读取 → TOCTOU）。

**新版修复**：
- `evaluation_rules_digest()`：**重算** digest 并与存储值比对，不一致返回 `None`（不可信）；
  `evaluation_rules_errors()`（`:721`）给出 `PE12` 诊断；`freeze_evaluation_rules()` 遇到
  内容与 digest 不一致时返回 `INVALID` 而不是 `ALREADY_FROZEN`。
- 评价与晋升都要求 `候选绑定 digest == 当前重算 digest`，否则 `PE12`。
- `policy_lock()`（`:773`）+ `append_chained(..., lock_held=True)`（`decision_trajectory.py:232`）：
  策略存储的**校验 → 追加 → supersede → 快照**在同一临界区内；
  `propose` / `transition` / `rollback` / 三个受控入口全部持锁。

**测试**：`TestFrozenRulesIntegrity` 3 项 + `TestEvaluationArtifactBinding` 中的规则篡改项。

---

## 5. P2 损坏的 Head 文件

**旧版复现**：`test_a_head_with_invalid_ascii_is_a_trajectory_error` /
`test_a_tolerant_read_reports_the_head_problem`——`.head` 写入非 ASCII 字节后
`load_records()` 抛出**未捕获的** `UnicodeDecodeError` traceback。
（合法 ASCII 但截断的 `.head` 旧版已能报 `TrajectoryError`。）

**新版修复**（`scripts/decision_trajectory.py:188`）：`head.read_text(encoding="ascii")` 包在
`try/except (UnicodeDecodeError, OSError)` 中；不可读/非 ASCII/截断/不可读权限 →
严格模式抛 `TrajectoryError`（`DT0` 诊断），tolerant 模式返回诊断而不抛。

**测试**：`TestDamagedHead` 3 项。

---

## 6. 源码位置汇总

| 缺陷 | 文件 | 位置 |
|---|---|---|
| P0-A 受控目标 / 授权 | `policy_evolution.py` | `GATED_TARGETS` `:762`、`TARGET_LEVEL` `:764`、`transition()` `:1042`、`transition_errors()` `:938` |
| P0-A 评价产物 | `policy_evolution.py` | `_read_artifact` `:824`、`_artifact_gate_errors` `:882`、`latest_evaluation_artifact` `:867` |
| P0-A 受控入口 | `policy_evolution.py` | `evaluate_candidate` `:1234`、`begin_bounded_trial` `:1324`、`validate_candidate` `:1371`、`promote_to_active` `:1392` |
| P0-B 方向与结论 | `policy_evolution.py` | `distinguishable` `:1108`、`ablation_verdict` `:1147`、`BENEFIT_DIMENSIONS` `:756`、`RELIABILITY_DIMENSIONS` `:758` |
| P1-A PT9 | `policy_transfer.py` | `_evidence_level_errors` `:1346`，`unbacked_refs` `:1411` |
| P1-B 规则完整性 | `policy_evolution.py` | `evaluation_rules_errors` `:721`、`evaluation_rules_digest` |
| P1-B 原子性 | `policy_evolution.py` / `decision_trajectory.py` | `policy_lock` `:773`、`_transition_locked` `:1010`、`append_chained(lock_held)` `:232` |
| P2 损坏 head | `decision_trajectory.py` | `:188` |
| CLI | `policy_evolution.py` | `build_parser` + `main`（`trial`/`validate`/`promote`，`transition` 拒绝受控目标） |

## 7. 契约变更（需要下游注意）

1. `transition_errors(records, policy_id, target, evidence)` →
   `transition_errors(state_path, records, policy_id, target, evidence, *, authority_ok=False)`。
2. 受控目标不能再用 `transition()` 达到；必须走四个受控入口。
3. `evaluate_candidate()` 的 `independent/leakage_checked/reproducible` 兼容参数**被忽略**，
   门由报告重算。
4. 评价报告现在必须带 `schema`、逐 case `results` 与具名 `runner` 才能达到 L3。
5. 文档同步：`references/skill-rsi-policy.md` §5.3/§5.3.1/§5.3.2、
   `presets/strategy-evolution.md` R6–R10 命令表。

## 8. 尚未解决的限制（不假装已解决）

1. **产物是防篡改记录，不是「外部评价者确实运行过」的证明。** 有路由写权限者可以伪造一份
   *内部自洽* 的报告 + 产物对（摘要、绑定、门都会自洽）。产物保证的是：来源路径受约束、
   内容自写入未被改动、结论与报告一致、绑定到具体策略版本与冻结规则。
2. **`evaluate_candidate` 的报告仍由调用方提供**（回放运行器产出）。本轮把「报告字段是否可信」
   改成「结论必须由报告重算 + 报告必须带执行记录」，但没有密码学级别的运行器签名。
3. **并发只验证了同机多线程**；跨进程/跨主机 flock 语义未验证。
4. **`PE14`（global 作用域）仍读候选自述的 `evaluation_refs` 项目数**，未接入轨迹库的
   「背书项目」判定（PT9 已接入）。局部成功升级全局的门槛因此弱于 PT9。
5. L1/L2/L3 的区分保持严格：本轮所有结论仍是回放/合成证据，**不构成 L3 科研能力提升**。

## 9. 独立复核：测试确实复现旧版错误

为避免「只在修复后通过」，把**同一份新版测试文件**放到 **基线 `198a420` 的源码**上重跑
（`git archive 198a420 research-idea-pipeline` 后的干净副本 + 新版 `test_promotion_integrity.py`）：

```text
Ran 31 tests in 0.092s
FAILED (failures=14, errors=9)     # 23/31 失败
```

同一文件在本轮修复后的树上：`Ran 31 tests ... OK`（31/31）。
因此这 23 项是旧版行为的真实复现，而不是修复后的追认。
