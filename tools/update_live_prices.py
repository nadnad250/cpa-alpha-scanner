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
        # AUTO-CLÔTURE : détecte si le prix a franchi TP ou SL
        # ================================================================
        closed_reason = None
        exit_price = None
        if entry and tp and sl:
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

    # Marque la date de génération
    data["generated_at"] = now_iso

    SIGNALS_PATH.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )
    msg = f"✅ {updated} signaux mis à jour avec prix live ({len(latest_prices)}/{len(tickers)} fetchés)"
    if auto_closed:
        msg += f" · 🎯 {auto_closed} AUTO-CLÔTURÉS (TP/SL touchés)"
    log.info(msg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
