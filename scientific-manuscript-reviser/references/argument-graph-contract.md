# Located scientific argument artifacts

The graph and audit are separately stored. Extraction alone never certifies a link.
Artifacts use canonical digests and exact Unicode offsets as in scientific-invariance.md.
They apply to manuscript text or a normalized, immutable material corpus. For multiple
documents use a source map into the corpus and retain original document locators.

## Graph

`scientific-argument-graph@1` fields are manuscript_digest, document_scope
(whole_paper/section/research_materials), missing_context, nodes, edges,
central_claim_ids and main_chain. Partial input cannot certify whole-paper reasoning.

Each node has id, type, label, location `{start,end}`, source_span and context.
Context records a human locator such as Methods paragraph 2 / Eq. 4 / Fig. 2 caption.
The label describes the actual assertion, not an enhanced version. Important nodes
must be source-bound. Types are the 25 `audit_coherence.NODE_TYPES`, including
problem, gap, RQ, hypothesis, assumption, definition, method, theory, experiment,
control, baseline, metric, observation, interpretation, claim and boundary.

Each edge has id, source, target, type, reasoning_type, location and source_span.
Use the 16 `EDGE_TYPES` and nine `REASONING` types. Direction is source → target;
`depends_on` names the dependent as source and its premise as target. An experiment
`tests` a hypothesis or question. An observation `supports` an interpretation or
claim. `motivates` is not evidence. A claimed implicit edge must cite the nearby
source span from which it was reconstructed and can later be judged unclear.
Missing premises become findings, not invented source nodes.

## Coherence report

`scientific-coherence-audit@1` fields are manuscript_digest, graph_digest, passes,
edge_checks, rq_matrix, proof_steps, counterfactuals, scorecard, well_supported,
aggregation. Stage names and enums are in the script to prevent interface drift.

Each of six passes has status, examined_node_ids and findings. Status is COMPLETE,
NOT_APPLICABLE, NOT_VERIFIED or NEEDS_EXTERNAL_VERIFICATION. Only absent theory or
experiment passes may be not applicable. An unverified pass remains unresolved.
Each applicable complete pass covers its relevant located nodes; whole-paper passes
inspect all nodes. Edge checks cover every edge once with edge_id, reasoning_type,
verdict and why. Supported topology does not replace local semantic verification.

Findings have id, code, category (scientific_logic/theory/experimental_design/
conclusion_validity), severity, confidence, evidence_node_ids, reasoning_type,
verdict, why, alternative_interpretation, verification_needed, verification_status,
basis, external_sources and repairs. Evidence locations are resolved from node IDs.
Use INTERNAL_CHECKED/NOT_VERIFIED/NEEDS_EXTERNAL_VERIFICATION, separate from confidence.
Basis is INTERNAL INCONSISTENCY or EXTERNAL SCIENTIFIC CONCERN. External sources are
inspected primary links; without them external concern must need verification.
Important findings need at least two genuine repairs with id, option and requires
(text-only/reanalysis/new-experiment/new-theory enums in the script).

RQ rows have rq_id, hypothesis_ids, experiment_ids, result_ids, claim_ids,
identifiable, testable, support_condition, refute_condition and permitted_conclusion.
Each RQ is covered once. Identifiable/testable are PASS/FAIL/UNKNOWN. A missing test
stays UNTESTED_HYPOTHESIS rather than an imagined experiment.

Proof steps have id, proposition_id, location, source_span, dependencies, verdict,
why. Dependencies have kind and id, referring to a previously checked step or graph
node. Verdict is VERIFIED_LOCALLY/NOT_VERIFIED/FAIL. Every theorem/lemma/proposition
requires actual step coverage, not a blank proof reliability rating.

Counterfactual entries have claim_id, question, alternative_explanations,
discriminating_evidence_ids, verdict and why. Each central claim is interrogated.
Mechanistic and causal claims require plausible competing explanations and a source
trace for discrimination; underdetermination is visible.

Scorecard contains the 13 named items from the script, each with level,
evidence_node_ids, finding_ids and why. No number or overall score. Well Supported
records node_ids, edge_ids and why. Aggregation is only a ranked list of existing
finding IDs exactly once; it cannot introduce criticism. Scientific strength records
are not permission to suppress serious findings.

```
python3 scripts/audit_coherence.py manuscript.md --graph graph.json --report report.json
```

PASS is conditional on the supplied local judgments and complete input. Missing
context or unverified science yields NEEDS_REVIEW. Unsupported/contradicted checked
links or serious verified issues yield FAIL. Structural cycle/orphan diagnostics
need semantic resolution and cannot be hidden by a general “looks good” review.
