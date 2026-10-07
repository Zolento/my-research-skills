# Research Idea Pipeline

A research search skill centered on a persistent Research State. It connects
literature discovery, hypothesis search, experimental evidence, adversarial review
and paper narratives. Discovery expands the search space. Assurance checks what the
evidence permits. R0–R14 are capabilities that can be revisited as the project evolves.

| Entry | Input | Output |
|---|---|---|
| `start-project` | Research goal, constraints and available materials | Project intake, research contract and initial state |
| `continue-research` | Existing project and current evidence | State review and the next justified research action |
| `explore` | Research question, literature or a candidate direction | Diverse hypotheses, alternatives and discriminating tests |
| `audit` | Existing claims, proposal, results or narrative | Source-grounded findings, missing evidence and repair paths |

An existing code project starts with Bootstrap observation before research advances.
Declare the project anchor rather than assuming that higher benchmark performance
is the goal. Supporting routes must explain how they affect that anchor. Changing
the project direction requires the user's instruction.

## Workflow

Research contract → field mapping → Discovery and Assurance → evidence contract
and preregistration → experiment execution → Evidence Outcome Analysis → R10/R11
state update → Assurance and decision gate → next action.

When evidence is ready for communication, R12 builds a narrative from the state.
Claim hierarchy search determines the scientific story. Rhetorical realization
then searches equivalent expressions of that frozen story. Equivalence checks,
blind claim recovery and paired sensitivity diagnostics precede adversarial review.
Narrative generation cannot rewrite claims, evidence, scope or uncertainty in the state.

R9.O separates valid negative evidence from invalid execution. Each claim and
hypothesis receives its own scoped assessment, so performance, mechanism and
robustness can lead to different decisions. Negative knowledge and stop rules are
retained for the next Discovery and Planning pass. CONTINUE, RETRY, REDESIGN, PIVOT,
STOP and HOLD remain experiment-level recommendations, separate from R14's route decisions.

## Core principles

Keep claims traceable to evidence and explicit alternatives. Research State contains
eight first-class collections, with separate scheduling telemetry. Preserve failed
and refuted hypotheses rather than deleting inconvenient history. Local evidence
must not become a global conclusion.

Freeze experimental predictions and project replication criteria before results.
A training crash cannot falsify a hypothesis. One negative run cannot automatically
falsify a central hypothesis. Attribution requires inspected sources, alternatives
and a test that distinguishes them. PIVOT and STOP create persistent stop rules.
A different seed or code commit does not, by itself, release a stopped protocol.

Make supported strengths visible without inflating novelty, significance, causality
or scope. Rhetorical search preserves limitations and optimizes claim, evidence,
prior-work delta and boundary recovery. It does not maximize a reviewer score.

Attempt web search first, then query the local library and multiple sources.
Verify original pages discovered through web search. Record unavailable tools and
continue with accessible sources. Explicit offline requests skip online retrieval.
Source outages, missing dependencies and unverified metadata are not evidence
that prior work is absent. Offline results cannot establish a novelty claim.

The following triggers require all enabled sources and expanded retrieval.

| Trigger | Condition | Minimum level |
|---|---|---|
| T1 | Priority or novelty claim such as first or previously unexplored | L3 exhaustive |
| T2 | Unclear theory, proof, assumptions or convergence | L2 enhanced |
| T3 | Uncertain feasibility | L2 enhanced |
| T4 | Novelty judgment in R7 or R12; R3–R6 concept screening is the L2 exception | L3 exhaustive |
| T5 | Fewer than five local hits | L2 enhanced |
| T6 | Request for comprehensive retrieval | L3 exhaustive |
| T7 | Claim that existing work has not addressed an issue | L2 enhanced |
| T8 | Observed method bottleneck, repeated failures or diagnostics that no longer change method decisions | L2 enhanced |

L2 uses at least four queries. L3 uses at least eight, including negative results
and counterclaims. Stop only when the policy's saturation criteria are met. A
priority claim additionally requires specialist literature verification and a
negative-search record; retrieval alone cannot establish priority.

The operating contracts are in [SKILL.md](SKILL.md), the
[Research State policy](references/research-state-policy.md),
[claim-first policy](references/claim-first-policy.md),
[evidence policy](references/evidence-policy.md),
[literature policy](references/literature-policy.md) and
[scheduler policy](references/scheduler-policy.md).
Use the [invocation contract](references/invocation-prompts.md) for entry selection,
[project intake](references/project-intake.md) for existing projects and
[project layout](references/project-layout.md) for route files, anchor changes and experiment IDs.

## Mechanical helpers and semantic trust boundary

Install the skill with

```sh
npx skills add Zolento/my-research-skills -g -s research-idea-pipeline -y
```

From this directory, use the state and release gates

```sh
python3 scripts/state_check.py --check path/to/research-state.json
python3 scripts/render_status.py path/to/research-state.json --out path/to/STATUS.md
python3 scripts/release_check.py
```

The state gate retains S1–S7 shape checks and V1–V24 scientific/reference checks.
Projects with a frozen outcome policy also pass EO1 receipt and transition checks.
Legacy states remain readable, but adopting the outcome policy requires actual
source-grounded historical analyses. Missing logs cannot be replaced with invented audits.

The outcome helper validates proposals, applies a copy and exposes planning constraints

