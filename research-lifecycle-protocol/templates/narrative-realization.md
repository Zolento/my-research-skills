# Narrative Realization Record

Use one record per frozen scientific hierarchy in R12-post.
Keep the original narrative document and its six slots.
Store companion artifacts under `routes/<R>/narrative-realization/<doc-id>/`.
Do not add fields to Research State.

## Scientific freeze (D4a)

| Item | Record |
|---|---|
| Scientific hierarchy | Existing central and supporting claim IDs |
| Framing and preset | Frozen scientific framing and one main preset |
| Contribution order | Existing claims in the frozen scientific order |
| Mapping | State support and refutation edges |
| Anchor | eligible or conditional, with the scientific audit rationale |
| Provenance | JSON Pointers for all 14 frozen fields and S1–S6 |
| Boundaries | All scope, assumptions, uncertainty, limitations and failures |
| Source identity | State version, state digest and snapshot digest |
| Empty fields | Explicit reasons and no invented facts |

Audit source completeness before generating rhetoric.
The manifest is a reviewed projection, not a scientific evidence upgrade.
Use the [example manifest](../examples/narrative-realization/manifest.json).

## Bounded realization (D4b–D4c)

Read the [operator registry](../references/rhetorical-operators.md).
Generate neutral, evidence-forward, contribution-forward and slightly-conservative once.
Record operators and RE1–RE5 results for every variant, including perturbations.
Keep boundary content at the same early position in every profile.
FAIL means reject that variant. Do not repair Research State.

| Variant | Profile | Operators | Snapshot | Equivalence | Rejection reason |
|---|---|---|---|---|---|
| V1 | neutral | Registry profile | Frozen digest | PASS / FAIL | Explicit reason |

## Blind recovery (D4d)

Persist the evaluation plan before reading any response.
Use at least two distinct model IDs and the same panel for all profiles.
Send only the checked probe-task payload to each fresh judge context.
Record model identity and execution provenance outside that payload.
Collect all responses, including unfavorable ones. Do not rerun to chase scores.

The six response keys are central_claim, main_contribution, closest_prior_work_delta,
key_evidence, main_boundary and unsupported_or_overstated_claims.
Each response key holds an array of exact source units from the narrative.
An adjudicator compares these units to the frozen truth after the probe.

| Variant / judge | Claim Recovery | Evidence Recovery | Novelty-Delta Recovery | Boundary Recovery | Unsupported |
|---|---|---|---|---|---|
| V1 / registered judge | PASS / PARTIAL / FAIL | PASS / PARTIAL / FAIL | PASS / PARTIAL / FAIL | PASS / PARTIAL / FAIL | Explicit list |

## Sensitivity and choice

Record paired range, variance and disagreement for each metric and judge.
Record judge disagreement per variant without averaging it away.
Keep optional scientific judgment categories for diagnosis only.
Report STABLE, RHETORICALLY_FRAGILE or INCOMPLETE, with the panel and reasons.
STABLE applies only to the registered panel and perturbations.

Select by semantic PASS, zero unsupported claims and worst recovery per dimension:
claim, evidence, novelty delta, then boundary. Break ties by lower fragility and fixed order.
Exclude a variant if any registered judge has FAIL in any recovery dimension.
Do not optimize an overall reviewer score or reduce limitation visibility.
Selection is not submission approval. Continue with D5 and original G1–G5/D8.

## Gaps and handoff

Record missing evidence and narrative_gap without changing the frozen State.
For a scientific correction, stop this snapshot and hand the gap to R1/R8/R10.
Only then create a new freeze.
Keep failure, fragility and missing probe data visible in the final narrative recommendation.
Retain the existing four-key narrative_view descriptor.

See the [equivalence policy](../references/rhetoric-equivalence-policy.md) and
[runnable example](../examples/narrative-realization/README.md).
