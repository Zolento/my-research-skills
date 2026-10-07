# Suggestion taxonomy and quality contract

## Categories

| Internal category | User bank | Inspect |
|---|---|---|
| narrative | Narrative | motivation, tension, gap, contribution hierarchy, claim order, introduction progression, method motivation, result interpretation, discussion and conclusion |
| paragraph | Paragraph structure | role, progression, length imbalance, repeated mini conclusions/transitions, excessive symmetry, jumps, redundant setup, density |
| claims | Claims and evidence | nearby evidence, actual quantitative effect and comparator, novelty delta, calibrated strength, abstract/body agreement |
| language | Language and naturalness | overpolishing, syntax/lexical regularity, empty meta prose, symmetry, nominalization |
| references | References and presentation | statement-first narration, citation meaning, reference identity and attachments |
| defensive | Defensive language | necessary calibration, optional hedge, redundant defense, unsupported weakening |

All six categories are inspected, but empty categories stay empty. Keep as is is
a separate protected set, not a seventh suggestion quota. One underlying problem
gets one entry; frequency and representative locations describe repetition.

## Internal JSON bank

Top-level keys are `schema` (manuscript-suggestions@1), `manuscript_digest`, `mode`
(audit/suggest/revise), `short_diagnosis`, `reviewed_categories` (all six),
`suggestions`, `keep_as_is`, and `quality_audit`.

Each suggestion contains

```
id, category, severity, confidence, location, original_span,
diagnosis, why_it_matters, scientific_risk, recommended_action,
alternatives, rule_refs, apply_by_default
```

`location` is `{start, end}` using zero-based Unicode character offsets and an
exclusive end, not byte offsets. `original_span` must match exactly. Confidence
is high/medium/low. Severity is critical/major/moderate/minor. Scientific risk is
low/medium/high. Rule references identify applicable N/P/C/L/H/F rules from these
references, not invented venue requirements. Important means critical or major.

Alternatives have `id`, `option`, `tradeoff`, and `direction`. Directions describe
different editorial operations, such as move the problem constraint to the opening,
introduce tension before method, or sharpen a topic sentence in the current order.
Two wording synonyms are not two directions. In Suggest and Revise, an important
issue gets 2–3 genuine alternatives. Audit may simply identify actions. Small
grammar fixes need no manufactured alternatives. `apply_by_default` is false for
every high-risk entry and all Audit/Suggest entries.

Keep entries contain `location`, `original_span`, `rationale`. Preserve already
clear wording, domain vocabulary and helpful author variation. Never edit them
just to meet an output count. When everything is good, an empty bank plus Keep
as is is a successful result.

## Separate editorial quality audit

An independent reading of the bank and manuscript records `findings` as a list of
`{suggestion_id, checks}`. `checks` contains exactly `actionable`,
`distinct_alternatives`, `not_synonym_only`, `not_quota_driven`, `calibrated_claim`,
`preserves_voice`, each PASS/FAIL/UNKNOWN. Findings cover every suggestion exactly
once and carry `manuscript_digest` and `bank_digest` (bank without quality_audit).
No findings are needed for an empty bank. This is structured LLM judgment, not
a regex quality classifier. Script validation checks coverage and honors FAIL or
UNKNOWN; it cannot certify an evaluator's sincerity or semantic competence.

F1 necessary calibration is retained. F2 optional hedge is an editorial choice.
F3 redundant defensive language can be consolidated while retaining the boundary.
F4 claim weakening without evidence basis is a problem, as is unsupported confidence.
L1 minimum intervention, L2 rhythm, L3 contextual lexical density, L4 meta prose,
L5 symmetry, L6 nominalization. N1 hierarchy/tension; P1 paragraph roles; C1 claim
evidence alignment. H1 punctuation, H2 cross-reference stacking, H3 calibrated confidence.
