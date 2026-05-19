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


def _get_series(prices, ticker: str) -> pd.Series | None:
    """
    Accesseur uniforme : prices peut être un dict[str, Series] OU un DataFrame.
    Retourne None si ticker absent.
    """
    if prices is None:
        return None
    if isinstance(prices, dict):
        return prices.get(ticker)
    # DataFrame
    if hasattr(prices, "columns") and ticker in prices.columns:
        return prices[ticker]
    return None


def _is_empty(prices) -> bool:
    """True si pas de data exploitable."""
    if prices is None:
        return True
    if isinstance(prices, dict):
        return len(prices) == 0
    if hasattr(prices, "empty"):
        return bool(prices.empty)
    return True


def filter_uncorrelated(
    candidates: Iterable,
    existing_tickers: set[str],
    prices,
    threshold: float = DEFAULT_THRESHOLD,
) -> list:
    """
    Filtre les candidats trop corrélés avec les positions existantes
    OU avec les candidats déjà acceptés (corrélation incrémentale).

    Args:
        candidates : itérable d'Opportunity (déjà filtrés premium, triés par qualité)
        existing_tickers : tickers en position ouverte (de signals.json)
        prices : Dict[str, pd.Series] OU pd.DataFrame (colonnes = tickers)
        threshold : seuil de corrélation max (default 0.85)

    Returns:
        Liste filtrée d'Opportunity, dans l'ordre d'entrée.
    """
    if _is_empty(prices):
        # Pas de data → ne filtre rien (fail-open)
        return list(candidates)

    accepted: list = []
    # Set initial = positions ouvertes (à comparer contre)
    reference_tickers: set[str] = set(existing_tickers)
    skipped = 0

    for o in candidates:
        ticker = getattr(o, "ticker", None)
        if not ticker:
            continue

        cand_series = _get_series(prices, ticker)
        if cand_series is None or len(cand_series) < 20:
            # Pas de prix → on accepte sans filtre (fail-open)
            accepted.append(o)
            reference_tickers.add(ticker)
            continue

        # Restreindre aux N derniers points
        cand_recent = cand_series.tail(LOOKBACK_DAYS)

        max_corr = 0.0
        culprit = None
        for ref in reference_tickers:
            if ref == ticker:
                continue
            ref_series = _get_series(prices, ref)
            if ref_series is None or len(ref_series) < 20:
                continue
            ref_recent = ref_series.tail(LOOKBACK_DAYS)
            corr = _safe_corr(cand_recent, ref_recent)
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
