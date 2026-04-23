"""
Analyseur de performance du bot CPA Alpha Scanner.
Produit un rapport JSON structuré pour alimenter les décisions de tuning.

Usage:
    python .claude/skills/cpa-bot-optimizer/scripts/analyze_performance.py

Produit : rapport JSON sur stdout + écrit dans
          .claude/skills/cpa-bot-optimizer/last_analysis.json
"""
import json
import logging
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger()

ROOT = Path(__file__).parent.parent.parent.parent.parent
SIGNALS_JSON = ROOT / "dashboard" / "data" / "signals.json"
TRACKER_DIR = ROOT / "data" / "signals"
OUTPUT = Path(__file__).parent.parent / "last_analysis.json"


def load_all_signals() -> list[dict]:
    """Consolide signals.json + tous les fichiers data/signals/*.json."""
    all_sigs: list[dict] = []

    # Source 1 : dashboard/data/signals.json (état courant du dashboard)
    if SIGNALS_JSON.exists():
        try:
            data = json.loads(SIGNALS_JSON.read_text(encoding="utf-8"))
            all_sigs.extend(data.get("signals", []))
        except Exception as e:
            log.warning(f"signals.json illisible: {e}")

    # Source 2 : data/signals/*.json (historique quotidien complet du tracker)
    if TRACKER_DIR.exists():
        for jf in sorted(TRACKER_DIR.glob("*.json")):
            try:
                daily = json.loads(jf.read_text(encoding="utf-8"))
                # Le tracker renvoie directement une liste
                if isinstance(daily, list):
                    for s in daily:
                        s["_from_tracker"] = True
                        s["_file"] = jf.name
                    all_sigs.extend(daily)
            except Exception as e:
                log.warning(f"{jf.name} illisible: {e}")

    # Dédup par (ticker, action, issued_at)
    seen: set[tuple] = set()
    unique: list[dict] = []
    for s in all_sigs:
        key = (s.get("ticker"), s.get("action"), s.get("issued_at"))
        if key in seen:
            continue
        seen.add(key)
        unique.append(s)

    return unique


