"""
Auditeur automatique du site CPA Alpha Scanner.
Charge signals.json, calcule les valeurs attendues, scanne les HTML/JS
pour détecter les incohérences, et produit un rapport structuré.

Usage:
    python .claude/skills/cpa-site-debugger/scripts/audit_site.py

Sortie:
    - Rapport console + JSON
    - Fichier : .claude/skills/cpa-site-debugger/last_audit.json
"""
import json
import logging
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger()

ROOT = Path(__file__).parent.parent.parent.parent.parent
SIGNALS_JSON = ROOT / "dashboard" / "data" / "signals.json"
DASHBOARD_DIR = ROOT / "dashboard"
OUTPUT = Path(__file__).parent.parent / "last_audit.json"


# ============================================================
# CALCUL DES VRAIES VALEURS ATTENDUES (source de vérité)
# ============================================================
def compute_truth(signals: list[dict]) -> dict[str, Any]:
    opens = [s for s in signals if s.get("status") == "open"]
    tp_hits = [s for s in signals if s.get("status") == "tp_hit"]
    sl_hits = [s for s in signals if s.get("status") == "sl_hit"]
    closed = tp_hits + sl_hits

    # Win rate (règle sacrée : wins / (wins+losses), PAS /total)
    win_rate = len(tp_hits) / len(closed) if closed else None

    # P&L réalisé : uniquement closed
    def pnl_real(s):
        if "pnl_pct" in s and s["pnl_pct"] is not None:
            return s["pnl_pct"]
        up = abs(s.get("upside_pct") or 0)
        return up if s.get("status") == "tp_hit" else -up
    pnl_total = sum(pnl_real(s) for s in closed)

    # P&L live : uniquement opens
    pnl_live_sum = sum(s.get("pnl_pct_live", 0) or 0 for s in opens)

    # Signaux mal catégorisés (open mais prix au-delà TP/SL)
    stuck_open = []
    for s in opens:
        entry = s.get("price")
        tp = s.get("take_profit")
        sl = s.get("stop_loss")
        current = s.get("current_price")
        if not all([entry, tp, sl, current]):
            continue
        is_buy = (s.get("score") or 0) > 0
        if is_buy:
            if current >= tp or current <= sl:
                stuck_open.append({
                    "ticker": s["ticker"], "action": s["action"],
                    "entry": entry, "current": current, "tp": tp, "sl": sl,
                    "issue": "devrait être tp_hit" if current >= tp else "devrait être sl_hit"
                })
        else:
            if current <= tp or current >= sl:
                stuck_open.append({
                    "ticker": s["ticker"], "action": s["action"],
                    "entry": entry, "current": current, "tp": tp, "sl": sl,
                    "issue": "devrait être tp_hit" if current <= tp else "devrait être sl_hit"
                })

    # Doublons par (ticker, action)
    by_key: dict[tuple, list] = defaultdict(list)
    for s in signals:
        by_key[(s.get("ticker"), s.get("action"), s.get("status"))].append(s)
    duplicates = {k: len(v) for k, v in by_key.items() if len(v) > 1}

    # Distribution actions
    action_dist = defaultdict(int)
    for s in signals:
        action_dist[s.get("action", "?")] += 1

    # Distribution univers
    univ_dist = defaultdict(int)
    for s in signals:
        univ_dist[s.get("universe", "?")] += 1

    return {
        "total_signals":     len(signals),
        "open_count":        len(opens),
        "tp_hit_count":      len(tp_hits),
        "sl_hit_count":      len(sl_hits),
        "closed_count":      len(closed),
        "win_rate":          round(win_rate, 3) if win_rate is not None else None,
        "pnl_total_realized": round(pnl_total, 2),
        "pnl_live_sum":       round(pnl_live_sum, 2),
        "stuck_open":        stuck_open,
        "duplicates":        {f"{k[0]}/{k[1]}/{k[2]}": v for k, v in duplicates.items()},
        "action_distribution": dict(action_dist),
        "universe_distribution": dict(univ_dist),
    }


