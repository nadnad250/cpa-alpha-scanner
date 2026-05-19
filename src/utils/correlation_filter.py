"""
Filtre corrélation entre signaux — évite le sur-concentration sectorielle.

Problème : 8/10 positions actuelles sont Tech (CSCO, MU, CRWD, PANW, FTNT,
GOOGL, NVDA…). Si le NASDAQ corrige de -2%, on prend -16% en cumulé.

Solution : avant d'ouvrir un nouveau signal, vérifier qu'il n'est pas
trop corrélé (60j) avec les positions DÉJÀ ouvertes. Si max(corr) > seuil
→ skip (un nouveau ticker tech n'apporte rien si on a déjà 8 tech).

API :
    filter_uncorrelated(
        candidates: list[Opportunity],
        existing_tickers: set[str],
        prices_df: pd.DataFrame,
        threshold: float = 0.85,
    ) -> list[Opportunity]

Garanties :
- Préserve l'ordre relatif des candidats (par |score|×conf)
- Skip silencieusement si pas assez de data prix
- Ne pénalise pas le premier candidat (corrélation contre un set vide)
"""
import logging
from typing import Iterable

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

DEFAULT_THRESHOLD = 0.85
LOOKBACK_DAYS = 60


def _safe_corr(s1: pd.Series, s2: pd.Series) -> float | None:
    """Corrélation de Pearson sur returns, tolérante au manque de données."""
    if s1 is None or s2 is None:
        return None
    df = pd.concat([s1, s2], axis=1).dropna()
    if len(df) < 20:
        return None
    returns = df.pct_change().dropna()
    if len(returns) < 15:
        return None
    try:
        return float(returns.corr().iloc[0, 1])
    except Exception:
        return None


def filter_uncorrelated(
    candidates: Iterable,
    existing_tickers: set[str],
    prices_df: pd.DataFrame | None,
    threshold: float = DEFAULT_THRESHOLD,
) -> list:
    """
    Filtre les candidats trop corrélés avec les positions existantes
    OU avec les candidats déjà acceptés (corrélation incrémentale).

    Args:
        candidates : itérable d'Opportunity (déjà filtrés premium, triés par qualité)
        existing_tickers : tickers en position ouverte (de signals.json)
        prices_df : DataFrame des prix (colonnes = tickers, lignes = dates)
        threshold : seuil de corrélation max (default 0.85)

    Returns:
        Liste filtrée d'Opportunity, dans l'ordre d'entrée.
    """
    if prices_df is None or prices_df.empty:
        # Pas de data → ne filtre rien (fail-open)
        return list(candidates)

    # Restreindre aux 60 derniers jours
    recent = prices_df.tail(LOOKBACK_DAYS) if len(prices_df) > LOOKBACK_DAYS else prices_df

    accepted: list = []
    # Set initial = positions ouvertes (à comparer contre)
    reference_tickers: set[str] = set(existing_tickers)
    skipped = 0

    for o in candidates:
        ticker = getattr(o, "ticker", None)
        if not ticker:
            continue
        if ticker not in recent.columns:
            # Si ticker absent du prices_df, on l'accepte sans filtre
            accepted.append(o)
            reference_tickers.add(ticker)
            continue

        max_corr = 0.0
        culprit = None
        cand_series = recent[ticker]
        for ref in reference_tickers:
            if ref == ticker:
                continue
            if ref not in recent.columns:
                continue
            corr = _safe_corr(cand_series, recent[ref])
            if corr is None:
                continue
            if abs(corr) > abs(max_corr):
                max_corr = corr
                culprit = ref

        if abs(max_corr) > threshold:
            logger.info(
                f"⏭ {ticker} : corr {max_corr:+.2f} avec {culprit} (> {threshold}) → skip"
            )
            skipped += 1
            continue

        accepted.append(o)
        reference_tickers.add(ticker)

    if skipped:
        logger.info(f"🔗 Corrélation : {skipped} candidats skippés (> {threshold})")

    return accepted