def compute_metrics(signals: list[dict]) -> dict[str, Any]:
    closed = [s for s in signals if s.get("status") in ("tp_hit", "sl_hit")]
    open_ = [s for s in signals if s.get("status") == "open"]

    if not closed:
        return {
            "total_signals": len(signals),
            "open": len(open_),
            "closed": 0,
            "message": "Pas encore assez de trades clôturés pour analyser. Attendre 10+ clôtures.",
        }

    wins = [s for s in closed if s.get("status") == "tp_hit"]
    losses = [s for s in closed if s.get("status") == "sl_hit"]

    def pnl(s: dict) -> float:
        up = abs(s.get("upside_pct") or 0)
        return up if s.get("status") == "tp_hit" else -up

    pnls = [pnl(s) for s in closed]
    win_rate = len(wins) / len(closed) if closed else 0
    total_pnl = sum(pnls)
    expectancy = total_pnl / len(pnls) if pnls else 0
    gain_sum = sum(pnl(s) for s in wins)
    loss_sum = abs(sum(pnl(s) for s in losses))
    profit_factor = gain_sum / loss_sum if loss_sum > 0 else float("inf") if gain_sum > 0 else 0

    # Distribution
    pnls_sorted = sorted(pnls)

    # Par action type
    by_action = defaultdict(list)
    for s in closed:
        by_action[s.get("action", "UNKNOWN")].append(s)
    action_stats = {
        a: {
            "n": len(v),
            "win_rate": round(sum(1 for s in v if s.get("status") == "tp_hit") / len(v), 3),
            "avg_pnl": round(sum(pnl(s) for s in v) / len(v), 2),
        }
        for a, v in by_action.items()
    }

    # Par univers
    by_universe = defaultdict(list)
    for s in closed:
        by_universe[s.get("universe", "?")].append(s)
    universe_stats = {
        u: {
            "n": len(v),
            "win_rate": round(sum(1 for s in v if s.get("status") == "tp_hit") / len(v), 3),
            "avg_pnl": round(sum(pnl(s) for s in v) / len(v), 2),
        }
        for u, v in by_universe.items()
    }

    # Par secteur
    by_sector = defaultdict(list)
    for s in closed:
        sec = s.get("sector") or "—"
        by_sector[sec].append(s)
    sector_stats = {
        s: {
            "n": len(v),
            "win_rate": round(sum(1 for s in v if s.get("status") == "tp_hit") / len(v), 3),
            "avg_pnl": round(sum(pnl(s) for s in v) / len(v), 2),
        }
        for s, v in by_sector.items() if len(v) >= 3
    }

    # Comparaison winners vs losers
    def avg(lst: list[float]) -> float:
        return round(sum(lst) / len(lst), 3) if lst else 0

    winner_confs = [s.get("confidence") or 0 for s in wins]
    loser_confs  = [s.get("confidence") or 0 for s in losses]
    winner_scores = [abs(s.get("score") or 0) for s in wins]
    loser_scores  = [abs(s.get("score") or 0) for s in losses]
    winner_rr = [s.get("risk_reward") or 0 for s in wins]
    loser_rr  = [s.get("risk_reward") or 0 for s in losses]

    comparison = {
        "avg_confidence_winners": avg(winner_confs),
        "avg_confidence_losers":  avg(loser_confs),
        "avg_score_winners":      avg(winner_scores),
        "avg_score_losers":       avg(loser_scores),
        "avg_rr_winners":         avg(winner_rr),
        "avg_rr_losers":          avg(loser_rr),
    }

    # Buckets de confiance
    conf_buckets = {
        "0.65-0.70": [s for s in closed if 0.65 <= (s.get("confidence") or 0) < 0.70],
        "0.70-0.75": [s for s in closed if 0.70 <= (s.get("confidence") or 0) < 0.75],
        "0.75-0.80": [s for s in closed if 0.75 <= (s.get("confidence") or 0) < 0.80],
        "0.80+":     [s for s in closed if (s.get("confidence") or 0) >= 0.80],
    }
    conf_bucket_stats = {
        k: {
            "n": len(v),
            "win_rate": round(sum(1 for s in v if s.get("status") == "tp_hit") / max(1, len(v)), 3),
        }
        for k, v in conf_buckets.items() if v
    }

    return {
        "total_signals":   len(signals),
        "open":            len(open_),
        "closed":          len(closed),
        "wins":            len(wins),
        "losses":          len(losses),
        "win_rate":        round(win_rate, 3),
        "profit_factor":   round(profit_factor, 2),
        "expectancy_pct":  round(expectancy, 2),
        "total_pnl_pct":   round(total_pnl, 2),
        "median_pnl":      round(statistics.median(pnls), 2) if pnls else 0,
        "best_trade":      round(max(pnls), 2) if pnls else 0,
        "worst_trade":     round(min(pnls), 2) if pnls else 0,
        "by_action":       action_stats,
        "by_universe":     universe_stats,
        "by_sector":       sector_stats,
        "winners_vs_losers": comparison,
        "by_confidence_bucket": conf_bucket_stats,
    }


