"""Deployment-time reconstruction.

The only inputs are undersampled k-space and the sampling mask.  No target
image, no ground truth and no fully-sampled reference is loaded here.
"""

import argparse

import torch

import solver
from models.flow import FlowPrior
from solver import SolverParams


def load_checkpoint(path: str, cfg: dict):
    """Load the pre-trained flow prior and the target-adapted solver parameters."""
    ckpt = torch.load(path, map_location="cpu")

    prior = FlowPrior(**cfg["model"]["flow"])
    prior.load_state_dict(ckpt["flow"])
    prior.eval()

    params = SolverParams(num_stages=cfg["solver"]["num_steps"],
                          dc_step_size=cfg["solver"]["dc_step_size"],
                          prior_step_size=cfg["solver"]["prior_step_size"])
    params.load_state_dict(ckpt["solver_params"])
    return prior, params


def reconstruct(kspace: torch.Tensor, mask: torch.Tensor, prior, params,
                cfg: dict) -> torch.Tensor:
    """Reconstruct an image from undersampled k-space via the unrolled solver."""
    num_steps = cfg["solver"]["num_steps"]
    with torch.no_grad():
        x_hat = solver.solve(kspace, mask, prior, params, num_steps=num_steps)
    return x_hat


def main():
    import yaml

    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/base.yaml")
    ap.add_argument("--ckpt", default="checkpoint.pt")
    ap.add_argument("--kspace", required=True)
    ap.add_argument("--mask", required=True)
    args = ap.parse_args()

    cfg = yaml.safe_load(open(args.config))
    prior, params = load_checkpoint(args.ckpt, cfg)
    x_hat = reconstruct(torch.load(args.kspace), torch.load(args.mask),
                        prior, params, cfg)
    torch.save(x_hat, "reconstruction.pt")


if __name__ == "__main__":
    main()
