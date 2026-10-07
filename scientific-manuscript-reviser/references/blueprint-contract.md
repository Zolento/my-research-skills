# Research material and blueprint contract

All objects are JSON and source-bound. `architect.py` checks structure/statuses and
supplied audits; it does not pretend to synthesize scientific arguments with regex.
The agent performs normalization, thesis/architecture search, sketches and independent
outline/alignment review under architect-mode.md.

## Material map

research-material-map@1 contains sources (`id`, `text`), items, missing_context.
Each item has id, type, statement, source_id, location, source_span. Offsets are local
to its original source. `corpus(map)` joins source texts with two newlines for the
shared graph. Retain original source IDs in graph context. The material digest covers
all sources, items and epistemic types. Unknown is the safe normalizer default.

## Blueprint

manuscript-blueprint@1 contains material_digest, graph_digest, coherence_digest, depth,
claims, sufficiency, theses, selected_thesis_id, architectures, recommended_architecture_id,
sections, gaps, experiment_portfolio, literature_roles and outline_options.

Claims have id, claim, claim_type, importance, evidence, support_status, assumptions,
scope, risk_of_overclaim, used_in_sections. Evidence and assumptions use material item
IDs. A supported claim needs established experimental/theoretical/literature/fact
sources, not planned or interpretive items alone. Source type is not proof of validity;
the same scientific audits judge its actual support. Partial support needs a real
established source and its boundaries. Planned/unsupported claims stay labeled.

Sufficiency has supported_claim_ids, partially_supported_claim_ids,
unsupported_desired_claim_ids, missing_evidence, missing_theory, missing_experiments,
missing_literature_grounding. Missing lists are explicit descriptions.

Theses have id, text, central_claim_id, support_level, main_evidence, novelty_delta,
novelty_evidence, strength, risk, best_fit_venue. No novelty evidence means unknown or
not established, not an invented “first” assertion. Alternatives require different
central scientific anchors; if only one is supported, avoid manufacturing another.
The selected thesis has the highest available support level; tied anchors are real
editorial choices. A planned thesis is a research route, not a completed-paper claim.

Architectures have id, central_tension, opening_anchor, claim_order,
strongest_advantage, main_risk, required_evidence, recommended_when. Different
architectures should differ in actual ordering/anchor, not just their descriptions.

Sections have id, title, purpose, claim_ids, subsections. Subsections have id, title,
purpose, claim_ids, evidence_ids, key_transition, paragraphs, experiment_contract
(null when not experimental). Compact includes at least one representative sketch
per subsection; Full lists every intended paragraph. Experiment contracts contain
scientific_question, hypothesis, comparison, control, metric, expected_interpretation,
actual_result, allowed_conclusion, forbidden_overinterpretation. Values use source
IDs or explicit unknown/planned descriptions; no invented measurements.

Paragraphs have id, role, purpose, claim_ids, evidence_ids, logical_predecessor,
logical_successor, content_to_include, content_to_avoid, reference_candidates,
paragraph_sketch, writing_instruction, gap_marker, finding_ids. References point to
source items; they are candidates, not fabricated citation keys or figure numbers.
Gap marker is empty or SCIENTIFIC GAP TO RESOLVE. Gaps map finding_id to paragraph_ids
and requires, preserving every Critical/Major scientific finding. Unresolved desired
claims must be bounded by gap markers, not presented as established contributions.

Experiment portfolio entries have material_id, necessity, claim_ids, logic_gap.
Necessity is required/strongly_recommended/optional/redundant/orphan. Planned
experiments/analyses name a concrete gap. Literature roles have material_id, role,
claim_ids. Role is problem_importance/closest_prior_method/theoretical_foundation/
competing_explanation/baseline_justification. All cited items must actually be literature.
Outline options have area, option, advantage, risk, best_when. No required option count.

## Independent blueprint audit

blueprint-audit@1 contains blueprint_digest, material_digest, paragraph_checks,
outline_checks and alignment_checks. Paragraph checks cover each paragraph once
with paragraph_id, status PASS/FAIL/UNKNOWN and rationale. This reading explicitly
checks new facts, support/epistemic status, scope, terminology, naturalness, voice,
confidence and citation meaning. It is separate from generation.

Outline checks contain the ten `architect.OUTLINE_CHECKS`, each status and rationale.
Alignment checks cover each theory claim with claim_id, status and rationale. Review
the actual method/theory/experiment connection, not a decorative theorem label.
FAIL blocks acceptance; UNKNOWN yields NEEDS_REVIEW. This does not formally verify
proofs. Shared coherence findings cannot be suppressed by a blueprint PASS.

## Approved section draft

Approval has blueprint_digest, approved, section_ids. It represents explicit user
approval, not a self-issued authorization. The draft contract has blueprint_digest,
section_id, claim_order, evidence_ids, original_facts, revised_facts, semantic_audit.
Compare the approved section sketches against the draft with the shared invariance
checker, exact hierarchy/evidence contract and H1/H2 checks. H3/naturalness are in
semantic and editorial passes. Do not generate a different central claim for convenience.
No external model APIs are called or simulated by these helpers.

Theory alignment coverage follows graph node types as well as claim labels.
A theorem, lemma, proposition, bound or corollary cannot skip alignment by using
a different claim_type spelling. Unresolved scientific findings keep drafting blocked.
