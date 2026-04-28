"""
Dédup Telegram — empêche d'envoyer plusieurs fois le même signal.

Logique :
- Chaque signal envoyé est tracé dans `data/telegram_state.json` avec
  une clé `(ticker, action)` → timestamp ISO UTC.
- Avant d'envoyer un signal, on vérifie :
    1) Le ticker n'a-t-il PAS été envoyé dans les TELEGRAM_DEDUP_HOURS dernières heures ?
    2) Le ticker n'est-il pas déjà en position ouverte (signal_tracker) ?
- Si oui aux deux → on envoie + on enregistre.
- Sinon → on skip.

Le state est persisté dans le repo via le workflow GitHub Actions.
"""
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable

logger = logging.getLogger(__name__)

STATE_PATH = Path(__file__).resolve().parents[2] / "data" / "telegram_state.json"


def _load_state() -> dict:
    if not STATE_PATH.exists():
        return {}
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning(f"telegram_state corrompu, reset : {e}")
        return {}


def _save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _key(ticker: str, action: str) -> str:
    """Clé canonique : SMCI:STRONG_BUY, AAPL:SELL …"""
    return f"{ticker.upper()}:{action.upper()}"


def filter_new_signals(
    opportunities: Iterable,
    open_tickers: set[str],
    cooldown_hours: int = 24,
) -> list:
    """
    Retourne uniquement les signaux qui :
    1) Ne sont pas déjà ouverts (open_tickers = ce qu'a le tracker)
    2) N'ont pas été envoyés sur Telegram récemment (cooldown_hours)

    Met à jour atomiquement le state pour les signaux retenus.
    """
    state = _load_state()
    now = datetime.utcnow()
    cutoff = now - timedelta(hours=cooldown_hours)

    # Purge des entrées trop vieilles (économise du JSON)
    purge_cutoff = now - timedelta(hours=cooldown_hours * 4)
    state = {
        k: v for k, v in state.items()
        if _try_parse(v) and _try_parse(v) > purge_cutoff
    }

    fresh = []
    for o in opportunities:
        if not getattr(o, "ticker", None) or not getattr(o, "action", None):
            continue
        ticker = o.ticker.upper()
        if ticker in open_tickers:
            logger.info(f"⏭ skip {ticker} : position déjà ouverte")
            continue
        key = _key(o.ticker, o.action)
        last_str = state.get(key)
        last = _try_parse(last_str) if last_str else None
        if last and last > cutoff:
            logger.info(f"⏭ skip {key} : envoyé il y a {(now-last).total_seconds()/3600:.1f}h")
            continue
        # Retenu !
        state[key] = now.isoformat()
        fresh.append(o)

    _save_state(state)
    return fresh


def _try_parse(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "").split("+")[0])
    except Exception:
        return None


def get_open_tickers_from_signals_json(path: Path) -> set[str]:
    """
    Extrait les tickers en position ouverte depuis dashboard/data/signals.json.
    Plus rapide et fiable que de re-charger le tracker.
    """
    if not path.exists():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        sigs = data.get("signals", []) or []
        return {
            s.get("ticker", "").upper()
            for s in sigs
            if s.get("status") == "open"
        }
    except Exception as e:
        logger.warning(f"Impossible de lire {path} : {e}")
        return set()
