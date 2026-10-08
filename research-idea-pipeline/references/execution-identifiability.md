# R8/R9 execution identifiability and bounded diagnosis

This contract extends existing experiments, assurance and repairs. It adds no R
stage, collection, scientific score or R10/R14 enum. Failure Memory remains the
stop-rule authority; Evidence Outcome remains the result/transaction authority.
The schemas in [../schemas](../schemas/preflight-protocol.schema.json) and
[protocol template](../templates/preflight-protocol.template.json) define the
machine carriers. Incomplete designs may be stored while planned. They cannot run.

## PEIG: design before permission

R7 records relevant attacks in assurance with `id`, `target`, `severity` (critical,
high, medium, low), `risk_type` and `kill_condition`. High/critical scientific
uncertainties with `target` and `risk_type` are also part of the inventory. R8
stores `experiments[].execution_protocol`; R9 consumes it. Formal permissions
cover X3/X4/X5 and targeted X6, including central claims. Exploration, X1 sanity
and X2 calibration use bounded diagnostic permission and never confirm a claim.
Stage X2 still has an empty claim_targeted. Pilot never retroactively becomes X3.

The protocol binds target claims, existing competing hypotheses, all affected R7
attack IDs, experimental arms, comparisons, training freedom/capacity, compute,
intervention definition/frozen dose/observable manipulation check, optimizer/LR/
schedule/batch/steps/tuning budget/diagnostics, splits/seeds/metrics/minimum meaningful
effect/statistics, and four outcome criteria with decisions. It includes stop,
failure and redesign conditions. Criteria are prospective. The independent
scientific review binds the actual design digest; PASS/UNKNOWN/FAIL judgments
are distinct from syntactic completeness.
Risk inventory includes the exact target, all of its ancestors and all competing
hypotheses. Narrowing to a child claim does not drop either child-specific or
inherited attacks. R10 diagnosis requirements also follow claim ancestry.

Each risk has exactly one disposition:

- `DESIGN_CONTROL`: an existing comparison directly fixes the relevant variables;
- `DISCRIMINATING_CONTROL`: a real comparison predicts different observations
  under competing hypotheses and maps them to different research decisions;
- `SCOPE_LIMIT`: explicit limited claim scope, exclusions and source R10 repair;
- `UNIDENTIFIABLE`: named owner and finite HOLD or exploratory study.

A control ID alone is insufficient. The gate resolves its arms, checks actual
values for every claimed controlled variable and differing contrast variable,
checks capacity/training freedom/compute/tuning symmetry, and requires distinct
hypothesis predictions and decision branches. Scope limits must already exist in
claim.scope and a NARROW_SCOPE repair. They do not erase Failure Memory. Capacity
risk requires a matched capacity comparison; intervention risk requires an
observable, frozen dose definition. Human review checks whether these quantities
and predictions scientifically address the attack. The machine does not prove
causality from field names or review scores.

`PASS` allows only the frozen formal budget. `PILOT_ONLY` allows a prospectively
specified goal, measurement, decision branches, maximum runs/hours and stop
condition. `HOLD` denies affected validation. A pilot requires an execution
protocol even before its first run. No global freeze of independent exploration.
A scientific UNKNOWN gives a finite HOLD. Human exceptions name reviewer, reason,
scope, expiry and maximum hours; they authorize only a bounded exploratory pilot,
retain the failed/unknown checks, and never produce mechanical formal PASS.

## Finite gate and AALG

