# Flow-Matching Prior in an Unrolled Solver (demo source)

Minimal research code for **self-supervised accelerated MRI reconstruction with a
flow-matching prior inside an unrolled solver**.

This repository is the *method under study*. It is intentionally small, but every
symbol referenced by the worked example exists here.

## Method

Reconstruction is an **alternating unrolled solver**, not a single forward pass:

```
x_0 = zero-filled adjoint (A^H M y)
for k in 0 .. K-1:
    x_{k+1} = PriorStep( DataStep(x_k) )
```

* `solver.py::dc_step()` — one data-consistency gradient step
  `x - alpha * A^H M (A x - y)`.
* `solver.py::prior_step()` — one Euler step along the velocity field of the
  flow-matching prior: `x + beta * v_theta(x, t=1, cond)`.
* `solver.py::solve()` — runs `K` such alternating iterations. `K` is
  `solver.num_steps` in `configs/base.yaml` (default 8).
* `models/flow.py::FlowPrior` — conditional flow-matching velocity field
  `v_theta(x, t, cond)`, conditioned on the zero-filled adjoint `x_0`.

The prior is a **generative** prior: it is trained with a conditional
flow-matching objective, and it is used inside the solver as a learned
denoising / transport direction.

## Training setup

`train.py` has **two stages with different optimizers and different data access**.

### Stage 1 — `source_pretrain()`

* Data: a **source-domain** dataset that *does* have fully-sampled k-space.
* Supervision: **self-supervised split-mask (SSDU-style)**.
  `train.py::split_mask()` partitions the acquired samples `M` into a training
  partition `M_tr` and a disjoint hold-out partition `M_ho`. The solver only ever
  sees `M_tr`; the loss is evaluated on `M_ho`
  (`train.py::holdout_loss()`).
* Losses: `dc` + `holdout` (both self-supervised) and `flow`
  (`train.py::flow_matching_loss()`, which uses the fully-sampled **source**
  image as the flow-matching target distribution).
* Trainable: the flow prior `theta` **and** the solver parameters `phi`.
* Optimizer: `Adam`, `source.lr` (see `configs/base.yaml`).

### Stage 2 — `target_adapt()`

* Data: **target-domain undersampled k-space only**. No fully-sampled target
  data is loaded, requested, or generated anywhere in this stage.
* **Frozen:** the flow prior `theta_0` (the source checkpoint). `target_adapt()`
  calls `requires_grad_(False)` on every `FlowPrior` parameter; no gradient path
  reaches the prior. The flow-matching loss is not used here because there is no
  fully-sampled target image to define it.
* **Updated:** only the small adaptation parameter set
  `solver.py::SolverParams` — the per-iteration log step sizes `log_alpha`,
  `log_beta` and a scalar `prior_scale` (~`2K + 1` scalars).
* Supervision: the same SSDU split-mask hold-out objective on the target
  k-space.
* Optimizer: a **separate** `Adam` built only over the adaptation parameters,
  `adapt.lr`.

## Inference setup

`infer.py::reconstruct(kspace, mask)` calls `solver.solve()` with the trained
prior and the adapted solver parameters and returns the reconstructed image.
Inference needs exactly two inputs: undersampled k-space and the sampling mask.
**No target image, no ground truth, and no fully-sampled reference is available
or used at inference.**

## Source-free constraint (summary)

| Item | Source pretrain | Target adaptation | Inference |
|---|---|---|---|
| fully-sampled data | yes (source only) | **no** | **no** |
| flow prior `theta` | trainable | **frozen** | frozen |
| solver params `phi` | trainable | **trainable** | frozen |
