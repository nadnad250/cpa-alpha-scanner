"""
Fetcher FRED (Federal Reserve Economic Data) — indicateurs macro pour enrichir le CPA.

Séries utilisées :
- DFF       : Fed Funds Rate (quotidien)
- DGS10     : 10-Year Treasury Yield
- T10Y2Y    : 10Y - 2Y spread (récession si < 0)
- VIXCLS    : VIX index (volatilité attendue SP500)
- DTWEXBGS  : Dollar Index (trade-weighted)
- UNRATE    : Unemployment rate (mensuel)
- CPIAUCSL  : CPI (inflation)

Usage:
    from src.data.fred_fetcher import get_macro_context
    ctx = get_macro_context()
    # ctx['regime'] = 'bullish' | 'neutral' | 'bearish' | 'recession'
    # ctx['risk_free_rate'] = 0.045
    # ctx['vix'] = 15.4
    # ctx['yield_curve'] = 0.42   (10Y - 2Y, négatif = récession)

Requires env var FRED_API_KEY (secret GitHub).
"""
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

import requests

logger = logging.getLogger(__name__)

FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"
CACHE_TTL = timedelta(hours=6)   # refresh 4 fois par jour max

# Cache en mémoire (réinitialisé à chaque exécution du bot)
_cache: dict[str, tuple[datetime, float]] = {}


@dataclass
class MacroContext:
    """Snapshot du contexte macro à un instant T."""
    risk_free_rate: Optional[float] = None      # Fed Funds %
    treasury_10y: Optional[float] = None        # 10Y yield %
    yield_curve: Optional[float] = None         # 10Y - 2Y
    vix: Optional[float] = None                 # Volatility index
    dollar_index: Optional[float] = None        # DXY
    unemployment: Optional[float] = None        # %
    cpi_yoy: Optional[float] = None             # Inflation YoY %
    # Interprétation
    regime: str = "unknown"                     # bullish|neutral|bearish|recession
    regime_score: float = 0.0                   # [-1, +1]
    regime_reasons: list[str] = field(default_factory=list)
    fetched_at: Optional[str] = None


def _fetch_latest(series_id: str, api_key: str) -> Optional[float]:
    """Retourne la dernière valeur numérique pour une série FRED."""
    # Cache check
    now = datetime.utcnow()
    if series_id in _cache:
        ts, val = _cache[series_id]
        if now - ts < CACHE_TTL:
            return val

    params = {
        "series_id":        series_id,
        "api_key":          api_key,
        "file_type":        "json",
        "sort_order":       "desc",
        "limit":            5,   # dernières 5 obs pour skip les "."
    }
    # Retry up to 3 times with exponential backoff on transient errors (5xx, timeout)
    for attempt in range(3):
        try:
            r = requests.get(FRED_BASE, params=params, timeout=10)
            if r.status_code == 200:
                obs = r.json().get("observations", [])
                for o in obs:
                    v = o.get("value")
                    if v and v != ".":
                        try:
                            val = float(v)
                            _cache[series_id] = (now, val)
                            return val
                        except ValueError:
                            continue
                return None
            # 4xx = erreur définitive (clé invalide, série inconnue) — pas de retry
            if 400 <= r.status_code < 500:
                logger.warning(f"FRED {series_id} HTTP {r.status_code} (no retry)")
                return None
            # 5xx = erreur serveur transitoire — retry
            logger.warning(f"FRED {series_id} HTTP {r.status_code} (attempt {attempt + 1}/3)")
        except (requests.Timeout, requests.ConnectionError) as e:
            logger.warning(f"FRED {series_id} network error: {e} (attempt {attempt + 1}/3)")
        except Exception as e:
            logger.warning(f"FRED {series_id} unexpected error: {e}")
            return None
        if attempt < 2:
            time.sleep(2 ** attempt)   # 1s, 2s
    return None


def get_macro_context() -> MacroContext:
    """
    Récupère les indicateurs macro FRED et calcule le régime de marché.
    Retourne un MacroContext vide si FRED_API_KEY absent.
    """
    ctx = MacroContext(fetched_at=datetime.utcnow().isoformat())
    api_key = os.getenv("FRED_API_KEY", "").strip()
    if not api_key:
        logger.debug("FRED_API_KEY non défini — contexte macro vide")
        return ctx

    # Fetch parallèle serait plus rapide, mais ça fait 7 requêtes en série ~1s total
    ctx.risk_free_rate = _fetch_latest("DFF", api_key)
    ctx.treasury_10y   = _fetch_latest("DGS10", api_key)
    ctx.yield_curve    = _fetch_latest("T10Y2Y", api_key)
    ctx.vix            = _fetch_latest("VIXCLS", api_key)
    ctx.dollar_index   = _fetch_latest("DTWEXBGS", api_key)
    ctx.unemployment   = _fetch_latest("UNRATE", api_key)
    # CPI : on calcule le YoY depuis les 13 derniers mois (too complex ici, on skip)

    # ---- Déterminer le régime ----
    reasons = []
    score = 0.0

    # Yield curve (plus gros facteur)
    if ctx.yield_curve is not None:
        if ctx.yield_curve < -0.5:
            score -= 0.4
            reasons.append(f"Yield curve inversée à {ctx.yield_curve}% (signal récession)")
        elif ctx.yield_curve < 0:
            score -= 0.2
            reasons.append(f"Yield curve légèrement inversée ({ctx.yield_curve}%)")
        elif ctx.yield_curve > 1.0:
            score += 0.15
            reasons.append(f"Yield curve saine à +{ctx.yield_curve}%")

    # VIX (volatilité)
    if ctx.vix is not None:
        if ctx.vix > 30:
            score -= 0.3
            reasons.append(f"VIX extrême ({ctx.vix}) — panique")
        elif ctx.vix > 25:
            score -= 0.15
            reasons.append(f"VIX élevé ({ctx.vix}) — risk-off")
        elif ctx.vix < 15:
            score += 0.15
            reasons.append(f"VIX bas ({ctx.vix}) — risk-on")

    # Fed funds (taux directeur)
    if ctx.risk_free_rate is not None:
        if ctx.risk_free_rate > 5.0:
            score -= 0.10
            reasons.append(f"Fed restrictive ({ctx.risk_free_rate}%)")
        elif ctx.risk_free_rate < 2.5:
            score += 0.10
            reasons.append(f"Fed accommodante ({ctx.risk_free_rate}%)")

    # Chômage
    if ctx.unemployment is not None:
        if ctx.unemployment > 5.0:
            score -= 0.10
            reasons.append(f"Chômage en hausse ({ctx.unemployment}%)")
        elif ctx.unemployment < 4.0:
            score += 0.05

    # Clamp score
    ctx.regime_score = max(-1.0, min(1.0, score))
    ctx.regime_reasons = reasons

    if ctx.regime_score <= -0.35:
        ctx.regime = "recession"
    elif ctx.regime_score <= -0.10:
        ctx.regime = "bearish"
    elif ctx.regime_score >= 0.20:
        ctx.regime = "bullish"
    else:
        ctx.regime = "neutral"

    logger.info(
        f"📊 Macro FRED : régime={ctx.regime} (score={ctx.regime_score:+.2f}) "
        f"— VIX {ctx.vix}, Fed {ctx.risk_free_rate}%, "
        f"YC {ctx.yield_curve}"
    )
    return ctx


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    ctx = get_macro_context()
    print(ctx)
