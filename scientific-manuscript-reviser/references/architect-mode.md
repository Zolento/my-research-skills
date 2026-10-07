# Architect Mode

Structure the paper around what evidence establishes, not what sounds most impressive.
A detailed outline is a scientific argument plan, not a table of contents.
Generate with the same standards used to audit.

## Normalize materials and assess sufficiency

Accept narrative, motivation, RQ, hypothesis, method, theory, proofs, experiments,
results, figures, tables, literature, closest prior work, baselines, limitations,
failures, venue, desired claims and notes. None is mandatory. Logs and natural-language
documents are valid inputs. Keep originals and exact source locations.

Use the [blueprint contract](blueprint-contract.md). Normalize into established_fact,
experimental_result, theoretical_result, hypothesis, interpretation, planned_experiment,
planned_analysis, unsupported_idea, literature_evidence, known_limitation or unknown.
Do not infer completed results from planned/hypothesized/expected material. The
bundled normalizer initializes unclassified text as unknown. Classification and
support judgments require actual source reading, not a keyword-based truth detector.

Separate supported/partial claims, unsupported desired claims, missing evidence,
theory, experiments and literature. If desired C only has indirect support, say so.
Offer Route A retaining evidence with calibrated claims, and Route B retaining a
stronger desired claim as a research target with explicit work needed. Neither route
fabricates success. Normalize evidence status once and freeze it for the blueprints.

## Build the scientific argument first

Run the shared Scientific Coherence Audit on the material corpus and graph. Apply
the same local theory, identification, fairness, entailment and counterfactual rules
as Audit. State the limits of incomplete context; do not certify a whole paper from
notes. Construct claim/evidence/experiment-or-theory/assumption matrix and main chain.
Report strong, weak, missing and circular links plus alternative explanations.
An orphan result can suggest a supported narrative opportunity. An orphan claim,
redundant experiment, missing control or unsupported mechanism remains a finding.

## Thesis and architecture search

Generate 2–4 theses only when genuinely different scientific hierarchies are supported.
With one viable anchor, offer one and explain why alternatives would overstate the
materials. Each thesis is 2–5 sentences identifying problem, central claim, actual
novelty, credible evidence and main boundary. Metadata includes central_claim,
support_level, main_evidence, novelty_delta, strength, risk and best_fit_venue.
Mechanism/method/problem/assumption-removal/empirical-discovery anchors need real
scientific differences, not paraphrases of the same thesis.

Build a hierarchy with central, phenomenon, method, theory, empirical, explanatory,
robustness and boundary claims only as applicable. Each names importance, evidence,
support status SUPPORTED/PARTIALLY_SUPPORTED/PLANNED/UNSUPPORTED, assumptions, scope,
overclaim risk and sections. Planned/unsupported claims cannot be established
contributions, results or conclusions. They can be marked research gaps or hypotheses.

From this same evidence/claim graph search 2–4 actual architectures when warranted.
Problem-first, mechanism-first or assumption-removal are possibilities, not defaults.
For each show central tension, opening anchor, claim order, advantage, risk, required
evidence and when useful. Recommend the scientifically best-supported anchor before
considering voice/venue fit. The most impressive sounding thesis gets no privilege.

## Blueprint depth and paragraphs

“论文大纲” means Compact. Subsections have purpose, claims, evidence, transition and
short sketch. Full means section → subsection → located paragraph IDs. Each paragraph
has role, purpose, claim/evidence IDs, logical predecessor/successor, content to include
and avoid, reference candidates, short writing instruction and a 2–5 sentence sketch
when useful. Roles come from `architect.ROLE_TYPES`. A direct result paragraph may be
shorter. Never impose a five-part paragraph template or add random rhythm variance.

All sketches obey H1–H3, naturalization and scientific invariance. Structured metadata
can use colons; sketch prose cannot. No unsupported novelty/causality/scope/statistics,
inflated language, unnecessary self-defense or stacked references. An unresolved
Critical/Major issue appears where relevant as **SCIENTIFIC GAP TO RESOLVE**. Do not
write an apparently complete argument around it. Bound incomplete plans honestly.

## Section-specific architecture

- Introduction moves through the actual problem/tension, gap, insight/hypothesis,
  approach and supported contribution preview as needed. Avoid generic field openings
  and feature lists. Six such roles are an abstraction, never six required paragraphs.
- Related Work organizes scientific axes, assumptions, families and structural delta,
  not a paper catalogue. Each subsection says what existing work establishes and what
  remains unresolved. Introduction citations serve the main argument; full taxonomy
  belongs here. Unknown prior-work delta cannot become novelty.
- Method gives each major component's purpose, solved problem, assumptions, output
  and connection to the next component. Tie construction to scientific motivation,
  not an implementation walkthrough.
- Theory separates motivation, definitions, assumptions, propositions, lemmas,
  intuition, formal proof, algorithm connection and empirical implications. Include
  only available theory. Explain what it constrains about the actual method.
- Experiments organize scientific questions, not just datasets. Each subsection
  declares question, hypothesis, comparison, control, metric, expected interpretation,
  actual result, allowed conclusion and forbidden overinterpretation. Planned results
  stay planned; a missing control is visible. Use experiments to test claims.
- Results separate observation, interpretation, mechanism and implication. Associative
  evidence uses associative wording and does not become a mechanism by placement.
- Discussion addresses what was learned, why, hypothesis revisions, alternatives,
  boundaries and failure cases. It does not repeat Results or dilute supported findings
  with anticipatory apologies. Real limitations remain accessible.
- Conclusion restates established claims only. No first appearance of a new mechanism,
  generalization, result, limitation or contribution. Previously established boundaries
  can be restated. Newly discovered limits belong earlier before conclusion writing.

## Portfolio, literature and alignment

Judge the experiment portfolio against central claims. Classify required, strongly
recommended, optional, redundant and orphan experiments. Performance, fairness,
ablation, mechanism, robustness, failure, sensitivity, statistical reliability and
generalization are axes to consider, not a mandatory checklist for every paper.
Any proposed experiment says which logic gap it resolves and why this design identifies
the claim. “More experiments” is not an adequate repair.

Map supplied literature to problem importance, closest prior method, theoretical
foundation, competing explanation or baseline justification. Check each use against
what the source establishes. No unsupported citation, disconnected literature cluster
or vanished closest-prior-work delta. External retrieval follows permissioned grounding
from Scientific Coherence Audit, and does not overwrite internal inconsistency findings.

After construction audit theory → prediction → measured quantity/valid proxy → result
→ bounded conclusion. Identify decorative/unconnected theory, unjustified method
guarantees and mechanism leaps. Repairs can move/remove material, add analysis or
experiment, calibrate a claim or clarify a supported connection. Their requirements
and epistemic status must remain explicit.

Outline review checks thesis visibility, purpose of major sections, evidence for each
central claim, experiment purpose, theory/experiment connection, entailed conclusion,
no unsupported leap, no duplicated role, contribution visibility and proportionate
boundary visibility. Failed structure is revised structurally, not merely polished.
Provide alternative openings, claim orders, experiment organization, theory placement
and discussion framing only when there is a real advantage/risk/fit tradeoff.

## Optional drafting

Only after explicit blueprint approval, generate one requested section at a time.
Audit the draft against approved hierarchy, evidence, scope, terminology and material
status, re-extract facts, run semantic/mechanical/style gates, then continue. Missing
science cannot be filled by draft prose. Drafted sections remain proposed if checks
fail or context is unresolved. No default one-shot full manuscript generation.
