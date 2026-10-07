# Evidence Outcome Analysis contract

## Additive Research State fields

Keep the eight first-class collections, existing enums and original S/V gates.
No top-level negative_knowledge, stop_rules, next_actions or new decision enum.

| Existing object | New field | Responsibility |
|---|---|---|
| contract | outcome_policy | R0 freezes project replication criteria |
| hypotheses | scientific_scope, central | R3/R8 declares tested scope and central importance |
| experiments | hypothesis_targeted, outcome_protocol | R8 freezes hypothesis targets and scientific protocol |
| experiments | outcome_analysis | R10/R11 stores source packet, proposal, audit, historical context and receipt |
| experiments | execution_blocked_by | R11 records a stop/fix hold for existing planned/running work |
| experiments | outcome_plan_clearance | R8 records a source-grounded changed-condition/fix audit |
| claims/hypotheses | scoped_outcomes, outcome_status | R10/R11 scientific status, separate from legacy lifecycle |
| failures | negative_knowledge, stop_rules, failure_attributions, source_analysis_id | Scientific Failure Memory |
| evidence | outcome_observations, hypothesis_target, claim_target | Result links, including hypothesis-only or local evidence |
| repairs | outcome_analysis_id | Original R10 disposition provenance |

`outcome_policy` has exactly schema=evidence-outcome-policy@1,
frozen_at_state_version, min_valid_runs, min_seeds, min_datasets,
require_independent_replication and min_verification_tier. Counts are positive
integers; tier is T2–T5. Freeze at/before the experiment preregistration version.
Thresholds cannot be weakened after results. For central experiments the minimum
is two valid runs even if a noncentral project threshold is one.

`outcome_protocol` records project-specific scientific design and dataset. Use
`dataset`, `scope`, `design` with an explicit comparison/control description, and optionally
independent_replication=true only when established. Freeze before execution.
The signature includes stage, data_split, metric, claim_targeted, hypothesis_targeted,
alternative_targeted, outcome_protocol and preregistration apart from its timestamp.
Seed and implementation commit still remain in result provenance, but do not release
a negative-result stop rule by themselves.

A scoped history item contains analysis_id, experiment_id, scope, scope_relation,
status and applied. Invalid/unidentified attempts and NOT_TESTED are retained with
applied=false; they do not erase previous support. outcome_status follows the latest
applied FULL assessment. Scientific FALSIFIED is independent of QD killed/archived.

## Compatibility and adoption

Legacy states without outcome_policy and without outcome extension fields continue
to pass their original gates. Empty template carriers (null receipt, empty memory)
are not applied analyses. Removing the policy from an analysed state fails. This
preserves installed projects and old examples; it does not certify old results as
analysed. New R0 states enable outcome_policy with empty experiment arrays. Before
continuing an existing project, explicitly adopt the policy and backfill historical
terminal outcomes from their actual artifacts. Do not invent positive or negative
labels to complete migration.

Strict mode requires outcome_analysis on every done/failed experiment. A migration
transaction with an outstanding historical backlog returns NEEDS_REVIEW and an
unaccepted proposed_state. Continue source-grounded backfill against that snapshot;
only the final complete state can PASS and become input to the next loop. Missing
logs remain unresolved; they cannot be manufactured or grandfathered as PASS.
Terminal-result coverage and receipt checks are EO1, an additive hard gate after
S1–S7 and V1–V24. state_check preserves original rule IDs and reports outcome
violations separately. No false claim that the original 24 rules perform semantic
outcome classification is made.

## Source-bound result packet

Schema is evidence-result@1. Exact top-level keys

```
schema, experiment_id, experiment_digest, execution_status,
result_summary, sources, observations
```

execution_status is completed/failed. The digest binds the executed experiment
snapshot before outcome application. Sources contain id, kind, location, content,
digest. kind is log/metric/config/protocol/result. Digest is SHA256 of exact UTF-8
content. Observations contain id, statement, scope, source_ids. Source content can
be bounded excerpts with exact locations; independently check that relevant context
was not omitted. Missing artifacts make validity UNKNOWN, not assumed PASS.

