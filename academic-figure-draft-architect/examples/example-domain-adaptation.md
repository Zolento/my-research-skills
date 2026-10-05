# 示例：`FIGURE_TYPE: domain_adaptation` + `SKETCH_STYLE: stage_panel`

演示新增的第 9 类 `FIGURE_TYPE`，以及 `stage_panel` 风格如何把
**source → target 的数据可用性差异**画成看得见的结构。

- `FIGURE_TYPE: domain_adaptation` —— 强调 source 阶段 → 迁移接口 → target 阶段，
  以及**每个阶段能看到什么数据**；
- `SKETCH_STYLE: stage_panel` —— 用大外框表达阶段边界；
- `SKETCH_VARIANTS: single` —— 每份 draft 一个字符图。

两个 draft 的 grammar 不同：Draft A 用 `Source / Target Domain`（域对照），
Draft B 用 `Temporal / Stage View`（阶段推进）。

---

## 调用

```
调用 academic-figure-draft-architect
sources:          examples/demo-source/
FIGURE_TYPE:      domain_adaptation
SKETCH_STYLE:     stage_panel
SKETCH_VARIANTS:  single
DETAIL_LEVEL:     medium
NUM_DRAFTS:       2
FOCUS:            讲清 target 阶段没有任何 fully-sampled 数据、且先验 θ 被冻结
MUST_INCLUDE:     [source pretraining, target adaptation, frozen flow prior, NO SOURCE DATA]
MUST_NOT_INCLUDE: [fully-sampled target data, Cross Attention, Alignment Module]
KNOWN_FACTS:      [flow prior 在 target 阶段冻结]
```

---

## 1. Figure Understanding

方法分两个训练阶段，**两个阶段的数据可用性不同**，这是本图要讲的核心。

- **输入：** Stage 1 是源域 fully-sampled k-space `y_s` 加其参考图像 `x_ref`；
  Stage 2 只有目标域欠采样 k-space `y_t`；推理期只有 `(y, M)`；
- **核心计算路径：** Stage 1 用 SSDU 自监督同时训练 flow prior θ 与 solver 参数 φ；
  Stage 2 冻结 θ，只更新 φ（约 `2K+1` 个标量）；推理期把两者放进 unrolled solver；
- **训练关系：** flow-matching 项需要 `x_ref`，**只在 Stage 1 存在**；
  Stage 2 与推理期都没有 fully-sampled 目标数据；
- **inference 关系：** 部署期只有 `(y, M)` 与两个冻结 checkpoint；
- **核心贡献：** 在**无源数据（source-free）**约束下，只调步长参数完成目标域适配。

---

## 2. Evidence Summary

| Figure element | Evidence | Confidence |
|---|---|---|
| Source pre-training stage | `train.py::source_pretrain()` | High |
| Target adaptation stage | `train.py::target_adapt()` | High |
| Flow prior θ 在 Stage 2 冻结 | `train.py::target_adapt()` 的 `p.requires_grad_(False)` | High |
| 只更新 φ | `train.py::target_adapt()` 的 `trainable` 参数组；`configs/base.yaml::adapt.trainable` | High |
| 源域有 fully-sampled k-space | `configs/base.yaml::data.dataset`（`fastMRI_knee_source`）+ `train.py` 的 `x_ref` 入参 | High |
| 目标域只有欠采样 k-space | `configs/base.yaml::data.target_dataset`；`train.py::target_adapt()` 的 loader 只产出 `(y, mask)` | High |
| Flow-matching loss 仅 Stage 1 | `train.py::training_step()` 的 `x_ref is not None` 分支 | High |
| SSDU split-mask（两阶段共用） | `train.py::split_mask()` | High |
| 推理只吃 `(y, M)` | `infer.py::reconstruct()` | High |
| 两阶段用不同优化器与 lr | `configs/base.yaml::source.lr` / `adapt.lr` | High |
| 多步 inner prior sampler | `configs/base.yaml::solver.prior_inner_steps`（**代码未引用**） | Low |

