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

## Preset library and intent router (v2.3.1)

Sixteen rehearsed protocols inside the four semantic entries. You do not memorise ids: say what
you mean, and the router resolves it (explicit id > alias > intent + entry > intent > loop
suggestion). Policy: [references/preset-policy.md](references/preset-policy.md); protocols:
[presets/](presets/).

| Group | Presets | Entry |
|---|---|---|
| User-invoked (6) | `research-loop`, `paradigm-escape`, `research-recovery`, `scientific-replanning`, `research-audit`, `research-review` | `continue-research` / `explore` / `audit` |
| Loop-triggered recovery (7) | `evidence-conflict-repair`, `context-drift-recovery`, `memory-consolidation`, `resource-recovery`, `experiment-failure-recovery`, `loop-health-check`, `stagnation-breaker` | `continue-research` / `audit` |
| Self-evolution (3) | `strategy-evolution`, `hypothesis-rebalance`, `discovery-replay` | `continue-research` / `explore` / `audit` |

The package is data-driven: `preset-registry.json` is the source of truth for ids, entries,
triggers, execution scopes, protocol paths and the 16×3 intent examples; `shared-contract.md` is the
common contract every protocol loads first; `presets/<id>.md` are 16 independent protocols;
`router-fixtures.json` is the intent-routing base test (48 positive + 5 guarded cases).
A call loads the shared contract plus **one** protocol — never all sixteen.

```sh
python3 scripts/preset_router.py list                            # 16 presets, groups, scopes, auto signals
python3 scripts/preset_router.py load --preset research-review    # what one call loads (+ not_loaded)
python3 scripts/preset_router.py check --fixtures                 # registry ↔ protocol + provided fixtures
python3 scripts/preset_router.py resolve --text "继续自动科研"     # natural language → preset
python3 scripts/preset_router.py resolve --text "训练 OOM 了"      # → experiment-failure-recovery (diagnose first)
python3 scripts/preset_router.py resolve --text "不要审计"         # → HOLD (negation respected)
python3 scripts/preset_router.py inspect --preset paradigm-escape  # full machine-readable contract
python3 scripts/preset_router.py trigger --state <research-state.json>   # machine signals → recovery, or HOLD
python3 scripts/preset_router.py run --preset loop-health-check --state <research-state.json>
python3 scripts/preset_router.py record --state <research-state.json> --preset stagnation-breaker
python3 scripts/preset_router.py check                           # registry ↔ protocol parity
```

**Start the autonomous loop:** `resolve --text "继续自动科研"` (or `--preset research-loop`) runs the CIE
scientific loop — Recall → Understand → Discover → Predict → Intervene → Verify → Revise →
Consolidate → Loop — inside the existing stages and gates.

**Who triggers what:** the event listener, dispatcher and any background loop belong to the
caller — the existing Scheduler, the runtime, or a platform hook. This skill ships an executable,
idempotent trigger/record interface (`trigger`, `record`, `cognition/recovery-log.jsonl`) with
cooldown and per-fingerprint attempt caps; it does **not** install a daemon and does not claim
unattended auto-triggering. A user preset the registry marks as event-triggerable is only ever
*recommended* (`recommended_only`), never started by the trigger.

**When the loop stalls:** the trigger engine reads machine-readable state only and proposes
`stagnation-breaker` (behaviour switch and smallest decision-changing intervention) or
`hypothesis-rebalance` / `paradigm-escape` when candidates have converged on one representation.
Recovery is guarded: the same `(state_version, preset, signal fingerprint)` runs once, then cooldown
and a per-fingerprint attempt cap apply, and the loop ends in an explicit `HOLD` instead of repeating.
Hard gates are never relaxed, and the AALG diagnostic budget is never refreshed.

**Engineering failure vs scientific failure:** OOM, NaN, crashes, broken dependencies and budget
exhaustion route to `resource-recovery` / `experiment-failure-recovery`, which classify the failure
and plan the repair. They never touch `claims[].status`, never write an experiment's scientific
verdict, and never re-run the same experiment without a fresh PEIG/AALG receipt.

