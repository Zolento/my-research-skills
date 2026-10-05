# 示例：证据不足时如何降级（`NUM_DRAFTS=2` + `MUST_NOT_INCLUDE`）

演示四件事：

1. `NUM_DRAFTS=2`（方法本来简单，不硬凑三个）；
2. 用户只是**提问 / 转述设计文档**，没有确认事实 ⇒ 相关内容按 **D 级**处理，
   **不画进任何 draft**，只进 `Uncertainties`；
3. 真需要提示"可能有但未定"的地方，只用 `[? label]` **占位标记**，且必须同时出现在
   `Uncertainties`；
4. 图里**只画代码真的有的**关系（例如 φ 确实进入 solver，就必须画；不能因为"不确定"就省掉）。

---

## 调用

```
调用 academic-figure-draft-architect
sources:      examples/demo-source/          # self-supervised MRI recon + flow prior + unrolled solver
FIGURE_TYPE:  method-overview
DETAIL_LEVEL: medium
NUM_DRAFTS:   2
FOCUS:        突出 target adaptation 只更新少量参数、flow prior 全程冻结
MUST_INCLUDE: [Flow Prior, Unrolled Solver, Solver Params φ]
MUST_NOT_INCLUDE: [Cross Attention, Alignment Module, Contrastive Loss]
KNOWN_FACTS:  []                              # ← 关键：用户没有确认任何东西
```

**用户补充原话（未确认，不是 `KNOWN_FACTS`）：**

> "设计文档里提到 target adaptation 会加一个 cross-domain alignment loss，代码可能还没实现；
> 另外 config 里那个 `prior_inner_steps` 到底有没有用，我也记不清了。"

**处理：**

- alignment loss 系列 ⇒ 命中 `MUST_NOT_INCLUDE` 且代码无实现 ⇒ **不画**（U2）；
- `prior_inner_steps` ⇒ 只在 config 里出现、代码无人读取 ⇒ 材料无法确认意图 ⇒
  D 级 ⇒ 图内只留 `[? inner_prior_sampler]` 占位，正文进 `Uncertainties`（U1）。

---

## 1. Figure Understanding

方法在**无源数据（source-free）**设定下，把预训练好的条件 flow-matching 先验迁移到目标域做加速 MRI 重建。

- **输入：** 训练期是欠采样 k-space（源域 `y_s`、目标域 `y_t`）；推理期只有 `(y, mask)`；
- **核心计算路径：** Stage 1 用 SSDU split-mask 自监督同时学 flow prior θ 与 solver 步长参数 φ；
  Stage 2 冻结 θ、只更新 φ；推理期把冻结的 θ 与 φ 一起放进 unrolled solver，交替做
  data-consistency 步与 prior 步，重复 K 次；
- **训练关系：** 两个 loss（DC + hold-out）都只在训练期存在；**源域与目标域都没有
  fully-sampled 参考**——flow-matching 项只在源域阶段用 fully-sampled 源图像定义；
- **inference 关系：** 部署期可得信息只有 `(y, mask)` 与两个冻结 checkpoint（θ、φ），
  **没有任何 target / GT**；
- **核心贡献：** 冻结先验下、只调 ~2K+1 个步长参数的目标域后训练。

---

## 2. Evidence Summary

| Figure element | Evidence | Confidence |
|---|---|---|
| Flow prior | `models/flow.py::FlowPrior` | High |
| Velocity field v_θ | `models/flow.py::FlowPrior.velocity()` | High |
| SSDU split mask (M_tr / M_ho) | `train.py::split_mask()` | High |
| Flow-matching loss（仅源域） | `train.py::flow_matching_loss()` | High |
| DC + hold-out loss | `train.py::data_consistency_loss()` / `train.py::holdout_loss()` | High |
| Source pre-training stage（θ 与 φ 都可训练） | `train.py::source_pretrain()` | High |
| Target adaptation stage（只更新 φ） | `train.py::target_adapt()` | High |
| Prior 冻结 | `train.py::target_adapt()` 的 `p.requires_grad_(False)` | High |
| Solver 步长参数 φ（log_alpha / log_beta / prior_scale） | `solver.py::SolverParams` | High |
| Data consistency step | `solver.py::dc_step()` | High |
| Prior step（Euler，单步） | `solver.py::prior_step()` | High |
| 交替迭代 K 次 + zero-filled 初值 | `solver.py::solve()` / `solver.py::zero_filled_init()` | High |
| 推理入口，不加载任何参考数据 | `infer.py::reconstruct()` / `infer.py::load_checkpoint()` | High |
| 多步 inner prior sampler | `configs/base.yaml::solver.prior_inner_steps`（**代码未引用**） | Low |

