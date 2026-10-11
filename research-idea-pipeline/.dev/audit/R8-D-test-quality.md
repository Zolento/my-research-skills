# R8-D test quality

HEAD: 53ea2006b010b98d323e6be04467aa4b5998f8af (pinned revision audited)
Branch: research-idea-pipeline/skill-rsi-dev

> Note on the moving worktree. The live worktree advanced during this audit: at the start
> `HEAD` was `53ea2006`, and by the end it was `dda4fe3` ("close the findings from the
> round-nine subagent audits"), with `0fad638` and `389e36b` in between. To keep every claim
> reproducible I extracted the pinned revision from git (`git archive 53ea2006`) into
> `/tmp/r8d_pin_ws` and ran everything there. Findings are against `53ea2006`.
>
> Re-check against the live branch: I re-applied 12 of the 13 surviving mutations to a clean
> `dda4fe3` export and ran the full suite again — **all 12 still survive**
> (`M3b, M4, M6, M7, M8, M10, M23, M24, M28, D5, P1, P3` → `OK (skipped=5)`). `M27` could
> not be re-applied verbatim (its anchor string now occurs twice in the changed
> `approval_errors`). So none of the gaps below were closed by the round-nine fix commits.

## Method

- Baseline, from the component root: `python3 -m unittest discover -s scripts -p 'test_*.py'`
  → `Ran 1810 tests ... OK (skipped=5)`.
- Hermetic mutation loop: for each mutation, a fresh copy of the pinned tree, one literal
  string replacement in one source file, full suite, then discard the copy. No mutation ever
  ran against the real worktree; the real tree was never modified.
- 43 mutations applied: 25 in `policy_evolution.py`, 5 in `decision_trajectory.py`,
  3 in `policy_transfer.py`, 4 in `source_freeze.py`, 1 in `rsi_ablation.py`.
  Result: **30 killed, 13 survived.**
- Determinism: two default full-suite runs plus `PYTHONHASHSEED=0/1/424242` all produced
  `Ran 1810 tests ... OK (skipped=5)` — no order/timing/hash dependence observed.

## SURVIVING MUTATIONS (coverage gaps)

### D-1 L3 research-validation credential accepts a missing `isolation_verified` [HIGH]
- mutation (`scripts/policy_evolution.py`, `_validation_errors`, ~L1242):
  `if not isinstance(row, dict) or row.get("isolation_verified") is not True:`
  → `if not isinstance(row, dict) or row.get("isolation_verified") is False:`
- observed: full suite `Ran 1810 tests ... OK (skipped=5)`, 0 failures.
- concrete demonstration (approved credential, every `isolation_verified` key deleted):
  - baseline: `status: INVALID`, diagnostics `PE11 ... policy 的 case 缺少隔离验证证明（必须显式为 true）` (×12);
  - under the mutation: `status: VALIDATED`, `diagnostics: []`.
- should have been caught by: `test_a_validation_without_isolation_proof_is_refused`
  (`scripts/test_promotion_credentials.py`) — it passes `isolation=False`, i.e. an *explicit*
  `False`, which the loosened check still rejects. The report path has the missing-key variant
  (`report(drop_isolation=True)`, caught by mutation M3a), the credential path does not.
  The test also passes under the mutation: `Ran 1 test ... OK`.

### D-2 Promotion-time re-audit ignores the frozen rule set [HIGH]
- mutation (`scripts/policy_evolution.py`, `_artifact_gate_errors`, ~L1394):
  `rules = frozen_rules(state_path) or DEFAULT_EVALUATION_RULES` → `rules = DEFAULT_EVALUATION_RULES`
- observed: full suite `OK (skipped=5)`, 0 failures.
- concrete demonstration (freeze `delta_tolerance=0.5`, store a supported replay artifact,
  then rewrite the stored records down to a 0.3 delta and re-run the gate):
  - baseline: 4 diagnostics, incl. `产物记录的结论 'SUPPORTED' 与根据其执行记录重算的 'UNDIFFERENTIATED' 不一致`
    and `REPLAY_EVALUATED 需要 L2 级证据，产物只达到 L1`;
  - under the mutation: `gate diagnostics: []` — the tampered artifact is accepted, because
    the gate re-audits under the default tolerance `0.05`.
- should have been caught by: `TestFrozenParameters.test_the_frozen_tolerance_is_used_not_the_default`
  only calls `ablation_verdict(..., rules=frozen_rules(...))`; `evaluate_candidate` uses frozen
  rules at eval time, and `test_an_artifact_whose_report_no_longer_recomputes_is_refused`
  tampers only under **default** rules. No test tampers a stored artifact under a custom frozen
  rule set and re-runs the promotion gate.

### D-3 Overlapping ranges are counted as a confident benefit [MED]
- mutation (`scripts/policy_evolution.py`, `distinguishable`, ~L1922):
  `confident = different and not overlapping` → `confident = different`
- observed: full suite `OK (skipped=5)`, 0 failures.
- should have been caught by: `test_an_overlapping_benefit_is_not_counted_as_evidence`
  (`scripts/test_promotion_credentials.py`) — it is vacuous w.r.t. overlap (see D-14). The
  test passes under the mutation: `Ran 1 test ... OK`.

### D-4 Cross-arm case-set comparison skipped in `audit_report` [MED]
- mutation (`scripts/policy_evolution.py`, `audit_report`, ~L1081):
  `if len(case_sets) > 1 and len(set(map(frozenset, case_sets.values()))) > 1:` → `if False:`
- observed: full suite `OK (skipped=5)`, 0 failures.
- baseline still detects the shape directly: `audit_report(...)` with candidate cases `C0..C2`
  and control cases `W0..W2` returns `各臂执行的 case 集合不一致：无法配对比较`.
- should have been caught by: `test_arms_running_different_case_sets_are_refused` drives the
  **credential** path (`_validation_errors`, L1258); that site's own mutation (M21) *is* caught.
  No test drives a cross-arm mismatch through `evaluate_candidate`/`audit_report`.

### D-5 `cases × runs` record-count check skipped in `audit_report` [MED]
- mutation (`scripts/policy_evolution.py`, `audit_report`, ~L1076):
  `if cases and runs and len(results) != cases * runs:` → `if False:`
- observed: full suite `OK (skipped=5)`, 0 failures.
- baseline still detects the shape directly: `cases=3, runs_per_case=3` with 6 rows per arm
  returns `rsi_full 的执行记录数 6 与 cases×runs (3×3) 不一致` (and the same for `full_cie`).
- should have been caught by: `test_a_report_whose_case_count_disagrees_with_the_records_is_refused`
  sets `cases = 99`, which the *distinct case-id* check (L1074) catches first; no test keeps the
  distinct ids equal while `len(results) != cases*runs`.

### D-6 Non-SUPPORTED research-validation verdict accepted by `_validation_errors` [HIGH]
- mutation (`scripts/policy_evolution.py`, `_validation_errors`, ~L1271):
  `if verdict.get("verdict") != "SUPPORTED":` → `if False:`
- observed: full suite `OK (skipped=5)`, 0 failures.
- concrete demonstration (same credential as the test, **plus a valid human approval**):
  - baseline: `status: INVALID`, `evaluations before/after: 1 / 1`, diagnostic
    `科研验证结论是 'REJECTED'，不是 SUPPORTED：科学可靠性维度退化：mechanistic_understanding`;
  - under the mutation: `status: INVALID` **but** `evaluations before/after: 1 / 2` — the
    refused credential was written to the credential store before the later L3 gate rejected it.
- should have been caught by: `test_a_non_supported_credential_leaves_no_artifact_behind`
  (`scripts/test_promotion_credentials.py`). It constructs no approval, so under the mutation the
  PE15 approval gate refuses first and `before == after` still holds. The test passes under the
  mutation: `Ran 1 test ... OK`. This is a real store-integrity gap: with an approval present the
  "refused credential must not be stored" invariant is silently lost.

### D-7 Trial level ignores `budget_expanded` / `hard_gates_unchanged` [MED]
- mutation (`scripts/policy_evolution.py`, `_recomputed_level`, ~L1318-1320):
  ```python
  safe = (bool(gates.get("dispatch_record"))
          and not gates.get("budget_expanded")
          and bool(gates.get("hard_gates_unchanged")))
  ```
  → `safe = bool(gates.get("dispatch_record"))`
- observed: full suite `OK (skipped=5)`, 0 failures.
- baseline still rejects the tampered artifact:
  `_recomputed_level(trial, budget_expanded=True) = L1`.
- should have been caught by: `test_the_bounded_trial_may_not_expand_resources`
  (`scripts/test_policy_evolution.py`) only calls `begin_bounded_trial(budget_expanded=True)`,
  which is refused by the caller before any artifact exists. No test tampers a *stored* trial
  artifact and re-checks its recomputed level. The test passes under the mutation: `Ran 1 test ... OK`.

### D-8 Approval binding to the policy signature / frozen rules ignored [MED]
- mutation (`scripts/policy_evolution.py`, `approval_errors`, ~L1583):
  `if signature is not None and event.get("policy_signature") != signature:` → `if False and ...`
- observed: full suite `OK (skipped=5)`, 0 failures.
- should have been caught by: `test_promotion_reverifies_the_approval`
  (`scripts/test_l3_trust_boundary.py`) only expires the approval. No test presents an approval
  issued for another policy signature or another frozen rules digest, even though
  `approve_l3` records both. (The credential-digest binding *is* covered by
  `test_an_approval_for_another_credential_does_not_authorize_this_one`.)

### D-9 Global scope allows zero attested projects [HIGH]
- mutation (`scripts/policy_evolution.py`, `transition_errors`, ~L1753):
  `if len(attested) < 2:` → `if len(attested) < 0:`
- observed: full suite `OK (skipped=5)`, 0 failures.
- concrete demonstration (global-scope policy with **no** `evaluation_refs` and no trajectories):
  - baseline: `status: INVALID`, `PE14 ... global 作用域需要 ≥2 个有「决策 + 合格 outcome」轨迹的背书项目；当前背书项目 []`;
  - under the mutation: `status: ACTIVE, level: L3`.
- should have been caught by: `test_a_global_scope_cannot_be_backed_by_one_project`
  supplies `evaluation_refs=[{... "project": "A"}]`, so the `named - attested` "unbacked"
  branch also emits PE14 and the assertion passes through that second branch. The test passes
  under the mutation: `Ran 1 test ... OK`.

### D-10 Stale `outcome.at_state_version` accepted [MED]
- mutation (`scripts/decision_trajectory.py`, `_outcome_errors`, ~L685-686):
  the `record["at_state_version"] < decision_version` guard → `if False:`
- observed: full suite `OK (skipped=5)`, 0 failures.
- should have been caught by: `test_stale_state_is_refused`
  (`scripts/test_decision_trajectory.py`) exercises the decision record's `context.state_version`
  (DT4 in `_decision_errors`), not the outcome record's `at_state_version` (DT4 in
  `_outcome_errors`). No test covers the outcome-side stale-state guard.

