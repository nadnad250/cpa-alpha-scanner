"""
Messages Telegram — format ULTRA COMPACT, ZÉRO REPETITION.

Philosophie :
- 1 banner unique en tête (brand + date + track record + cible)
- 1 message par signal (LONG ou SHORT, identifié par emoji)
- 1 footer minimal avec timestamp seul
"""
from datetime import datetime
from typing import List, Optional, Dict


def chart_link(ticker: str, universe: str = "") -> str:
    """Lien TradingView cliquable selon l'univers."""
    if ticker.endswith(".PA"):
        return f"https://www.tradingview.com/symbols/EURONEXT-{ticker[:-3]}/"
    if ticker.endswith(".DE"):
        return f"https://www.tradingview.com/symbols/XETR-{ticker[:-3]}/"
    if ticker.endswith(".L"):
        return f"https://www.tradingview.com/symbols/LSE-{ticker[:-2]}/"
    if ticker.endswith(".MI"):
        return f"https://www.tradingview.com/symbols/MIL-{ticker[:-3]}/"
    if ticker.endswith(".MC"):
        return f"https://www.tradingview.com/symbols/BME-{ticker[:-3]}/"
    if ticker.endswith(".AS"):
        return f"https://www.tradingview.com/symbols/EURONEXT-{ticker[:-3]}/"
    if ticker.endswith(".BR"):
        return f"https://www.tradingview.com/symbols/EURONEXT-{ticker[:-3]}/"
    return f"https://www.tradingview.com/symbols/{ticker}/"


def _action_emoji(action: str) -> str:
    """Emoji unique par action."""
    return {
        "STRONG_BUY":  "🟢🟢",
        "BUY":         "🟢",
        "SELL":        "🔴",
        "STRONG_SELL": "🔴🔴",
    }.get(action, "•")


class ProMessageBuilder:
    DIVIDER = "━━━━━━━━━━━━━━"

    @staticmethod
    def session_banner(
        n_signals: int,
        n_long: int,
        n_short: int,
        n_analyzed: int,
        n_open: int,
        max_open: int = 10,
        stats: Optional[Dict] = None,
    ) -> str:
        """
        Bannière UNIQUE par scan : tout ce que l'utilisateur doit savoir en 4 lignes.
        Remplace startup() + market_open_banner() + _build_header() (3→1).
        """
        now = datetime.now().strftime("%d/%m %H:%M")
        lines = [
            f"⚡ <b>ALPHAFORGE NASDAQ</b> · {now}",
            f"💎 <b>{n_signals}</b> signaux · {n_long}🟢 / {n_short}🔴 · "
            f"📂 {n_open}/{max_open} · scanné {n_analyzed}",
        ]
        if stats and stats.get("total", 0) > 0:
            wr = stats["win_rate"] * 100
            pf = stats["profit_factor"]
            pf_str = "∞" if pf == float("inf") else f"{pf:.2f}"
            lines.append(
                f"📊 <b>{stats['total']}</b> trades · "
                f"WR <b>{wr:.0f}%</b> · PF <b>{pf_str}</b>"
            )
        return "\n".join(lines)

    @staticmethod
    def no_new_signals(open_count: int, dedup_skipped: int) -> str:
        """Aucun nouveau signal — message minimaliste."""
        now = datetime.now().strftime("%H:%M")
        msg = f"💤 {now} · Aucun nouveau signal · 📂 {open_count}/10 ouverts"
        if dedup_skipped:
            msg += f" · 🔁 {dedup_skipped} cooldown"
        return msg

    @staticmethod
    def vix_warning(vix: float) -> str:
        """Message risk-off VIX."""
        return f"⛔ VIX {vix:.1f} · capital preservation · aucun nouveau signal"

    @staticmethod
    def signal_line(o, rank: int) -> str:
        """
        Format ultra-compact d'un signal (5 lignes max).
        L'emoji indique l'action — pas besoin du texte "ACHAT FORT".

        🟢🟢 #1 <a>CSCO</a> · 118.21$ · +12%
        ├ 🤖 IA 65% · Conf 80% · R/R 2.5
        ├ Momentum positif soutenu
        └ TP 131.81 · SL 113.21
        """
        is_buy = o.action in ("BUY", "STRONG_BUY")
        emoji = _action_emoji(o.action)

        url = chart_link(o.ticker, o.universe)
        ticker_link = f'<a href="{url}">{o.ticker}</a>'

        price_str = f"{o.price:.2f}$" if o.price else "?"
        up_str = ""
        if o.upside_pct is not None and abs(o.upside_pct) > 1:
            sign = "+" if o.upside_pct > 0 else ""
            up_str = f" · <b>{sign}{o.upside_pct:.0f}%</b>"

        # Ligne 1 : ticker + prix + potentiel — emoji DIT déjà l'action
        head = f"{emoji} <b>#{rank} {ticker_link}</b> · {price_str}{up_str}"

        # Ligne 2 : signaux quantitatifs (IA si dispo, sinon skip)
        stats = []
        if o.ml_proba_up is not None:
            p = o.ml_proba_up if is_buy else (1 - o.ml_proba_up)
            stats.append(f"🤖 IA {p*100:.0f}%")
        stats.append(f"Conf {o.confidence*100:.0f}%")
        if o.risk_reward:
            stats.append(f"R/R {o.risk_reward:.1f}")

        lines = [head, f"├ {' · '.join(stats)}"]

        # Ligne 3 : raison (1 seule, la primaire)
        if getattr(o, "primary_reason", None):
            lines.append(f"├ {o.primary_reason}")

        # Ligne 4 : TP/SL compacts (le 🎯/🛑 redondant retiré)
        if o.stop_loss and o.take_profit:
            lines.append(f"└ TP {o.take_profit:.2f} · SL {o.stop_loss:.2f}")
        else:
            # Convertir la dernière ligne ├ → └
            if lines and lines[-1].startswith("├"):
                lines[-1] = "└" + lines[-1][1:]

        return "\n".join(lines)

    # === ALIAS de rétro-compat ===
    @staticmethod
    def premium_signal(o, rank: int) -> str:
        """Alias pour compat ancienne API."""
        return ProMessageBuilder.signal_line(o, rank)

    @staticmethod
    def startup(stats: Optional[Dict] = None) -> str:
        """DEPRECATED — préférer session_banner. Conservé pour compat."""
        # Renvoie vide : le banner unique gère tout.
        return ""

    @staticmethod
    def market_open_banner() -> str:
        return ""

    @staticmethod
    def alert_flash(opp) -> str:
        """Compat scanner_agent — alias de signal_line."""
        return ProMessageBuilder.signal_line(opp, 1)

    @staticmethod
    def premium_block(*args, **kwargs) -> str:
        """DEPRECATED."""
        return ""

    @staticmethod
    def opportunities(*args, **kwargs) -> str:
        """DEPRECATED."""
        return ""

    @staticmethod
    def market_summary(*args, **kwargs) -> str:
        """DEPRECATED — fusionné dans session_banner."""
        return ""

    @staticmethod
    def footer() -> str:
        """Footer minimal — juste timestamp."""
        return ""
