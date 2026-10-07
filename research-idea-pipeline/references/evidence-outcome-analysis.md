# Evidence Outcome Analysis — R9.O internal capability

A valid negative result is scientific evidence and changes the search space.
Failure is not the absence of progress. Remember what was ruled out and why.

## Placement and authority

This is an internal capability, not a new skill or a sixteenth R stage.

```
R8 planning and frozen preregistration
→ R9 execution and result collection
→ R9.O source parsing and Evidence Outcome Analysis proposal
→ R10 disposition and R11 scientific state transaction
→ Assurance check
→ per-target decision gate
→ constrained next research action
```

Read [evidence-outcome-contract.md](evidence-outcome-contract.md) for artifact/schema
fields. The authority for original claim lifecycle changes remains R10, defined in
[phase-r9-r11-experiment-loop.md](phase-r9-r11-experiment-loop.md). R14 alone handles
route-level continue/pivot/archive/submit. An experiment-level PIVOT is not permission
to change the project anchor or open a route. R12 is a read-only scientific view.
Never edit narrative to explain away a negative finding.

## Five separate judgments

1. Parse what actually happened from result/log/config/metric sources, retaining
   numbers, comparator, aggregation, evaluation conditions and exact locators.
   Expected and planned results are not observations.
2. Check execution, protocol, measurement and evaluation validity separately.
   A crash or corrupted metric is not a scientific refutation. Unknown validity
   cannot become valid merely because a result appears plausible.
3. Assess every declared claim and hypothesis individually and within its scope.
   Mark SUPPORTED, WEAKENED, FALSIFIED, UNRESOLVED or NOT_TESTED. A trial can support
   performance, weaken mechanism and leave robustness unresolved.
4. Attribute only what the sources establish. Keep plausible alternatives separate
   from observed faults. Include confidence and a discriminating check.
5. Recommend the next action that resolves the scientific decision, not the action
   most likely to raise a benchmark score.

Execution lifecycle done/failed, scientific support, QD elite/archived and evidential
validity are different dimensions. A done experiment can be INVALID_EXPERIMENT when
its metric is wrong. A valid NEGATIVE_EVIDENCE experiment remains done. An invalid
attempt is recorded against its attempted targets without changing their existing
scientific support. Invalid source dependencies become stale, never automatically
falsified downstream propositions.

## Outcome classification

| Outcome | Meaning |
|---|---|
| POSITIVE_EVIDENCE | Valid identifying evidence supports the tested predictions |
| NEGATIVE_EVIDENCE | Valid identifying evidence weakens/refutes a prediction |
| MIXED_EVIDENCE | Different tested predictions have positive and negative effects |
| INCONCLUSIVE | Validity, power or identification leaves the inference unresolved |
| INVALID_EXPERIMENT | Execution/protocol/measurement/evaluation cannot support inference |

Weak or mixed evidence is not automatically falsifying. No significance is not
proof of equivalence. A performance improvement does not identify a mechanism.
Confounding is an identifiability failure, even if training completed successfully.
A planned sample-size requirement not met is a protocol failure; an honestly
completed but underpowered design can be inconclusive rather than invalid.

## Failure taxonomy

| Type | Relevant evidence to inspect |
|---|---|
| implementation_failure | traceback, config/method mismatch, faulty tensor or code path |
| optimization_failure | observed divergence, objective traces or failed optimizer criteria |
| data_failure | corrupted/duplicated data, leakage or verified data access problem |
| protocol_failure | frozen procedure was not followed |
| measurement_failure | observation/measurement pipeline was defective |
| evaluation_failure | wrong metric, aggregation or evaluation condition |
| baseline_failure | broken or unfair reference implementation/procedure |
| statistical_power_failure | uncertainty cannot discriminate the required effect |
| identifiability_failure | interventions/comparisons do not isolate competing explanations |
| hypothesis_failure | valid identifying evidence violates the scoped prediction |
| theory_failure | a derivation or its scoped prediction is contradicted by appropriate evidence |
| assumption_violation | a stated premise fails in the evaluated setting |
| distribution_shift | inspected distribution differences affect the inference |
| unknown | causes remain unresolved |

Each attribution carries type, confidence, source evidence, alternative explanations
and what_would_disambiguate. A bad result alone is not evidence of an implementation
bug, random fluctuation or inadequate tuning. Unsupported attribution fails with
UNSUPPORTED_FAILURE_ATTRIBUTION. Use unknown when a cause is merely possible.
Similarly, a single negative run does not establish a whole direction is false.

## Replication and local scope

