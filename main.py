"""
CPA Alpha Scanner — Point d'entrée principal.

Usage:
    python main.py                    # Scan SP500 + Nasdaq + Eurostoxx
    python main.py --universe SP500   # Scan SP500 uniquement
    python main.py --test             # Mode test (20 tickers)
    python main.py --no-telegram      # Sans notification Telegram
"""
import argparse
import logging
import os
import sys
from datetime import datetime
from typing import Dict, List

# Ajouter le dossier racine au path
sys.path.insert(0, os.path.dirname(__file__))

from config.settings import UNIVERSES, TOP_N_SIGNALS, ALPHA_THRESHOLD
from src.agents.scanner_agent import ScannerAgent
from src.agents.reporter_agent import ReporterAgent
from src.models.cpa import CPAResult

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("data/cpa_scanner.log", mode="a"),
    ],
)
logger = logging.getLogger("main")


def parse_args():
    parser = argparse.ArgumentParser(description="CPA Alpha Scanner")
    parser.add_argument("--universe", nargs="+", default=None,
                        help="Univers à scanner (SP500, NASDAQ100, EUROSTOXX50)")
    parser.add_argument("--test", action="store_true",
                        help="Mode test (20 tickers par univers)")
    parser.add_argument("--no-telegram", action="store_true",
                        help="Désactiver les notifications Telegram")
    parser.add_argument("--top", type=int, default=TOP_N_SIGNALS,
                        help=f"Nombre de signaux top (défaut: {TOP_N_SIGNALS})")
    parser.add_argument("--threshold", type=float, default=ALPHA_THRESHOLD,
                        help=f"Seuil alpha minimum (défaut: {ALPHA_THRESHOLD})")
    return parser.parse_args()


def run_scan(
    universes: List[str],
    max_tickers: int = None,
    send_telegram: bool = True,
    top_n: int = TOP_N_SIGNALS,
) -> Dict[str, List[CPAResult]]:
    """Exécute le scan complet."""
    os.makedirs("data/cache", exist_ok=True)
    os.makedirs("data/reports", exist_ok=True)

    results_by_universe = {}
    reporter = ReporterAgent()

    for universe in universes:
        logger.info(f"\n{'='*50}")
        logger.info(f"SCAN: {universe}")
        logger.info(f"{'='*50}")

        try:
            scanner = ScannerAgent(universe=universe)
            results = scanner.run(max_tickers=max_tickers)
            results_by_universe[universe] = results

            # Affichage console
            top = scanner.top_signals(n=top_n)
            logger.info(f"\n[{universe}] TOP {len(top)} SIGNAUX:")
            for i, r in enumerate(top, 1):
                logger.info(f"  {i:2}. {r.summary()}")

        except Exception as e:
            logger.error(f"Erreur scan {universe}: {e}", exc_info=True)
            reporter.notifier.send_error(f"Scan {universe}: {str(e)[:200]}")

    # Rapport final
    logger.info("\n" + "="*50)
    logger.info("GÉNÉRATION DU RAPPORT")
    logger.info("="*50)

    if results_by_universe:
        report = reporter.report(results_by_universe, send_telegram=send_telegram)
        print(report)

        # Alertes signaux forts (seuil 20%)
        all_results = [r for rs in results_by_universe.values() for r in rs]
        if send_telegram:
            reporter.alert_strong_signals(all_results, threshold=0.20)

    return results_by_universe


def main():
    args = parse_args()

    universes = args.universe or UNIVERSES
    max_tickers = 20 if args.test else None
    send_telegram = not args.no_telegram

    logger.info(f"CPA Alpha Scanner — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    logger.info(f"Univers: {universes}")
    logger.info(f"Mode test: {args.test}")
    logger.info(f"Telegram: {'OFF' if args.no_telegram else 'ON'}")

    run_scan(
        universes=universes,
        max_tickers=max_tickers,
        send_telegram=send_telegram,
        top_n=args.top,
    )


if __name__ == "__main__":
    main()
