"""
Earnings Calendar — blackout des signaux à proximité d'un earnings report.

Les actions dans les ±48h d'un earnings report bougent sur le résultat
(beat/miss/guidance) et pas sur la technique. Le bot évite ces setups
pour ne pas se faire surprendre par un gap overnight de ±10%.

API :
    is_blacked_out("NVDA") -> bool
    days_until_earnings("NVDA") -> Optional[int]

Cache en mémoire + disque (TTL 24h) car les dates earnings changent rarement.
"""
import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

CACHE_PATH = Path(__file__).resolve().parents[2] / "data" / "cache" / "earnings.json"
CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
CACHE_TTL_HOURS = 24

# Blackout window (en jours) : skip si earnings dans ±BLACKOUT_DAYS
# 2 jours = couvre overnight + day-of + lendemain (volatilité post-earnings)
BLACKOUT_DAYS = 2

# Cache en mémoire (rapidité scan)
_memory_cache: dict[str, tuple[datetime, Optional[str]]] = {}


def _load_disk_cache() -> dict:
    """Charge le cache disque. Format : {ticker: {"date": iso, "cached_at": iso}}"""
    if not CACHE_PATH.exists():
        return {}
    try:
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_disk_cache(cache: dict) -> None:
    try:
        CACHE_PATH.write_text(json.dumps(cache, indent=2), encoding="utf-8")
    except Exception as e:
        logger.debug(f"Earnings cache write failed: {e}")


def _is_cache_fresh(cached_at_iso: str) -> bool:
    try:
        cached = datetime.fromisoformat(cached_at_iso.replace("Z", ""))
        return (datetime.utcnow() - cached) < timedelta(hours=CACHE_TTL_HOURS)
    except Exception:
        return False


def _fetch_next_earnings(ticker: str) -> Optional[str]:
    """
    Récupère la prochaine date d'earnings via yfinance.

    Retourne ISO date ("2026-05-22") ou None si indisponible.
    yfinance.Ticker.calendar est une dict avec "Earnings Date" -> list[datetime].
    """
    try:
        import yfinance as yf
        cal = yf.Ticker(ticker).calendar
        if cal is None:
            return None
        # cal peut être dict (nouveau yfinance) ou DataFrame (ancien)
        dates = None
        if isinstance(cal, dict):
            dates = cal.get("Earnings Date")
        else:
            # DataFrame
            try:
                dates = cal.loc["Earnings Date"].tolist()
            except Exception:
                pass
        if not dates:
            return None
        # Prendre la première date future
        now = datetime.utcnow().date()
        for d in dates:
            try:
                if hasattr(d, "date"):
                    d_obj = d.date()
                elif isinstance(d, str):
                    d_obj = datetime.fromisoformat(d).date()
                else:
                    d_obj = d
                if d_obj >= now:
                    return d_obj.isoformat()
            except Exception:
                continue
        return None
    except Exception as e:
        logger.debug(f"yfinance calendar {ticker} failed: {e}")
        return None


def days_until_earnings(ticker: str) -> Optional[int]:
    """Nombre de jours jusqu'au prochain earnings. None si inconnu."""
    ticker = ticker.upper()
    now_dt = datetime.utcnow()

    # 1) cache mémoire
    if ticker in _memory_cache:
        cached_at, date_iso = _memory_cache[ticker]
        if (now_dt - cached_at) < timedelta(hours=CACHE_TTL_HOURS):
            if date_iso is None:
                return None
            return (datetime.fromisoformat(date_iso).date() - now_dt.date()).days

    # 2) cache disque
    disk = _load_disk_cache()
    entry = disk.get(ticker)
    if entry and _is_cache_fresh(entry.get("cached_at", "")):
        date_iso = entry.get("date")
        _memory_cache[ticker] = (now_dt, date_iso)
        if date_iso is None:
            return None
        return (datetime.fromisoformat(date_iso).date() - now_dt.date()).days

    # 3) fetch live
    date_iso = _fetch_next_earnings(ticker)
    _memory_cache[ticker] = (now_dt, date_iso)
    disk[ticker] = {"date": date_iso, "cached_at": now_dt.isoformat()}
    _save_disk_cache(disk)

    if date_iso is None:
        return None
    return (datetime.fromisoformat(date_iso).date() - now_dt.date()).days


def is_blacked_out(ticker: str, window_days: int = BLACKOUT_DAYS) -> bool:
    """
    True si le ticker est dans la fenêtre de blackout earnings.

    Retourne False (= autorisé) si :
    - Earnings inconnu (pas de penalty si data manquante)
    - Earnings > window_days dans le futur
    - Earnings dans le passé (déjà passé, pas de risque)
    """
    days = days_until_earnings(ticker)
    if days is None:
        return False  # No data → ne pas pénaliser
    # Blackout = entre 0 (aujourd'hui) et window_days inclus
    return 0 <= days <= window_days