**Cross-session memory:** `research-recovery` and `context-drift-recovery` rebuild the skill contract,
canonical state and CIE projections **from disk** (never from chat history), and `memory-consolidation`
rebuilds projections after legal revisions without touching canonical science.

**Self-evolution limits:** `strategy-evolution` may only update already-authorised strategy memory and
exploration advice. Its advice enters the real action selection through the Strategy Decision Adapter
(`strategy_memory.py decide`), which may reorder **inside one `EIG ÷ cost` tier** and only among actions
that already pass the hard gates; it records candidates, advice, choice, adoption and reason in
`scheduler.strategy_decisions[]`, and the next round consumes it. It cannot change the fixed priority
rules, the Research Contract, evidence qualification, the AALG budget, anchors or execution permissions.
Adoption is **not** evidence of research capability: that is measured by Discovery Replay and by
scientific results (see [references/preset-policy.md](references/preset-policy.md) §7 for L1/L2/L3).

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

### Zotero local library

The local literature source is served by the Zotero desktop Local API by default, and
falls back to `docs/refs/` when that API is unreachable. Enable it in Zotero under
`Settings → Advanced` (`Allow other applications on this computer to communicate with Zotero`).
See [zotero-local-api.md](references/zotero-local-api.md) for the endpoint and authorization contract.

```sh
python3 scripts/zotero_client.py --probe                 # reachability and Server ID
python3 scripts/zotero_write.py                          # capability only; never writes
python3 scripts/literature_search.py -q "..." --local-only --zotero-fulltext
python3 scripts/zotero_refs.py --check                   # drift against docs/refs/
```

Retrieval, full-text search and deep reading are read-only. Writes go through
`scripts/zotero_crud.py` and require an explicit user request plus an authorization prompt.
`delete_paper` defaults to dry-run; the Local API `DELETE` is a permanent erase, not trash.
An index hit is reported as `indexed_fulltext` and never carries a page number; page-level
evidence comes only from parsing the actual PDF.

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

## Cognitive memory across sessions

Research State records what we believe about the world. It does not record how our
understanding of a mechanism changed, or what the next session must recover before it can
reason. The Cognitive Insight Engine adds that layer without adding a state slot.

```
canonical   research-state.json + frozen preregistration      sole authority
event       cognition/model-revisions.jsonl                   append-only, no epistemics
derived     cognition/index.json, cognition/context-brief.md  rebuildable
```

A mechanism's support level is computed from canonical facts, never declared by the agent
that proposes it. Lifecycle decisions such as dormant or merged are recorded explicitly;
they are decisions, not measurements. Recall is tiered into hot, warm and cold memory and
bounded by a context budget, so a session does not receive the whole history.

```sh
python3 scripts/cognition.py build --state .research-idea-pipeline/routes/A/research-state.json
python3 scripts/cognition.py check --state .research-idea-pipeline/routes/A/research-state.json
python3 scripts/cognition.py brief --state .research-idea-pipeline/routes/A/research-state.json --budget 4000
```

The builder never writes `research-state.json`; `check` compares the stored projection
against a fresh rebuild and fails on drift. See the
[cognitive memory policy](references/cognitive-memory-policy.md) and the
[architecture note](docs/cognitive-insight-engine.md).

Predictions become decidable through a frozen `criterion` inside the existing
`preregistration.outcomes[]`. An observation is compared with it and classified as held,
deviated, within tolerance, exploratory, invalid or untestable. Two mechanisms compete only
when each owns a frozen prediction with a different criterion; rewording is not a
distinction. See the
[prediction and competition contract](references/prediction-anomaly-competition.md).

```sh
python3 scripts/prediction_compare.py compare --state <state.json> --packet observation.json
python3 scripts/prediction_compare.py compete --state <state.json> --competition CP1
python3 scripts/prediction_compare.py switch  --state <state.json>
```

## Taking over an existing project

