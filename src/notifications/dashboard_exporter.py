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
        closed_by_key = {}            # (ticker, action, exit_date) -> signal clôturé (DÉDUPLIQUÉ)
        try:
            if path.exists():
                prev = json.loads(path.read_text(encoding="utf-8"))
                for s in prev.get("signals", []):
                    if s.get("status") == "open":
                        key = (s.get("ticker"), s.get("action"))
                        existing_open_by_key[key] = s
                    else:
                        # Dédup strict par (status, ticker, action)
                        # Un ticker+action ne peut avoir qu'UN tp_hit ou UN sl_hit
                        # (évite 4×IBM tp_hit qui s'accumule à chaque scan)
                        ckey = (s.get("status"), s.get("ticker"), s.get("action"))
                        if ckey not in closed_by_key:
                            closed_by_key[ckey] = s
        except Exception as e:
            logger.warning(f"Existant non lisible: {e}")

        # Cap sur l'historique clôturé (évite grossissement infini du JSON)
        try:
            from config.settings import MAX_CLOSED_HISTORY
        except ImportError:
            MAX_CLOSED_HISTORY = 200
        closed_history = sorted(
            closed_by_key.values(),
            key=lambda s: s.get("exit_date") or s.get("issued_at") or "",
            reverse=True,
        )[:MAX_CLOSED_HISTORY]

        # ---- SYNCHRONISATION TRACKER → DASHBOARD ----
        # Charge les signaux ouverts du tracker qui ne seraient pas dans signals.json
        # (garantit que le dashboard reflète fidèlement les positions actives)
        if tracker:
            try:
                tracker_opens = tracker.load_open_signals()
                for ts in tracker_opens:
                    key = (ts.ticker, ts.action)
                    if key in existing_open_by_key:
                        continue  # Déjà dans signals.json
                    # Convertir TrackedSignal → format dashboard
                    isBuyT = (ts.score or 0) > 0
                    upT = None
                    if ts.entry_price and ts.take_profit:
                        if isBuyT:
                            upT = round((ts.take_profit - ts.entry_price) / ts.entry_price * 100, 1)
                        else:
                            upT = round((ts.entry_price - ts.take_profit) / ts.entry_price * 100, 1)
                    rrT = None
                    if ts.entry_price and ts.take_profit and ts.stop_loss:
                        reward = abs(ts.take_profit - ts.entry_price)
                        risk = abs(ts.entry_price - ts.stop_loss)
                        rrT = round(reward / risk, 2) if risk > 0 else None
                    pT = ts.confidence or 0.5
                    bT = rrT or 2.0
                    rawT = (pT * bT - (1 - pT)) / bT if bT > 0 else 0
                    sfT = 0.7 + 0.6 * min(abs(ts.score or 0), 1.0)
                    kellyT = max(0.025, min(0.10, rawT * 0.15 * sfT))
                    existing_open_by_key[key] = {
                        "ticker":         ts.ticker,
                        "action":         ts.action,
                        "price":          round(ts.entry_price, 2) if ts.entry_price else None,
                        "take_profit":    round(ts.take_profit, 2) if ts.take_profit else None,
                        "stop_loss":      round(ts.stop_loss, 2) if ts.stop_loss else None,
                        "upside_pct":     upT,
                        "confidence":     round(ts.confidence, 3),
                        "score":          round(ts.score, 4),
                        "risk_reward":    rrT,
                        "kelly_position": round(kellyT, 3),
                        "cpa_alpha":      None,
                        "ml_proba_up":    None,
                        "sector":         "—",
                        "universe":       ts.universe or "—",
                        "primary_reason": "Signal CPA Alpha (actif)",
                        "secondary_reasons": [],
                        "risk_flags":     [],
                        "intrinsic_value": None,
                        "value_gap":      0, "factor_premia": 0, "mean_reversion": 0, "info_flow": 0,
                        "news_score":     None, "top_news_title": None, "top_news_url": None,
                        "status":         "open",
                        "issued_at":      ts.issued_at,
                    }
                logger.info(f"🔗 {len(tracker_opens)} signaux chargés depuis le tracker")
            except Exception as e:
                logger.warning(f"Sync tracker → dashboard échoué: {e}")

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
                "value_gap":        round(o.value_gap, 4) if getattr(o, "value_gap", None) is not None else None,
                "factor_premia":    round(o.factor_premia, 4) if getattr(o, "factor_premia", None) is not None else None,
                "mean_reversion":   round(o.mean_reversion, 4) if getattr(o, "mean_reversion", None) is not None else None,
                "info_flow":        round(o.info_flow, 4) if getattr(o, "info_flow", None) is not None else None,
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

        # ================================================================
        # AUTO-CLÔTURE : vérifie si current_price a franchi TP ou SL
        # Partagé avec update_live_prices.py pour garantir la cohérence.
        # ================================================================
        auto_closed_count = 0
        for sig in signals:
            if sig.get("status") != "open":
                continue
            entry = sig.get("price")
            tp = sig.get("take_profit")
            sl = sig.get("stop_loss")
            current = sig.get("current_price")
            if not all([entry, tp, sl, current]):
                continue
            is_buy = (sig.get("score") or 0) > 0
            exit_px = None; reason = None
            if is_buy:
                if current >= tp:
                    exit_px, reason = tp, "tp_hit"
                elif current <= sl:
                    exit_px, reason = sl, "sl_hit"
            else:  # SHORT
                if current <= tp:
                    exit_px, reason = tp, "tp_hit"
                elif current >= sl:
                    exit_px, reason = sl, "sl_hit"
            if reason:
                sig["status"] = reason
                sig["exit_price"] = exit_px
                sig["exit_date"] = now.isoformat()
                if is_buy:
                    sig["pnl_pct"] = round(((exit_px - entry) / entry) * 100, 2)
                else:
                    sig["pnl_pct"] = round(((entry - exit_px) / entry) * 100, 2)
                sig["pnl_pct_live"] = sig["pnl_pct"]
                auto_closed_count += 1
                logger.info(f"  🎯 {sig['ticker']} AUTO-CLOSED (exporter): {reason} @ ${exit_px} P&L {sig['pnl_pct']:+.2f}%")

        if auto_closed_count:
            logger.info(f"✅ {auto_closed_count} signaux auto-clôturés par l'exporter")

        # ================================================================
        # LOGIQUE DE SLOTS : MAX_OPEN_SIGNALS positions simultanées
        # Règle absolue : les signaux EXISTANTS (déjà dans signals.json)
        # restent jusqu'à TP/SL — jamais éjectés par un new "mieux noté".
        # Seuls les slots libérés par clôtures accueillent de nouveaux signaux,
        # sélectionnés par |score| × confidence décroissant.
        # ================================================================
        try:
            from config.settings import MAX_OPEN_SIGNALS
        except ImportError:
            MAX_OPEN_SIGNALS = 10

        open_sigs = [s for s in signals if s.get("status") == "open"]
        other_sigs = [s for s in signals if s.get("status") != "open"]

        # Identifier existants vs nouveaux
        # (existant = était dans signals.json précédent comme status='open')
        prev_open_keys = {
            (k[0], k[1])  # (ticker, action)
            for k, s in existing_open_by_key.items()
            if s.get("status") == "open"
        }
        existing_still_open = [
            s for s in open_sigs
            if (s.get("ticker"), s.get("action")) in prev_open_keys
        ]
        new_arrivals = [
            s for s in open_sigs
            if (s.get("ticker"), s.get("action")) not in prev_open_keys
        ]

        # Safeguard : si jamais on dépasse MAX (cas edge), tronquer par qualité
        if len(existing_still_open) > MAX_OPEN_SIGNALS:
            existing_still_open.sort(
                key=lambda s: abs(s.get("score") or 0) * (s.get("confidence") or 0),
                reverse=True,
            )
            existing_still_open = existing_still_open[:MAX_OPEN_SIGNALS]

        # Slots restants pour de nouveaux signaux
        slots_left = MAX_OPEN_SIGNALS - len(existing_still_open)

        if slots_left > 0 and new_arrivals:
            # Tri des new par qualité décroissante
            new_arrivals.sort(
                key=lambda s: abs(s.get("score") or 0) * (s.get("confidence") or 0),
                reverse=True,
            )
            accepted_new = new_arrivals[:slots_left]
            rejected_new = new_arrivals[slots_left:]
            logger.info(
                f"🎯 SLOTS : {len(existing_still_open)} existants gardés, "
                f"{len(accepted_new)}/{len(new_arrivals)} nouveaux acceptés "
                f"(slots libres: {slots_left})"
            )
            if rejected_new:
                logger.info(
                    f"   💤 {len(rejected_new)} nouveaux rejetés (déjà 10 slots): "
                    f"{[s['ticker'] for s in rejected_new[:10]]}"
                )
            open_sigs = existing_still_open + accepted_new
        else:
            # Aucun slot libre : on garde uniquement les existants
            if new_arrivals:
                logger.info(
                    f"💤 0 slot libre — {len(new_arrivals)} nouveaux signaux ignorés "
                    f"(attendez qu'un TP/SL libère une place)"
                )
            open_sigs = existing_still_open

        signals = open_sigs + other_sigs

        # Ajoute les clôturés récents après les ouverts (pour historique visible)
        # Dédup par clé stable (status, ticker, action) — plus correct et O(1) au lieu de O(n²)
        existing_keys = {(s.get("status"), s.get("ticker"), s.get("action")) for s in signals}
        all_signals = signals + [
            s for s in closed_history
            if (s.get("status"), s.get("ticker"), s.get("action")) not in existing_keys
        ]

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

        # ================================================================
        # STATS EOD : calcul direct depuis les signaux clôturés dans signals
        # (évite dépendance au tracker dont les clés diffèrent :
        #  tracker.performance_stats() → total/wins/losses/win_rate/expectancy
        #  alors qu'on lisait total_signals/tp_hit/sl_hit/avg_pnl = None)
        # ================================================================
        closed_sigs = [s for s in signals if s.get("status") in ("tp_hit", "sl_hit")]
        tp_hit = sum(1 for s in closed_sigs if s.get("status") == "tp_hit")
        sl_hit = sum(1 for s in closed_sigs if s.get("status") == "sl_hit")
        n_closed = tp_hit + sl_hit
        win_rate = round(tp_hit / n_closed, 3) if n_closed > 0 else 0.0

        # P&L cumulé : somme des pnl_pct réalisés (privilégie pnl_pct, fallback upside_pct signé)
        def _real_pnl(s):
            if isinstance(s.get("pnl_pct"), (int, float)):
                return float(s["pnl_pct"])
            up = abs(float(s.get("upside_pct") or 0))
            return up if s.get("status") == "tp_hit" else -up
        total_pnl_pct = sum(_real_pnl(s) for s in closed_sigs)
        daily_pnl = round(total_pnl_pct / 100, 4)   # en fraction pour compat

        # Force cohérence : active_positions = nb de signaux ouverts affichés
        open_pos = n

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