Freeze project criteria before preregistration. Evaluate single-run, multi-seed,
cross-dataset and independent-replication evidence separately. The script counts
real eligible experiment IDs and their registered seeds/datasets, not a prose
claim that “five runs were negative”. Prior invalid/stale results are ineligible.
The semantic audit must check matching conditions, independence and whether these
runs cover the scientific scope and satisfy the preregistered rejection criterion
under the measured uncertainty. Replication counts are necessary, not sufficient,
for scientific falsification. A central experimental claim/hypothesis needs
at least two eligible runs and the project thresholds before FALSIFIED. Formal
counterexample/proof reasoning belongs to its existing theory/Assurance path.

FULL updates require the exact declared scientific scope. LOCAL observations are
retained in scoped_outcomes and Failure Memory without changing the broad claim
status or attaching local evidence as global support/refutation. The next R10 repair
can create a narrower claim explicitly. Preserve the original and its history.
A previously falsified scoped hypothesis is not silently restored. Use an explicitly
resolved new scoped hypothesis and a traced relationship to prior negative knowledge.

## Decision rules

| Decision | Preconditions and next action |
|---|---|
| CONTINUE | The affected line is supported; follow the existing plan |
| RETRY | The attempt is invalid; specify evidenced fixes before a new experiment ID |
| REDESIGN | The comparison cannot identify the hypothesis or needs a scientific control |
| PIVOT | Valid evidence weakens/refutes the explanation; retain alternatives and stop rule |
| STOP | Repeated validated negatives meet project criteria; prohibit wasteful repetition |
| HOLD | Information, prerequisites or an audit remain unresolved |

For mixed evidence, give separate decisions by target. Method line can CONTINUE
while mechanism explanation PIVOTs and robustness experiment is REDESIGNed. Do not
pick a single experiment success label. PIVOT and STOP each require a scoped stop
rule, bound to the scientific protocol, plus revisit conditions. A stop rule can
block a protocol or the whole scoped claim line. Changing only seed, code commit
or preregistration timestamp does not change the protocol fingerprint.

Discovery and R8/R9 planning read `evidence_outcome.py constraints`. Before executing
any candidate, run check-plan. Hypothesis and claim parents are included in blocked-line
checks. Existing planned/running nodes affected by a newly recorded rule receive
an explicit execution hold. Do not claim that writing this hold terminates a job;
R9 must stop affected execution and account for existing resource processes.
Release requires a new, source-grounded planning audit of the changed condition.
Do not delete the rule. RETRY also requires a source-grounded fix clearance for
an invalid parent or an unchanged failed protocol. A new seed is not a fix.

## Alternatives, information gain and repair

Keep only a small set of existing/directly relevant competing explanations. Record
what supports each, what opposes each, what remains unknown, and the next comparison
that distinguishes them. A relative plausibility shift is not absolute confirmation.
If materials do not discriminate an alternative, say so rather than inventing one.

Followups carry expected_information_gain, cost, scientific_value and risk using
high/medium/low, plus decision_it_resolves. These are reasoned estimates, not measured
entropy or new scientific evidence. Existing EIG/cost scheduler priorities remain.

Offer only relevant repair paths. They can include implementation/protocol fix,
scientific redesign and abandoning/narrowing the claim. Do not force three options
when only one is defensible. Additional experiments and analyses remain planned.

## Each run's concise, traceable output

1. Observed outcome with source locators
2. Experiment validity and unresolved checks
3. Claims affected with previous/new scoped support
4. Hypotheses affected with previous/new scientific status
5. Scientific negative evidence versus experiment failure classification
6. Relevant alternative explanations and discriminating evidence
7. Exact state changes and unchanged facts
8. Per-target decision recommendations and Assurance status
9. Stop/retry rule and conditions for release
10. Next action, information gain, cost and scientific decision resolved

The independent audit checks source fidelity, validity, calibrated inference,
scope, attribution, confirmation bias, replication, alternatives and decisions.
PASS/FAIL/UNKNOWN judgments stay separate from mechanical schema validation.
Missing or UNKNOWN audit blocks application. A post-update Assurance gate is still
required before choosing the next execution. The aggregation must not invent new
observations, errors or explanations.

## Limits

Hashes bind snapshots but do not authenticate a reviewer or certify scientific truth.
Structured LLM judgments can still be wrong. A protocol fingerprint is a conservative
syntactic check, not a semantic-equivalence proof. Inspect changed designs and matching
scopes in planning/Assurance. The bundled helper neither executes experiments nor
rewrites papers. Test fixtures verify contracts and transitions, not detection accuracy.
