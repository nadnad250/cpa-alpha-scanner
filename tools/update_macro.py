"""
Écrit le contexte macro FRED dans dashboard/data/macro.json.
Exécuté par un workflow GitHub Actions (toutes les 6h).

Résilience :
- Si FRED renvoie HTTP 5xx (panne transitoire), on conserve le précédent macro.json
  et on sort en code 0 (le workflow ne s'affiche pas en échec sur un incident externe).
- On retourne code 1 uniquement si :
    1) FRED_API_KEY manquant ET
    2) Aucun macro.json existant (rien à servir au front).
"""
import json
import logging
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.data.fred_fetcher import get_macro_context

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s")
log = logging.getLogger()

OUT = Path(__file__).parent.parent / "dashboard" / "data" / "macro.json"


def main() -> int:
    ctx = get_macro_context()
    has_data = ctx.risk_free_rate is not None or ctx.vix is not None or ctx.yield_curve is not None

    if has_data:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(asdict(ctx), indent=2, ensure_ascii=False), encoding="utf-8")
        log.info(f"Macro écrit : {OUT} (régime={ctx.regime})")
        return 0

    # Pas de données fraîches — fallback sur le fichier existant si présent
    if OUT.exists():
        try:
            existing = json.loads(OUT.read_text(encoding="utf-8"))
            existing["last_failed_fetch"] = datetime.utcnow().isoformat()
            OUT.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")
            log.warning(
                f"FRED indisponible (panne externe) — conservation du précédent "
                f"macro.json (régime={existing.get('regime', '?')})"
            )
            return 0   # Ne PAS faire échouer le workflow sur incident externe
        except Exception as e:
            log.error(f"macro.json existant illisible : {e}")

    log.error("Aucune donnée FRED et aucun cache disponible — FRED_API_KEY manquant ?")
    return 1


if __name__ == "__main__":
    sys.exit(main())
