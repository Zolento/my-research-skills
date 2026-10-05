# 示例：`FIGURE_TYPE: auto` / `SKETCH_STYLE: auto` 与"何时才该问"

演示 `SKILL.md` §1.1：**类别与风格默认自己推断，不主动询问**；
只有在**两个叙事重点都合理、且会实质改变图在讲什么**时才问。

本示例故意选在一个**该问**的位置，展示问法应该是"叙事重点"而不是"画风"。

---

## 调用

```
调用 academic-figure-draft-architect
sources:          examples/demo-source/
FIGURE_TYPE:      auto          # ← 未给出
SKETCH_STYLE:     auto          # ← 未给出
SKETCH_VARIANTS:  single
DETAIL_LEVEL:     auto
NUM_DRAFTS:       2
FOCUS:            未给出
```

---

## 推断结果与声明

**输出开头必须给出的那一行：**

> `FIGURE_TYPE` 未给出，按材料推断为 `optimization`；
> `SKETCH_STYLE` 未给出，按材料推断为 `clean`；
> `DETAIL_LEVEL` 未给出，按材料推断为 `medium`。

**推断依据：**

1. 代码的核心是 `solver.py::solve()` 里 `for k in range(K)` 的交替迭代 —— 驱动结构是**循环**；
2. 方法贡献是"把生成式先验放进每一步"，属于**更新规则**层面的贡献；
3. 材料里没有消融配置，也没有基线实现 ⇒ 不是 `ablation` / `comparison`；
4. 用户没有强调训练编排 ⇒ 不是 `training`；但 `train.py` 的两阶段仍需在附录出现。

---

## 为什么这里要问，以及怎么问

这是**该问**的情形：同一个方法有两个都合理的叙事重点，且选择会改变图的中心。

**应该这么问（问叙事重点）：**

> 这张图有两个合理重点：
> A. 强调完整重建流程 `(y, M) → x_0 → solver → x̂`，把 solver 收成一个块；
> B. 强调 solver 内部 `DC ↔ Prior` 的迭代机制与步长参数 φ 的作用。
> 若无偏好，我默认选 A，并把 B 作为局部 inset 草图。

**不应该这么问（问画风）：**

> ❌ "你想要立体块还是平面框？" —— 由 `SKETCH_STYLE` 决定，agent 自己选；
> ❌ "这算什么 figure type？" —— 那正是本 skill 该判断的事。

**本例设定：** 用户回答"两个都画出来给我看"。于是产出下面两个 draft ——
它们的 grammar 必须不同（`Linear Pipeline` vs `Iterative Loop`）。

---

## 1. Figure Understanding

自监督加速 MRI 重建：把条件 flow-matching 先验放进一个展开的交替求解器里，
每一步先做 data-consistency 更新，再沿先验的 velocity field 走一个 Euler 步。

- **输入：** 欠采样 k-space `y` 与采样掩码 `M`；
- **核心计算路径：** 零填充伴随 `x_0 = Aᴴ M y` → `K = 8` 次 `dc_step` 与 `prior_step` 交替 → `x̂`；
- **训练关系：** 两阶段训练（源域预训练 + 目标域适配），flow-matching 项只在源域存在；
- **inference 关系：** 部署期只有 `(y, M)` 与冻结的 θ、φ；
- **核心贡献：** 冻结的先验 + 只调约 `2K+1` 个步长参数 φ。

---

## 2. Evidence Summary

| Figure element | Evidence | Confidence |
|---|---|---|
| Zero-filled 伴随 x_0 | `solver.py::zero_filled_init()` | High |
| Data-consistency 步 | `solver.py::dc_step()` | High |
| Prior 步（单步 Euler） | `solver.py::prior_step()` | High |
| 交替迭代 K 次 | `solver.py::solve()`；K = `configs/base.yaml::solver.num_steps` = 8 | High |
| 步长参数 φ 提供 α_k / β_k | `solver.py::SolverParams.alpha()` / `.beta()` | High |
| Flow prior θ（推理期冻结） | `models/flow.py::FlowPrior`；`train.py::target_adapt()` 冻结 | High |
| 推理入口 | `infer.py::reconstruct()` | High |
| 多步 inner prior sampler | `configs/base.yaml::solver.prior_inner_steps`（**代码未引用**） | Low |

---

### 2.1 多样性矩阵（自检用，非契约段）