The route's execution ledger is scheduler telemetry, not evidence. Policy freezes
on its first operation. Defaults: at most 3 unsuccessful revisions in each of the separate formal and
diagnostic permission classes per
claim line/evidence snapshot; at most 2 equivalent diagnostic attempts; at most
1 pilot run and 2 GPU hours per claim line/evidence snapshot; receipts expire in
900 seconds. Lower or higher project limits must be configured before the first
operation. Rewriting cards, adding controls/documents, changing IDs/seeds or
narrowing prose does not reset these counters. A failing revision consumes one
attempt; passing a genuinely completed design can proceed without demanding any
new ablations. Once the formal revision limit is reached, HOLD/REDESIGN is terminal for
formal execution at that evidence snapshot. A separately bounded prospective pilot
remains available to obtain independent evidence. Targetless X1/X2 exploration
has separate design/mode budgets so calibration does not consume sanity permission. No auto-generated followup chain. Independent evidence
or a human-reviewed new mechanism protocol can reopen a diagnosis; it cannot
silently release a scientific stop rule.
Managed protocol stop signatures bind the scientific design; target overlap is
checked separately through claim/hypothesis ancestry. Renaming a hypothesis or
using a child claim cannot evade an unchanged-design stop rule. Legacy protocol
signatures keep their original semantics.

R10 `RUN_TEST`, `FIX_IMPLEMENTATION` and diagnostic `NARROW_SCOPE` actions attach
`repairs[].diagnostic_protocol`. Its schema is
[../schemas/diagnostic-protocol.schema.json](../schemas/diagnostic-protocol.schema.json).
It answers substantive difference, new observed evidence or testable premise,
competing predictions, decision branches and terminal fallback. Post-hoc proposals
are `exploratory`; confirmed hypotheses require independent observations from a
new identifying protocol, excluding hypothesis-generating evidence.

Equivalence uses stable claim ancestry/risk type bindings, a digest of source-bound
scientific evidence content (not its ID), and the actual scientific design
projection (arm/comparison labels and seed excluded). Narrative explanations,
uncertainty edits, reports, new experiment IDs and preregistration timestamps are
not evidence. An unchanged mechanism/design with no new evidence is equivalent.
Changing a free-text mechanism name is not a new mechanism: a changed hypothesis ID or structural-distance label does not reset the same
design. A distinct mechanism requires a new identifying design and a source-bound
independent scientific review, binding the hypothesis snapshot and protocol.

The ledger returns `STOP_DIAGNOSIS` with existing outcome `REDESIGN` and T8 routing
(R5.1 once, then R3/R6), or `PIVOT_RECOMMENDED` for an already stopped line. R14
still decides pivot/archive; R10 still owns claim changes. Negative results remain
negative; unverified causes remain unknown/uncertainty. Diagnostics cannot upgrade
them, rewrite original preregistration, or bypass check-plan.

## Supported execution boundary and receipts

There was no GPU launcher in this package before this interface. All Skill-managed
execution now goes through `scripts/experiment_execute.py` (`issue`, `run`,
`diagnose`, `scheduler-check`). Existing `evidence_outcome.py check-plan` also
checks PEIG when an execution_protocol is present. Legacy states remain readable,
but the launcher never certifies legacy experiments without a reviewed protocol.

A manifest binds argv, working directory, environment overrides, requested hours,
and exact file bytes for code/config/data_split/preregistration. Code entries must
include the executable when it is a local program; Python/module/remote launchers
must list every relevant implementation/config/dependency artifact. The command
and resource envelope must correspond to the reviewed protocol. Hashes bind the
listed bytes, not unlisted files or remote images.

`issue` produces a locally sealed, expiring, single-use receipt, stored in an
append-only hash-chained route ledger. It binds full state, protocol, preregistration,
manifest, code/config/split bytes, budget, PEIG verdict and engine source digests.
`run` locks the ledger, checks seal/registry/expiry/content and reruns all gates,
reserves the budget and consumes the receipt before invoking argv without a shell.
Dry-run consumes a receipt too and never starts its command. Concurrent launches
cannot reuse receipts. Failed commands still consume budget; elapsed time does not
refund a reservation. A forced CUDA_VISIBLE_DEVICES mask binds the listed GPUs. A timeout of requested
GPU-hours divided by device count enforces the local wall-clock envelope. Child
stdout/stderr go to a retained run log, keeping CLI receipts structured.
PEIG/AALG errors are structured JSON with nonzero exit codes (3 denied, 4 invalid
input). A state change requires a new receipt. Result collection binds the original
execution protocol; outcome application does not mint execution permission.