---

### 2.1 多样性矩阵（自检用，非契约段）

| 维度 | Draft A | Draft B |
|---|---|---|
| 主阅读方向 | 上→下（阶段堆叠） | 左→右 + 双列对照 |
| 信息分组 | 按**训练阶段**分组 | 按 **training / inference** 分组 |
| 视觉中心 | Stage 2（核心贡献） | 中部的 `══` 分隔带与两列差异 |
| 抽象层级 | medium（solver 内部展开） | medium（solver 收成一个块） |
| train/inference 表达 | stage 容器 + 标题 | 左右两栏 + 分隔带 |
| 循环表达 | 显式回流（`x_k ⇄ x_{k+1}`） | `repeat K` 注释 + inset 建议 |

---

## 3. Draft A — Hierarchical System

> 设计意图：按**阶段层级**自上而下铺开，把 Stage 2 的"冻结 θ、只训 φ"放在视觉中心，
> 并在 Stage 3 内部展开 unrolled solver 的交替结构。

```text
STAGE 1 - SOURCE PRETRAINING   (train only; source has fully-sampled k-space)
--------------------------------------------------------------------------
  [N1 y_s] ──▶ [N2 Split Mask] ──▶ [N3 Flow Prior θ]
                                            │
                                            ▼
                                   [N4 Flow-matching Loss]
                                            │
                                            ▼
                                   [N5 Prior weights θ]
                                            │
                                        update θ

STAGE 2 - TARGET ADAPTATION  [CORE CONTRIBUTION]   (train only; no GT)
--------------------------------------------------------------------------
  [N3 Flow Prior θ] [FROZEN] ──▶ velocity field (no gradient)
                                                    │
                                                    ▼
  [N6 y_t] ──▶ [N2 Split Mask] ──▶ [N7 SSDU Hold-out Loss] ──▶ [N8 Solver params φ]
                                                                   [TRAINABLE]
                                                                        │
                                                                  update φ only

STAGE 3 - INFERENCE   (no target, no fully-sampled reference)
--------------------------------------------------------------------------
  [N9 k-space (y, mask)]
             │
             ▼
  ┌─────────────────────────────────────────────────────────────┐
  │  N10 UNROLLED SOLVER            repeat K (K = 8)            │
  │                                                             │
  │  [N13 x_k] ─▶ [N11 DC Step] ─▶ [N12 Prior Step] ─▶ x_{k+1}  │
  │                   ▲                    ▲                    │
  │              [N9 y, mask]       [N3 Flow Prior θ][FROZEN]   │
  └─────────────────────────────────────────────────────────────┘
             │
             ▼
  [N14 Reconstructed image x*]

  α_k, β_k  ◀──  [N8 Solver params φ]  [FROZEN after adaptation]
  [? inner_prior_sampler]                                  (见 U1)
```

**Best for:**
- 单栏论文的 method overview（阶段叙事最清楚）
- 附录里需要同时讲清"两阶段训练 + 推理 solver"的补充图

**Strength:** 阶段边界与冻结关系一眼可辨；solver 的 recurrence 在 Stage 3 内部展开，
不会被误读成 `measurement → network → image`；φ 进 solver 的关系也画出来了。

**Weakness:** 图偏高，双栏里会缩得偏小；训练/推理的**可得信息差异**要靠标题文字读出来。

---

## 4. Draft B — Train vs Inference

> 设计意图：把 **training** 与 **inference** 做成左右对照，用 `══` 分隔带显式表达
> "推理期没有 target、没有 fully-sampled 参考"；solver 收成一个块，只保留 `repeat K`。