### D-11 Broad transfer scope with fewer than 2 attested projects accepted [MED]
- mutation (`scripts/policy_transfer.py`, `_evidence_level_errors`, ~L1430):
  `if len(attested_projects) < 2:` → `if False:`
- observed: full suite `OK (skipped=5)`, 0 failures.
- should have been caught by: the broad-scope tests all supply unbacked projects/refs, so
  `unbacked` or `unbacked_refs` still blocks; none supplies a broad scope whose independent
  refs are backed but resolve to a single project (which is the only shape this check guards).

### D-12 Self-declared evidence projects accepted without trajectories [LOW, masked]
- mutation (`scripts/policy_transfer.py`, `_evidence_level_errors`, ~L1436): `if unbacked:` → `if False:`
- observed: full suite `OK (skipped=5)`, 0 failures.
- should have been caught by: `test_project_names_are_not_independent_evaluation_evidence`
  (`scripts/test_promotion_integrity.py`) still blocks via the `<2 attested projects` and
  `not independent and <2` branches. The check is not isolatable with the existing fixtures.

### D-13 Artifact gate accepts a non-SUPPORTED evaluation verdict [LOW, redundant]
- mutation (`scripts/policy_evolution.py`, `_artifact_gate_errors`, ~L1436):
  `if not using_trial and verdict.get("verdict") != "SUPPORTED":` → `if False:`
