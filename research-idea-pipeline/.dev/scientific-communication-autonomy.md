# Research-first communication & operational autonomy — branch record

Date: 2026-10-24
Base HEAD: `f4099eeea7e53233fc396b4468a66c5e03ebbf47`
Branch: `research-idea-pipeline/skill-rsi-dev`
Scope: `research-idea-pipeline/` only.

## Phase 0 — actual call paths inspected

- `SKILL.md` (§0.4, §1.3, §1.10, §4 R9/R10/R11, §5, §6), `references/invocation-prompts.md`,
  `references/scheduler-policy.md`, `references/research-state-policy.md`,
  `references/evidence-policy.md`, `references/loop-assurance-review.md`,
  `presets/research-loop.md`, `shared-contract.md`.
- `scripts/preset_router.py`: `_loop_step`, `_handle_research_loop`, `run_preset`,
  `strategy_dispatch`, `r10_status`, `assurance_status`.
- `scripts/evidence_outcome.py`: `validate`, `_apply`, `state_errors`, `decision_gate`,
  `store_assurance`.
- `scripts/state_check.py`: `check_state`, `emit`, EO1/EX1.
- `scripts/render_status.py`, `scripts/cognition.py` (`op_build`, `op_check`),
  `scripts/experiment_execute.py` (`issue`/`run`/`verify_result_execution`),
  `scripts/execution_gate.py` (`peig`, `scheduler_check`).
- Tests: `test_preset_router`, `test_r10_liveness`, `test_loop_runtime_correctness`,
  `test_skill_rsi_e2e`, `test_state_check`, `test_evidence_outcome`, `test_render_status`.
- Real project snapshot: MoSA `state_version=163`; state_check fails with 29 EO1
  (X88/X89 terminal without outcome receipt); cognition index at 162; scheduler at 160;
  X87 stopped by SIGTERM with `execution_boundary` saying not scientifically complete.

## Findings

1. **Already automatic:** deterministic state validation, outcome transaction validation/apply,
   assurance binding, scheduler gate, execution ledger, cognition build/check, STATUS render,
   router trigger/record, source freeze.
2. **Still manual:** authoring R9.O packet/analysis/audit, invoking outcome apply,
   refreshing cognition/STATUS (loop only declared it), rewriting stale scheduler telemetry,
   monitoring external processes, INDEX/log archival.
3. **Evidence-gated:** terminal outcome, claim/hypothesis status, failures/repairs,
   assurance, decision, PEIG/AALG, preregistration and budget.
4. **Reporting template drift:** `shared-contract` and `research-loop` required machine
   metadata at the start/end; the loop payload exposes command steps and state versions;
   `continue-research` asked for "已执行动作". These encouraged operations-first reports.
5. **Unsafe liveness gap:** `_loop_step` could use stale scheduler `next_actions`; a stopped
   running experiment was treated as executable work. Fixed here.

## Changes

- New `references/scientific-communication-policy.md`.
- New `references/operational-autonomy-policy.md`.
- New `scripts/operational_reconcile.py` (thin coordinator; no state, no daemon).
- `preset_router._handle_research_loop` runs reconciliation first; stale scheduler actions are
  excluded; stopped experiments are not dispatched; `operations`/`operational_holds` are emitted.
- `state_check.emit` prints EO1/EX1 rows by default instead of only a count.
- Loop/entry/shared/preset/scheduler/research-state/evidence contracts updated.
- Formal example `examples/scientific-reporting.md` (before/after X88–X90 + audit expansion).
- Tests: `test_operational_reconcile.py` (16), `test_scientific_communication.py` (19).

## Capability classification

| Capability | Status |
|---|---|
| Cognition/STATUS projection refresh on loop apply | **新增** (it was declared but not executed before) |
| Stale scheduler exclusion | **新增** |
| Stopped experiment exclusion + hold | **新增** |
| Prepared outcome bundle auto-commit | **新增**, through the existing R9.O/R10/R11 transaction |
| Outcome science judgement / audit authoring | **仍依赖宿主 Agent** (intentionally; must not be inferred from logs) |
| Claim/assurance/decision changes | **已有能力**, unchanged gates |
| PID/GPU/path suppression and audit expansion | **新增 contract**, enforced by agent report policy and semantic tests |
| Process liveness detection | **仍依赖宿主/外部运行时**; skill sees only structured records |

## Residual risks

- The bundle discovery convention (`<XID>-packet.json` / `-analysis.json` / `-audit.json`
  under a results route) must be followed by the project. A missing bundle produces HOLD,
  never an inferred outcome.
- External process liveness is not observable by this skill. It only refuses to convert a
  structured stop record into completion.
- Auto-commit still requires the existing execute authorization and the existing evidence
  transaction; it does not add a new gate or a new permission.