# ============================================================
# DÉTECTION DE BUGS CLASSIQUES DANS LE CODE FRONTEND
# ============================================================
def scan_frontend_bugs() -> list[dict]:
    bugs = []
    js_files = list(DASHBOARD_DIR.glob("**/*.js")) + list(DASHBOARD_DIR.glob("**/*.html"))

    for f in js_files:
        if "node_modules" in str(f):
            continue
        try:
            content = f.read_text(encoding="utf-8")
        except Exception:
            continue
        rel = str(f.relative_to(DASHBOARD_DIR))

        # Bug 1 : win_rate = wins / total (doit être wins / closed)
        if re.search(r"win_rate.*\btotal\b|winRate.*\bsignals\.length", content):
            # Heuristique approximative — à vérifier manuellement
            bugs.append({
                "severity": "high",
                "file": rel,
                "category": "formula",
                "desc": "Possible division par total au lieu de closed pour win rate",
            })

        # Bug 2 : status check incomplet ('tp_hit' || 'sl_hit' manqué)
        if "status === 'tp_hit'" in content and "status === 'sl_hit'" not in content:
            # Si un seul des deux est mentionné dans le même fichier, probable oubli
            pass  # Désactivé — trop de faux positifs

        # Bug 3 : utilisation de upside_pct au lieu de pnl_pct (P&L réalisé)
        matches = re.findall(r"upside_pct[^;]{0,80}status.*tp_hit", content)
        if matches:
            for m in matches[:2]:
                bugs.append({
                    "severity": "medium",
                    "file": rel,
                    "category": "formula",
                    "desc": f"Utilise upside_pct (cible théorique) au lieu de pnl_pct (réalisé) : {m[:60]}...",
                })

        # Bug 4 : `|| 0` sur valeurs potentiellement nulles légitimes
        if re.search(r"s\.(value_gap|factor_premia|mean_reversion|info_flow)\s*\|\|\s*0", content):
            bugs.append({
                "severity": "low",
                "file": rel,
                "category": "null_handling",
                "desc": "Composante CPA traitée avec `|| 0` (perd la distinction null vs 0 réel)",
            })

        # Bug 5 : `status === 'open'` sans filtrer les clôturés
        if "filter(s => s.status === 'open')" not in content and "signal_ouvert" in content.lower():
            pass  # disabled

    return bugs


# ============================================================
# ANALYSE DES IMPORTS / DÉPENDANCES
# ============================================================
def scan_page_dependencies() -> dict[str, list[str]]:
    deps = {}
    for html in DASHBOARD_DIR.glob("*.html"):
        content = html.read_text(encoding="utf-8")
        srcs = re.findall(r'src="([^"]+\.js)"', content)
        hrefs = re.findall(r'href="([^"]+\.css)"', content)
        deps[html.name] = {"js": srcs, "css": hrefs}
    return deps


# ============================================================
# MAIN
# ============================================================
def main() -> int:
    log.info("🔍 Audit CPA Site Debugger\n" + "=" * 60)

    if not SIGNALS_JSON.exists():
        log.error("❌ signals.json introuvable — le bot n'a pas encore tourné ?")
        return 1

    data = json.loads(SIGNALS_JSON.read_text(encoding="utf-8"))
    signals = data.get("signals", [])

    # 1. Vérités terrain
    truth = compute_truth(signals)
    log.info("\n📊 VÉRITÉS TERRAIN (depuis signals.json)")
    log.info("-" * 60)
    for k, v in truth.items():
        if isinstance(v, (list, dict)) and v:
            log.info(f"  {k:25s} : {len(v) if isinstance(v, list) else len(v)} items")
        else:
            log.info(f"  {k:25s} : {v}")

    # 2. Signaux coincés en "open" alors qu'ils devraient être clôturés
    if truth["stuck_open"]:
        log.info("\n🚨 SIGNAUX COINCÉS EN 'OPEN' (TP ou SL franchi)")
        log.info("-" * 60)
        for s in truth["stuck_open"]:
            log.info(f"  ⚠️  {s['ticker']:10s} {s['action']:14s} entry=${s['entry']} current=${s['current']} — {s['issue']}")

    # 3. Doublons suspects
    if truth["duplicates"]:
        log.info("\n🔁 DOUBLONS (ticker, action, status)")
        log.info("-" * 60)
        for k, n in truth["duplicates"].items():
            log.info(f"  ⚠️  {k} apparaît {n} fois")

    # 4. Scan code frontend
    bugs = scan_frontend_bugs()
    if bugs:
        log.info("\n🐛 BUGS POTENTIELS DANS LE CODE")
        log.info("-" * 60)
        for b in bugs:
            log.info(f"  [{b['severity'].upper():6s}] {b['file']:40s} {b['desc'][:80]}")

    # 5. Dépendances
    deps = scan_page_dependencies()
    log.info("\n📦 DÉPENDANCES DES PAGES")
    log.info("-" * 60)
    for page, d in deps.items():
        log.info(f"  {page:25s} JS: {len(d['js'])}, CSS: {len(d['css'])}")

    # 6. Rapport final
    report = {
        "truth":  truth,
        "code_bugs": bugs,
        "dependencies": deps,
        "summary": {
            "total_bugs":      len(bugs) + len(truth["stuck_open"]),
            "critical_bugs":   len(truth["stuck_open"]),
            "high_bugs":       sum(1 for b in bugs if b["severity"] == "high"),
            "medium_bugs":     sum(1 for b in bugs if b["severity"] == "medium"),
            "low_bugs":        sum(1 for b in bugs if b["severity"] == "low"),
        },
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    log.info("\n" + "=" * 60)
    log.info(f"📋 RÉSUMÉ FINAL")
    log.info(f"   Critical (signaux coincés) : {report['summary']['critical_bugs']}")
    log.info(f"   High (erreurs de formule)  : {report['summary']['high_bugs']}")
    log.info(f"   Medium (données suspectes) : {report['summary']['medium_bugs']}")
    log.info(f"   Low (code smell)           : {report['summary']['low_bugs']}")
    log.info(f"\n✅ Rapport complet : {OUTPUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
