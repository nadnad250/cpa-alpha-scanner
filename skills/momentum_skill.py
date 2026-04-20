"""
Skill : Analyse de momentum avancée (Cross-Sectional + Time-Series).

Utilisation :
    from skills.momentum_skill import MomentumSkill
    skill = MomentumSkill()
    score = skill.score(prices_dict)
"""
import numpy as np
import pandas as pd
from typing import Dict, Optional, List
from dataclasses import dataclass


@dataclass
class MomentumScore:
    ticker: str
    ts_momentum: float      # Time-Series : performance vs propre historique
    xs_rank: float          # Cross-Sectional : rang dans l'univers (0-1)
    reversal_1m: float      # Retournement court terme (contrarian)
    composite: float        # Score composé


class MomentumSkill:
    """
    Skill de momentum à double approche :
    - Time-Series (absolue) : Jegadeesh & Titman 1993
    - Cross-Sectional (relative) : rang dans l'univers

    Combiner les deux réduit la sensibilité aux bear markets.
    """

    def score(
        self,
        prices: Dict[str, pd.Series],
        lookback_long: int = 252,
        lookback_skip: int = 21,
        lookback_reversal: int = 21,
    ) -> List[MomentumScore]:
        """
        Calcule les scores de momentum pour l'ensemble de l'univers.

        Args:
            prices: Dict {ticker: pd.Series de prix}
            lookback_long: fenêtre principale (252J = 12 mois)
            lookback_skip: jours à exclure (évite le reversal à 1 mois)
            lookback_reversal: fenêtre pour le signal de retournement
        """
        ts_scores = {}
        reversal_scores = {}

        for ticker, p in prices.items():
            p = p.dropna()
            if len(p) < lookback_long + 10:
                continue

            # Time-Series : log-return 12-1 mois
            ts = np.log(p.iloc[-lookback_skip] / p.iloc[-lookback_long])
            ts_scores[ticker] = ts

            # Reversal 1 mois
            rev = np.log(p.iloc[-1] / p.iloc[-lookback_reversal])
            reversal_scores[ticker] = rev

        if not ts_scores:
            return []

        # Cross-Sectional rank (0 = worst, 1 = best)
        ts_series = pd.Series(ts_scores)
        xs_ranks = ts_series.rank(pct=True)

        scores = []
        for ticker in ts_scores:
            composite = (
                0.5 * ts_scores[ticker] / (ts_series.std() + 1e-8)  # normalisé
                + 0.5 * xs_ranks.get(ticker, 0.5)                   # rang relatif
                - 0.1 * reversal_scores.get(ticker, 0)               # pénalité reversal
            )
            scores.append(MomentumScore(
                ticker=ticker,
                ts_momentum=ts_scores[ticker],
                xs_rank=xs_ranks.get(ticker, 0.5),
                reversal_1m=reversal_scores.get(ticker, 0),
                composite=float(composite),
            ))

        return sorted(scores, key=lambda s: s.composite, reverse=True)

    def momentum_crash_filter(
        self,
        index_prices: pd.Series,
        threshold: float = -0.10,
    ) -> bool:
        """
        Détecte les momentum crashes (mercé bear).
        Retourne True si le marché a chuté > threshold les 3 derniers mois.
        Quand True → réduire l'exposition momentum (Daniel & Moskowitz 2016).
        """
        if len(index_prices) < 63:
            return False
        recent_return = np.log(index_prices.iloc[-1] / index_prices.iloc[-63])
        return bool(recent_return < threshold)
