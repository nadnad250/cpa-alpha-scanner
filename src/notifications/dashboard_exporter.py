"""
Dashboard Exporter — convertit les Opportunity en signals.json pour le site web.
Appelé automatiquement par bot_loop après chaque cycle de scan.
"""
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


def export_to_dashboard(
    opportunities: list,
    tracker=None,
    dashboard_path: Optional[str] = None,
) -> bool:
    """
    Exporte les signaux premium vers le fichier signals.json du dashboard web.

    Args:
        opportunities: liste d'objets Opportunity (déjà filtrés premium)
        tracker:       SignalTracker pour récupérer les stats EOD
        dashboard_path: chemin vers le fichier signals.json du dashboard

    Returns:
        True si export réussi, False sinon
    """
    if not dashboard_path:
        # Chemin par défaut relatif au projet math/
        base = Path(__file__).parent.parent.parent.parent
        dashboard_path = str(base / "vitrine  2" / "dashboard" / "data" / "signals.json")

    try:
        path = Path(dashboard_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        now = datetime.utcnow()
        today = now.date().isoformat()

        # ---- Convertir les Opportunity en dict dashboard ----
        signals = []
        for o in opportunities:
            isBuy = o.score > 0
            upside = None
            if o.price and o.take_profit:
                if isBuy:
                    upside = round((o.take_profit - o.price) / o.price * 100, 1)
                else:
                    upside = round((o.price - o.take_profit) / o.price * 100, 1)

            # Fallback Kelly : quart-Kelly basé sur confidence + R/R, clampé [2%, 12%]
            kelly = o.kelly_position
            if not kelly or kelly <= 0:
                p = o.confidence or 0.5
                b = o.risk_reward or 2.0
                raw = (p * b - (1 - p)) / b if b > 0 else 0
                kelly = max(0.02, min(0.12, raw * 0.25))

            sig = {
                "ticker":           o.ticker,
                "action":           o.action,
                "price":            round(o.price, 2) if o.price else None,
                "take_profit":      round(o.take_profit, 2) if o.take_profit else None,
                "stop_loss":        round(o.stop_loss, 2) if o.stop_loss else None,
                "upside_pct":       upside,
                "confidence":       round(o.confidence, 3),
                "score":            round(o.score, 4),
                "risk_reward":      round(o.risk_reward, 2) if o.risk_reward else None,
                "kelly_position":   round(kelly, 3),
                "cpa_alpha":        round(o.cpa_alpha, 4) if o.cpa_alpha else None,
                "ml_proba_up":      round(o.ml_proba_up, 3) if o.ml_proba_up else None,
                "sector":           o.sector or "—",
                "universe":         o.universe or "—",
                "primary_reason":   getattr(o, "primary_reason", "Signal CPA Alpha"),
                "secondary_reasons":getattr(o, "secondary_reasons", []),
                "risk_flags":       getattr(o, "risk_flags", []),
                "intrinsic_value":  round(o.target_price, 2) if getattr(o, "target_price", None) else None,
                "value_gap":        round(getattr(o, "value_gap", 0) or 0, 4),
                "factor_premia":    round(getattr(o, "factor_premia", 0) or 0, 4),
                "mean_reversion":   round(getattr(o, "mean_reversion", 0) or 0, 4),
                "info_flow":        round(getattr(o, "info_flow", 0) or 0, 4),
                "news_score":       round(getattr(o, "news_score", 0) or 0, 2) if getattr(o, "news_score", None) is not None else None,
                "top_news_title":   getattr(o, "top_news_title", None),
                "top_news_url":     getattr(o, "top_news_url", None),
                "status":           "open",
                "issued_at":        now.isoformat(),
            }
            signals.append(sig)

        # Tri : STRONG_BUY > BUY > SELL > STRONG_SELL, puis par score
        action_order = {"STRONG_BUY": 0, "BUY": 1, "STRONG_SELL": 2, "SELL": 3}
        signals.sort(key=lambda s: (action_order.get(s["action"], 9), -abs(s["score"] or 0)))

        # ---- Stats globales ----
        n = len(signals)
        n_buy  = sum(1 for s in signals if s["score"] and s["score"] > 0)
        n_sell = n - n_buy
        avg_conf = round(sum(s["confidence"] for s in signals) / n, 3) if n else 0
        rr_vals = [s["risk_reward"] for s in signals if s["risk_reward"]]
        avg_rr = round(sum(rr_vals) / len(rr_vals), 2) if rr_vals else 0

        # ---- Stats EOD depuis le tracker ----
        tp_hit = sl_hit = open_pos = 0
        win_rate = 0.0
        daily_pnl = 0.0

        if tracker:
            try:
                perf = tracker.performance_stats(lookback_days=1)
                if perf:
                    total_closed = perf.get("total_signals", 0)
                    tp_hit   = perf.get("tp_hit", 0)
                    sl_hit   = perf.get("sl_hit", 0)
                    win_rate = round(perf.get("win_rate", 0), 3)
                    daily_pnl = round(perf.get("avg_pnl", 0) / 100, 4)
                open_sigs = tracker.load_open_signals()
                open_pos  = len(open_sigs)
            except Exception as e:
                logger.warning(f"Stats tracker non disponibles: {e}")

        data = {
            "generated_at": now.isoformat(),
            "date":         today,
            "stats": {
                "total":          n,
                "buy_signals":    n_buy,
                "sell_signals":   n_sell,
                "avg_confidence": avg_conf,
                "avg_rr":         avg_rr,
                "win_rate":       win_rate,
                "active_positions": open_pos,
                "daily_pnl":      daily_pnl,
            },
            "eod": {
                "tp_hit":         tp_hit,
                "sl_hit":         sl_hit,
                "open":           open_pos,
                "cumulative_pnl": daily_pnl,
            },
            "signals": signals,
        }

        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info(f"✅ Dashboard exporté → {path} ({n} signaux)")
        return True

    except Exception as e:
        logger.error(f"❌ Erreur export dashboard: {e}", exc_info=True)
        return False