```text
┌───────────────────────────────────────┐   ┌─────────────────────────────────────┐
│  TRAINING                             │   │  INFERENCE                          │
│                                       │   │                                     │
│  Stage 1  SOURCE PRETRAINING          │   │  no target / no GT here             │
│  [N1 y_s] ─▶ [N2 Split Mask]          │   │                                     │
│        ─▶ [N3 Flow Prior θ]           │   │  [N9 k-space (y, mask)]             │
│                │                      │   │          │                          │
│                ▼                      │   │          ▼                          │
│    [N4 Flow-matching Loss]            │   │  [N10 Unrolled Solver]  repeat K    │
│                │                      │   │     ├ [N11 DC Step]   (α_k)         │
│                ▼                      │   │     ├ [N12 Prior Step] (β_k)        │
│    [N5 Prior weights θ]               │   │     │      [? inner_prior_sampler]  │
│                │  update θ            │   │     └ [N13 x_k]                     │
│                                       │   │          │                          │
│  Stage 2  TARGET ADAPTATION   [CORE]  │   │          ▼                          │
│  [N6 y_t] ─▶ [N2 Split Mask]          │   │  [N14 Reconstructed x*]             │
│        ─▶ [N7 SSDU Hold-out Loss]     │   │                                     │
│                │                      │   │  α_k, β_k ◀── [N8 φ] [FROZEN]       │
│                ▼                      │   └─────────────────────────────────────┘
│  [N8 Solver params φ][TRAINABLE]      │
│  [N3 Flow Prior θ][FROZEN]            │
└───────────────────────────────────────┘

  ══ θ crosses over as a FROZEN checkpoint;  φ crosses over frozen too ══
```

**Best for:**
- 主论文 Fig. 2（双栏，横版）
- source-free / 无 GT 约束需要视觉可见的场合

**Strength:** training / inference 的可得信息差异由版面结构直接表达，不靠读者推理；
`[FROZEN]`、`[TRAINABLE]`、`no target / no GT` 三处标记互相印证；箭头少、水平展开，
双栏缩放后仍可读。

**Weakness:** solver 内部只给 `repeat K`，看不到 `x_k → x_{k+1}` 的更新规则；
需要一句 caption 或放大 inset。

---

## 5. Recommended Draft

**Recommended: Draft B**

Why:
1. 方法的核心风险是"source-free / 无 GT"被误读，B 用版面结构把这件事变成**可见事实**；
2. training / inference 不易混淆——两栏物理分离，右栏内根本没有 reference data；
3. 横版双列与主论文 Fig. 2 的画幅一致，SVG 转换后天然形成两级视觉层级；
4. 箭头更少、无交叉，缩放友好；
5. 冻结 / 可训练标记集中在左栏底部，视觉权重与"核心贡献"匹配。

（Draft A 更适合作为**附录的求解过程图**：它把 `x_k → x_{k+1}` 的交替迭代画全了，
但作为总览图信息密度偏高。）

---

## 6. Alignment Notes

```text
N1  Source measurements y_s      ── train.py::source_pretrain() 的 loader（源域有 fully-sampled k-space）
N2  Split Mask (M_tr / M_ho)     ── train.py::split_mask()
N3  Flow Prior θ                 ── models/flow.py::FlowPrior
                                     · Stage 1: 可训练（在 source_pretrain 的 optimizer 参数组内）
                                     · Stage 2 / Inference: [FROZEN]（requires_grad_(False)）
N4  Flow-matching Loss           ── train.py::flow_matching_loss()（仅当传入 x_ref，即仅源域阶段）
N5  Prior weights θ              ── train.py::source_pretrain() 的 opt.step() 更新目标（语义聚合）
N6  Target k-space y_t           ── train.py::target_adapt() 的 loader（无 fully-sampled 参考）
N7  SSDU Hold-out Loss           ── train.py::holdout_loss() + train.py::data_consistency_loss()
N8  Solver params φ              ── solver.py::SolverParams（log_alpha / log_beta / prior_scale）
N9  k-space (y, mask)            ── infer.py::reconstruct() 的入参
N10 Unrolled Solver              ── solver.py::solve()（K = cfg["solver"]["num_steps"] = 8）
N11 Data Consistency Step        ── solver.py::dc_step()（步长 α_k 来自 N8）
N12 Prior Step                   ── solver.py::prior_step()（步长 β_k 来自 N8；单步 Euler）
N13 Current reconstruction x_k   ── solver.py::solve() 的循环变量
N14 Reconstructed image x*       ── solver.py::solve() 的返回值
```

