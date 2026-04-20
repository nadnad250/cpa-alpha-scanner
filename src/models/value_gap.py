"""
Composant 1 — Value Gap : Residual Income Model + mise à jour Bayésienne.

V* = B₀ + Σ E[ROEt - re | Ft]·Bt-1 / (1+re)^t  +  TV/(1+re)^T

Mise à jour Bayésienne : P(ROEt+1 | Dt) ∝ P(Dt | ROEt+1)·P(ROEt+1)
"""
import logging
import numpy as np
from typing import Dict, Optional, List
from scipy.stats import norm

logger = logging.getLogger(__name__)


class ResidualIncomeModel:
    """
    Valorisation par Residual Income avec croyances Bayésiennes.

    Avantage vs DCF : ancré sur la valeur comptable réelle,
    moins sensible aux hypothèses de croissance libre des flux.
    """

    def __init__(
        self,
        cost_of_equity: float = 0.09,
        terminal_growth: float = 0.025,
        horizon: int = 5,
    ):
        self.re = cost_of_equity
        self.g = terminal_growth
        self.T = horizon

    def intrinsic_value(self, fundamentals: Dict) -> Optional[float]:
        """Calcule V* (valeur intrinsèque par action)."""
        price = fundamentals.get("price")
        book = fundamentals.get("book_value_per_share")
        roe_hist = fundamentals.get("roe_history", [])
        roe_current = fundamentals.get("roe")
        shares = fundamentals.get("shares_outstanding")
        book_total = fundamentals.get("book_value_total")

        if not price or not book or book <= 0:
            return None

        # Estimation ROE via Bayes
        roe_forecast = self._bayesian_roe_estimate(roe_hist, roe_current)
        if roe_forecast is None:
            return None

        # Valeur comptable initiale
        b0 = book

        # Actualisation des Residual Incomes
        pv_ri = 0.0
        bt = b0
        for t in range(1, self.T + 1):
            # ROE décroît vers le coût du capital (mean reversion sectoriel)
            decay = 0.85 ** t
            roe_t = roe_forecast * decay + self.re * (1 - decay)
            ri_t = (roe_t - self.re) * bt
            pv_ri += ri_t / (1 + self.re) ** t
            bt = bt * (1 + roe_t * (1 - 0.5))  # retention ratio ~50%

        # Terminal Value (Gordon growth sur residual income terminal)
        ri_terminal = (roe_forecast * 0.5 - self.re) * bt  # steady state
        if self.re > self.g:
            tv = ri_terminal / (self.re - self.g)
        else:
            tv = ri_terminal * 15  # fallback multiple

        tv_pv = tv / (1 + self.re) ** self.T

        v_star = b0 + pv_ri + tv_pv
        return max(v_star, 0.01)

    def value_gap_signal(self, fundamentals: Dict) -> Optional[float]:
        """
        Signal de la Value Gap = ln(V*/P).
        Positif → sous-évalué, négatif → sur-évalué.
        """
        price = fundamentals.get("price")
        v_star = self.intrinsic_value(fundamentals)

        if v_star is None or not price or price <= 0:
            return None

        return np.log(v_star / price)

    def _bayesian_roe_estimate(
        self,
        roe_history: List[float],
        roe_current: Optional[float],
    ) -> Optional[float]:
        """
        Estimation Bayésienne du ROE futur.

        Prior : N(sector_mean=0.12, sigma_prior=0.05)
        Likelihood : données historiques
        Posterior : mise à jour analytique (conjugué Gaussien)
        """
        PRIOR_MEAN = 0.12   # ROE moyen marché
        PRIOR_VAR = 0.05 ** 2

        observations = []
        if roe_history:
            observations.extend([r for r in roe_history if -1 < r < 2])
        if roe_current and -1 < roe_current < 2:
            observations.append(roe_current)

        if not observations:
            return None

        # Variance de mesure (bruit dans les rapports financiers)
        sigma_obs = 0.04
        obs_var = sigma_obs ** 2

        # Mise à jour Bayésienne conjuguée (Gaussien-Gaussien)
        n = len(observations)
        obs_mean = np.mean(observations)

        posterior_var = 1 / (1 / PRIOR_VAR + n / obs_var)
        posterior_mean = posterior_var * (
            PRIOR_MEAN / PRIOR_VAR + n * obs_mean / obs_var
        )

        # Limites réalistes
        return float(np.clip(posterior_mean, -0.5, 0.8))
