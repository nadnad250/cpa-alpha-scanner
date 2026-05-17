"""
Quick live price updater — runs every 15 min during market hours.
Fetches current prices for OPEN signals via yfinance and writes them
directly into dashboard/data/signals.json (no CORS proxy needed).
"""
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import yfinance as yf

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s")
log = logging.getLogger("prices")

SIGNALS_PATH = Path(__file__).parent.parent / "dashboard" / "data" / "signals.json"


def main() -> int:
    if not SIGNALS_PATH.exists():
        log.warning("Pas de signals.json trouvé")
        return 0

    data = json.loads(SIGNALS_PATH.read_text(encoding="utf-8"))
    signals = data.get("signals", [])
    open_sigs = [s for s in signals if s.get("status") == "open"]
    if not open_sigs:
        log.info("Aucun signal ouvert — rien à mettre à jour")
        return 0

    tickers = sorted({s["ticker"] for s in open_sigs})
    log.info(f"📡 Fetch prix live pour {len(tickers)} tickers : {tickers}")

    latest_prices: dict[str, float] = {}
    for t in tickers:
        try:
            hist = yf.Ticker(t).history(period="1d", interval="5m")
            if hist.empty:
                hist = yf.Ticker(t).history(period="5d", interval="1h")
            if hist.empty:
                log.warning(f"  ⚠️ {t} — pas de données")
                continue
            close = hist["Close"].dropna()
            if len(close) == 0:
                continue
            latest_prices[t] = float(close.iloc[-1])
        except Exception as e:
            log.warning(f"  ⚠️ {t} — erreur : {e}")

    if not latest_prices:
        log.error("❌ Aucun prix récupéré")
        return 1

    now_iso = datetime.now(timezone.utc).isoformat()
    updated = 0
    auto_closed = 0
    for sig in signals:
        if sig.get("status") != "open":
            continue
        ticker = sig.get("ticker")
        if ticker not in latest_prices:
            continue

        current = round(latest_prices[ticker], 2)
        entry = sig.get("price")
        tp = sig.get("take_profit")
        sl = sig.get("stop_loss")
        is_buy = (sig.get("score") or 0) > 0

        sig["current_price"] = current
        sig["current_price_time"] = now_iso

        # ================================================================
        # AUTO-CLÔTURE : TP/SL franchi OU horizon 24h dépassé (intraday)
        # ================================================================
        closed_reason = None
        exit_price = None

        # 1) Time-stop intraday : 24h max
        try:
            issued_str = sig.get("issued_at", "").replace("Z", "")
            if issued_str:
                # Gère les ISO avec/sans timezone
                if "+" in issued_str:
                    issued_str = issued_str.split("+")[0]
                issued_dt = datetime.fromisoformat(issued_str)
                hours_open = (datetime.utcnow() - issued_dt).total_seconds() / 3600.0
                if hours_open >= 24:
                    closed_reason = "expired"
                    exit_price = current   # exit au prix courant
        except Exception:
            pass

        # 2) TP/SL franchi (seulement si pas déjà time-stop)
        if not closed_reason and entry and tp and sl:
            if is_buy:
                if current >= tp:
                    closed_reason = "tp_hit"
                    exit_price = tp        # pris au niveau du TP (conservateur)
                elif current <= sl:
                    closed_reason = "sl_hit"
                    exit_price = sl
            else:  # SHORT
                if current <= tp:
                    closed_reason = "tp_hit"
                    exit_price = tp
                elif current >= sl:
                    closed_reason = "sl_hit"
                    exit_price = sl

        if closed_reason:
            sig["status"] = closed_reason
            sig["exit_price"] = exit_price
            sig["exit_date"] = now_iso
            # P&L réalisé au niveau du TP/SL
            if is_buy:
                sig["pnl_pct"] = round(((exit_price - entry) / entry) * 100, 2)
                sig["pnl_pct_live"] = sig["pnl_pct"]
            else:
                sig["pnl_pct"] = round(((entry - exit_price) / entry) * 100, 2)
                sig["pnl_pct_live"] = sig["pnl_pct"]
            auto_closed += 1
            log.info(f"  🎯 {ticker} AUTO-CLOSED: {closed_reason} @ ${exit_price} (P&L {sig['pnl_pct']:+.2f}%)")
            continue  # pas de progression pour un signal clôturé

        # P&L % depuis l'entrée (ouvert)
        if entry and entry > 0:
            if is_buy:
                sig["pnl_pct_live"] = round(((current - entry) / entry) * 100, 2)
            else:
                sig["pnl_pct_live"] = round(((entry - current) / entry) * 100, 2)

        # ─── B3 : TRAILING BREAK-EVEN ──────────────────────────────
        # Quand le prix a parcouru ≥ 50% du chemin vers TP, on remonte
        # le SL au prix d'entrée (verrouille no-loss). Une seule fois.
        if entry and tp and sl and not sig.get("be_locked"):
            try:
                if is_buy:
                    reached = (current - entry) / max(1e-9, tp - entry)
                else:
                    reached = (entry - current) / max(1e-9, entry - tp)
                if reached >= 0.5:
                    sig["stop_loss"] = entry
                    sig["be_locked"] = True
                    log.info(f"  🔒 {ticker} : break-even verrouillé (SL = entry ${entry})")
            except Exception:
                pass

        # Progression vers TP (+100%) ou SL (-100%)
        if entry and tp and sl:
            if is_buy:
                if current >= entry:
                    prog = ((current - entry) / (tp - entry)) * 100
                else:
                    prog = -((entry - current) / (entry - sl)) * 100
            else:
                if current <= entry:
                    prog = ((entry - current) / (entry - tp)) * 100
                else:
                    prog = -((current - entry) / (sl - entry)) * 100
            sig["progression_pct"] = round(max(-120, min(120, prog)), 1)

        updated += 1

    # Bug #1 fix : recalculer les stats après auto-clôture pour cohérence
    # (sinon active_positions reste figé à la valeur écrite par bot_loop)
    open_now = [s for s in signals if s.get("status") == "open"]
    tp_hits  = [s for s in signals if s.get("status") == "tp_hit"]
    sl_hits  = [s for s in signals if s.get("status") == "sl_hit"]
    n_open = len(open_now)
    n_closed_today = len(tp_hits) + len(sl_hits)
    win_rate = round(len(tp_hits) / n_closed_today, 3) if n_closed_today else 0.0

    def _pnl(s):
        v = s.get("pnl_pct")
        return float(v) if isinstance(v, (int, float)) else 0.0
    daily_pnl_pct = sum(_pnl(s) for s in tp_hits + sl_hits)

    # Sécurise dict.stats / dict.eod
    stats = data.setdefault("stats", {})
    eod   = data.setdefault("eod", {})
    stats["active_positions"] = n_open
    stats["total"]            = n_open
    stats["buy_signals"]      = sum(1 for s in open_now if (s.get("score") or 0) > 0)
    stats["sell_signals"]     = sum(1 for s in open_now if (s.get("score") or 0) < 0)
    stats["win_rate"]         = win_rate
    stats["daily_pnl"]        = round(daily_pnl_pct / 100, 4)
    eod["tp_hit"]             = len(tp_hits)
    eod["sl_hit"]             = len(sl_hits)
    eod["open"]               = n_open
    eod["cumulative_pnl"]     = round(daily_pnl_pct / 100, 4)

    # Marque la date de génération
    data["generated_at"] = now_iso

    SIGNALS_PATH.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )
    msg = f"✅ {updated} signaux mis à jour avec prix live ({len(latest_prices)}/{len(tickers)} fetchés)"
    if auto_closed:
        msg += f" · 🎯 {auto_closed} AUTO-CLÔTURÉS (TP/SL touchés)"
    msg += f" · 📊 stats recalc : {n_open} open, {len(tp_hits)} tp, {len(sl_hits)} sl"
    log.info(msg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