---

### 2.1 多样性矩阵（自检用，非契约段）

| 维度 | Draft A | Draft B |
|---|---|---|
| 主阅读方向 | 上→下（两个域带 + 分隔带） | 左→右（时间轴三阶段） |
| 信息分组 | 按 **domain**（source / target） | 按 **stage**（A / B / C） |
| 视觉中心 | `NO SOURCE DATA` 分隔带 | Stage B 的 `[FROZEN]` 与可训练 φ |
| 抽象层级 | medium | medium |
| train/inference 表达 | 显式的可用性对照行 | 阶段列内的可训练 / 冻结标记 |
| 循环表达 | 未出现 | 未出现 |

---

## 3. Draft A — Source / Target Domain

> 设计意图：把源域与目标域做成上下两条**数据可用性带**，中间用 `══` 分隔带
> 明确"过了这条线就没有源数据"，并把冻结的 θ 放在目标带里。

```text
┌─ SOURCE DOMAIN  (fully-sampled k-space available) ─────┐
│                                                        │
│   y_s   ──▶ [ Split Mask ] ──▶ [ DC + Hold-out ]       │
│   x_ref ──▶ [ Flow-Match ]                             │
│                                                        │
│   both losses update θ and φ together                  │
│   (one optimizer over prior.parameters() +             │
│    params.parameters();  θ, φ [TRAINABLE])             │
│                                                        │
└───────────────────────────┬────────────────────────────┘
                            ▼
                   ┌─────────────────┐
                   │ Checkpoint θ_0  │
                   │ φ_0             │
                   └────────┬────────┘
                            │
════════════════════════════┼════════════════════════════
            NO SOURCE DATA AVAILABLE
════════════════════════════┼════════════════════════════
                            ▼
┌─ TARGET DOMAIN  (undersampled k-space only) ──────────┐
│                                                        │
│   y_t ──▶ [ Split Mask ] ──▶ [ DC + Hold-out ] ──▶ φ   │
│                                               [TRAINABLE]
│                                                        │
│   θ_0 [FROZEN] ── no gradient path ──▶ ✗               │
└────────────────────────────────────────────────────────┘
```

**Best for:**
- source-free / 域适配方法的主图
- 需要让审稿人一眼看到"目标阶段没有 fully-sampled 数据"的场合

**Strength:** 数据可用性差异由**版面结构**表达，不靠 caption；`[FROZEN]` / `[TRAINABLE]`
与分隔带三处互相印证；no-gradient 路径显式画成断开的 `✗`，不会被误读成可训练。

**Weakness:** 纵向偏长；target 带里的 `φ [TRAINABLE]` 与 source 带里的同名项容易看串，
需要 caption 区分"Stage 1 的 φ 与 Stage 2 的 φ 是同一组参数的不同状态"。

---

## 4. Draft B — Temporal / Stage View

> 设计意图：按时间轴横排三个阶段，让"可用数据在 Stage A 之后就消失"变成列与列之间的
> 差异，而不是靠文字说明。

```text
    Stage A                Stage B                Stage C
    source pretrain        target adapt           inference
    ─────────────          ────────────           ─────────
    y_s , x_ref            y_t only               y , M
    θ  [TRAINABLE]         θ  [FROZEN]            θ  [FROZEN]
    φ  [TRAINABLE]         φ  [TRAINABLE]         φ  [FROZEN]
         │                      │                      │
         ▼                      ▼                      ▼
    ┌─────────┐            ┌─────────┐            ┌─────────┐
    │ θ, φ    │───────────▶│ φ*      │───────────▶│ x_hat   │
    └─────────┘            └─────────┘            └─────────┘

    ════════════ NO SOURCE DATA beyond Stage A ════════════
```

**Best for:**
- 多阶段训练的方法总览
- 需要同时交代"每阶段训什么、用什么数据"的补充图

**Strength:** 三列对齐后，读者扫一眼 `x_ref` 只出现在 Stage A，就能理解 source-free；
每列底部的模型块给出阶段产物的传递关系；横向布局对双栏友好。

