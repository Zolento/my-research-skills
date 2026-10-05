# 示例索引与覆盖矩阵

> ⚠️ **本文件不是 draft。** 校验示例时请用 `examples/example-*.md`，
> **不要**用 `examples/*.md`——那会把本文件也当 draft，报出一串"缺段"错误。

本目录的示例是**照抄对象**——它们示范的写法会被直接复制。所以哪条规则有示例、
哪条没有，必须是**可查的**，不能靠记忆（这正是 `SKILL.md` §8 A3 记录的漂移来源）。

## 1. 示例清单

| 文件 | 演示什么 | 有据来源 |
|---|---|---|
| [example-code-grounded.md](example-code-grounded.md) | 从一个小型真实源码库产出 3 个结构不同的 draft 的完整流程 | `demo-source/` |
| [example-uncertainty.md](example-uncertainty.md) | 证据不足时如何降级到 `Uncertainties`、`MUST_NOT_INCLUDE` 如何生效、`[? label]` 占位 | `demo-source/` |
| [example-sketch-legend.md](example-sketch-legend.md) | **形状编码语义图例**（`╔═╗` / `[ IFFT ]` / tensor 堆叠 / `[slice]` / `╭─╮`）+ `SKETCH_VARIANTS: both` 双画法对照 | `demo-source/` |
| [example-domain-adaptation.md](example-domain-adaptation.md) | 新增的 `FIGURE_TYPE: domain_adaptation` + `SKETCH_STYLE: stage_panel`；source-free 分隔带与冻结/可训练 | `demo-source/` |
| [example-auto-inference.md](example-auto-inference.md) | `FIGURE_TYPE: auto` / `SKETCH_STYLE: auto` 的推断声明，以及"**何时才该问**、问什么" | `demo-source/` |

## 2. 怎么校验

**所有示例都必须通过 `--strict`**（`SKILL.md` §8「机器校验」）：

```bash
cd academic-figure-draft-architect
for f in examples/example-*.md; do
  python3 scripts/check_draft.py --strict "$f" || exit 1
done
# 预期：每个文件都是 0 error(s), 0 warning(s)，退出码 0
```

## 3. 覆盖矩阵：`FIGURE_TYPE`

| `FIGURE_TYPE` | 覆盖示例 |
|---|---|
| `method-overview` | example-code-grounded、example-uncertainty |
| `architecture` | example-sketch-legend |
| `training` | ❌ **未覆盖** |
| `inference` | ❌ **未覆盖** |
| `optimization` | ⚠️ 仅间接（example-auto-inference 在推断声明里推断为它，未显式声明） |
| `domain_adaptation` | example-domain-adaptation |
| `motivation` | ❌ **未覆盖**（需要论文文本，`demo-source/` 不提供） |
| `comparison` | ❌ **未覆盖**（`demo-source/` 无基线实现） |
| `ablation` | ❌ **未覆盖**（`demo-source/` 无变体配置） |

## 4. 覆盖矩阵：visual grammar（A–H）

| grammar | 覆盖示例 |
|---|---|
| A `Linear Pipeline` | example-sketch-legend、example-auto-inference |
| B `Dual / Multi Branch` | ❌ **未覆盖** |
| C `Hierarchical System` | example-uncertainty |
| D `Iterative Loop` | example-code-grounded、example-auto-inference |
| E `Train vs Inference` | example-code-grounded、example-uncertainty |
| F `Data / Model / Objective` | example-sketch-legend |
| G `Source / Target Domain` | example-code-grounded、example-domain-adaptation |
| H `Temporal / Stage View` | example-domain-adaptation |

## 5. 覆盖矩阵：参数取值

| 参数 | 已覆盖 | 未覆盖 |
|---|---|---|
| `SKETCH_STYLE` | `auto`、`enhanced`、`stage_panel` | `block_architecture`、`loop_centric`；`clean` 仅在 example-auto-inference 的**推断声明**里出现，无显式声明示例 |
| `SKETCH_VARIANTS` | `single`、`both` | — |
| `DETAIL_LEVEL` | `medium`、`auto` | `overview`、`detailed` |
| `NUM_DRAFTS` | `2`、`3` | `4`、`5` |

## 6. 未覆盖清单（显式，供维护用）

以下格子**没有示例**。这不代表规则不存在，只代表**没有被示范过**；
新增示例时请同步更新本表，否则下一个人还得重新数一遍。

```text
grammar        B Dual / Multi Branch
FIGURE_TYPE    training / inference / optimization（仅间接）/ motivation / comparison / ablation
SKETCH_STYLE   block_architecture / loop_centric（clean 仅间接）
DETAIL_LEVEL   overview / detailed
NUM_DRAFTS     4 / 5
```

## 7. `demo-source/` 的能力边界

`demo-source/` 是**自监督 MRI 重建 + flow-matching 先验 + unrolled solver** 的最小真实代码，
它是所有示例的证据来源。它能支撑与**不能**支撑的 `FIGURE_TYPE`：

| 可支撑 | 依据 |
|---|---|
| `method-overview` | `train.py::train()` 串起两阶段 + 推理 |
| `architecture` | `models/flow.py::FlowPrior.encode/velocity` 的条件结构 |
| `training` | `train.py::training_step()` 与三个 loss |
| `inference` | `infer.py::reconstruct()` |
| `optimization` | `solver.py::solve()` 的 `dc_step` / `prior_step` 交替 |
| `domain_adaptation` | `train.py::source_pretrain()` / `target_adapt()` 的不同数据可见性 |

| 不可支撑 | 原因 |
|---|---|
| `ablation` | 没有任何变体配置（`configs/base.yaml` 只有一份 base） |
| `comparison` | 没有基线实现 |
| `motivation` | 没有论文正文，失败机制只能来自用户口述 |

**要给 `ablation` / `comparison` 补有据的示例，必须先扩 `demo-source/`**
（加一组消融配置 / 一个基线实现）。不扩就只能写"示意"，
而示意违反 [evidence-policy.md](../references/evidence-policy.md) 的 A/B/C/D 纪律。

## 8. 维护提示

改了任何**规则 / 枚举 / 列名 / 计数 / 路径**后：

1. 跑 §2 的校验命令，确认 5 份示例仍然 `--strict` 通过；
2. 检查本文件 §3–§5 的矩阵是否还准确（尤其是新增 `FIGURE_TYPE` / grammar 时）；
3. 特别检查**示例是否还在示范旧写法**——这是 §8 A3 点名的历史坑。