The ledger/key must be retained and protected by the operator. A same-user attacker
can replace code, state, ledger or key; this is not a security sandbox. Direct
`torchrun`, shell/SSH, sbatch, notebooks, other GPU services, pre-existing jobs,
unlisted dependencies and commands that detach child jobs are outside interception.
Use a site-specific scheduler adapter for remote budget enforcement. Do not claim
that the Skill globally blocks GPUs or cancels already-running jobs.

## Scheduler: evidence-grounded eligibility before EIG

`scheduler-check` binds telemetry state_version and validates each actual EIG
record against the corresponding immutable outcome receipt's state_delta and
observations. It recomputes the existing high/medium/low/zero rating. Predicted EIG
remains an estimate. Uncertainty downgrades/new uncertainty alone can retain the
legacy rating, but cannot authorize a diagnostic: AALG still requires evidence,
distinct possible observations, changed decision and bounded cost. No score or
number of documents is a PEIG success criterion. Scheduler-check also applies
Failure Memory and PEIG to selected experiments; bounded diagnosis is checked at
issue time against the shared ledger. Telemetry cannot be cited as evidence.

## Migration

Original S1–S7/V1–V24, eight collections, R10 dispositions and R14 verdicts remain
unchanged. Additive EX1 checks enforce extension shape and immutable execution
snapshots, without requiring every old experiment to have new fields. Backfill
real R7 attacks/designs only when planning a new managed execution. Historical
experiments receive no retrospective PASS. Install by copying the entire package,
including schemas; validate the copy with `scripts/release_check.py`. Existing
external installation directories are not modified by development.

## Commands and source bindings

See [../README.md](../README.md) for issue/run/diagnose/scheduler-check commands.
The managed boundary requires current scheduler input and seals its digest too.
Each protocol outcome carries preregistration_id whose criterion exactly matches
the frozen outcome observation. The runner returns execution_record (receipt,
launch_seal, dry_run); R9 persists it before outcome analysis. The outcome CLI
checks consumed provenance against the ledger, including --execution-ledger for
an explicit route path. Library clients call verify_result_execution themselves.
The launch flag must be a boolean and agree with the authenticated consumption
event. Changing a dry-run record to false cannot turn telemetry into evidence.

Diagnostic review_digest binds the proposal, tested protocol and hypothesis
snapshot. A preregistered diagnosis must have its digest in the original
preregistration.diagnostic_protocols; adding it after execution fails receipt
verification. Independent ad hoc observations use evidence[].diagnostic_observation
with kind/location/content/digest. Only source-bound observations count as new
scientific evidence; a new E ID or source locator does not reset budgets.

The scientific_review.execution_digest binds the exact command manifest, resource
request, targeted claim/hypothesis content and ancestry, and
code/config/split/preregistration file bytes. Compute it with
experiment_execute.execution_review_digest only after reviewing those artifacts;
issue refuses an unreviewed command even when the abstract design passed PEIG.
Config files contain execution_design (arms/intervention/evaluation), and split
files contain data_split; the gate compares these with the protocol. These carrier
checks do not prove arbitrary training code actually honors them. Inspect the
implementation or use a site adapter with runtime operation checks. This is the
remaining semantic trust boundary. Listed files are rehashed at dispatch; dynamic
imports, code that changes its own GPU mask, concurrent malicious file mutation
and detached descendants are outside filesystem/process isolation.

The ledger verifies an authenticated chain plus a persistent head marker. Missing
or truncated history fails closed. A crash between event and head persistence may
require operator recovery; the system never silently resets counters. Do not reuse
a ledger from another route or copy its key into scientific artifacts.