Canonical JSON hashing uses sorted keys, Unicode preserved and compact separators.
Text hashing uses exact UTF-8. NaN and Infinity are invalid scientific artifacts.

## Analysis proposal

Schema is evidence-outcome-analysis@1. Required keys

```
schema, id, experiment_id, base_state_digest, context_digest, packet_digest,
outcome, validity_checks, verification_tier, claim_updates, hypothesis_updates,
failure_attributions, alternatives, decisions, stop_rules, followups,
negative_knowledge, repairs, open_questions, uncertainty_updates,
unchanged, reasoning_summary
```

validity_checks has execution/protocol/measurement/evaluation. Each contains
status=PASS/FAIL/UNKNOWN, reason and source_ids. A failed execution or FAIL on any
validity check gives INVALID_EXPERIMENT. Unknown validity only permits INCONCLUSIVE.
A valid negative result must not be relabeled invalid to protect the hypothesis.

Each claim/hypothesis update contains id, scope, scope_relation=FULL/LOCAL,
previous_status, new_status, evidence (observation IDs), direction
(positive/negative/neutral/not_tested), identification=PASS/FAIL/UNKNOWN, reason and
replication_ids. Cited observations must retain the update scope. Scope labels are
immutable bindings. Retain narrower seed/condition boundaries in the assessment
reason and use LOCAL when evidence does not identify the full claim. All declared
targets appear, even if NOT_TESTED. FULL scope must
match claim.scope or hypothesis.scientific_scope exactly. Claims additionally have
previous_support/new_support from the original lifecycle and scope_change=null.
Scope rewriting remains a separate R10 repair, not an equivalence shortcut.

SUPPORTED maps to positive. WEAKENED/FALSIFIED map to negative. UNRESOLVED maps to
neutral. NOT_TESTED maps to not_tested. Invalid/unidentified attempts allow only
UNRESOLVED/NOT_TESTED. FULL claim updates map supported/partially-supported/
contradicted through original evidence-tier gates and a real R10 repairs entry.
WEAKENED downgrades a supported claim to partially-supported; it preserves an
ungrounded/contradicted/killed lifecycle rather than creating support from negative
evidence. Scientific outcome_status records WEAKENED independently. V3 forbids E
links on an ungrounded claim. Such a weakened claim keeps negative E via claim_target
and the receipt/Failure Memory, without global E adjacency until a valid R10
lifecycle disposition. This does not remove or conceal the negative observation.
LOCAL evidence remains scoped rather than changing a global claim.

failure_attributions contain type, confidence, evidence (source IDs),
alternative_explanations and what_would_disambiguate. See
[evidence-outcome-analysis.md](evidence-outcome-analysis.md) for the fourteen types.
Known execution defects contradict VALID; possible unverified causes remain unknown.

alternatives contain hypothesis_id (existing H), evidence_for/evidence_against
(observation IDs), status and discriminating_next_action (a followup ID). Keep at
most three distinct hypotheses. A changed support status needs a corresponding
individual hypothesis assessment. Unresolved alternatives are not new conclusions.
followups contain id, target_ids, description, expected_information_gain, cost,
scientific_value, risk and decision_it_resolves. Targets must exist in the source
state. They are plans, never results.

Each decision contains target_ids, action, reason, required_fixes, stop_rule_id and
next_action_id. Every target gets exactly one decision. A registered next action
must cover the decision targets. stop_rule_id is mandatory
only for PIVOT/STOP; next_action_id is a followup ID or null for a genuine halt.

A stop rule contains id, target_ids, scope, kind=protocol/claim_line, rule,
protocol_signature and revisit_conditions. IDs are route-unique. Preserve rules in
Failure Memory even after a condition is explicitly cleared for a new experiment.
The rule scope must match the assessed target scope. Scope overlap of a changed
plan is a semantic judgment. The syntactic gate conservatively holds matching
target/protocol lines for explicit review rather than broadening scientific conclusions.