- observed: full suite `OK (skipped=5)`, 0 failures.
- should have been caught by: no test isolates it; `_recomputed_level` already forces L1 for a
  non-SUPPORTED verdict, and the level-rank check still refuses. The mutation that removes that
  backstop (M19) is caught by 29 tests, so this is defence-in-depth rather than an exploitable gap.

## WEAK OR MISLEADING TESTS

### D-14 `test_an_overlapping_benefit_is_not_counted_as_evidence` is vacuous
- file: `scripts/test_promotion_credentials.py` (TestFrozenParameters, ~L476)
- why it passes for the wrong reason: the docstring/comment says "force overlapping ranges by
  declaring wide min/max on the same means", but there is no such code. The `report()` helper's
  `arm_block` sets `min = max = mean`, so the ranges do not overlap; the test then asserts only
  `outcome["verdict"] != "SUPPORTED"`, which is satisfied by an unrelated rule.
- demonstration (baseline, pinned):
  ```
  rsi_full: mean=0.9 min=0.9 max=0.9  (min==max)
  full_cie: mean=0.3 min=0.3 max=0.3  (min==max)
  distinguishable: {"delta": 0.6, "overlapping": false, "direction": "BETTER", "confident": true, "status": "DISTINGUISHABLE"}
  verdict = INSUFFICIENT_SAMPLE | reasons = ['样本不足（cases=2, runs=2, 可评维度 1）：不得宣称策略提升']
  ```
  The refusal is sample size (`cases=2 < min_cases=3`), not overlap. Confirmed by D-3: mutation
  M6 (overlap counted as confident) survives and this exact test still passes.

