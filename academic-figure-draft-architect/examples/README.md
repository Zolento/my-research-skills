# Examples and Coverage

This is an index, not a figure draft. Validate `examples/example-*.md` rather than
`examples/*.md`, which would incorrectly treat this index as a draft.

All five examples use the implementation in [demo-source](demo-source/README.md).
The matrices below distinguish demonstrated features from supported features that
still need a worked example.

## Examples

| File | What it demonstrates |
|---|---|
| [example-code-grounded.md](example-code-grounded.md) | Three structurally different drafts grounded in a small codebase |
| [example-uncertainty.md](example-uncertainty.md) | Missing evidence, `MUST_NOT_INCLUDE` and `[? label]` placeholders |
| [example-sketch-legend.md](example-sketch-legend.md) | Shape semantics and paired clean/enhanced sketches with `SKETCH_VARIANTS: both` |
| [example-domain-adaptation.md](example-domain-adaptation.md) | `domain_adaptation`, `stage_panel`, source-free boundaries and frozen/trainable status |
| [example-auto-inference.md](example-auto-inference.md) | Explicitly inferred figure type and sketch style, including when narrative focus needs clarification |

## Validation

Run from the skill directory. Every draft must pass strict validation with no errors
or warnings.

```sh
for f in examples/example-*.md; do
  python3 scripts/check_draft.py --strict "$f" || exit 1
done
```

## Figure type coverage

| `FIGURE_TYPE` | Examples |
|---|---|
| `method-overview` | example-code-grounded, example-uncertainty |
| `architecture` | example-sketch-legend |
| `training` | Not covered |
| `inference` | Not covered |
| `optimization` | Indirect only, inferred in example-auto-inference |
| `domain_adaptation` | example-domain-adaptation |
| `motivation` | Not covered, requires manuscript evidence absent from demo-source |
| `comparison` | Not covered, demo-source has no baseline implementation |
| `ablation` | Not covered, demo-source has no variant configurations |

## Visual grammar coverage

| Grammar | Examples |
|---|---|
| A `Linear Pipeline` | example-sketch-legend, example-auto-inference |
| B `Dual / Multi Branch` | Not covered |
| C `Hierarchical System` | example-uncertainty |
| D `Iterative Loop` | example-code-grounded, example-auto-inference |
| E `Train vs Inference` | example-code-grounded, example-uncertainty |
| F `Data / Model / Objective` | example-sketch-legend |
| G `Source / Target Domain` | example-code-grounded, example-domain-adaptation |
| H `Temporal / Stage View` | example-domain-adaptation |

## Parameter coverage

| Parameter | Demonstrated | Not demonstrated |
|---|---|---|
| `SKETCH_STYLE` | `auto`, `enhanced`, `stage_panel` | `block_architecture`, `loop_centric`; `clean` appears only as an inferred choice |
| `SKETCH_VARIANTS` | `single`, `both` | None |
| `DETAIL_LEVEL` | `medium`, `auto` | `overview`, `detailed` |
| `NUM_DRAFTS` | `2`, `3` | `4`, `5` |

## Source boundaries

Demo-source implements self-supervised MRI reconstruction with a flow-matching
prior and an unrolled solver. Its code supports the following figure types, even
where no dedicated example is present.

| Figure type | Source |
|---|---|
| `method-overview` | `train.py::train()` connects both stages and inference |
| `architecture` | `models/flow.py::FlowPrior.encode/velocity` defines conditioning |
| `training` | `train.py::training_step()` and its three losses |
| `inference` | `infer.py::reconstruct()` |
| `optimization` | `solver.py::solve()` alternates `dc_step` and `prior_step` |
| `domain_adaptation` | `train.py::source_pretrain()` and `target_adapt()` use different data access |

Ablation figures need actual variant configurations. Comparison figures need an
implemented baseline. Motivation figures need additional manuscript or user
material. Extend the source before adding examples that depend on missing code.
Do not invent components to fill the coverage matrix. See the
[evidence policy](../references/evidence-policy.md).

## Maintenance

After changing a rule, enum, output field or path, rerun strict validation and
update these matrices. Review the examples themselves for obsolete conventions,
rather than relying on a passing index or test alone.
