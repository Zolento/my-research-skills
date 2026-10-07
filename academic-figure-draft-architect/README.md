# Academic Figure Draft Architect

A scientific figure planning skill that turns code, manuscripts, configurations
and research notes into Markdown character diagrams. The drafts provide a semantic
blueprint for researcher review and subsequent SVG, TikZ, Illustrator or Figma work.
The output is a figure plan rather than a rendered illustration.

| Input | Work | Output |
|---|---|---|
| Code and experiment configuration | Trace the implemented computation and training setup | Grounded modules, relationships and alternative figure layouts |
| Manuscript or method notes | Identify claims, stages and unresolved details | Character diagrams with evidence and uncertainty records |
| Figure requirements | Select visual grammar and level of detail | Recommended draft, element inventory and drawing handoff |

The default is three structurally different drafts. `NUM_DRAFTS` allows two to five.
`FIGURE_TYPE` and `SKETCH_STYLE` can be inferred when absent, with the inference
reported explicitly. Ask about narrative focus when the choice changes what the
figure communicates. A Mermaid diagram alone does not satisfy the character-diagram contract.

## Workflow

Read sources → extract entities and relations → resolve the semantic questions
→ select distinct visual grammars → draw character diagrams → assemble the output
contract → check alignment, evidence and constraints.

Read actual entry points such as `forward`, `training_step`, `loss`, `solve` and
`reconstruct`. Preserve iterative structure and separate training from inference.
Choose the layout after establishing semantics, rather than fitting the method
into a generic encoder-decoder diagram.

Each result includes Figure Understanding, Evidence Summary, candidate drafts,
a recommendation, Alignment Notes, Uncertainties, SVG Handoff Notes and a Figure
Element Inventory. Aggregation and renamed elements require an explicit source map.
Save drafts under the target project's `.figure-drafts/`, using an identifier such
as `F001-method-overview.draft.md`.

## Core principles

Every module, arrow, variable and training relationship must trace to the inputs.
Do not add a component to make the diagram look complete. The evidence policy uses
four levels

| Level | Meaning | Treatment |
|---|---|---|
| A | Directly Observed | Include with a source location |
| B | Strongly Implied | Include with the source and semantic abstraction |
| C | Author-Level Interpretation | Include with an explicit operation-to-element mapping |
| D | Speculative | Keep in Uncertainties or an explicitly marked placeholder, outside the main factual diagram |

Ground truth must not appear as an inference input. A frozen module must not look
trainable. An iterative solver must not be collapsed into a single network pass.
User-provided `MUST_INCLUDE` and `MUST_NOT_INCLUDE` lists are hard constraints.

Solid arrows represent forward or inference flow. Dashed arrows represent training
supervision. Dotted arrows denote optional or conceptual relationships. Double lines
separate domains or stages rather than showing data flow. Character alignment uses
display width, with CJK characters occupying two columns.

`SKETCH_VARIANTS=both` provides clean and enhanced versions of each draft.
`DETAIL_LEVEL` selects overview, medium or detailed content. Domain-specific facts
and uncertainty stay the same across visual variants.

The contracts are in [SKILL.md](SKILL.md),
[evidence policy](references/evidence-policy.md),
[source reading](references/source-reading.md),
[figure semantics](references/figure-semantics.md),
[visual grammar](references/visual-grammar.md),
[character design language](references/ascii-design-language.md),
[sketch primitives](references/sketch-primitives.md),
[sketch templates](references/sketch-templates.md),
[figure types](references/figure-types.md) and
[output contract](references/output-contract.md).

## Mechanical helpers and semantic trust boundary

Install the skill with

```sh
npx skills add Zolento/my-research-skills -g -s academic-figure-draft-architect -y
```

From this directory, check a draft or run the offline tests

```sh
python3 scripts/check_draft.py path/to/F001-method-overview.draft.md
python3 scripts/check_draft.py --strict \
  --forbid "Cross Attention" --require "Flow Prior" \
  path/to/F001-method-overview.draft.md
python3 scripts/check_draft.py --json path/to/F001-method-overview.draft.md
python3 -m unittest discover -s scripts -p 'test_*.py'
```

Exit 0 means the draft passed, 1 means a usage/file error, 2 means warnings and 3
means a contract violation. Strict mode promotes warnings to errors.
`--forbid` scans diagram content, the evidence table and element inventory, so the
prose can explain what was excluded. `--require` scans the complete document.

Mechanical checks cover required sections, character diagrams, IDs, status values,
evidence declarations, alignment and layout diversity. Source fidelity and scientific
meaning require review against the code or manuscript. A passing draft is not proof
that the depicted method is scientifically correct.

## Examples

- [Example index](examples/README.md) records coverage by figure type, grammar and parameter.
- [Code-grounded draft](examples/example-code-grounded.md) traces a small MRI reconstruction
  implementation and shows an iterative solver, frozen prior and target adaptation.
- [Uncertainty handling](examples/example-uncertainty.md) keeps unsupported elements outside the main diagram.
- [Sketch legend](examples/example-sketch-legend.md) shows shape semantics and paired sketch styles.
- [Domain adaptation](examples/example-domain-adaptation.md) separates stages and data access.
- [Automatic inference](examples/example-auto-inference.md) records inferred presentation choices.

Start from the [figure template](templates/figure-draft.template.md) and
[element inventory](templates/element-inventory.template.md).

## Known limits

The helper checks a Markdown contract, not rendered SVG geometry or algorithmic
correctness. Display-width heuristics cannot account for every font or renderer.
Sparse source material limits the diagram, and missing evidence remains visible.
Not every figure type or visual grammar has a worked example.

This skill is self-contained. A proposal from another skill can be supplied as
input, but no other skill's code, state or directory layout is required.

## Recommended next evaluation

Give a source-grounded draft to a collaborator unfamiliar with the code and to a
renderer unfamiliar with the method. Check whether both recover the same stages,
data access, frozen/trainable status and iterative structure. Compare the rendered
figure against the original sources, and add missing example coverage using actual
implementations rather than invented components.
