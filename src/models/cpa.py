"""
Composite Predictive Alpha (CPA) — Signal agrégé.

αᵢ(t) = w₁·ln(V*/P) + w₂·Φᵢ(t) + w₃·θ(μᵢ-Pᵢ) + w₄·Iᵢ(t) - λ·σᵢ²

Retourne le score CPA normalisé et les contributions de chaque composant.
"""
import logging
import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from datetime import datetime

from .value_gap import ResidualIncomeModel
from .factor_premia import FactorPremiaModel
from .mean_reversion import OrnsteinUhlenbeckModel
from .kalman_signal import InformationFlowEstimator

logger = logging.getLogger(__name__)


@dataclass
class CPAResult:
    """Résultat du calcul CPA pour un titre."""
    ticker: str
    alpha: float                      # Signal global CPA
    universe: str = ""
    price: Optional[float] = None
    intrinsic_value: Optional[float] = None
    upside_pct: Optional[float] = None

    # Composants
    value_gap: Optional[float] = None       # w1 · ln(V*/P)
    factor_premia: Optional[float] = None   # w2 · Φ
    mean_reversion: Optional[float] = None  # w3 · θ(μ-P)
    info_flow: Optional[float] = None       # w4 · I
    variance_penalty: Optional[float] = None

    # Qualité
    n_signals: int = 0                  # nombre de composants calculés
    confidence: float = 0.0            # 0-1 selon n_signals
    computed_at: str = field(
        default_factory=lambda: datetime.now().isoformat()
    )

    # Méta
    sector: str = ""
    kelly_position: Optional[float] = None

    def summary(self) -> str:
        """Résumé texte du résultat."""
        lines = [
            f"📊 {self.ticker} | Alpha: {self.alpha:+.4f} | Confiance: {self.confidence:.0%}",
            f"   Prix: {self.price:.2f} | VI: {self.intrinsic_value:.2f} | Potentiel: {self.upside_pct:+.1f}%"
            if self.price and self.intrinsic_value else f"   Prix: {self.price}",
        ]
        parts = []
        if self.value_gap is not None:
            parts.append(f"VG={self.value_gap:+.3f}")
        if self.factor_premia is not None:
            parts.append(f"FF={self.factor_premia:+.3f}")
        if self.mean_reversion is not None:
            parts.append(f"OU={self.mean_reversion:+.3f}")
        if self.info_flow is not None:
            parts.append(f"KF={self.info_flow:+.3f}")
        if parts:
            lines.append("   " + " | ".join(parts))
        if self.kelly_position is not None:
            lines.append(f"   Kelly: {self.kelly_position:.2%} du portefeuille")
        return "\n".join(lines)