**Weakness:** `[FROZEN]` / `[TRAINABLE]` 数量较多，视觉上会与模型块抢注意力；
`x_ref` 的"仅 Stage A 可用"仍需要 caption 点一句。

---

## 5. Recommended Draft

**Recommended: Draft A**

Why:
1. `domain_adaptation` 的第一重点是**数据可用性差异**，A 用分隔带把它做成结构性事实；
2. 只有 A 显式画出"θ 的梯度路径断开"，这正是防复现审查会看的地方；
3. 域带的结构与 `Source / Target Domain` grammar 的阅读方向一致，不需要额外解释；
4. B 的三列标记密度偏高，缩到双栏后 `[FROZEN]` / `[TRAINABLE]` 会变小字；
5. A 的两个域带天然对应论文里的 "Stage 1 / Stage 2" 小节划分，便于读者对照正文。

（Draft B 更适合放在附录，作为"每阶段输入输出"的速查图。）

---

## 6. Alignment Notes

```text
N1  y_s (source k-space)     ── train.py::source_pretrain() 的 loader 产出（源域有 fully-sampled k-space）
N2  x_ref (source image)     ── train.py::training_step() 的 x_ref 入参；仅 Stage 1 传入
N3  Split Mask (M_tr / M_ho) ── train.py::split_mask()
N4  DC + Hold-out            ── train.py::data_consistency_loss() + train.py::holdout_loss()
N5  Flow-Match               ── train.py::flow_matching_loss()
N6  Flow prior θ             ── models/flow.py::FlowPrior（Stage 2 起 [FROZEN]）
N7  Solver params φ          ── solver.py::SolverParams（两阶段都可训练，推理期冻结）
N8  Checkpoint θ_0 / φ_0     ── train.py::train() 的 torch.save({"flow":…, "solver_params":…})
N9  y_t (target k-space)     ── train.py::target_adapt() 的 loader 产出（无 fully-sampled 参考）
N10 Unrolled Solver          ── solver.py::solve()（Stage 2 用 cfg["adapt"]["unroll"] = 8）
N11 Reconstructed image x*   ── solver.py::solve() 的返回值 / infer.py::reconstruct() 的输出
```

**语义聚合声明：**

- `"DC + Hold-out"（N4）` is a semantic abstraction of: `training_step()` 中
  `weights["dc"] * data_consistency_loss(...) + weights["holdout"] * holdout_loss(...)` 两项。
- `"Checkpoint θ_0 / φ_0"（N8）` is a semantic abstraction of: `train()` 里
  `torch.save({"flow": prior.state_dict(), "solver_params": params.state_dict()})` 的产物。

**命名映射：**

```
Flow prior θ      ↔ models/flow.py::FlowPrior
Solver params φ   ↔ solver.py::SolverParams
Source stage      ↔ train.py::source_pretrain()
Target stage      ↔ train.py::target_adapt()
```

**未画出的内容（明确声明）：**

- **fully-sampled target data**：命中 `MUST_NOT_INCLUDE`，且 `target_adapt()` 的 loader
  只产出 `(y, mask)` ⇒ 不画、不进元素表。
- **multi-step inner prior sampler**：config 声明 `prior_inner_steps: 4` 但代码无人读取
  ⇒ 不画（U1）。

---

## 7. Uncertainties

```text
Uncertain:
- inner_prior_sampler：configs/base.yaml 的 solver.prior_inner_steps: 4 在代码中
  无读取点（solver.py::prior_step 每步只做一次 Euler 更新）。不画、不登记（U1）。
- k_vs_unroll：Stage 2 用 cfg["adapt"]["unroll"] = 8 作为展开深度，而推理期用
  cfg["solver"]["num_steps"] = 8。两者当前数值相同，但代码没有约束它们必须一致；
  图中只写 Unrolled Solver，不标具体深度（U2）。
- out_key：train.py::train() 用 cfg.get("out", "checkpoint.pt") 取保存路径，而
  configs/base.yaml 里没有 out 键。是否应显式声明保存路径，材料无法判断；
  不影响本图结构（U3）。
```

