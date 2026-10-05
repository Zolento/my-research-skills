"""Conditional flow-matching prior over complex MR images.

The prior is a velocity field v_theta(x, t, cond) trained with a conditional
flow-matching objective.  Inside the unrolled solver it is evaluated once per
iteration (see ``solver.prior_step``); it is never fine-tuned on target data
(see ``train.target_adapt``).
"""

import torch
import torch.nn as nn


class FlowPrior(nn.Module):
    """Velocity field of a conditional flow-matching model.

    Args:
        in_ch:     number of image channels (2 = real / imaginary).
        base_ch:   width of the convolutional encoder.
        time_dim:  width of the time embedding.
    """

    def __init__(self, in_ch: int = 2, base_ch: int = 32, time_dim: int = 64):
        super().__init__()
        self.in_ch = in_ch
        self.base_ch = base_ch
        self.time_dim = time_dim

        self.encoder = nn.Sequential(
            nn.Conv2d(in_ch, base_ch, kernel_size=3, padding=1),
            nn.SiLU(),
            nn.Conv2d(base_ch, base_ch, kernel_size=3, padding=1),
            nn.SiLU(),
        )
        self.time_embed = nn.Sequential(
            nn.Linear(1, time_dim),
            nn.SiLU(),
            nn.Linear(time_dim, time_dim),
        )
        self.velocity_head = nn.Sequential(
            nn.Conv2d(2 * base_ch + time_dim, base_ch, kernel_size=3, padding=1),
            nn.SiLU(),
            nn.Conv2d(base_ch, in_ch, kernel_size=3, padding=1),
        )

    def encode(self, x: torch.Tensor) -> torch.Tensor:
        """Shared convolutional encoder, used for both x and the conditioning image."""
        return self.encoder(x)

    def velocity(self, x: torch.Tensor, t: torch.Tensor, cond: torch.Tensor) -> torch.Tensor:
        """Predict the flow velocity at state ``x``, time ``t`` in [0, 1]
        (shape [B, 1]) and conditioning image ``cond`` (the zero-filled adjoint
        reconstruction in this project).  Returns a field shaped like ``x``.
        """
        h_x = self.encode(x)
        h_c = self.encode(cond)
        t_emb = self.time_embed(t).view(x.shape[0], self.time_dim, 1, 1)
        t_emb = t_emb.expand(-1, -1, x.shape[-2], x.shape[-1])
        h = torch.cat([h_x, h_c, t_emb], dim=1)
        return self.velocity_head(h)

    @torch.no_grad()
    def sample(self, cond: torch.Tensor, steps: int = 8,
               x_init: torch.Tensor | None = None) -> torch.Tensor:
        """ODE-ish sampler: explicit Euler integration from t=0 to t=1.

        ``steps`` and ``x_init`` are exposed so the sampler can start from a
        partially reconstructed state instead of pure noise.
        """
        x = torch.randn_like(cond) if x_init is None else x_init.clone()
        dt = 1.0 / steps
        for i in range(steps):
            t = torch.full((x.shape[0], 1), i * dt, device=x.device, dtype=x.dtype)
            x = x + dt * self.velocity(x, t, cond)
        return x