**语义聚合声明：**

- `"Split Mask"（N2）` is a semantic abstraction of: `train.py::split_mask()` 对已采样相位编码行
  做 train / hold-out 二划分（`M_tr` 给 solver、`M_ho` 给 loss）。
- `"Prior weights θ"（N5）` is a semantic abstraction of: `source_pretrain()` 里
  `opt.step()` 对 `prior.parameters()` 的梯度更新（代码中没有名为 θ 的变量）。
- `"Unrolled Solver"（N10）` is a semantic abstraction of: `for k in range(K)` 内
  `dc_step()` 与 `prior_step()` 的交替调用（`solver.py::solve()`）。
  **聚合只用于 Draft B**；Draft A 已把它展开，两种画法信息等价。

**命名映射：**

```
Flow Prior θ         ↔ models/flow.py::FlowPrior
Solver params φ      ↔ solver.py::SolverParams  （= configs/base.yaml::adapt.trainable）
x_k                  ↔ solver.py::solve() 的局部变量
Data Consistency     ↔ solver.py::dc_step()
Prior Step           ↔ solver.py::prior_step()
```

**未画出的内容（明确声明）：**

- **cross-domain alignment loss / Alignment Module / Contrastive Loss / Cross Attention**：
  用户只是转述设计文档，代码中 `loss` / `criterion` 无对应实现，且命中 `MUST_NOT_INCLUDE`
  ⇒ **不画、不进元素表**（U2）。
- **多步 inner prior sampler**：config 声明 `prior_inner_steps: 4`，但
  `solver.py::prior_step()` 每个 k 只做一次 Euler 更新，`FlowPrior.sample()` 也未被调用
  ⇒ 无法确认这是"未启用的可选结构"还是"已废弃的配置" ⇒ **只留 `[?]` 占位**（U1）。

---

## 7. Uncertainties

```text
Uncertain:
- inner_prior_sampler：configs/base.yaml 声明 solver.prior_inner_steps: 4，但代码中
  没有任何地方读取它（prior_step 每步只做一次 Euler 更新，FlowPrior.sample() 也未被调用）。
  无法确认它是"未启用的可选结构"还是"废弃配置"，因此图内只用 [? inner_prior_sampler]
  占位，未画任何 inner loop（U1）。
- alignment_loss：设计文档提到的 cross-domain alignment loss 在 demo-source 中没有任何
  对应实现，且命中 MUST_NOT_INCLUDE，故不进入任何 draft（U2）。
- cond_at_inference：训练期 conditioning 用 M_tr 的零填充补全
  （train.py::training_step() 的 cond = zero_filled_init(y, m_tr)），推理期
  solver.solve() 在未传入 cond 时用完整 mask 的零填充补全。两者的差异是否为有意设计，
  材料无法判断；它影响性能解释，但不改变本图结构，故图中不做区分（U3）。
- K_vs_unroll：推理期 K 取 cfg["solver"]["num_steps"]（8），适配期取
  cfg["adapt"]["unroll"]；两个深度是否应当一致，代码没有约束，图中只写 repeat K（U4）。
```

---

## 8. SVG Handoff Notes