---

## 8. SVG Handoff Notes

```text
Canvas:                  portrait (Draft A) / landscape (Draft B)
Primary flow:            top → bottom (A) / left → right (B)
Suggested visual groups: Draft A: SOURCE DOMAIN / TARGET DOMAIN / 跨域 checkpoint
                         Draft B: Stage A / Stage B / Stage C
Visual emphasis:         Draft A 的 NO SOURCE DATA 分隔带；Stage B 的 [FROZEN] 与可训练 φ
Secondary elements:      Split Mask、DC + Hold-out（弱化，浅色）
Line semantics:          solid = 前向计算；dashed = 训练监督；dotted = checkpoint 传递；
                         ✗ 断线 = 不存在的梯度路径
Styling hierarchy:       Level 1 = 域带 / 阶段容器；Level 2 = 模型块；
                         Level 3 = loss 与算子
Color grouping:          θ 跨阶段同色，Stage 2 起加冻结样式；φ 用"可训练"强调色
De-emphasize:            Split Mask、DC + Hold-out
Center node:             Draft A 的分隔带；Draft B 的 Stage B
Curved arrows:           θ_0 从 Stage A 到 Stage B 的 checkpoint 传递线
Inset candidates:        Draft B 的 Unrolled Solver 可展开为 inset
Sketch primitives:       stage panel x4（SOURCE DOMAIN / TARGET DOMAIN / Stage A-B-C 带）；
                         本图不用双线框——stage 容器与阶段产物都不是 model 形状
```

---

## 9. Figure Element Inventory

| ID | Type | Label | Group | Inputs | Outputs | Status |
|---|---|---|---|---|---|---|
| N1 | data | y_s (source k-space) | Source Domain | — | N3 | observed · train-only |
| N2 | data | x_ref (source image) | Source Domain | — | N5 | observed · train-only |
| N3 | operator | Split Mask (M_tr / M_ho) | Source Domain | N1,N9 | N4,N5 | observed · train-only |
| N4 | objective | DC + Hold-out | Source Domain | N3 | N7 | observed · train-only |
| N5 | objective | Flow-Match | Source Domain | N2,N3 | N6 | observed · train-only |
| N6 | model | Flow prior θ | Prior | N5 | N8,N10 | observed · trainable |
| N7 | parameter | Solver params φ | Solver | N4 | N8,N10 | observed · trainable |
| N8 | state | Checkpoint θ_0 / φ_0 | Adaptation | N6,N7 | N10 | abstraction |
| N9 | data | y_t (target k-space) | Target Domain | — | N3 | observed · train-only |
| N10 | operator | Unrolled Solver | Target Domain | N6,N7,N8,N9 | N11 | observed |
| N11 | output | Reconstructed image x* | Inference | N10 | — | observed · inference-only |

> **形状说明：** Stage 容器（SOURCE DOMAIN / TARGET DOMAIN / 三阶段带）**不是节点**，
> 不进本表；`θ` 与 `φ` 的阶段状态差异由 `Status` 限定词与图内 `[FROZEN]` / `[TRAINABLE]`
> 共同表达。

---

## 这个示例演示了什么

| 行为 | 体现位置 |
|---|---|
| 新增 `FIGURE_TYPE: domain_adaptation` | 全篇围绕 source → target 的数据可用性 |
| `SKETCH_STYLE: stage_panel` | 域带与阶段带用大外框，`══` 表达边界 |
| 冻结 / 可训练视觉可见 | `[FROZEN]` / `[TRAINABLE]` + 断开的梯度路径 `✗` |
| source-free 约束可见 | `NO SOURCE DATA` 分隔带 + `x_ref` 只出现在 Source Domain |
| 阶段容器不进元素表 | 表内 11 行全是真实节点，无一为容器 |
| 未确认内容不画 | `prior_inner_steps`、`out` 键只进 `Uncertainties` |
