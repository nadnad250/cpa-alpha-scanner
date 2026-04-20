"""
Composant 4 — Flux d'information (Filtre de Kalman).

I(t) = I(t-1)·e^(-δΔt) + Kt·(yt - ŷt)

Permet de fusionner des signaux hétérogènes (momentum, surprises
de bénéfices, sentiment) avec une décroissance temporelle explicite.
"""
import logging
import numpy as np
import pandas as pd
from typing import List, Optional, Dict

logger = logging.getLogger(__name__)


class KalmanSignalFilter:
    """
    Filtre de Kalman 1D pour agréger les signaux d'information.

    Etat caché : la "valeur d'information" latente du titre.
    Observations : rendements anormaux, surprises bénéfices, momentum.

    Paramètres:
        decay (δ)        : taux de décroissance de l'info (0-1 par jour)
        process_noise    : incertitude sur l'évolution de l'état (Q)
        obs_noise        : incertitude de mesure (R)
    """

    def __init__(
        self,
        decay: float = 0.95,
        process_noise: float = 0.01,
        obs_noise: float = 0.05,
    ):
        self.decay = decay
        self.Q = process_noise   # bruit processus
        self.R = obs_noise       # bruit observation
        self._state = 0.0
        self._variance = 1.0

    def update(self, observation: float, dt: float = 1.0) -> float:
        """
        Une étape du filtre :
        1. Prédiction : I_pred = I * exp(-δ·dt)
        2. Correction  : I_new  = I_pred + K·(y - y_hat)
        """
        # Prédiction
        decay_factor = np.exp(-self.decay * dt / 252)
        state_pred = self._state * decay_factor
        var_pred = self._variance * decay_factor ** 2 + self.Q

        # Gain de Kalman
        K = var_pred / (var_pred + self.R)

        # Innovation (résidu)
        y_hat = state_pred  # modèle naif : signal attendu = état prédit
        innovation = observation - y_hat

        # Mise à jour
        self._state = state_pred + K * innovation
        self._variance = (1 - K) * var_pred

        return float(self._state)

    def reset(self):
        """Réinitialise l'état du filtre."""
        self._state = 0.0
        self._variance = 1.0

    @property
    def current_state(self) -> float:
        return self._state


class InformationFlowEstimator:
    """
    Estime le signal d'information agrégé pour un titre.

    Signaux bruts fusionnés :
    1. Momentum 12-1 (rendement 12 mois sauf le dernier)
    2. Momentum à court terme (5J, 21J)
    3. Surprise de volume (volume vs moyenne 20J)
    4. Anomalie de rendement (rendement vs benchmark)
    """

    def __init__(self, decay: float = 0.95):
        self.kalman = KalmanSignalFilter(decay=decay)

    def compute_signal(
        self,
        prices: pd.Series,
        benchmark_prices: Optional[pd.Series] = None,
    ) -> Optional[float]:
        """
        Calcule le signal d'information agrégé via Kalman.
        """
        prices = prices.dropna()
        if len(prices) < 30:
            return None

        self.kalman.reset()

        # Rendements journaliers
        returns = np.log(prices / prices.shift(1)).dropna()

        observations = self._build_observations(prices, returns, benchmark_prices)
        if not observations:
            return None

        state = 0.0
        for obs in observations:
            state = self.kalman.update(obs)

        return float(np.tanh(state))  # borné [-1, 1]

    def _build_observations(
        self,
        prices: pd.Series,
        returns: pd.Series,
        benchmark: Optional[pd.Series],
    ) -> List[float]:
        """Construit la liste des observations pour le filtre."""
        obs = []

        # Momentum 12-1 (standard anomalie de momentum)
        if len(prices) >= 252:
            mom_12_1 = np.log(prices.iloc[-22] / prices.iloc[-252])
            obs.append(self._normalize(mom_12_1, 0, 0.3))

        # Momentum court terme (21 jours)
        if len(returns) >= 21:
            mom_21 = returns.iloc[-21:].sum()
            obs.append(self._normalize(mom_21, 0, 0.1))

        # Momentum très court (5 jours)
        if len(returns) >= 5:
            mom_5 = returns.iloc[-5:].sum()
            obs.append(self._normalize(mom_5, 0, 0.05))

        # Rendement relatif vs benchmark
        if benchmark is not None:
            bench_r = np.log(benchmark / benchmark.shift(1)).dropna()
            common_idx = returns.index.intersection(bench_r.index)
            if len(common_idx) >= 21:
                rel = (returns.loc[common_idx] - bench_r.loc[common_idx]).iloc[-21:].sum()
                obs.append(self._normalize(rel, 0, 0.05))

        return obs

    @staticmethod
    def _normalize(value: float, mean: float, std: float) -> float:
        """Normalise une observation."""
        if std == 0:
            return 0.0
        return float(np.clip((value - mean) / std, -3, 3))
