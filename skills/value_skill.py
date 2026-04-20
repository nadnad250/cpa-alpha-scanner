"""
Skill : Analyse de valeur multi-critères (value investing quantitatif).

Combine P/B, P/E, EV/EBITDA, Graham Number, F-Score Piotroski.
"""
import numpy as np
import pandas as pd
from typing import Dict, Optional, List
from dataclasses import dataclass


@dataclass
class ValueScore:
    ticker: str
    pb_score: float          # P/B normalisé
    pe_score: float          # P/E normalisé
    graham_margin: float     # Marge vs Graham Number
    piotroski_f: int         # Score Piotroski (0-9)
    composite: float


class ValueSkill:
    """
    Analyse value quantitative avec le F-Score de Piotroski (2000).

    Avantage : le F-Score filtre les "value traps" — actions bon marché
    mais fondamentaux détériorés.
    Score 8-9 = value+qualité = meilleure combinaison.
    """

    def score(
        self,
        fundamentals_list: List[Dict],
    ) -> List[ValueScore]:
        """Calcule les scores value pour une liste de fondamentaux."""
        scores = []
        for f in fundamentals_list:
            vs = self._compute_single(f)
            if vs:
                scores.append(vs)

        # Normaliser les scores relatifs à l'univers
        if not scores:
            return []

        pb_vals = [s.pb_score for s in scores]
        pe_vals = [s.pe_score for s in scores]
        pb_mean, pb_std = np.mean(pb_vals), np.std(pb_vals) + 1e-8
        pe_mean, pe_std = np.mean(pe_vals), np.std(pe_vals) + 1e-8

        for s in scores:
            pb_z = -(s.pb_score - pb_mean) / pb_std   # plus petit P/B = mieux
            pe_z = -(s.pe_score - pe_mean) / pe_std   # plus petit P/E = mieux
            f_score_norm = s.piotroski_f / 9.0
            graham_signal = np.tanh(s.graham_margin)

            s.composite = (
                0.25 * pb_z
                + 0.25 * pe_z
                + 0.30 * f_score_norm
                + 0.20 * graham_signal
            )

        return sorted(scores, key=lambda s: s.composite, reverse=True)

    def _compute_single(self, f: Dict) -> Optional[ValueScore]:
        """Calcule le score pour un seul titre."""
        ticker = f.get("ticker", "")
        price = f.get("price")
        book = f.get("book_value_per_share")
        roe = f.get("roe")

        if not price or price <= 0:
            return None

        # P/B ratio
        pb = (price / book) if book and book > 0 else 999

        # P/E approximé via ROE et P/B (P/E = P/B / ROE)
        if book and book > 0 and roe and roe > 0:
            pe = pb / roe
        else:
            pe = 999

        # Graham Number = sqrt(22.5 × EPS × BVPS)
        eps = (price / pe) if pe < 999 else None
        if eps and book and eps > 0 and book > 0:
            graham_number = np.sqrt(22.5 * eps * book)
            graham_margin = (graham_number / price) - 1  # positif = sous la valeur Graham
        else:
            graham_margin = 0.0

        # Piotroski F-Score simplifié (sans comptes détaillés)
        f_score = self._estimate_piotroski(f)

        return ValueScore(
            ticker=ticker,
            pb_score=pb,
            pe_score=pe,
            graham_margin=float(graham_margin),
            piotroski_f=f_score,
            composite=0.0,  # calculé après normalisation
        )

    @staticmethod
    def _estimate_piotroski(f: Dict) -> int:
        """
        Estime le F-Score Piotroski (0-9) avec les données disponibles.
        9 critères binaires sur rentabilité, levier, efficacité.
        """
        score = 0
        # Rentabilité
        roe = f.get("roe", 0) or 0
        if roe > 0:
            score += 1  # ROA positif (proxy)
        if roe > 0.05:
            score += 1  # ROA au-dessus du seuil
        # Levier / Liquidité
        current_ratio = f.get("current_ratio", 1) or 1
        if current_ratio > 1:
            score += 1
        debt_to_equity = f.get("debt_to_equity", 100) or 100
        if debt_to_equity < 100:
            score += 1
        if debt_to_equity < 50:
            score += 1
        # Efficacité
        gross_margin = f.get("gross_margin", 0) or 0
        if gross_margin > 0.20:
            score += 1
        if gross_margin > 0.40:
            score += 1
        operating_margin = f.get("operating_margin", 0) or 0
        if operating_margin > 0.05:
            score += 1
        earnings_growth = f.get("earnings_growth", 0) or 0
        if earnings_growth > 0:
            score += 1

        return min(score, 9)