### D-15 `test_a_non_supported_credential_leaves_no_artifact_behind` does not isolate its target
- file: `scripts/test_promotion_credentials.py` (TestCredentialChainGaps, ~L568)
- why it passes for the wrong reason: it never approves the credential, so the store path is
  shielded by the PE15 approval gate. Under mutation M10 the assertion `before == after` still
  holds because a *different* check (missing approval) refuses instead. Adding the approval
  exposes the lost invariant: the artifact is written (D-6).
- demonstration: `Ran 1 test ... OK` under M10; baseline-vs-M10 with an approval gives
  `1/1` vs `1/2` stored evaluations.

### D-16 `test_the_bounded_trial_may_not_expand_resources` claims more than it checks
- file: `scripts/test_policy_evolution.py` (TestLifecycleAndPromotion, ~L281)
- why it passes for the wrong reason: the name/claim is about the bounded-trial level
  recomputation, but the test only exercises the caller-side validation inside
  `begin_bounded_trial`. The stored-artifact guard in `_recomputed_level` is never reached.
- demonstration: mutation M24 survives the full suite and this test passes under it
  (`Ran 1 test ... OK`); baseline `_recomputed_level(trial, budget_expanded=True) = L1`.

### D-17 `test_a_global_scope_cannot_be_backed_by_one_project` does not isolate the `<2` branch
- file: `scripts/test_policy_evolution.py` (TestLifecycleAndPromotion, ~L291)
- why it passes for the wrong reason: with `evaluation_refs=[{project:"A"}]` two independent
  branches emit PE14 (`len(attested) < 2` and `named - attested`); the assertion cannot tell
  which fired.
- demonstration: mutation M28 survives and this test passes under it (`Ran 1 test ... OK`);
  with no refs at all, baseline blocks and M28 promotes to ACTIVE/L3 (D-9).

