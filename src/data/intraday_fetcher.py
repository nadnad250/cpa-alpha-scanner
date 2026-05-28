"""
Intraday Fetcher — bougies OHLCV 5 minutes via yfinance.

Pour la stratégie Opening Range Breakout (ORB) "Stocks in Play" :
- Récupère les bougies 5m de la session courante (+ historique pour baseline volume)
- Calcule le Relative Volume (RVOL) = volume cumulé du jour / moyenne 14j
- Fournit les données OHLCV intraday au moteur de signal

Contraintes yfinance :
- interval="5m"  → max ~60 jours d'historique
- interval="1m"  → max ~7 jours
On utilise 5m (bon compromis edge/latence/historique).

Cache disque TTL court (10 min) car les données bougent en intraday.
"""
import hashlib
import logging
import os
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)

CACHE_DIR = "data/cache/intraday"
CACHE_TTL_MIN = 10          # bougies 5m → refresh toutes les 10 min
HISTORY_DAYS = 20           # 20j de 5m pour baseline RVOL (≈ 14 sessions)


def _cache_path(key: str) -> str:
    os.makedirs(CACHE_DIR, exist_ok=True)
    h = hashlib.md5(key.encode()).hexdigest()[:12]
    return os.path.join(CACHE_DIR, f"{h}.pkl")


def _cache_valid(path: str) -> bool:
    if not os.path.exists(path):
        return False
    age = datetime.now() - datetime.fromtimestamp(os.path.getmtime(path))
    return age < timedelta(minutes=CACHE_TTL_MIN)


def fetch_intraday_5m(
    tickers: List[str],
    period_days: int = HISTORY_DAYS,
) -> Dict[str, pd.DataFrame]:
    """
    Retourne {ticker: DataFrame OHLCV 5m} sur les `period_days` derniers jours.

    DataFrame colonnes : Open, High, Low, Close, Volume
    Index : timestamps (timezone US/Eastern via yfinance).
    """
    import yfinance as yf

    out: Dict[str, pd.DataFrame] = {}
    cache_key = f"intraday5m_{'-'.join(sorted(tickers)[:8])}_{period_days}_{len(tickers)}"
    path = _cache_path(cache_key)
    if _cache_valid(path):
        try:
            return pd.read_pickle(path)
        except Exception:
            pass

    period = f"{period_days}d"
    # yfinance download multi-ticker en une fois (plus rapide, moins de rate-limit)
    try:
        raw = yf.download(
            tickers,
            period=period,
            interval="5m",
            auto_adjust=True,
            progress=False,
            threads=True,
            group_by="ticker",
        )
    except Exception as e:
        logger.error(f"Intraday download error: {e}")
        return out

    if raw is None or len(raw) == 0:
        return out

    for t in tickers:
        try:
            if len(tickers) == 1:
                df = raw.copy()
            else:
                if t not in raw.columns.get_level_values(0):
                    continue
                df = raw[t].copy()
            df = df.dropna(how="all")
            # Garde les colonnes standard
            cols = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in df.columns]
            if len(cols) < 5:
                continue
            df = df[cols].dropna()
            if len(df) < 20:
                continue
            out[t] = df
        except Exception as e:
            logger.debug(f"Intraday parse {t}: {e}")

    logger.info(f"[IntradayFetcher] 5m OHLCV : {len(out)}/{len(tickers)} tickers")
    try:
        pd.to_pickle(out, path)
    except Exception:
        pass
    return out


def session_date(df: pd.DataFrame) -> Optional[pd.Timestamp]:
    """Date de la dernière session présente dans le DataFrame."""
    if df is None or len(df) == 0:
        return None
    try:
        return df.index[-1].normalize()
    except Exception:
        return None


def split_by_session(df: pd.DataFrame) -> Dict[pd.Timestamp, pd.DataFrame]:
    """Découpe un DataFrame 5m par jour de bourse."""
    sessions: Dict[pd.Timestamp, pd.DataFrame] = {}
    if df is None or len(df) == 0:
        return sessions
    try:
        for day, group in df.groupby(df.index.normalize()):
            sessions[day] = group
    except Exception:
        pass
    return sessions
