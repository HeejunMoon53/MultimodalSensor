import torch
import torch.nn as nn
import torch.nn.functional as F


# ── Stage 1: ΔR_norm → ε̂_norm ─────────────────────────────────────────────
# Architecture: 1 → 16 → 8 → 1  (177 parameters)
# Physical basis: ΔR depends only on strain → clean monotonic target

class Stage1Net(nn.Module):
    def __init__(self):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(1, 16), nn.Tanh(),
            nn.Linear(16, 8), nn.Tanh(),
            nn.Linear(8, 1),
        )
        self._init()

    def _init(self):
        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.xavier_uniform_(m.weight)
                nn.init.zeros_(m.bias)

    def forward(self, dR_norm: torch.Tensor) -> torch.Tensor:
        return self.net(dR_norm)   # (B, 1)


# ── Stage 2: (ΔL_norm, ε̂_norm) → d̂_norm ───────────────────────────────────
# Architecture: 2 → 32 → 16 → 1  (577 parameters)
# Physical basis: once ε̂ is known, L residual encodes proximity only
# Wider than Stage 1 because L(ε,d) has a more complex surface to approximate

class Stage2Net(nn.Module):
    def __init__(self):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(2, 32), nn.Tanh(),
            nn.Linear(32, 16), nn.Tanh(),
            nn.Linear(16, 1),
        )
        self._init()

    def _init(self):
        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.xavier_uniform_(m.weight)
                nn.init.zeros_(m.bias)

    def forward(self, dL_norm: torch.Tensor,
                eps_hat: torch.Tensor) -> torch.Tensor:
        return self.net(torch.cat([dL_norm, eps_hat], dim=1))  # (B, 1)


# ── Combined two-stage decoupler ─────────────────────────────────────────────
# Total: 370 parameters  |  <2.5 KB Flash after INT8 quantization
# Exports as a single ONNX graph (static batch=1 for STM32)

class TwoStageDecoupler(nn.Module):
    """
    Input:  X = [ΔL_norm, ΔR_norm]  shape (B, 2)
    Output: Y = [ε̂_norm, d̂_norm]   shape (B, 2)
    """
    def __init__(self):
        super().__init__()
        self.stage1 = Stage1Net()
        self.stage2 = Stage2Net()

    def forward(self, X: torch.Tensor) -> torch.Tensor:
        dL_norm = X[:, 0:1]
        dR_norm = X[:, 1:2]
        eps_hat = self.stage1(dR_norm)
        d_hat   = self.stage2(dL_norm, eps_hat)
        return torch.cat([eps_hat, d_hat], dim=1)   # (B, 2)

    def param_count(self) -> int:
        return sum(p.numel() for p in self.parameters())


# ── Ablation baseline: single PINN MLP ───────────────────────────────────────
# Architecture: 2 → 24 → 16 → 8 → 2  (626 parameters)

class SinglePINNMLP(nn.Module):
    """
    Input:  X = [ΔL_norm, ΔR_norm]  shape (B, 2)
    Output: Y = [ε̂_norm, d̂_norm]   shape (B, 2)
    """
    def __init__(self):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(2, 24), nn.Tanh(),
            nn.Linear(24, 16), nn.Tanh(),
            nn.Linear(16, 8), nn.Tanh(),
            nn.Linear(8, 2),
        )
        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.xavier_uniform_(m.weight)
                nn.init.zeros_(m.bias)

    def forward(self, X: torch.Tensor) -> torch.Tensor:
        return self.net(X)

    def param_count(self) -> int:
        return sum(p.numel() for p in self.parameters())


# ── Physics-Informed loss ─────────────────────────────────────────────────────
# Operates in physical units (not normalized).
# Physics parameters are jointly optimized with the network.

class PhysicsLoss(nn.Module):
    """
    Empirical physics model:
      R_theory(ε)    = α₁·ε + α₂·ε²
      L_theory(ε, d) = β₁·ε + β₂/(d+d₀)^k + β₃·ε/(d+d₀)

    All quantities in physical units:
      ε   — strain ratio  (0..0.30)
      d   — distance mm   (0..50)
      ΔR  — ΔR/R₀ (%)
      ΔL  — ΔL/L₀ (%)

    α₁, α₂, β₁, β₂, β₃ are unconstrained; d₀ and k are kept positive
    via softplus to avoid singularities.
    """
    def __init__(self):
        super().__init__()
        # Priors estimated from data:
        #   dR_mean/eps_mean ≈ 51  → α₁ ≈ 50
        #   dL driven by proximity → β₂ ~ dL_std ≈ 9
        #   d₀ should be physically meaningful (≥ 2mm)
        self.alpha1 = nn.Parameter(torch.tensor(50.0))
        self.alpha2 = nn.Parameter(torch.tensor(25.0))
        self.beta1  = nn.Parameter(torch.tensor(5.0))
        self.beta2  = nn.Parameter(torch.tensor(8.0))
        self.beta3  = nn.Parameter(torch.tensor(-1.0))
        # Stored as raw values; actual d₀, k = softplus(raw)
        self._d0_raw = nn.Parameter(torch.tensor(2.0))   # softplus(2.0)≈2.13
        self._k_raw  = nn.Parameter(torch.tensor(0.5))   # softplus(0.5)≈0.97

    @property
    def d0(self) -> torch.Tensor:
        return F.softplus(self._d0_raw)

    @property
    def k(self) -> torch.Tensor:
        return F.softplus(self._k_raw)

    def R_theory(self, eps: torch.Tensor) -> torch.Tensor:
        return self.alpha1 * eps + self.alpha2 * eps ** 2

    def L_theory(self, eps: torch.Tensor, d: torch.Tensor) -> torch.Tensor:
        d_safe = self.d0 + d.abs()
        return (self.beta1 * eps
                + self.beta2 / d_safe ** self.k
                + self.beta3 * eps / d_safe)

    def forward(self, eps_hat: torch.Tensor, d_hat: torch.Tensor,
                dR_true: torch.Tensor, dL_true: torch.Tensor) -> torch.Tensor:
        """
        All inputs are 1-D tensors in physical units.
        Returns scalar physics residual loss.
        """
        loss_R = F.mse_loss(self.R_theory(eps_hat), dR_true)
        loss_L = F.mse_loss(self.L_theory(eps_hat, d_hat), dL_true)
        return loss_R + loss_L


if __name__ == '__main__':
    model = TwoStageDecoupler()
    ablation = SinglePINNMLP()
    print(f"TwoStageDecoupler : {model.param_count()} parameters")
    print(f"SinglePINNMLP     : {ablation.param_count()} parameters")

    dummy = torch.randn(4, 2)
    out   = model(dummy)
    print(f"Forward output shape: {out.shape}")   # (4, 2)