### D-18 `test_a_validation_without_isolation_proof_is_refused` only tests explicit `False`
- file: `scripts/test_promotion_credentials.py` (TestResearchValidationCredential, ~L313)
- why it passes for the wrong reason: `isolation=False` produces `"isolation_verified": False`;
  the missing-key case is untested, which is exactly what D-1 exploits.
- demonstration: `Ran 1 test ... OK` under M3b; with an approved credential that omits the key,
  baseline refuses and M3b returns VALIDATED.

### D-19 Four module selftests are never run by the suite
- files: `scripts/policy_evolution.py`, `scripts/source_freeze.py`, `scripts/decision_trajectory.py`,
  `scripts/rsi_ablation.py` each define `selftest()`, but `python3 -m unittest discover -s scripts`
  never invokes them. Only `policy_transfer --selftest` is exercised (`test_selftest_flag_passes`
  in `scripts/test_policy_transfer.py`). All four pass when run by hand
  (`python3 scripts/policy_evolution.py --selftest` → `selftest OK`, etc.).
- consequence: a regression inside them is invisible to the suite, and `rsi_ablation.level_report`
  cites "decision_trajectory / policy_evolution / source_freeze / research_replay selftest" as L1
  evidence even though that evidence is not gated by the test suite.

### D-20 Test leaves artefacts in the skill source when the guard regresses (hygiene)
- file: `scripts/test_decision_trajectory.py`, `TestWriteGuardIsWired.test_a_store_pointed_into_the_skill_source_is_refused`.
- behaviour: it calls `dt.append_chained(<skill_root>/scripts/_rsi_probe.jsonl, ...)` and then
  asserts the file does not exist. When the guard is broken (mutation S2) the write succeeds and
  the test fails **but leaves `scripts/_rsi_probe.jsonl`, its `.head` and `.lock` behind**, which
  then fails unrelated source-freeze tests in every later run in the same tree. My first
  (non-hermetic) batch was contaminated this way; all numbers reported here come from the
  fresh-copy-per-mutation loop. In the green suite the guard raises before writing, so the tree
  stays clean and the suite is deterministic.

## NOT-BUGS (mutation caught, or test verified sound)