| 维度 | Draft A | Draft B |
|---|---|---|
| 主阅读方向 | 左→右（单程） | 环形 |
| 信息分组 | 按 **pipeline 阶段** | 按 **循环体内部** |
| 视觉中心 | solver 块 | `DC ↔ Prior` 的交替 |
| 抽象层级 | overview（solver 收成一个块） | medium（展开循环体） |
| train/inference 表达 | 行内 `[FROZEN]` | 行内 `[FROZEN]` + φ 输入标注 |
| 循环表达 | `repeat K` 注释 | 显式回流线 |

---

## 3. Draft A — Linear Pipeline

> 设计意图：把重建流程收成单程，solver 作为一个块，让"输入到输出"一眼可读。
> 对应上面问题里的叙事 A。

```text
(y, M) ──▶ [ IFFT ] ──▶ x_0 ──▶ ┌──────────────────┐
                                │ Unrolled Solver  │──▶ x_hat
                                │  repeat K = 8    │
                                └─────────┬────────┘
                                          ▲
                     α_k, β_k  ◀── [ φ ]  │  [FROZEN after adapt]
```

**Best for:**
- 主论文 Fig. 2 的 method overview
- 读者只需要知道"输入是什么、经过什么、输出是什么"

**Strength:** 一屏读完；`repeat K = 8` 说明了它不是一个前向网络；
φ 与 θ 的冻结状态有标注。

**Weakness:** 看不到 `x_k → x_{k+1}` 的更新规则，审稿人可能仍把它误读成单次前向；
需要 caption 或 inset 补充。

---

## 4. Draft B — Iterative Loop

> 设计意图：把循环体展开，让 `DC ↔ Prior` 的交替与 φ 的作用成为视觉中心。
> 对应上面问题里的叙事 B。

```text
                α_k                        β_k
                 │                          │
                 ▼                          ▼
x_k ──▶ [ DC Step ] ──▶ x'_k ──▶ [ Prior Step ] ──▶ x_{k+1}
 ▲                                                      │
 └──────────────── repeat K = 8 ────────────────────────┘

inputs:      (y, M) ──▶ [ DC Step ]        x_0 = Aᴴ M y
             θ [FROZEN] ──▶ [ Prior Step ] v_θ(x, t=1, cond)
```

**Best for:**
- 附录的求解过程图
- 需要说明"贡献在更新规则层"而不是"换了个网络"的场合

**Strength:** recurrence 闭合，`x_k → x_{k+1}` 的更新规则完全展开；
α_k / β_k 来自 φ 这件事画在循环体上方，参数与算子的关系明确；θ 的冻结状态可见。

**Weakness:** 横向偏长；`cond` 的来源只用一行标注，没有画进主循环。

---

## 5. Recommended Draft

**Recommended: Draft A**

Why:
1. 用户没有指定叙事重点时，默认选"完整流程"（§1.1 的默认行为），改图成本最低；
2. 作为主图，A 的 5–15 秒可读性更好，审稿人不需要先理解循环；
3. B 的信息密度更适合附录，把它作为 A 的 inset 候选最省版面；
4. 两个 draft 的 grammar 不同，满足了多样性要求，但**推荐仍按结构而非复杂度**给。

（B 在附录里能补上 A 缺的迭代细节，两者不冲突。）

---

## 6. Alignment Notes

```text
N1  (y, M)                   ── infer.py::reconstruct() 的入参
N2  IFFT [IFFT]              ── solver.py::ifft2()（被 solver.py::zero_filled_init() 调用）
N3  x_0                      ── solver.py::zero_filled_init()
N4  Unrolled Solver          ── solver.py::solve()（K = cfg["solver"]["num_steps"] = 8）
N5  Data Consistency Step    ── solver.py::dc_step()
N6  Prior Step               ── solver.py::prior_step()
N7  Solver params φ          ── solver.py::SolverParams（alpha() / beta()）
N8  Flow prior θ             ── models/flow.py::FlowPrior（推理期 [FROZEN]）
N9  x_k / x'_k               ── solver.py::solve() 的循环变量
N10 Reconstructed image x̂    ── solver.py::solve() 的返回值
```

**语义聚合声明：**

- `"Unrolled Solver"（N4）` is a semantic abstraction of: `solve()` 中
  `for k in range(K)` 内 `dc_step()` 与 `prior_step()` 的交替调用。
  **仅 Draft A 使用该聚合**；Draft B 已展开，两者信息等价。