```sh
python3 scripts/evidence_outcome.py validate --state state.json --packet result.json \
  --analysis analysis.json --audit audit.json
python3 scripts/evidence_outcome.py apply --state state.json --packet result.json \
  --analysis analysis.json --audit audit.json --output next-state.json
python3 scripts/evidence_outcome.py constraints --state next-state.json
python3 scripts/evidence_outcome.py check-plan --state next-state.json --experiment X-next
python3 scripts/evidence_outcome.py decision --state next-state.json \
  --experiment X-result --assurance assurance.json
```

It preserves the source state and refuses an existing output path. Applying a result
does not execute a followup. Missing or unknown outcome audits block application.
Unknown experimental validity can be recorded as inconclusive when the audit confirms
that no unsupported inference is applied. Post-update Assurance is required before
releasing the next decision.

Search and PDF indexing use a working interpreter with `arxiv` and `pypdf` available.
Check the environment before retrieval

```sh
python3 scripts/literature_search.py --check-env
python3 scripts/literature_search.py -q "diffusion model combinatorial optimization" --max 20
python3 scripts/literature_search.py -q "discrete diffusion combinatorial optimization" \
  --level L3 --exhaustive --also-query "limits of discrete diffusion optimization" --json
python3 scripts/refs_index.py --check
python3 scripts/refs_index.py --migrate
```

Search exit 2 reports partial or unavailable sources, and exit 4 reports an unmet
environment requirement. State and outcome gates use exit 0 for PASS, 3 for a failed
gate and 4 for review or input/environment errors. The release gate requires exit 0
and a final PASS. These commands have different contracts, so inspect each command's output.

Mechanical checks cover structure, references, source binding, allowed transitions
and audit completeness. Scientific validity, equivalence, attribution and scope
coverage require source-grounded review. Digests bind artifacts but do not certify
an evaluator's identity or judgment. The outcome and rhetorical helpers do not call
reviewer models or fabricate their responses.

Detailed contracts are in the [experiment loop](references/phase-r9-r11-experiment-loop.md),
[outcome workflow](references/evidence-outcome-analysis.md),
[outcome schema](references/evidence-outcome-contract.md),
[narrative workflow](references/phase-r12-narrative.md),
[rhetorical operators](references/rhetorical-operators.md),
[equivalence policy](references/rhetoric-equivalence-policy.md) and
[structural equivalence policy](references/structural-equivalence-policy.md).

## Examples

| Example | What it demonstrates |
|---|---|
| [example-project-layout.md](examples/example-project-layout.md) | Multiple routes, state projections, experiment IDs and document placement |
| [example-full-pipeline.md](examples/example-full-pipeline.md) | Discovery, evidence planning, narrative and Assurance |
| [example-field-mapping-standalone.md](examples/example-field-mapping-standalone.md) | Standalone field mapping and retrieval |
| [example-d-narrative.md](examples/example-d-narrative.md) | Claim-first narrative selection |
| [example-followup-review.md](examples/example-followup-review.md) | Continuing an existing review |
| [example-writing-tier.md](examples/example-writing-tier.md) | Controlled-language writing tiers |
| [Rhetorical realization](examples/narrative-realization/README.md) | Frozen sources, four expression profiles, recovery probes and fragility checks |
| [Evidence outcomes](examples/evidence-outcome/README.md) | Positive, negative, invalid, pivot and mixed state transitions |
| [Structural equivalence fixtures](examples/structural-equivalence/) | Near-neighbor audits and structural deltas |
| [Literature library](docs/refs/README.md) | Portable PDF metadata, sidecars and indexing |

Structural equivalence fixtures cover
[equivalent.json](examples/structural-equivalence/equivalent.json),
[reframing-neighbor.json](examples/structural-equivalence/reframing-neighbor.json),
[transfer-only.json](examples/structural-equivalence/transfer-only.json),
[component-neighbor.json](examples/structural-equivalence/component-neighbor.json),
[mechanism-neighbor.json](examples/structural-equivalence/mechanism-neighbor.json),
[formulation-delta.json](examples/structural-equivalence/formulation-delta.json) and
[paradigm-candidate.json](examples/structural-equivalence/paradigm-candidate.json).

Use the [state template](templates/research-state.template.json),
[outcome report](templates/evidence-outcome-analysis.md),
[route README](templates/README.route.md),
[route index](templates/INDEX.md),
[root index](templates/INDEX.root.md) and
[status template](templates/STATUS.md) as the corresponding artifact skeletons.

## Known limits

Structured audits can be wrong. Contract tests establish transition behavior and
source integrity, not scientific detection accuracy. A protocol fingerprint is a
syntactic guard rather than a proof of semantic equivalence. Scope labels require
exact binding, with narrower conditions recorded in the assessment.

The rhetorical realization MVP uses fixed source units and can reject correct
paraphrases. Recovery records cannot prove that an external reviewer used the
claimed model or a fresh context. Missing panel data remains incomplete, and
RHETORICALLY_FRAGILE diagnostics remain visible. D5 and G1–G5 still apply.

Retrieval coverage depends on the enabled sources, service availability and metadata
quality. Venue-specific judgments need verified standards. No offline release result
certifies an experiment, proof, novelty claim or future submission.

## Recommended next evaluation

Use preregistered experiments with real logs to compare source-grounded outcomes
against expert judgments. Measure invalid/negative confusion, local scope preservation,
attribution errors, replication handling and adherence to stop rules.

For R12, hold Research State and claim hierarchy fixed, compare multiple expressions
across reviewer models and retain all observations. Evaluate claim, evidence,
novelty-delta and boundary recovery alongside sensitivity. Compare comprehension-based
selection with a separate score-based evaluation without feeding scores into the selector.
