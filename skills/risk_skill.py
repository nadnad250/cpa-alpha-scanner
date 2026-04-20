"""
Skill : Analyse et gestion du risque (VaR, CVaR, volatilité, corrélations).
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from scipy.stats import norm


@dataclass
class RiskMetrics:
    ticker: str
    annual_vol: float           # Volatilité annualisée
    var_95: float               # Value at Risk 95% (1 jour)
    cvar_95: float              # CVaR / Expected Shortfall 95%
    max_drawdown: float         # Drawdown maximum historique
    sharpe_estimate: float      # Ratio de Sharpe estimé
    calmar_ratio: float         # Rendement annuel / Max Drawdown
    risk_score: float           # Score de risque global (0=faible, 1=élevé)


class RiskSkill:
    """
    Calcule les métriques de risque standard pour un portefeuille ou titre.
    Utilisé par le Kelly Calculator pour ajuster les positions.
    """

    def __init__(self, risk_free: float = 0.045):
        self.rf = risk_free

    def compute_risk(
        self,
        returns: pd.Series,
        ticker: str = "",
    ) -> RiskMetrics:
        """Calcule toutes les métriques de risque."""
        r = returns.dropna()

        # Volatilité annualisée
        annual_vol = float(r.std() * np.sqrt(252))

        # VaR paramétrique 95%
        var_95 = float(-norm.ppf(0.05) * r.std())

        # CVaR (Expected Shortfall) 95%
        cvar_95 = float(-r[r < r.quantile(0.05)].mean())

        # Max Drawdown
        cumulative = r.cumsum().apply(np.exp)
        rolling_max = cumulative.cummax()
        drawdowns = (cumulative - rolling_max) / rolling_max
        max_drawdown = float(drawdowns.min())

        # Rendement annualisé estimé
        annual_return = float(r.mean() * 252)

        # Sharpe
        sharpe = (annual_return - self.rf) / (annual_vol + 1e-8)

        # Calmar
        calmar = annual_return / (abs(max_drawdown) + 1e-8) if max_drawdown < 0 else 0

        # Score de risque composite (0=faible risque, 1=haut risque)
        risk_score = np.clip(annual_vol / 0.50, 0, 1)  # normalisé sur 50% vol

        return RiskMetrics(
            ticker=ticker,
            annual_vol=annual_vol,
            var_95=var_95,
            cvar_95=cvar_95,
            max_drawdown=max_drawdown,
            sharpe_estimate=sharpe,
            calmar_ratio=calmar,
            risk_score=float(risk_score),
        )

    def correlation_matrix(
        self,
        returns_dict: Dict[str, pd.Series],
        min_overlap: int = 100,
    ) -> pd.DataFrame:
        """Calcule la matrice de corrélation entre titres."""
        df = pd.DataFrame(returns_dict).dropna(how="all")
        corr = df.corr()
        return corr

    def portfolio_var(
        self,
        weights: Dict[str, float],
        returns_dict: Dict[str, pd.Series],
        confidence: float = 0.95,
    ) -> float:
        """Calcule la VaR du portefeuille avec corrélations."""
        tickers = list(weights.keys())
        df = pd.DataFrame({t: returns_dict[t] for t in tickers if t in returns_dict})
        df = df.dropna()
        if df.empty:
            return 0.0

        w = np.array([weights.get(t, 0) for t in df.columns])
        cov_matrix = df.cov().values * 252

        port_var_annual = float(w @ cov_matrix @ w)
        port_vol_daily = np.sqrt(port_var_annual / 252)

        return float(-norm.ppf(1 - confidence) * port_vol_daily)