- `"IFFT"（N2）` is a semantic abstraction of: `solver.py::zero_filled_init()` 里的
  `ifft2(mask * y)`——把掩码相乘与逆变换画成一个算子节点。
  **它是逆变换（`ifft2`），不是 `fft2()`**；`fft2()` 只出现在 `dc_step()` 内部。

**命名映射：**

```
Data Consistency Step  ↔ solver.py::dc_step()
Prior Step             ↔ solver.py::prior_step()
Solver params φ        ↔ solver.py::SolverParams
Flow prior θ           ↔ models/flow.py::FlowPrior
```

**未画出的内容（明确声明）：**

- **multi-step inner prior sampler**：`prior_inner_steps: 4` 无任何读取点 ⇒ 不画（U1）。
- **两阶段训练编排**：本图的推断类型是 `optimization`，训练编排由
  [example-domain-adaptation.md](example-domain-adaptation.md) 覆盖，本图不重复。

---

## 7. Uncertainties

```text
Uncertain:
- inner_prior_sampler：configs/base.yaml 的 solver.prior_inner_steps: 4 在代码中
  无读取点。不画、不登记（U1）。
- cond_in_loop：训练期的 cond 由 M_tr 的零填充补全给出
  （train.py::training_step()），而推理期 solve() 未传 cond 时用完整 mask 的零填充。
  两者的差异是否有意设计，材料无法判断；本图只画一次 cond 来源，不做区分（U2）。
```

---

## 8. SVG Handoff Notes

```text
Canvas:                  landscape
Primary flow:            left → right (A) / cyclic (B)
Suggested visual groups: Draft A: 输入 / solver 块 / 输出
                         Draft B: 循环体 / 参数输入 / 冻结先验
Visual emphasis:         Draft A 的 solver 块；Draft B 的 DC ↔ Prior 交替
Secondary elements:      N2 [IFFT]、N3 x_0
Line semantics:          solid = 前向计算；dashed = 参数注入（φ → α_k / β_k）；
                         dotted = 冻结先验的 velocity 查询
Styling hierarchy:       Level 1 = 循环体容器；Level 2 = 模型块；
                         Level 3 = [IFFT] 与算子
Color grouping:          N5 / N6 同色系表示"一步之内的两个子步"
De-emphasize:            N2、N3
Center node:             Draft A 的 solver 块；Draft B 的循环体
Curved arrows:           Draft B 的回流线
Inset candidates:        Draft B 整体可作为 Draft A 的 inset
Sketch primitives:       operator [IFFT] x1；state 变量不加框 (x_k, x'_k)；
                         Unrolled Solver 是 operator 聚合，故用平面框而非 model 双线框
```

---

## 9. Figure Element Inventory

| ID | Type | Label | Group | Inputs | Outputs | Status |
|---|---|---|---|---|---|---|
| N1 | data | (y, M) | Inference | — | N2,N5 | observed · inference-only |
| N2 | operator | IFFT | Inference | N1 | N3 | observed · inference-only |
| N3 | state | x_0 | Inference | N2 | N4 | observed · inference-only |
| N4 | operator | Unrolled Solver | Inference | N3,N7,N8 | N10 | observed · inference-only |
| N5 | operator | Data Consistency Step | Solver Loop | N1,N7,N9 | N6 | observed |
| N6 | operator | Prior Step | Solver Loop | N5,N7,N8 | N9 | observed |
| N7 | parameter | Solver params φ | Solver Loop | — | N4,N5,N6 | observed |
| N8 | model | Flow prior θ | Prior | — | N4,N6 | observed · inference-only |
| N9 | state | x_k / x'_k | Solver Loop | N6 | N5 | observed |
| N10 | output | Reconstructed image x̂ | Inference | N4 | — | observed · inference-only |

---

## 这个示例演示了什么

| 行为 | 体现位置 |
|---|---|
| `FIGURE_TYPE: auto` 推断并声明 | 「推断结果与声明」段的三行声明 |
| `SKETCH_STYLE: auto` 推断并声明 | 同上；推断为 `clean`，故全图无伪 3D / tensor 堆叠 |
| **该问才问，且问的是叙事重点** | 「为什么这里要问」段的正例与反例 |
| 不问纯画风 | 反例两条（立体块 / 这是什么 type） |
| 两个叙事各自成 draft | Draft A `Linear Pipeline` + Draft B `Iterative Loop` |
| auto 档不绕过契约 | 两 draft grammar 不同、元素表完整、`--strict` 退出码 0 |
| 未确认内容不画 | `prior_inner_sampler` 只进 `Uncertainties` |
