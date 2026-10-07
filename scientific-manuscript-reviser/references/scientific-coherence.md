# Scientific Coherence Audit

Never infer scientific validity from rhetorical fluency. Audit scientific reasoning
edge by edge rather than judging the manuscript holistically. Scientific writing
can clarify an argument, but cannot repair missing evidence by rhetoric.

This stage follows invariance extraction and precedes narrative or language edits.
Use [argument-graph-contract.md](argument-graph-contract.md) for source-bound artifacts.
For theory read [theory-audit.md](theory-audit.md); for experiments read
[experiment-audit.md](experiment-audit.md). Separate passes can be sequential in
fresh evaluation contexts. Do not substitute a single generic reviewer prompt.

## Passes

1. **Extract graph.** Locate every important node and typed edge in the manuscript.
   Preserve exact spans plus section/paragraph/equation/figure/table locators. Record
   missing sections. Trace the actual main chain, not an idealized story filled with
   invented hypotheses. The 25 node types and 18 edge types are in the contract.
2. **Claim/evidence links.** Classify each important inference as deductive,
   inductive, abductive, causal, statistical, analogical, mechanistic, empirical
   generalization or mathematical derivation. Apply the appropriate rules below.
   Every edge gets supported/partially_supported/unsupported/contradicted/
   underdetermined/unclear and a local rationale. Detect broken or missing links,
   circular premises, orphan claims and experiments. Reconstruct the RQ → H →
   experiment → result → permitted claim matrix with support/refutation conditions.
3. **Theory and assumptions.** Verify definitions and proof dependencies stepwise.
   Unknown proof steps stay NOT_VERIFIED, not PASS. Use theory-audit.md.
4. **Experimental identification and fairness.** Separate high-level scientific
   question/alternative identification from low-level validity. Use experiment-audit.md.
5. **Entailment and conclusion calibration.** For each important claim trace
   Claim ← Interpretation ← Result ← Experiment (or valid theoretical dependency).
   Verdicts are SUPPORTED/PARTIALLY_SUPPORTED/UNDERDETERMINED/UNSUPPORTED/CONTRADICTED.
   Evaluate each central claim in Abstract, Introduction, Discussion and Conclusion
   as overclaim, underclaim or correctly calibrated. Keep supported strong conclusions.
6. **Cross-section consistency.** Compare Abstract, Introduction, Related Work,
   Method, Theory, Experiments, Results, Discussion and Conclusion. Check strength,
   scope, causality, assumptions, comparator, novelty, values and terminology.
   Find an unevaluated introduction contribution, abstract/body mismatch, untested
   theory deployment, new conclusion claim, omitted central result or a limitation
   contradicting an earlier unconditional statement.
7. **Counterfactual and alternatives.** For each central claim ask whether the
   observation could persist with its proposed mechanism false, a substituted
   component, matched baseline compute/data, a failed assumption or a failed dataset.
   Mechanism/causal claims require plausible alternatives and current discriminating
   evidence. Alternatives can be optimization, capacity, augmentation, regularization,
   compute, initialization, sampling, leakage, metric artifact or selection bias.
   ALTERNATIVE_EXPLANATION_NOT_RULED_OUT does not automatically refute the paper.
8. **Aggregate.** Merge/deduplicate and rank existing findings only. Do not invent
   new criticisms. Preserve evidence, confidence, verification status and scientific
   strengths. No opaque overall score or reviewer score hill climbing.

## Inference checks

Deduction needs valid premises and an actual derivation. Induction needs representative
sampling and bounded extrapolation. Abduction needs competing explanations, not
“plausible therefore proved”. Causal inference needs identification and controls.
Statistical inference needs justified estimands, uncertainty, tests and aggregation.
Analogy needs a mapped relation and acknowledged mismatch. Mechanistic claims need
discriminating interventions or evidence. Empirical generalization needs actual
held-out settings. Mathematical derivation needs stepwise dependencies and domains.

Forbidden entailment leaps

- performance gain → mechanism correctness
- correlation → causation
- ablation gain → claimed causal mechanism
- two benchmarks → universal effectiveness
- better mean → robustness across conditions
- non-significance → equivalence
- observed convergence → theoretical guarantee
- permissive theory → explanation of empirical success
- local/asymptotic/sufficient result → global/finite-sample/necessary guarantee

## Findings and scorecard

Critical means the central claim is invalidated (leakage, contradictory conclusion,
central hypothesis untestable, invalid main guarantee). Major means support is
insufficient (missing essential control, unfair baseline, unsupported mechanism,
theory/method mismatch). Moderate affects interpretation/credibility. Minor concerns
clarity without substantive impact. Confidence is separate from severity.

Each finding states evidence location, reasoning type, verdict, why, alternative
interpretation and verification needed. Domain facts not in the manuscript require
NEEDS_EXTERNAL_VERIFICATION. Separate INTERNAL INCONSISTENCY from EXTERNAL SCIENTIFIC
CONCERN. Literature retrieval occurs only when the user allows it; cite inspected
primary sources for novelty, baseline or standard-practice concerns. Memory is not
evidence. External concerns cannot be labeled verified without a retrieved source.

The profile covers RQ coherence, claim/evidence alignment, theory completeness,
proof reliability, theory/method alignment, experimental identification, baseline
fairness, metric validity, ablation informativeness, statistical support, mechanism
support, conclusion calibration and cross-section consistency. Each is strong,
adequate, needs attention, serious issue or not applicable, with specific evidence.
Record **Well Supported**, including isolated ablations, fair baselines, controls,
bounded theorems and calibrated conclusions. Do not manufacture criticisms.

## Repair boundaries

Scientific findings lead the suggestion bank, then narrative and language findings.
Every important finding offers distinct paths with explicit requirements
`requires_text_change_only`, `requires_reanalysis`, `requires_new_experiment`,
`requires_new_theory`. Name what each path would resolve. No imagined result may
appear in revised text. Even text-only calibration may change a protected claim;
it is high scientific risk and stays a suggestion until the author resolves it and
establishes a new baseline. Cosmetic rewriting cannot erase an unresolved finding.

## Evidence for the architecture choice

[Automatic Reviewers Fail to Detect Faulty Reasoning](https://arxiv.org/abs/2508.21422)
studies counterfactual faulty-logic review; its results motivate decomposition rather
than trusting holistic review. [Rhetorical Sensitivity](https://arxiv.org/abs/2608.08975)
studies presentation effects in AI reviews. These are motivations, not proof that
this skill or its passes achieve human-level error detection. No such benchmark is claimed.
