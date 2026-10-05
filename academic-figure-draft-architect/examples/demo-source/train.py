"""Two-stage training for the flow-matching prior and the adaptation parameters.

Stage 1  source_pretrain()  self-supervised (SSDU) pre-training on a *source*
                            dataset that has fully-sampled k-space.
Stage 2  target_adapt()     source-free adaptation on *target* undersampled
                            k-space only; the flow prior is frozen and only
                            ``solver.SolverParams`` are updated.
"""

import torch
import torch.nn.functional as F

import solver
from solver import SolverParams


def split_mask(mask: torch.Tensor, rho: float,
               generator: torch.Generator | None = None):
    """SSDU split-mask: partition the acquired lines of ``mask`` into a
    training partition ``M_tr`` (seen by the solver) and a disjoint hold-out
    partition ``M_ho`` (used by the loss).  ``rho`` is the hold-out fraction.
    """
    acq = torch.nonzero(mask[0, 0, 0]).flatten()
    perm = acq[torch.randperm(acq.numel(), generator=generator)]
    n_ho = int(round(rho * acq.numel()))
    m_tr = torch.zeros_like(mask)
    m_ho = torch.zeros_like(mask)
    m_tr[..., perm[n_ho:]] = 1.0
    m_ho[..., perm[:n_ho]] = 1.0
    return m_tr, m_ho


def holdout_loss(x: torch.Tensor, y: torch.Tensor, mask_ho: torch.Tensor) -> torch.Tensor:
    """SSDU consistency loss, evaluated *only* on the held-out samples."""
    residual = mask_ho * (solver.fft2(x) - y)
    return (residual.abs() ** 2).mean()


def data_consistency_loss(x: torch.Tensor, y: torch.Tensor,
                          mask_tr: torch.Tensor) -> torch.Tensor:
    """Consistency of the reconstruction with the samples the solver has seen."""
    residual = mask_tr * (solver.fft2(x) - y)
    return (residual.abs() ** 2).mean()


def flow_matching_loss(prior, x1: torch.Tensor, cond: torch.Tensor) -> torch.Tensor:
    """Conditional flow matching on the interpolant x_t = (1-t) x_0 + t x_1.

    ``x1`` is drawn from the training image distribution; during source
    pre-training that distribution is given by fully-sampled *source* images.
    """
    t = torch.rand(x1.shape[0], 1, 1, 1, device=x1.device, dtype=x1.dtype)
    x0 = torch.randn_like(x1)
    x_t = (1.0 - t) * x0 + t * x1
    target_v = x1 - x0
    v = prior.velocity(x_t, t.view(x1.shape[0], 1), cond)
    return F.mse_loss(v, target_v)


def training_step(prior, params: SolverParams, y: torch.Tensor, mask: torch.Tensor,
                  cfg: dict, stage: str, x_ref: torch.Tensor | None = None,
                  num_steps: int | None = None):
    """One self-supervised training step (shared by both stages).

    ``x_ref`` is the fully-sampled image distribution and is available in the
    source stage only; when it is ``None`` (target adaptation) the
    flow-matching term is skipped, because there is no fully-sampled target
    image to define it.
    """
    weights = cfg[stage]["losses"]
    m_tr, m_ho = split_mask(mask, cfg["data"]["rho"])
    cond = solver.zero_filled_init(y, m_tr)

    x_hat = solver.solve(y, m_tr, prior, params, num_steps=num_steps, cond=cond)

    loss = weights["dc"] * data_consistency_loss(x_hat, y, m_tr)
    loss = loss + weights["holdout"] * holdout_loss(x_hat, y, m_ho)
    if x_ref is not None and weights.get("flow", 0.0) > 0.0:
        loss = loss + weights["flow"] * flow_matching_loss(prior, x_ref, cond)
    return loss, x_hat


def source_pretrain(source_loader, prior, params: SolverParams, cfg: dict):
    """Stage 1: self-supervised pre-training of the flow prior on source data.

    Trainable: the flow prior theta *and* the solver parameters phi.
    """
    opt = torch.optim.Adam(
        list(prior.parameters()) + list(params.parameters()),
        lr=cfg["source"]["lr"],
    )
    for _ in range(cfg["source"]["epochs"]):
        for y, mask, x_ref in source_loader:          # source has fully-sampled k-space
            loss, _ = training_step(prior, params, y, mask, cfg,
                                    stage="source", x_ref=x_ref)
            opt.zero_grad()
            loss.backward()
            opt.step()
    return prior, params


def target_adapt(target_loader, prior, params: SolverParams, cfg: dict):
    """Stage 2: source-free target adaptation.

    The flow prior is frozen; the optimizer only ever sees the small adaptation
    parameter set.  The target loader yields undersampled k-space and its mask
    -- never a fully-sampled reference image.
    """
    for p in prior.parameters():
        p.requires_grad_(False)                       # freeze the flow prior

    trainable = [p for p in params.parameters() if p.requires_grad]
    opt = torch.optim.Adam(trainable, lr=cfg["adapt"]["lr"])

    unroll = int(cfg["adapt"]["unroll"])              # unroll depth used for adaptation

    for _ in range(cfg["adapt"]["steps"]):
        for y, mask in target_loader:                 # no fully-sampled target data
            loss, _ = training_step(prior, params, y, mask, cfg,
                                    stage="adapt", num_steps=unroll)
            opt.zero_grad()
            loss.backward()                           # grads reach phi only
            opt.step()
    return params


def train(cfg: dict, source_loader, target_loader, prior):
    params = SolverParams(num_stages=cfg["solver"]["num_steps"],
                          dc_step_size=cfg["solver"]["dc_step_size"],
                          prior_step_size=cfg["solver"]["prior_step_size"])
    prior, params = source_pretrain(source_loader, prior, params, cfg)
    params = target_adapt(target_loader, prior, params, cfg)
    torch.save({"flow": prior.state_dict(), "solver_params": params.state_dict()},
               cfg.get("out", "checkpoint.pt"))
    return prior, params
