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

        # ---- Charger l'existant pour dédupliquer + préserver l'historique ----
        existing_open_by_key = {}     # (ticker, action) -> signal existant ouvert
        closed_history = []           # signaux clôturés (tp_hit/sl_hit) à garder
        try:
            if path.exists():
                prev = json.loads(path.read_text(encoding="utf-8"))
                for s in prev.get("signals", []):
                    key = (s.get("ticker"), s.get("action"))
                    if s.get("status") == "open":
                        existing_open_by_key[key] = s
                    else:
                        # Garder les clôturés des 7 derniers jours max
                        closed_history.append(s)
        except Exception as e:
            logger.warning(f"Existant non lisible: {e}")

        # Limiter l'historique clôturé aux 50 plus récents
        closed_history = sorted(
            closed_history,
            key=lambda s: s.get("issued_at", ""),
            reverse=True
        )[:50]

        # ---- Convertir les nouvelles Opportunity + dédupliquer ----
        signals = []
        seen_keys = set()   # dédup au sein du même scan
        for o in opportunities:
            key = (o.ticker, o.action)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            isBuy = o.score > 0
            upside = None
            if o.price and o.take_profit:
                if isBuy:
                    upside = round((o.take_profit - o.price) / o.price * 100, 1)
                else:
                    upside = round((o.price - o.take_profit) / o.price * 100, 1)

            # Fallback Kelly : 1/7-Kelly + score factor pour varier selon conviction
            kelly = o.kelly_position
            if not kelly or kelly <= 0:
                p = o.confidence or 0.5
                b = o.risk_reward or 2.0
                raw = (p * b - (1 - p)) / b if b > 0 else 0
                score_factor = 0.7 + 0.6 * min(abs(o.score or 0), 1.0)   # 0.7–1.3
                kelly = max(0.025, min(0.10, raw * 0.15 * score_factor))

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
                # Préserve issued_at du signal existant pour éviter de "rajeunir" un signal persistent
                "issued_at":        existing_open_by_key.get(key, {}).get("issued_at", now.isoformat()),
                "last_seen":        now.isoformat(),
            }
            signals.append(sig)

        # Préserve les signaux ouverts existants qui n'ont pas été regénérés ce scan
        # (tant qu'ils n'ont pas hit TP/SL, ils restent valides)
        new_keys = {(s["ticker"], s["action"]) for s in signals}
        for key, old_sig in existing_open_by_key.items():
            if key not in new_keys:
                # Marquer last_seen pour savoir depuis quand on ne l'a pas reconfirmé
                old_sig["last_seen"] = old_sig.get("last_seen", now.isoformat())
                signals.append(old_sig)

        # Ajoute les clôturés récents après les ouverts (pour historique visible)
        all_signals = signals + closed_history

        # Tri : ouverts d'abord (STRONG_BUY > BUY > SELL > STRONG_SELL), puis clôturés par date desc
        action_order = {"STRONG_BUY": 0, "BUY": 1, "STRONG_SELL": 2, "SELL": 3}
        all_signals.sort(key=lambda s: (
            0 if s.get("status") == "open" else 1,
            action_order.get(s["action"], 9),
            -abs(s.get("score") or 0),
        ))
        signals = all_signals

        # ---- Stats globales (uniquement signaux ouverts) ----
        open_sigs = [s for s in signals if s.get("status") == "open"]
        n = len(open_sigs)
        n_buy  = sum(1 for s in open_sigs if s["score"] and s["score"] > 0)
        n_sell = n - n_buy
        avg_conf = round(sum(s["confidence"] for s in open_sigs) / n, 3) if n else 0
        rr_vals = [s["risk_reward"] for s in open_sigs if s["risk_reward"]]
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