A project that already has a canonical `research-state.json` is **initialized**. Loading a
newer skill must not look like a fresh start, so the entry stays `continue-research` and no
Bootstrap runs. The takeover is read-only: state, scheduler and the execution ledger are
byte-identical afterwards, versions, claim statuses, experiment ids, the anchor and the
diagnostic budget are untouched, and no prediction is invented for an experiment that never
froze one. Cognitive memory is reconstructed from canonical evidence and every
reconstructed entry is marked retrospective.

```sh
python3 scripts/legacy_handoff.py detect --state .research-idea-pipeline/routes/A/research-state.json
python3 scripts/legacy_handoff.py take   --state .research-idea-pipeline/routes/A/research-state.json
```

A severe compatibility error writes nothing and exits 3. Rebuilding a new Research State to
work around it is not an option. See the [handoff contract](references/legacy-handoff.md).

## Scientific value and adaptive discovery

Ordering by `EIG ÷ cost` alone rewards cheap diagnostics that change no decision. Decision
value and discovery potential are therefore judged separately, per dimension, each with a
canonical source and an explicit uncertainty — and with no aggregate score by design. Taste
memory splits into what the user owns (`contract`, read-only) and what outcomes calibrated,
and the discovery menus reuse the existing `P1`—`P6` operators rather than adding an
Exploration Agent.

```sh
python3 scripts/strategy_memory.py value     --state <state.json> --target H1
python3 scripts/strategy_memory.py operators --state <state.json> --scheduler scheduler.json
python3 scripts/strategy_memory.py recommend --state <state.json> --scheduler scheduler.json
```

No operator is ever permanently banned: a downgrade needs at least two independent failures,
is scoped to the problem structure where they happened, and always carries reactivation
conditions. `scheduler.json` stays read-only. See the
[value and strategy contract](references/scientific-value-adaptive-discovery.md).

## Replay and verification

Claims about better discovery are easy to make, so the repository ships the means to check
them offline. Replay cases carry the state, revisions and observations as they were, plus a
hidden answer that never reaches the runner — a leak is detected rather than assumed away.
Seven dimensions are scored independently with no weighted total, four ablation arms are
compared, and an undersized sample reports that no improvement may be claimed. The ten
adversarial cases reward correct stopping as much as correct continuing.

```sh
python3 scripts/research_replay.py suite --dir examples/replay/adversarial --runs 2
python3 scripts/research_replay.py smoke --work /tmp/cie-smoke
```

**No real Agent A/B test has been run.** The fixtures are synthetic, no model is called, and
the ablation deltas are properties of the offline runner. See the
[replay contract](references/discovery-replay.md).

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
| [Cognitive memory fixture](examples/cognition/README.md) | Mechanisms, a competition and an anomaly derived from a synthetic state |
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

## Managed execution (PEIG/AALG)

Use the [execution contract](references/execution-identifiability.md),
[protocol template](templates/preflight-protocol.template.json),
[diagnostic template](templates/diagnostic-protocol.template.json) and
[manifest template](templates/execution-manifest.template.json).

```sh
python3 scripts/experiment_execute.py scheduler-check --state state.json --scheduler scheduler.json
python3 scripts/experiment_execute.py diagnose --state state.json --diagnostic diagnostic.json
python3 scripts/experiment_execute.py issue --state state.json --experiment X3 --scheduler scheduler.json --manifest manifest.json --output receipt.json
python3 scripts/experiment_execute.py run --state state.json --experiment X3 --scheduler scheduler.json --manifest manifest.json --receipt receipt.json
```

Run defaults to dry-run and consumes the receipt. Add --execute only for authorized
real execution. Development tests never run GPU training. Keep the route .execution
ledger/key; budget reservations persist across rewritten cards and new IDs/seeds.
PEIG revisions and equivalent diagnoses terminate at frozen project limits.

Install/copy the complete package, including schemas, then run release_check.py in
that copy. Historical states remain readable but require actual reviewed designs
for new execution. Scope of interception: this runner only. Direct shell/SSH,
notebooks, remote schedulers and existing jobs need site-specific integration.
Hashes and local seals do not authenticate scientific judgments or unlisted files.