def detect_patterns(metrics: dict[str, Any]) -> list[str]:
    """Détecte automatiquement les patterns exploitables pour tuning."""
    patterns = []

    if metrics.get("closed", 0) < 10:
        return ["Échantillon insuffisant (< 10 clôturés) — attendre plus de trades avant tuning."]

    wr = metrics.get("win_rate", 0)
    pf = metrics.get("profit_factor", 0)
    exp = metrics.get("expectancy_pct", 0)

    # Pattern 1 : win rate global faible
    if wr < 0.45:
        patterns.append(f"Win rate global faible ({wr*100:.1f} %) — durcir les filtres (score min, confidence min).")
    elif wr > 0.70:
        patterns.append(f"Win rate excellent ({wr*100:.1f} %) — possibilité de relâcher les filtres pour plus de volume.")

    # Pattern 2 : profit factor
    if pf < 1.0 and metrics.get("closed", 0) >= 20:
        patterns.append(f"Profit factor < 1 ({pf}) — les pertes dominent, urgence de revoir les stops ou le score minimum.")

    # Pattern 3 : déséquilibre BUY vs SELL
    by_action = metrics.get("by_action", {})
    buy_wr = by_action.get("BUY", {}).get("win_rate", 0)
    sb_wr  = by_action.get("STRONG_BUY", {}).get("win_rate", 0)
    sell_wr = by_action.get("SELL", {}).get("win_rate", 0)
    ss_wr  = by_action.get("STRONG_SELL", {}).get("win_rate", 0)
    avg_long = (buy_wr + sb_wr) / 2 if (buy_wr and sb_wr) else max(buy_wr, sb_wr)
    avg_short = (sell_wr + ss_wr) / 2 if (sell_wr and ss_wr) else max(sell_wr, ss_wr)
    if avg_long and avg_short:
        if avg_long - avg_short > 0.20:
            patterns.append(f"Shorts très inférieurs aux longs ({avg_short*100:.0f} % vs {avg_long*100:.0f} %) — envisager de désactiver temporairement les SHORT.")
        elif avg_short - avg_long > 0.20:
            patterns.append(f"Shorts supérieurs aux longs ({avg_short*100:.0f} % vs {avg_long*100:.0f} %) — surprenant, audit à faire.")

    # Pattern 4 : comparaison winners vs losers
    cmp = metrics.get("winners_vs_losers", {})
    if cmp.get("avg_confidence_winners", 0) - cmp.get("avg_confidence_losers", 0) > 0.05:
        patterns.append(f"Winners ont conf {cmp['avg_confidence_winners']:.2f} vs losers {cmp['avg_confidence_losers']:.2f} — remonter PREMIUM_MIN_CONFIDENCE pourrait aider.")
    if cmp.get("avg_score_winners", 0) - cmp.get("avg_score_losers", 0) > 0.10:
        patterns.append(f"Winners ont score abs {cmp['avg_score_winners']:.2f} vs losers {cmp['avg_score_losers']:.2f} — remonter PREMIUM_MIN_SCORE.")

    # Pattern 5 : bucket de confiance
    buckets = metrics.get("by_confidence_bucket", {})
    if buckets.get("0.65-0.70", {}).get("n", 0) >= 5:
        wr_low = buckets["0.65-0.70"]["win_rate"]
        if wr_low < 0.40:
            patterns.append(f"Bucket confiance 65-70 % a win rate {wr_low*100:.0f} % — relever le seuil minimum à 0.70.")

    # Pattern 6 : univers qui sous-performent
    for uni, st in metrics.get("by_universe", {}).items():
        if st["n"] >= 5 and st["win_rate"] < 0.35:
            patterns.append(f"Univers {uni} : {st['n']} trades, win rate {st['win_rate']*100:.0f} % — envisager de le désactiver.")

    if not patterns:
        patterns.append("Aucun pattern exploitable détecté — les paramètres actuels semblent équilibrés.")

    return patterns


def main() -> int:
    log.info("🔍 Analyse CPA Bot Optimizer\n" + "=" * 50)

    signals = load_all_signals()
    log.info(f"📊 {len(signals)} signaux consolidés")

    metrics = compute_metrics(signals)
    patterns = detect_patterns(metrics)

    report = {
        "metrics":  metrics,
        "patterns": patterns,
        "n_signals_analyzed": len(signals),
    }

    # Écrit le rapport
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    # Sortie lisible
    log.info("\n📈 MÉTRIQUES PRINCIPALES")
    log.info("-" * 50)
    for k, v in metrics.items():
        if not isinstance(v, dict):
            log.info(f"  {k:25s} : {v}")

    log.info("\n🎯 PATTERNS DÉTECTÉS (hypothèses de tuning)")
    log.info("-" * 50)
    for i, p in enumerate(patterns, 1):
        log.info(f"  {i}. {p}")

    log.info(f"\n✅ Rapport complet : {OUTPUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