```text
Canvas:                  landscape (推荐 Draft B)；Draft A 用 portrait
Primary flow:            left → right (Draft B) / top → bottom (Draft A)
Suggested visual groups: TRAINING（含 Stage 1 / Stage 2 两个子带）
                         INFERENCE
                         Prior（跨栏复用的冻结模块）
Visual emphasis:         Draft B 中部的 ══ 分隔带与 "no target / no GT" 标注；
                         Stage 2 的 [CORE CONTRIBUTION]
Secondary elements:      N2 Split Mask、N9 k-space（弱化，用浅色）
Line semantics:          solid = inference/forward；dashed = training supervision；
                         dotted = checkpoint 传递（θ、φ → inference）
Styling hierarchy:       Level 1 = TRAINING / INFERENCE 容器；Level 2 = 阶段与模块；
                         Level 3 = loss / 算子
Color grouping:          N3 用同一颜色跨 Stage 1 → Stage 2 → Inference，
                         Stage 2/Inference 内加锁形标记表示冻结；
                         N8 用"可训练"强调色，推理期换成冻结样式
De-emphasize:            N2 Split Mask、N9、N13
Center node:             Draft B 的分隔带；Draft A 的 Stage 2
Curved arrows:           θ、φ 从 Stage 1/2 到 Inference 的 checkpoint 传递线
Inset candidates:        Draft B 的 N10 Unrolled Solver 可放 inset，展开
                         x_k → DC Step(α_k) → Prior Step(β_k) → x_{k+1}
```

---

## 9. Figure Element Inventory

| ID | Type | Label | Group | Inputs | Outputs | Status |
|---|---|---|---|---|---|---|
| N1 | data | Source measurements y_s | Training · Stage 1 | — | N2 | observed · train-only |
| N2 | operator | Split Mask (M_tr / M_ho) | Training | N1,N6 | N3,N7 | observed · train-only |
| N3 | model | Flow Prior θ | Prior | N2,N13 | N4,N12 | observed · trainable |
| N4 | objective | Flow-matching Loss | Training · Stage 1 | N3 | N5 | observed · train-only |
| N5 | parameter | Prior weights θ | Training · Stage 1 | N4 | N3 | abstraction · trainable |
| N6 | data | Target k-space y_t | Training · Stage 2 | — | N2 | observed · train-only |
| N7 | objective | SSDU Hold-out Loss | Training · Stage 2 | N2,N3 | N8 | observed · train-only |
| N8 | parameter | Solver params φ | Solver | N7 | N10,N11,N12 | observed · trainable |
| N9 | data | k-space (y, mask) | Inference | — | N10,N11 | observed · inference-only |
| N10 | operator | Unrolled Solver (repeat K) | Inference | N9,N3,N8 | N14 | observed · inference-only |
| N11 | operator | Data Consistency Step | Inference | N9,N13,N8 | N12 | observed · inference-only |
| N12 | operator | Prior Step | Inference | N3,N11,N8 | N13 | observed · inference-only |
| N13 | state | Current reconstruction x_k | Inference | N12 | N11 | observed · inference-only |
| N14 | output | Reconstructed image x* | Inference | N10 | — | observed · inference-only |

> **未登记的节点：** alignment module / cross attention / contrastive loss / multi-step
> inner sampler —— 前三者无依据（且命中 `MUST_NOT_INCLUDE`），第四者无法确认，
> 按 [evidence-policy §2 规则 2、4](../references/evidence-policy.md) 不画、不登记。

---

## 这个示例演示了什么

| 行为 | 体现位置 |
|---|---|
| 参数缺失 / 用户不确定**不阻塞**，但降级写清楚 | 开头「处理」段 + U1–U4 |
| D 级内容不进正式 draft | `alignment_loss`、`inner_prior_sampler` 只出现在 `Uncertainties` |
| 必须提示的未定项用 `[? label]` 占位 | 两条 draft 的 `[? inner_prior_sampler]` |
| `MUST_NOT_INCLUDE` 生效 | 三个禁止模块在 draft 与元素表中都缺席，且有显式声明 |
| 简单方法只出 2 个 draft | `NUM_DRAFTS=2` |
| 冻结 / 可训练 / train-only 视觉可见 | `[FROZEN]`、`[TRAINABLE]`、状态限定词、分隔带 |
| inference 区没有 GT | Draft A Stage 3 与 Draft B 右栏都只有 `(y, mask)` |
| **有据的关系不能省** | φ（N8）确实进入 solver，两条 draft 都画了它 |
| 聚合不掩盖结构 | Alignment Notes 的 semantic abstraction 声明 |
