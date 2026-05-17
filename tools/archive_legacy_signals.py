"""
Archive les signaux legacy non-NASDAQ ou trop vieux pour repartir sur base propre.

Critères d'archivage :
- universe != "NASDAQ100"  (CAC40, SP500, EuroStoxx, futures, crypto…)
- OR issued_at antérieur à PRUNE_BEFORE

Output :
- Conservation des entrées NASDAQ récentes dans dashboard/data/signals.json
- Tout le reste copié dans data/archive/legacy_signals_<date>.json
"""
import io
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Force UTF-8 stdout (sinon Windows cp1252 plante sur les emoji)
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = Path(__file__).parent.parent
SIGNALS = ROOT / "dashboard" / "data" / "signals.json"
ARCHIVE_DIR = ROOT / "data" / "archive"
ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

# On garde uniquement les signaux NASDAQ100 et < 7 jours
PRUNE_BEFORE = datetime.utcnow() - timedelta(days=7)


def main() -> int:
    if not SIGNALS.exists():
        print(f"❌ {SIGNALS} introuvable")
        return 1

    data = json.loads(SIGNALS.read_text(encoding="utf-8"))
    sigs = data.get("signals", []) or []

    keep, drop = [], []
    for s in sigs:
        univ = (s.get("universe") or "").upper()
        issued = (s.get("issued_at") or "").replace("Z", "").split("+")[0]
        try:
            dt = datetime.fromisoformat(issued) if issued else None
        except Exception:
            dt = None

        is_nasdaq = univ in ("NASDAQ100", "NASDAQ", "NDX")
        is_recent = dt is None or dt >= PRUNE_BEFORE
        if is_nasdaq and is_recent:
            keep.append(s)
        else:
            drop.append(s)

    print(f"📊 Total: {len(sigs)} | Keep: {len(keep)} | Archive: {len(drop)}")

    if drop:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        archive_path = ARCHIVE_DIR / f"legacy_signals_{ts}.json"
        archive_path.write_text(
            json.dumps({"archived_at": ts, "signals": drop}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"📦 Archivé → {archive_path.relative_to(ROOT)}")

    # Recalcule les stats post-purge
    open_now = [s for s in keep if s.get("status") == "open"]
    tp = sum(1 for s in keep if s.get("status") == "tp_hit")
    sl = sum(1 for s in keep if s.get("status") == "sl_hit")
    n_closed = tp + sl
    win_rate = round(tp / n_closed, 3) if n_closed else 0.0

    data["signals"] = keep
    data["stats"] = data.get("stats", {})
    data["stats"]["total"] = len(open_now)
    data["stats"]["active_positions"] = len(open_now)
    data["stats"]["buy_signals"] = sum(1 for s in open_now if (s.get("score") or 0) > 0)
    data["stats"]["sell_signals"] = sum(1 for s in open_now if (s.get("score") or 0) < 0)
    data["stats"]["win_rate"] = win_rate
    data["eod"] = {"tp_hit": tp, "sl_hit": sl, "open": len(open_now), "cumulative_pnl": 0.0}
    data["generated_at"] = datetime.now(timezone.utc).isoformat()

    SIGNALS.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"✅ {SIGNALS.relative_to(ROOT)} : {len(open_now)} open, {tp} TP, {sl} SL")
    return 0


if __name__ == "__main__":
    sys.exit(main())