negative_knowledge contains target_id, finding, ruled_out, not_ruled_out,
likely_failure_mode, retry_allowed, retry_conditions, revisit_conditions, confidence.
Every negative target has a record. Only FALSIFIED can fill ruled_out. Invalid
experiments cannot enter scientific negative knowledge. Weakening preserves surviving
explanations. Evidence/experiment IDs are attached during the transaction.

repairs contain kind=implementation_or_protocol_fix/scientific_redesign/
abandon_or_narrow_claim, description, target_ids. They are suggestions. Actual
claims[].status edits create existing R10 disposition/closure records.
open_questions contain question, importance and uncertainty, becoming real U IDs.
uncertainty_updates contain id, previous_level/new_level, previous_status/new_status,
evidence and reason. Invalid results cannot close or reduce scientific uncertainty.

## Independent audit and transaction receipt

Audit schema is evidence-outcome-audit@1, with analysis_digest, packet_digest,
state_digest and checks. Checks are result_faithful, validity_grounded,
inference_calibrated, scope_preserved, attributions_grounded,
confirmation_bias_checked, replication_grounded, alternatives_grounded,
decisions_justified. Each has status=PASS/FAIL/UNKNOWN and reason. All must PASS.
A model's confidence is not a verification tier upgrade. Inspect actual artifacts.

The applied receipt contains packet, analysis, audit, validation_context, audit_trail.
The context is a flat historical snapshot with prior receipts reduced to their
packet/analysis/audit; contexts do not recursively nest. context_digest binds it.
Validation rechecks the historical transition, not only whether the audit says PASS.
The full source state digest stays in the audit and receipt for external comparison.

Audit trail contains source_experiment, source_result, previous_state (version,
digest), state_delta, decision, reasoning_summary, timestamp, state_version.
Each delta names collection/id and exact before/after object snapshots. Original
scientific histories remain present. Applying mutates a copy, increments version,
records valid evidence or failed execution separately, then enforces state_check.
experiments[].interpretation receives the audited reasoning_summary so existing
result consumers do not read a stale placeholder. Communication fields and project
anchors remain unchanged.

## Planning release and post-update Assurance

An outcome_plan_clearance contains schema=evidence-outcome-plan-clearance@1,
memory_digest, experiment_signature, reviewed_rules. Each rule review contains
rule_id, status=PASS, changed_condition, evidence_ids and reason. All triggering
rules need explicit grounded reviews; referenced evidence is valid Observed/Supported
at T1 or above. A reviewer must check relevance of that evidence to the stated
revisit/fix condition. Hash checks do not replace that scientific judgment.
For retry fixes the rule ID is RETRY-<analysis id>. Clear the released execution
hold explicitly in R8, then rerun state_check/check-plan. Applying a result packet
does not bypass an unresolved planning gate.

Post-update Assurance schema is evidence-outcome-assurance@1 with state_digest,
analysis_digest and checks=integrity/claim_calibration/reproducibility/
stop_rule_compliance. Each has status and reason. Missing/UNKNOWN yields HOLD;
FAIL blocks release. An assessment superseded by later results for the same target
and scope returns HOLD even with a new Assurance digest. Reassess current evidence.
PASS releases the current recorded recommendations. It does not itself
start a run, change the project anchor, or bypass R8 preregistration and check-plan.

## Helper commands and outputs

```
python3 scripts/evidence_outcome.py validate --state state.json --packet result.json --analysis analysis.json --audit audit.json
python3 scripts/evidence_outcome.py apply --state state.json --packet result.json --analysis analysis.json --audit audit.json --output next-state.json
python3 scripts/state_check.py --check next-state.json
python3 scripts/evidence_outcome.py constraints --state next-state.json
python3 scripts/evidence_outcome.py check-plan --state next-state.json --experiment X-next
python3 scripts/evidence_outcome.py decision --state next-state.json --experiment X-result --assurance assurance.json
```

Exit codes are 0 PASS, 3 FAIL, 4 NEEDS_REVIEW/environment input error. apply never
writes over the source state or an existing output file. Inspect and persist a passing copy through the existing
R11 workflow. A decision without Assurance returns HOLD. Scripts do not call a model,
execute experiments, infer causes by regex or perform arbitrary JSON patches.
