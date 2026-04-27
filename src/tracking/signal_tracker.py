"""
Signal Tracker — persistance et évaluation des signaux émis.

Stocke chaque signal dans data/signals/YYYY-MM-DD.json avec :
- ticker, action, prix d'entrée, SL, TP, score, horizon
- statut : open / tp_hit / sl_hit / expired
- PnL réalisé quand clôturé

Calcule :
- Win rate (% trades gagnants)
- Profit factor (gain moyen / perte moyenne)
- Ratio risk/reward moyen
- Expectancy par trade
"""
import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional

import pandas as pd

logger = logging.getLogger(__name__)

SIGNALS_DIR = Path(__file__).resolve().parents[2] / "data" / "signals"
SIGNALS_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class TrackedSignal:
    ticker: str
    action: str
    entry_price: float
    stop_loss: float
    take_profit: float
    score: float
    confidence: float
    universe: str
    issued_at: str          # ISO datetime
    # Intraday : horizon en heures (24h max), legacy field kept for backward compat
    horizon_days: int = 1
    horizon_hours: int = 24
    status: str = "open"    # open / tp_hit / sl_hit / expired / closed
    exit_price: Optional[float] = None
    exit_date: Optional[str] = None
    pnl_pct: Optional[float] = None
    max_favorable: Optional[float] = None  # meilleur gain atteint
    max_adverse: Optional[float] = None    # pire perte atteinte