class CPACalculator:
    """
    Orchestre les 4 composants et calcule l'alpha CPA final.
    """

    def __init__(
        self,
        w1: float = 0.35,   # Value Gap
        w2: float = 0.25,   # Factor Premia
        w3: float = 0.20,   # Mean Reversion
        w4: float = 0.20,   # Info Flow
        lambda_risk: float = 0.10,
        risk_free: float = 0.045,
        kelly_fraction: float = 0.25,
    ):
        self.w1 = w1
        self.w2 = w2
        self.w3 = w3
        self.w4 = w4
        self.lambda_risk = lambda_risk
        self.rf = risk_free
        self.kappa = kelly_fraction

        self.rim = ResidualIncomeModel()
        self.ff_model = FactorPremiaModel()
        self.ou_model = OrnsteinUhlenbeckModel()
        self.kf_model = InformationFlowEstimator()

    def compute(
        self,
        ticker: str,
        prices: pd.Series,
        fundamentals: Dict[str, Any],
        ff_factors: Optional[pd.DataFrame] = None,
        benchmark_prices: Optional[pd.Series] = None,
        universe: str = "",
    ) -> CPAResult:
        """Calcule le CPA complet pour un titre."""
        result = CPAResult(ticker=ticker, alpha=0.0, universe=universe)
        result.price = fundamentals.get("price")
        result.sector = fundamentals.get("sector", "")

        alpha = 0.0
        weights_used = 0.0

        # ── Composant 1 : Value Gap ────────────────────────────────────────────
        vg = self.rim.value_gap_signal(fundamentals)

        # Pas de fallback MA200 pour value_gap : il créait un biais contrarian
        # (marché haussier → tout au-dessus MA200 → signal "vendre" permanent).
        # Si fondamentaux indispos, value_gap reste None ; les 3 autres composants
        # (factor_premia, mean_reversion, info_flow) couvrent suffisamment.

        if vg is not None:
            # Clamp asymétrique : [-0.30, +1.0]
            # Le RIM est souvent trop pessimiste sur les stocks de croissance
            # (ex: NVDA, MSFT) — on limite le signal SELL à -0.30 max pour
            # éviter qu'il domine les 3 autres composantes.
            vg = float(max(-0.30, min(1.0, vg)))
            result.value_gap = self.w1 * vg
            result.intrinsic_value = self.rim.intrinsic_value(fundamentals)
            if result.price and result.intrinsic_value:
                raw_upside = (result.intrinsic_value / result.price - 1) * 100
                result.upside_pct = float(max(-100.0, min(100.0, raw_upside)))
            alpha += result.value_gap
            weights_used += self.w1
            result.n_signals += 1

        # ── Composant 2 : Factor Premia ────────────────────────────────────────
        phi = None
        if ff_factors is not None and not prices.empty:
            returns = np.log(prices / prices.shift(1)).dropna()
            phi = self.ff_model.factor_premium_signal(returns, ff_factors)

        # FALLBACK : momentum 3m + 6m en normalized z-score
        # Si Fama-French indispo, au moins capturer le momentum simple
        if phi is None and not prices.empty and len(prices) >= 126:
            mom_3m = float(prices.iloc[-1] / prices.iloc[-63] - 1) if len(prices) >= 63 else 0
            mom_6m = float(prices.iloc[-1] / prices.iloc[-126] - 1) if len(prices) >= 126 else 0
            # Combiné 60% court-terme + 40% moyen-terme
            combined = 0.6 * mom_3m + 0.4 * mom_6m
            # tanh clamp [-1, 1] avec échelle (~30% mvmt → saturation)
            phi = float(np.tanh(combined * 3.5))

        if phi is not None:
            result.factor_premia = self.w2 * phi
            alpha += result.factor_premia
            weights_used += self.w2
            result.n_signals += 1

        # ── Composant 3 : Mean Reversion (OU) ─────────────────────────────────
        if not prices.empty:
            ou_signal = self.ou_model.mean_reversion_signal(prices)
            if ou_signal is not None:
                result.mean_reversion = self.w3 * ou_signal
                alpha += result.mean_reversion
                weights_used += self.w3
                result.n_signals += 1

        # ── Composant 4 : Information Flow (Kalman) ───────────────────────────
        if not prices.empty:
            kf_signal = self.kf_model.compute_signal(prices, benchmark_prices)
            if kf_signal is not None:
                result.info_flow = self.w4 * kf_signal
                alpha += result.info_flow
                weights_used += self.w4
                result.n_signals += 1

        # ── Pénalité variance ─────────────────────────────────────────────────
        if not prices.empty:
            returns = np.log(prices / prices.shift(1)).dropna()
            if len(returns) > 20:
                ann_var = float(returns.var() * 252)
                result.variance_penalty = self.lambda_risk * ann_var
                alpha -= result.variance_penalty

        # ── Normalisation ────────────────────────────────────────────────────
        if weights_used > 0:
            alpha = alpha / weights_used * (weights_used / (self.w1 + self.w2 + self.w3 + self.w4))

        result.alpha = float(np.clip(alpha, -2.0, 2.0))
        result.confidence = result.n_signals / 4.0

        # ── Kelly Position ───────────────────────────────────────────────────
        result.kelly_position = self._kelly_position(result)

        return result

    def _kelly_position(self, result: CPAResult) -> Optional[float]:
        """f* = κ · (α - rf) / σ²"""
        if result.variance_penalty is None or result.alpha <= self.rf:
            return None
        sigma2 = result.variance_penalty / self.lambda_risk
        if sigma2 <= 0:
            return None
        f_star = self.kappa * (result.alpha - self.rf) / sigma2
        return float(np.clip(f_star, 0, 0.10))  # max 10% par position
