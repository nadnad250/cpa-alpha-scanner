"""
Composant 2 — Factor Premia (Fama-French 5 + Momentum).

Φᵢ(t) = Σₖ βᵢ,ₖ · (λₖ - rf)

Bêtas estimés par régression glissante 60 mois (OLS).
"""
import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from sklearn.linear_model import LinearRegression

logger = logging.getLogger(__name__)

FACTOR_NAMES = ["Mkt-RF", "SMB", "HML", "RMW", "CMA", "MOM"]
ROLLING_WINDOW = 60  # mois


class FactorPremiaModel:
    """
    Modèle à 6 facteurs (FF5 + Momentum) avec bêtas glissants.
    Retourne l'alpha attendu basé sur les primes de risque historiques.
    """

    def __init__(self, window: int = ROLLING_WINDOW):
        self.window = window

    def compute_betas(
        self,
        returns: pd.Series,
        factors: pd.DataFrame,
    ) -> Optional[Dict[str, float]]:
        """
        Estime les bêtas par OLS sur la fenêtre glissante.

        Args:
            returns: Rendements mensuels du titre (pd.Series avec DatetimeIndex)
            factors: DataFrame FF5+MOM (colonnes: Mkt-RF, SMB, HML, RMW, CMA, MOM, RF)
        """
        if returns is None or factors is None:
            return None

        # Aligner sur les mêmes dates
        returns_monthly = self._to_monthly(returns)
        common = returns_monthly.index.intersection(factors.index)
        if len(common) < 24:
            return None

        r = returns_monthly.loc[common]
        f = factors.loc[common]

        # Excès de rendement
        rf = f.get("RF", pd.Series(0, index=common))
        excess = r - rf

        # Utiliser uniquement les n derniers mois (fenêtre glissante)
        n = min(self.window, len(common))
        X = f[FACTOR_NAMES].iloc[-n:].values
        y = excess.iloc[-n:].values

        mask = ~(np.isnan(X).any(axis=1) | np.isnan(y))
        if mask.sum() < 12:
            return None

        model = LinearRegression(fit_intercept=True)
        model.fit(X[mask], y[mask])

        betas = dict(zip(FACTOR_NAMES, model.coef_))
        betas["alpha_regression"] = model.intercept_
        betas["r_squared"] = model.score(X[mask], y[mask])
        return betas

    def factor_premium_signal(
        self,
        returns: pd.Series,
        factors: pd.DataFrame,
    ) -> Optional[float]:
        """
        Calcule Φ = Σ βk · (λk - rf) en annualisé.
        Les primes (λk) sont la moyenne historique de chaque facteur.
        """
        betas = self.compute_betas(returns, factors)
        if betas is None:
            return None

        # Primes moyennes annualisées (approximation standard)
        factor_premia = {
            "Mkt-RF": factors["Mkt-RF"].mean() * 12 if "Mkt-RF" in factors.columns else 0.06,
            "SMB":    factors["SMB"].mean() * 12    if "SMB" in factors.columns else 0.02,
            "HML":    factors["HML"].mean() * 12    if "HML" in factors.columns else 0.03,
            "RMW":    factors["RMW"].mean() * 12    if "RMW" in factors.columns else 0.025,
            "CMA":    factors["CMA"].mean() * 12    if "CMA" in factors.columns else 0.02,
            "MOM":    factors["MOM"].mean() * 12    if "MOM" in factors.columns else 0.04,
        }

        rf_annual = factors["RF"].mean() * 12 if "RF" in factors.columns else 0.045

        phi = sum(
            betas.get(k, 0) * (factor_premia[k] - rf_annual)
            for k in FACTOR_NAMES
        )
        return float(np.clip(phi, -1.0, 1.0))

    def _to_monthly(self, returns: pd.Series) -> pd.Series:
        """Convertit les rendements journaliers en mensuels."""
        if returns.index.freq == "ME" or returns.index.freq == "M":
            return returns
        # Resample en composant les rendements journaliers
        monthly = returns.resample("ME").apply(
            lambda x: np.exp(x.sum()) - 1 if len(x) > 0 else np.nan
        )
        return monthly.dropna()
