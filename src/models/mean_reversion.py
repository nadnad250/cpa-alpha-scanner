"""
Composant 3 — Processus Ornstein-Uhlenbeck (Mean Reversion).

dP = θ(μ - P)dt + σ dW

θ estimé par MLE (Maximum de Vraisemblance).
Interprétation : si θ grand → retour rapide à la valeur équitable.
"""
import logging
import numpy as np
import pandas as pd
from typing import Optional, Tuple
from scipy.optimize import minimize

logger = logging.getLogger(__name__)


class OrnsteinUhlenbeckModel:
    """
    Estime les paramètres OU et génère un signal de mean-reversion.

    θ (vitesse) : la valeur clé — plus θ est grand, plus l'action
                  revient vite vers sa moyenne → opportunité proche.
    μ (moyenne à long terme) : proxy de "fair value" statistique.
    σ (volatilité stochastique) : risque résiduel.
    """

    def __init__(self, lookback: int = 252):
        self.lookback = lookback
        self.theta: Optional[float] = None
        self.mu: Optional[float] = None
        self.sigma: Optional[float] = None

    def fit(self, prices: pd.Series) -> bool:
        """
        Estime θ, μ, σ par MLE discret sur les prix observés.
        Retourne True si l'estimation a réussi.
        """
        series = prices.dropna().tail(self.lookback)
        if len(series) < 50:
            return False

        log_p = np.log(series.values.astype(float))
        dt = 1 / 252  # pas journalier

        try:
            theta, mu, sigma = self._mle_ou(log_p, dt)
            if theta > 0 and sigma > 0:
                self.theta = theta
                self.mu = mu
                self.sigma = sigma
                return True
        except Exception as e:
            logger.debug(f"OU MLE failed: {e}")
        return False

    def mean_reversion_signal(self, prices: pd.Series) -> Optional[float]:
        """
        Signal = θ · (μ - P_current).
        Positif → en dessous de la moyenne (acheter),
        Négatif → au-dessus (éviter/vendre).
        """
        if not self.fit(prices):
            return None

        current_log_p = np.log(float(prices.dropna().iloc[-1]))
        deviation = self.mu - current_log_p

        # Signal normalisé par σ (z-score OU)
        if self.sigma and self.sigma > 0:
            z_score = deviation / self.sigma
            signal = np.tanh(z_score)  # borné [-1, 1]
        else:
            signal = np.tanh(self.theta * deviation)

        return float(signal)

    def half_life_days(self) -> Optional[float]:
        """Demi-vie du processus en jours."""
        if self.theta and self.theta > 0:
            return np.log(2) / self.theta
        return None

    def _mle_ou(
        self, log_prices: np.ndarray, dt: float
    ) -> Tuple[float, float, float]:
        """
        MLE analytique pour OU discret.
        Formules fermées d'Ohlstein & Jacobs (2004).
        """
        n = len(log_prices) - 1
        x = log_prices[:-1]
        y = log_prices[1:]

        sx  = x.sum()
        sy  = y.sum()
        sxx = (x * x).sum()
        sxy = (x * y).sum()
        syy = (y * y).sum()

        denom = n * sxx - sx ** 2
        if abs(denom) < 1e-10:
            raise ValueError("Dénominateur MLE nul")

        mu = (sy * sxx - sx * sxy) / (n * (sxx - sxy) - (sx * sy - n * sx))
        theta_raw = -np.log((sxy - mu * sx - mu * sy + n * mu ** 2) /
                            (sxx - 2 * mu * sx + n * mu ** 2)) / dt
        alpha = np.exp(-theta_raw * dt)

        sigma2 = (syy - 2 * alpha * sxy + alpha ** 2 * sxx
                  - 2 * mu * (1 - alpha) * (sy - alpha * sx)
                  + n * mu ** 2 * (1 - alpha) ** 2) / n
        sigma2 = max(sigma2, 1e-8)
        sigma = np.sqrt(sigma2 * 2 * theta_raw / (1 - np.exp(-2 * theta_raw * dt)))

        return float(theta_raw), float(mu), float(sigma)
