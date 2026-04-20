"""
Revue quotidienne des signaux — exécutée en fin de journée.

1. Charge tous les signaux ouverts
2. Récupère les prix actuels via yfinance
3. Évalue chaque signal : TP hit / SL hit / en cours / expiré
4. Calcule les stats : winrate, profit factor, expectancy
5. Envoie un rapport Telegram
"""
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

env_file = Path(__file__).parent / ".env.local"
if env_file.exists():
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, val = line.split("=", 1)
            os.environ.setdefault(key.strip(), val.strip())

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.tracking.signal_tracker import SignalTracker
from src.data.fetcher import fetch_prices
from src.notifications.telegram_bot import TelegramNotifier
from src.notifications.pro_messages import ProMessageBuilder

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("daily_review")


def prices_getter(ticker: str):
    try:
        df = fetch_prices([ticker], period="3mo")
        if ticker in df.columns:
            return df[ticker].dropna()
    except Exception as e:
        logger.debug(f"Prix {ticker}: {e}")
    return None


def format_stats_message(stats: dict, open_count: int) -> str:
    """Message Telegram de perf."""
    if stats["total"] == 0:
        return (
            f"📊 <b>REVUE QUOTIDIENNE</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🕰 {datetime.now().strftime('%d/%m/%Y — %H:%M')}\n\n"
            f"📂 {open_count} signaux en cours\n"
            f"⏳ Aucun signal encore clôturé\n"
            f"<i>Les stats apparaîtront après TP/SL hit ou expiration.</i>"
        )

    wr = stats["win_rate"] * 100
    pf = stats["profit_factor"]
    pf_str = "∞" if pf == float("inf") else f"{pf:.2f}"
    exp = stats["expectancy"] * 100

    wr_emoji = "🟢" if wr >= 60 else "🟡" if wr >= 45 else "🔴"
    pf_emoji = "🟢" if (pf == float("inf") or pf >= 1.8) else "🟡" if pf >= 1.2 else "🔴"

    lines = [
        f"📊 <b>REVUE QUOTIDIENNE — PERFORMANCE</b>",
        f"━━━━━━━━━━━━━━━━━━━━━━━━",
        f"🕰 {datetime.now().strftime('%d/%m/%Y — %H:%M')}",
        f"",
        f"<b>🎯 STATISTIQUES GLOBALES</b>",
        f"📈 Trades clôturés : <b>{stats['total']}</b>",
        f"✅ Gagnants : {stats['wins']} | ❌ Perdants : {stats['losses']}",
        f"{wr_emoji} Win Rate : <b>{wr:.1f}%</b>",
        f"{pf_emoji} Profit Factor : <b>{pf_str}</b>",
        f"💰 Gain moyen : <b>+{stats['avg_win']*100:.2f}%</b>",
        f"💸 Perte moyenne : <b>{stats['avg_loss']*100:.2f}%</b>",
        f"🧮 Expectancy : <b>{exp:+.2f}%</b> / trade",
        f"",
        f"📂 Signaux actifs : <b>{open_count}</b>",
    ]

    if stats["by_action"]:
        lines.append("")
        lines.append("<b>📑 PAR TYPE D'ACTION</b>")
        for act, s in stats["by_action"].items():
            lines.append(
                f"• {act} — {s['count']} trades | "
                f"WR {s['win_rate']*100:.0f}% | "
                f"Avg {s['avg_pnl']*100:+.2f}%"
            )

    lines.append("")
    lines.append(f"{ProMessageBuilder.DIVIDER}")
    lines.append("<i>🧠 AlphaForge — suivi automatique</i>")

    return "\n".join(lines)


def main():
    tracker = SignalTracker()
    notifier = TelegramNotifier()

    if not notifier.token or not notifier.chat_id:
        logger.error("TELEGRAM credentials manquants")
        return

    logger.info("🔄 Évaluation des signaux ouverts...")
    stats = tracker.evaluate_signals(prices_getter)

    open_sigs = tracker.load_open_signals(lookback_days=60)
    message = format_stats_message(stats, len(open_sigs))

    notifier.send_chunk(message)
    logger.info(f"📤 Rapport envoyé — {stats['total']} trades évalués")


if __name__ == "__main__":
    main()
