"""
Écrit le contexte macro FRED dans dashboard/data/macro.json.
Exécuté par un workflow GitHub Actions (toutes les 6h).
"""
import json
import logging
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.data.fred_fetcher import get_macro_context

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s")
log = logging.getLogger()

OUT = Path(__file__).parent.parent / "dashboard" / "data" / "macro.json"


def main() -> int:
    ctx = get_macro_context()
    if ctx.risk_free_rate is None:
        log.error("Aucune donnée FRED — FRED_API_KEY manquant ?")
        return 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(asdict(ctx), indent=2, ensure_ascii=False), encoding="utf-8")
    log.info(f"Macro écrit : {OUT} (régime={ctx.regime})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
