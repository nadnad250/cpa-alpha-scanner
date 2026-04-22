"""
Bot Loop — scanne CPA + ML et envoie les opportunités sur Telegram.
"""
import argparse
import logging
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

env_file = Path(__file__).parent / ".env.local"
if env_file.exists():
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, val = line.split("=", 1)
            os.environ.setdefault(key.strip(), val.strip())

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime
from config.settings import (
    UNIVERSES, TOP_PER_UNIVERSE, PREMIUM_MIN_SCORE,
    PREMIUM_MIN_CONFIDENCE, PREMIUM_MIN_RR, MAX_GLOBAL_ALERTS,
)
from src.agents.scanner_agent import ScannerAgent
from src.notifications.telegram_bot import TelegramNotifier
from src.notifications.pro_messages import ProMessageBuilder
from src.tracking.signal_tracker import SignalTracker, TrackedSignal
from src.notifications.dashboard_exporter import export_to_dashboard

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("bot_loop")


class AlphaForgeBot:
    def __init__(self, interval_seconds: int = 14400, test_mode: bool = False):
        self.interval = interval_seconds
        self.test_mode = test_mode
        self.notifier = TelegramNotifier()
        self.msg = ProMessageBuilder()
        self.tracker = SignalTracker()
        self.iteration = 0
        self.start_time = datetime.now()

        if not self.notifier.token or not self.notifier.chat_id:
            logger.error("❌ TELEGRAM_BOT_TOKEN/CHAT_ID manquants")
            sys.exit(1)

    def run(self, once: bool = False):
        # Charge les stats tracker existantes pour afficher le track record
        try:
            self._track_stats = self.tracker.performance_stats(lookback_days=90)
        except Exception:
            self._track_stats = None
        self._send(self.msg.startup(stats=self._track_stats))
        logger.info("🚀 AlphaForge Bot démarré")

        try:
            while True:
                self.iteration += 1
                logger.info(f"\n{'='*60}\nITÉRATION #{self.iteration}\n{'='*60}")
                try:
                    self._run_cycle()
                except Exception as e:
                    logger.error(f"Erreur: {e}", exc_info=True)
                    self.notifier.send_message(f"⚠️ Erreur: {str(e)[:200]}")

                if once:
                    break

                next_run = datetime.now() + timedelta(seconds=self.interval)
                logger.info(f"💤 Prochain scan: {next_run.strftime('%H:%M:%S')}")
                time.sleep(self.interval)

        except KeyboardInterrupt:
            self._send("⏸ Bot arrêté")

    def _run_cycle(self):
        self._send(self.msg.market_open_banner())

        max_tickers = 15 if self.test_mode else None
        all_opportunities = []
        total_analyzed = 0

        # Scan de tous les univers (collecte)
        for universe in UNIVERSES:
            logger.info(f"🔍 Scan {universe}...")
            try:
                scanner = ScannerAgent(universe=universe)
                scanner.run(max_tickers=max_tickers)
                opps = scanner.all_universe_opportunities()
                all_opportunities.extend(opps)
                total_analyzed += len(scanner.results)
                logger.info(
                    f"  ✅ {len(opps)} opps / {len(scanner.results)} analysés"
                )
            except Exception as e:
                logger.error(f"  ❌ {e}")

        # Filtre PREMIUM : crème de la crème
        premium = [
            o for o in all_opportunities
            if abs(o.score) >= PREMIUM_MIN_SCORE
            and o.confidence >= PREMIUM_MIN_CONFIDENCE
            and (not o.risk_reward or o.risk_reward >= PREMIUM_MIN_RR)
            and o.action in ("STRONG_BUY", "BUY", "STRONG_SELL", "SELL")
        ]
        logger.info(f"💎 {len(premium)} signaux premium / {len(all_opportunities)}")

        # Envoi par univers (seulement ceux qui ont des signaux premium)
        for universe in UNIVERSES:
            block = self.msg.premium_block(
                premium,
                universe=universe,
                top_n=TOP_PER_UNIVERSE,
                min_score=PREMIUM_MIN_SCORE,
                min_confidence=PREMIUM_MIN_CONFIDENCE,
                min_rr=PREMIUM_MIN_RR,
            )
            if block:
                self._send(block)
                time.sleep(1)

        # Persistance des signaux premium uniquement
        actionable = [
            o for o in premium
            if o.price and o.stop_loss and o.take_profit
        ]
        if actionable:
            tracked = [
                TrackedSignal(
                    ticker=o.ticker, action=o.action,
                    entry_price=o.price, stop_loss=o.stop_loss,
                    take_profit=o.take_profit, score=o.score,
                    confidence=o.confidence, universe=o.universe,
                    issued_at=datetime.utcnow().isoformat(),
                )
                for o in actionable
            ]
            self.tracker.save_batch(tracked)
            logger.info(f"💾 {len(tracked)} signaux tracés")

        # ── Export vers le dashboard web ──────────────────────────
        from config.settings import DASHBOARD_PATH
        export_to_dashboard(
            opportunities=actionable if actionable else premium,
            tracker=self.tracker,
            dashboard_path=DASHBOARD_PATH or None,
        )
        # ──────────────────────────────────────────────────────────

        # Résumé avec stats tracker
        self._send(self.msg.market_summary(
            all_opportunities, total_analyzed, len(premium),
            stats=getattr(self, "_track_stats", None),
        ))

        # TOP ALERTES FLASH — les meilleures tous univers confondus
        top_alerts = sorted(
            premium, key=lambda o: abs(o.score) * o.confidence, reverse=True,
        )[:MAX_GLOBAL_ALERTS]
        if top_alerts:
            self._send("\n🚨 <b>TOP ALERTES — TOUS MARCHÉS</b>")
            for o in top_alerts:
                time.sleep(1)
                self._send(self.msg.alert_flash(o))

        self._send(self.msg.footer())

    def _send(self, text: str):
        ok = self.notifier.send_chunk(text)
        if ok:
            logger.info(f"📤 Envoyé ({len(text)} chars)")
        time.sleep(0.5)


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--demo", action="store_true")
    p.add_argument("--once", action="store_true")
    p.add_argument("--interval", type=int, default=14400)
    return p.parse_args()


def main():
    args = parse_args()
    bot = AlphaForgeBot(
        interval_seconds=300 if args.demo else args.interval,
        test_mode=args.demo,
    )
    bot.run(once=args.once)


if __name__ == "__main__":
    main()