| # | mutation (file) | killed by |
|---|---|---|
| M1 | `_recomputed_level` replay branch returns `L3` (`policy_evolution.py`) | `test_a_supported_replay_evaluation_is_L2`, `test_recomputed_level_never_returns_L3_for_a_replay_artifact` |
| M2 | declared-vs-recomputed metric comparison disabled | `test_declared_means_that_disagree_with_the_records_are_refused` |
| M3a | `audit_report` accepts missing `isolation_verified` | `test_a_report_missing_the_isolation_proof_is_refused` |
| M5 | `mechanistic_understanding` dropped from reliability rejection | `test_a_mechanistic_regression_blocks_promotion` |
| M9 | unobserved-count recomputation disabled | `test_an_understated_unobserved_count_is_refused` |
| M11 | store-time human-approval check disabled | 8 tests incl. `test_a_self_consistent_credential_without_human_approval_is_refused`, `test_the_cli_refuses_without_an_approval` |
| M12 | promotion-time approval re-check disabled | `test_promotion_reverifies_the_approval` |
| M13 | required controlled-axis comparison disabled | `test_a_missing_required_axis_is_refused` |
| M14 | execution-instance distinctness disabled | `test_the_same_execution_instance_for_both_arms_is_refused` |
| M15 | borrowed-dispatch reuse scan disabled | `test_a_dispatch_record_already_used_by_another_credential_is_reported` |
| M15b | latest-dispatch check disabled | `test_an_old_dispatch_record_cannot_be_reused_after_a_new_trial` |
| M16 | executor self-identity check disabled | `test_a_self_named_executor_is_refused` |
| M17 | `_numbers_differ` always `False` | `test_declared_means_that_disagree_with_the_records_are_refused` |
| M18 | `audit_report` suppresses all errors | 9 tests incl. `test_a_report_bound_to_another_policy_is_refused` |
| M19 | `_recomputed_level` always `L2` | 29 tests across `test_policy_evolution`, `test_promotion_integrity`, `test_skill_rsi_e2e`, `test_l3_trust_boundary` |
| M20 | undeclared changed-variable comparison disabled | 3 fairness tests (`test_an_undeclared_environment_difference_is_refused`, …) |
| M21 | credential-path cross-arm case-set comparison disabled | `test_arms_running_different_case_sets_are_refused` |
| M22 | credential-path `cases × runs` count disabled | `test_a_credential_that_overstates_its_run_count_is_refused` |
| M25 | approval expiry ignored | `test_an_expired_approval_does_not_authorize`, `test_promotion_reverifies_the_approval` |
| M26 | contrast axis that does not differ accepted | `test_a_contrast_that_does_not_differ_is_refused` |
| S1 | `source_freeze.verify` ignores removed files | `test_verify_detects_changed_added_and_removed_files`, `test_verify_never_raises_on_a_missing_tree`, `test_malformed_manifest_returns_violation_not_attribute_error` |
| S2 | `guard_write` allows protected skill source | 9 tests incl. `test_guard_denies_protected_skill_source`, `test_a_store_pointed_into_the_skill_source_is_refused` |
| S3 | manifest root mismatch ignored | `test_a_manifest_belongs_to_one_tree` |
| S4 | integrity head mismatch ignored | `test_integrity_events_detects_a_truncated_tail_via_head_sidecar` |
| D1 | renamed duplicate dispatch accepted | `test_a_renamed_duplicate_dispatch_is_refused` |
| D2 | post-hoc prediction accepted | `test_post_hoc_prediction_is_refused` |
| D3 | unqualified evidence claims scientific delta | `test_unqualified_evidence_cannot_claim_a_scientific_delta`, `test_an_engineering_failure_is_not_a_scientific_delta` |
| D4 | outcome before decision accepted | 23 tests/errors (incl. loader errors from the tear-down) |
| P2 | unbacked independent refs ignored | `test_every_reference_must_be_backed_not_just_one` |
| R1 | L3 claimed without evidence | `test_l1_and_l2_are_verified_and_l3_is_not_claimed` |

Other soundness checks:
- **Determinism**: 2 default runs + `PYTHONHASHSEED=0/1/424242` all `Ran 1810 tests ... OK (skipped=5)`.
- **Skips**: the 5 skips are all outside this scope (`test_state_check`, `test_r10_liveness`,
  `test_release_metadata`, `test_structural_equivalence`) and each carries a documented
  "known gap / not implemented" reason; no focused test in scope is skipped.
- **Focused-file hygiene**: `test_promotion_integrity.py`, `test_promotion_credentials.py`,
  `test_l3_trust_boundary.py`, `test_policy_evolution.py`, `test_decision_trajectory.py`,
  `test_policy_transfer.py`, `test_source_freeze.py`, `test_rsi_ablation.py`,
  `test_counterfactual_replay.py`, `test_skill_rsi_e2e.py` all contribute real assertions;
  the source-freeze, decision-trajectory, policy-transfer and rsi-ablation guards I mutated
  were each killed by at least one targeted test.

## Reproduction notes

- Pinned tree: `git -C <worktree> archive 53ea2006 research-idea-pipeline | tar -x -C /tmp/r8d_pin`.
- Each mutation is a single literal string replacement; the exact `old` strings are in
  `/tmp/muts_batch1.json` and `/tmp/muts_batch2.json` on the audit host, and the per-mutation
  full-suite logs are in `/tmp/r8d_logs_pin/`. The concentrated spot-check scripts are
  `/tmp/demo_pin2.py`, `/tmp/demo_m3b.py`, `/tmp/demo_m4.py`, `/tmp/demo_m10.py`,
  `/tmp/demo_m28.py` (run from `<tree>/scripts`).
