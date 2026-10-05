"""Alternating unrolled solver: data-consistency step + flow-prior step.

    x_0     = A^H (M y)                     (zero-filled adjoint)
    x_{k+1} = prior_step( dc_step(x_k) )    for k = 0 .. K-1

``dc_step`` is non-parametric; ``prior_step`` calls the flow prior.  Only the
small ``SolverParams`` set is adapted on target data (see ``train.target_adapt``).
"""

import math

import torch
import torch.nn as nn


def fft2(x: torch.Tensor) -> torch.Tensor:
    return torch.fft.fft2(x, dim=(-2, -1), norm="ortho")


def ifft2(k: torch.Tensor) -> torch.Tensor:
    return torch.fft.ifft2(k, dim=(-2, -1), norm="ortho")


class SolverParams(nn.Module):
    """Small adaptation parameter set phi (~2K + 1 scalars).

    One log step size per unrolled iteration for the data step and for the
    prior step, plus a scalar prior scale.  These are the *only* parameters
    updated during target adaptation.
    """

    def __init__(self, num_stages: int = 8, dc_step_size: float = 0.5,
                 prior_step_size: float = 0.2):
        super().__init__()
        self.num_stages = num_stages
        self.log_alpha = nn.Parameter(torch.full((num_stages,), math.log(dc_step_size)))
        self.log_beta = nn.Parameter(torch.full((num_stages,), math.log(prior_step_size)))
        self.prior_scale = nn.Parameter(torch.zeros(1))

    def alpha(self, k: int) -> torch.Tensor:
        """Data-consistency step size at iteration k."""
        return torch.exp(self.log_alpha[k])

    def beta(self, k: int) -> torch.Tensor:
        """Prior step size at iteration k, gated by the learned prior scale."""
        return torch.exp(self.log_beta[k]) * torch.sigmoid(self.prior_scale)


def zero_filled_init(y: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
    """x_0: zero-filled adjoint reconstruction, A^H (M y)."""
    return ifft2(mask * y)


def dc_step(x: torch.Tensor, y: torch.Tensor, mask: torch.Tensor,
            alpha: torch.Tensor) -> torch.Tensor:
    """One data-consistency gradient step.

        x - alpha * A^H M (A x - y)

    Args:
        x:     current reconstruction, shape [B, 2, H, W].
        y:     measured k-space,      shape [B, 2, H, W].
        mask:  sampling mask,         shape [B, 1, H, W] (broadcast over channels).
        alpha: scalar step size for this iteration.
    """
    residual = mask * (fft2(x) - y)
    return x - alpha * ifft2(residual)


def prior_step(x: torch.Tensor, prior: nn.Module, cond: torch.Tensor,
               beta: torch.Tensor) -> torch.Tensor:
    """One Euler step along the learned velocity field v_theta.

    The flow prior is *not* modified here: no gradient is required and the
    prior parameters stay frozen whenever this is called on target data.
    """
    t = torch.ones(x.shape[0], 1, device=x.device, dtype=x.dtype)
    v = prior.velocity(x, t, cond)
    return x + beta * v


def solve(y: torch.Tensor, mask: torch.Tensor, prior: nn.Module,
          params: SolverParams, num_steps: int | None = None,
          cond: torch.Tensor | None = None) -> torch.Tensor:
    """Run K alternating iterations and return the final reconstruction.

    Args:
        y:         measured k-space, shape [B, 2, H, W].
        mask:      sampling mask,    shape [B, 1, H, W].
        prior:     flow prior, frozen at this point of the pipeline.
        params:    solver parameters (adapted, or at their initial values).
        num_steps: K; defaults to ``params.num_stages``.
        cond:      conditioning image; defaults to the zero-filled adjoint x_0.
    """
    K = params.num_stages if num_steps is None else num_steps
    x = zero_filled_init(y, mask)
    if cond is None:
        cond = prior.encode(x)

    for k in range(K):
        x = dc_step(x, y, mask, alpha=params.alpha(k))
        x = prior_step(x, prior, cond, beta=params.beta(k))
    return x