class SignalTracker:
    def __init__(self, signals_dir: Path = SIGNALS_DIR):
        self.dir = signals_dir
        self.dir.mkdir(parents=True, exist_ok=True)

    def _file_for(self, date: str) -> Path:
        return self.dir / f"{date}.json"

    def save_batch(self, signals: List[TrackedSignal], date: Optional[str] = None):
        """Enregistre un lot de signaux du jour."""
        date = date or datetime.utcnow().strftime("%Y-%m-%d")
        path = self._file_for(date)
        existing = []
        if path.exists():
            existing = json.loads(path.read_text(encoding="utf-8"))
        existing.extend([asdict(s) for s in signals])
        path.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info(f"[Tracker] {len(signals)} signaux enregistrés → {path.name}")

    def load_open_signals(self, lookback_days: int = 30) -> List[TrackedSignal]:
        """Charge tous les signaux encore ouverts."""
        open_signals = []
        cutoff = datetime.utcnow() - timedelta(days=lookback_days)
        for f in sorted(self.dir.glob("*.json")):
            try:
                date_str = f.stem
                d = datetime.strptime(date_str, "%Y-%m-%d")
                if d < cutoff:
                    continue
                data = json.loads(f.read_text(encoding="utf-8"))
                for item in data:
                    sig = TrackedSignal(**item)
                    if sig.status == "open":
                        open_signals.append(sig)
            except Exception as e:
                logger.warning(f"Skip {f.name}: {e}")
        return open_signals

    def load_all_closed(self, lookback_days: int = 90) -> List[TrackedSignal]:
        """Charge tous les signaux clôturés (pour stats)."""
        closed = []
        cutoff = datetime.utcnow() - timedelta(days=lookback_days)
        for f in sorted(self.dir.glob("*.json")):
            try:
                date_str = f.stem
                d = datetime.strptime(date_str, "%Y-%m-%d")
                if d < cutoff:
                    continue
                data = json.loads(f.read_text(encoding="utf-8"))
                for item in data:
                    sig = TrackedSignal(**item)
                    if sig.status != "open":
                        closed.append(sig)
            except Exception as e:
                logger.warning(f"Skip {f.name}: {e}")
        return closed

    def update_signal(self, sig: TrackedSignal, date: str):
        """Ré-écrit un signal mis à jour dans son fichier."""
        path = self._file_for(date)
        if not path.exists():
            return
        data = json.loads(path.read_text(encoding="utf-8"))
        for i, item in enumerate(data):
            if item["ticker"] == sig.ticker and item["issued_at"] == sig.issued_at:
                data[i] = asdict(sig)
                break
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def evaluate_signals(self, prices_getter) -> Dict:
        """
        Évalue tous les signaux ouverts vs prix actuels.
        prices_getter : callable(ticker) -> pd.Series des prix depuis issued_at.

        Met à jour le statut : tp_hit, sl_hit, ou expired après horizon.
        Retourne des stats agrégées.
        """
        open_sigs = self.load_open_signals(lookback_days=60)
        updated = 0

        for sig in open_sigs:
            try:
                # Intraday : on raisonne en heures, plus en jours
                issued_dt = datetime.fromisoformat(sig.issued_at.replace("Z", "+00:00").replace("+00:00", ""))
                hours_elapsed = (datetime.utcnow() - issued_dt).total_seconds() / 3600.0
                issued_date = issued_dt.date()

                prices = prices_getter(sig.ticker)
                if prices is None or len(prices) == 0:
                    continue

                prices_since = prices[prices.index.date >= issued_date] if hasattr(prices.index, "date") else prices
                if len(prices_since) == 0:
                    continue

                is_buy = sig.action in ("BUY", "STRONG_BUY")
                high = float(prices_since.max())
                low = float(prices_since.min())
                last = float(prices_since.iloc[-1])

                if is_buy:
                    sig.max_favorable = (high - sig.entry_price) / sig.entry_price
                    sig.max_adverse = (low - sig.entry_price) / sig.entry_price
                else:
                    sig.max_favorable = (sig.entry_price - low) / sig.entry_price
                    sig.max_adverse = (sig.entry_price - high) / sig.entry_price

                # Check TP / SL
                closed = False
                if is_buy:
                    if high >= sig.take_profit:
                        sig.status = "tp_hit"
                        sig.exit_price = sig.take_profit
                        sig.pnl_pct = (sig.take_profit - sig.entry_price) / sig.entry_price
                        closed = True
                    elif low <= sig.stop_loss:
                        sig.status = "sl_hit"
                        sig.exit_price = sig.stop_loss
                        sig.pnl_pct = (sig.stop_loss - sig.entry_price) / sig.entry_price
                        closed = True
                else:
                    if low <= sig.take_profit:
                        sig.status = "tp_hit"
                        sig.exit_price = sig.take_profit
                        sig.pnl_pct = (sig.entry_price - sig.take_profit) / sig.entry_price
                        closed = True
                    elif high >= sig.stop_loss:
                        sig.status = "sl_hit"
                        sig.exit_price = sig.stop_loss
                        sig.pnl_pct = (sig.entry_price - sig.stop_loss) / sig.entry_price
                        closed = True

                # Expiration intraday : 24h max
                horizon_h = getattr(sig, "horizon_hours", 24) or 24
                if not closed and hours_elapsed >= horizon_h:
                    sig.status = "expired"
                    sig.exit_price = last
                    if is_buy:
                        sig.pnl_pct = (last - sig.entry_price) / sig.entry_price
                    else:
                        sig.pnl_pct = (sig.entry_price - last) / sig.entry_price
                    closed = True

                if closed:
                    sig.exit_date = datetime.utcnow().date().isoformat()

                self.update_signal(sig, sig.issued_at[:10])
                updated += 1
            except Exception as e:
                logger.debug(f"Eval {sig.ticker}: {e}")

        logger.info(f"[Tracker] {updated} signaux évalués")
        return self.performance_stats()

    def performance_stats(self, lookback_days: int = 90) -> Dict:
        """Calcule win rate, profit factor, expectancy."""
        closed = self.load_all_closed(lookback_days)
        if not closed:
            return {
                "total": 0,
                "wins": 0,
                "losses": 0,
                "win_rate": 0.0,
                "avg_win": 0.0,
                "avg_loss": 0.0,
                "profit_factor": 0.0,
                "expectancy": 0.0,
                "by_action": {},
            }

        wins = [s for s in closed if s.pnl_pct and s.pnl_pct > 0]
        losses = [s for s in closed if s.pnl_pct and s.pnl_pct <= 0]

        avg_win = sum(s.pnl_pct for s in wins) / len(wins) if wins else 0
        avg_loss = sum(s.pnl_pct for s in losses) / len(losses) if losses else 0
        total_win = sum(s.pnl_pct for s in wins)
        total_loss = abs(sum(s.pnl_pct for s in losses))
        pf = total_win / total_loss if total_loss > 0 else float("inf")
        win_rate = len(wins) / len(closed) if closed else 0
        expectancy = win_rate * avg_win + (1 - win_rate) * avg_loss

        # Par action
        by_action = {}
        for act in ("STRONG_BUY", "BUY", "SELL", "STRONG_SELL"):
            subset = [s for s in closed if s.action == act]
            if subset:
                w = [s for s in subset if s.pnl_pct and s.pnl_pct > 0]
                by_action[act] = {
                    "count": len(subset),
                    "win_rate": len(w) / len(subset),
                    "avg_pnl": sum(s.pnl_pct or 0 for s in subset) / len(subset),
                }

        return {
            "total": len(closed),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": win_rate,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "profit_factor": pf,
            "expectancy": expectancy,
            "by_action": by_action,
        }
