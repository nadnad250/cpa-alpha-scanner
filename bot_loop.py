"""
Bot Loop — scanne NASDAQ Top et envoie les opportunités intraday sur Telegram.

Mode INTRADAY AGRESSIF :
- Univers : NASDAQ-100 + mid-caps haute volatilité
- Horizon : 24h max (time-stop forcé)
- Objectif : +5%/jour via portefeuille concentré (≤10 positions)
- Dédup Telegram : pas de répétition d'un signal déjà envoyé / déjà ouvert
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

from config.settings import (
    UNIVERSES, TOP_PER_UNIVERSE, PREMIUM_MIN_SCORE,
    PREMIUM_MIN_CONFIDENCE, PREMIUM_MIN_RR, MAX_GLOBAL_ALERTS,
    MAX_PER_SECTOR, MAX_OPEN_SIGNALS, TELEGRAM_DEDUP_HOURS,
    VIX_RISK_OFF, VIX_PANIC,
)
from src.agents.scanner_agent import ScannerAgent
from src.notifications.telegram_bot import TelegramNotifier
from src.notifications.pro_messages import ProMessageBuilder
from src.notifications.telegram_dedup import (
    select_new_signals, mark_as_sent, get_open_tickers_from_signals_json,
)
from src.tracking.signal_tracker import SignalTracker, TrackedSignal
from src.notifications.dashboard_exporter import export_to_dashboard

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("bot_loop")

DASHBOARD_SIGNALS_PATH = Path(__file__).parent / "dashboard" / "data" / "signals.json"


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
            logger.error("TELEGRAM_BOT_TOKEN/CHAT_ID manquants")
            sys.exit(1)

    def run(self, once: bool = False):
        try:
            self._track_stats = self.tracker.performance_stats(lookback_days=90)
        except Exception:
            self._track_stats = None
        # Plus de startup() : la session_banner émise dans _run_cycle contient tout.
        logger.info("AlphaForge Bot démarré (NASDAQ INTRADAY)")

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

    def _read_vix(self) -> float | None:
        """Lit le VIX depuis macro.json (mis à jour toutes les 6h)."""
        try:
            macro_path = Path(__file__).parent / "dashboard" / "data" / "macro.json"
            if not macro_path.exists():
                return None
            import json as _json
            data = _json.loads(macro_path.read_text(encoding="utf-8"))
            v = data.get("vix")
            return float(v) if v is not None else None
        except Exception:
            return None

    def _run_cycle(self):
        max_tickers = 15 if self.test_mode else None
        all_opportunities = []
        total_analyzed = 0

        # ── VIX GATING (B2) ────────────────────────────────────────
        vix = self._read_vix()
        if vix is not None and vix > VIX_PANIC:
            logger.warning(f"⛔ VIX = {vix:.1f} > {VIX_PANIC} (PANIC) — aucun nouveau signal")
            self._send(
                f"⛔ <b>VIX = {vix:.1f}</b> · marché en panique\n"
                f"{ProMessageBuilder.DIVIDER}\n"
                f"Aucun nouveau signal envoyé pour préserver le capital."
            )
            return

        # Scan NASDAQ uniquement (univers défini en settings)
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

        # Filtre PREMIUM intraday
        premium_raw = [
            o for o in all_opportunities
            if abs(o.score) >= PREMIUM_MIN_SCORE
            and o.confidence >= PREMIUM_MIN_CONFIDENCE
            and (not o.risk_reward or o.risk_reward >= PREMIUM_MIN_RR)
            and o.action in ("STRONG_BUY", "BUY", "STRONG_SELL", "SELL")
        ]

        # B2 : VIX en zone "risk-off" → on désactive les SHORTs (risque squeeze)
        if vix is not None and vix > VIX_RISK_OFF:
            n_before = len(premium_raw)
            premium_raw = [o for o in premium_raw if o.action not in ("SELL", "STRONG_SELL")]
            n_dropped = n_before - len(premium_raw)
            if n_dropped:
                logger.info(f"⚠️ VIX = {vix:.1f} > {VIX_RISK_OFF} : {n_dropped} SHORTs désactivés")

        # Tri qualité décroissante
        premium_raw.sort(
            key=lambda o: abs(o.score or 0) * (o.confidence or 0),
            reverse=True,
        )

        # Diversification sectorielle
        premium = []
        sector_counts: dict[str, int] = {}
        for o in premium_raw:
            sec = (o.sector or "—")
            if sector_counts.get(sec, 0) >= MAX_PER_SECTOR:
                continue
            premium.append(o)
            sector_counts[sec] = sector_counts.get(sec, 0) + 1

        n_dropped = len(premium_raw) - len(premium)
        if n_dropped:
            logger.info(f"🏷 Diversification : {n_dropped} retirés (max {MAX_PER_SECTOR}/secteur)")
        logger.info(f"💎 {len(premium)} signaux premium / {len(all_opportunities)}")

        # ── DÉDUP TELEGRAM (Bug #3 — split filter/mark) ────────────
        # 1) Sélection PURE (sans écrire le state)
        open_tickers = get_open_tickers_from_signals_json(DASHBOARD_SIGNALS_PATH)
        before = len(premium)
        fresh_signals = select_new_signals(
            premium, open_tickers, cooldown_hours=TELEGRAM_DEDUP_HOURS,
        )
        skipped = before - len(fresh_signals)
        logger.info(f"🔁 Dédup : {skipped} skippés (déjà notifiés/ouverts)")

        # 2) Limite finale = min(frais, MAX_GLOBAL_ALERTS, slots libres)
        slots_libres = max(0, MAX_OPEN_SIGNALS - len(open_tickers))
        n_to_send = min(len(fresh_signals), MAX_GLOBAL_ALERTS, slots_libres)
        to_send = fresh_signals[:n_to_send]

        # ── ENVOI TELEGRAM (1 banner + N signaux, sans répétitions) ─
        sent_ok: list = []
        if not to_send:
            self._send(self.msg.no_new_signals(
                open_count=len(open_tickers),
                dedup_skipped=skipped,
            ))
        else:
            # Tri LONG d'abord, SHORT ensuite (au sein de chaque groupe : score décr.)
            buys  = sorted([o for o in to_send if o.action in ("BUY", "STRONG_BUY")],
                           key=lambda o: -abs(o.score or 0))
            sells = sorted([o for o in to_send if o.action in ("SELL", "STRONG_SELL")],
                           key=lambda o: -abs(o.score or 0))

            # 1 SEUL banner (date + counts + track record + positions)
            self._send(self.msg.session_banner(
                n_signals=len(to_send),
                n_long=len(buys),
                n_short=len(sells),
                n_analyzed=total_analyzed,
                n_open=len(open_tickers),
                max_open=MAX_OPEN_SIGNALS,
                stats=getattr(self, "_track_stats", None),
            ))

            # Signaux LONG puis SHORT — emoji différencie déjà l'action
            rank = 1
            for o in buys + sells:
                if self._send(self.msg.signal_line(o, rank)):
                    sent_ok.append(o)
                rank += 1
                time.sleep(0.5)

        # 3) Marquer comme envoyé UNIQUEMENT ceux réellement transmis
        if sent_ok:
            mark_as_sent(sent_ok, cooldown_hours=TELEGRAM_DEDUP_HOURS)
            logger.info(f"✅ State dédup mis à jour pour {len(sent_ok)} signaux envoyés")

        # ── PERSISTANCE TRACKER + DASHBOARD ────────────────────────
        actionable = [
            o for o in to_send
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
                    horizon_days=1, horizon_hours=24,
                    # Bug #2 + #5 : préserver sector + ml_proba + RR + reason
                    sector=getattr(o, "sector", "") or "",
                    ml_proba_up=getattr(o, "ml_proba_up", None),
                    risk_reward=getattr(o, "risk_reward", None),
                    primary_reason=getattr(o, "primary_reason", "") or "",
                )
                for o in actionable
            ]
            self.tracker.save_batch(tracked)
            logger.info(f"💾 {len(tracked)} signaux tracés")

        # Export dashboard (avec premium pour stats même si pas envoyés)
        from config.settings import DASHBOARD_PATH
        export_to_dashboard(
            opportunities=actionable if actionable else premium,
            tracker=self.tracker,
            dashboard_path=DASHBOARD_PATH or None,
        )

        # Pas de market_summary ni footer : la session_banner émise en tête
        # contient déjà tous les compteurs (signaux/long/short/analysés/positions/track).

    def _send(self, text: str) -> bool:
        """Envoie un message Telegram. Retourne True si OK, False sinon."""
        if not text or not text.strip():
            return False
        ok = self.notifier.send_chunk(text)
        if ok:
            logger.info(f"📤 Envoyé ({len(text)} chars)")
        else:
            logger.warning("📤 Envoi Telegram échoué")
        time.sleep(0.5)
        return bool(ok)


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
