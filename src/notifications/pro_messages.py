"""
Messages Telegram — format ULTRA SIMPLE + liens cliquables + stats tracker.

Philosophie :
- Une ligne par signal (max 3-4)
- Ticker cliquable → chart TradingView
- Stats tracker en header (winrate global)
- News en 1 ligne si impactante
"""
from datetime import datetime
from typing import List, Optional, Dict


def chart_link(ticker: str, universe: str = "") -> str:
    """Lien TradingView cliquable selon l'univers."""
    # Mapping univers → exchange TradingView
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
    # Défaut : marchés US (NASDAQ / NYSE)
    return f"https://www.tradingview.com/symbols/{ticker}/"


class ProMessageBuilder:
    DIVIDER = "━━━━━━━━━━━━━━━━━━"

    FLAGS = {
        "SP500": "🇺🇸 S&P 500",
        "NASDAQ100": "💻 NASDAQ 100",
        "DOW30": "🏛️ DOW 30",
        "EUROSTOXX50": "🇪🇺 EUROSTOXX 50",
        "CAC40": "🇫🇷 CAC 40",
        "DAX40": "🇩🇪 DAX 40",
        "FTSE100": "🇬🇧 FTSE 100",
    }

    @staticmethod
    def startup(stats: Optional[Dict] = None) -> str:
        now = datetime.now().strftime("%d/%m/%Y %H:%M")
        lines = [
            f"🟢 <b>ALPHAFORGE PRO</b>",
            f"{ProMessageBuilder.DIVIDER}",
            f"📅 {now}",
            f"🎯 <b>Crème de la crème</b> — score&gt;0.35 · conf&gt;65%",
        ]
        if stats and stats.get("total", 0) > 0:
            wr = stats["win_rate"] * 100
            pf = stats["profit_factor"]
            pf_str = "∞" if pf == float("inf") else f"{pf:.2f}"
            lines.append(
                f"📊 Track : <b>{stats['total']}</b> trades · "
                f"WR <b>{wr:.0f}%</b> · PF <b>{pf_str}</b>"
            )
        return "\n".join(lines)

    @staticmethod
    def market_open_banner() -> str:
        return (
            f"🔔 <b>SIGNAUX PREMIUM DU JOUR</b>\n"
            f"{ProMessageBuilder.DIVIDER}"
        )

    @staticmethod
    def premium_signal(o, rank: int) -> str:
        """
        Format ultra-simple, ticker cliquable :

        🟢🟢 <a>AAPL</a> · 185$ · +18% · ACHAT FORT
        ├ 🤖 IA 72% · Conf 85% · R/R 2.5
        ├ 📌 Sous-évaluée vs fondamentaux
        └ 📰 "Apple beats Q3..." (+sentiment)
        """
        is_buy = o.action in ("BUY", "STRONG_BUY")
        emoji = "🟢🟢" if o.action == "STRONG_BUY" else \
                "🟢" if o.action == "BUY" else \
                "🔴🔴" if o.action == "STRONG_SELL" else "🔴"
        action_fr = {
            "STRONG_BUY": "ACHAT FORT",
            "BUY": "ACHAT",
            "SELL": "VENTE",
            "STRONG_SELL": "VENTE FORTE",
        }.get(o.action, "?")

        url = chart_link(o.ticker, o.universe)
        ticker_link = f'<a href="{url}">{o.ticker}</a>'

        price_str = f"{o.price:.2f}$" if o.price else "?"
        up_str = ""
        if o.upside_pct is not None and abs(o.upside_pct) > 1:
            sign = "+" if o.upside_pct > 0 else ""
            up_str = f" · {sign}{o.upside_pct:.0f}%"

        # Ligne 1 — action
        head = f"{emoji} <b>#{rank} {ticker_link}</b> · <b>{price_str}</b>{up_str} · {action_fr}"

        # Ligne 2 — IA + confiance + R/R
        mid_parts = []
        if o.ml_proba_up is not None:
            p = o.ml_proba_up if is_buy else (1 - o.ml_proba_up)
            mid_parts.append(f"🤖 IA {p*100:.0f}%")
        mid_parts.append(f"Conf {o.confidence*100:.0f}%")
        if o.risk_reward:
            mid_parts.append(f"R/R {o.risk_reward:.1f}")
        if o.kelly_position and o.kelly_position > 0.005 and is_buy:
            mid_parts.append(f"💼 {o.kelly_position*100:.1f}%")

        lines = [head, f"├ {' · '.join(mid_parts)}"]

        # Ligne 3 — raison
        lines.append(f"├ 📌 {o.primary_reason}")

        # Ligne 4 — TP/SL condensés
        if o.stop_loss and o.take_profit:
            lines.append(f"├ 🎯 TP {o.take_profit:.2f}$ · 🛑 SL {o.stop_loss:.2f}$")

        # Ligne 5 — news (seulement si impactante)
        if o.top_news_title and abs(o.news_score or 0) > 0.15:
            news_emoji = "📰📈" if o.news_score > 0 else "📰📉"
            title = o.top_news_title[:70] + ("…" if len(o.top_news_title) > 70 else "")
            if o.top_news_url:
                news_line = f'└ {news_emoji} <a href="{o.top_news_url}">{title}</a>'
            else:
                news_line = f"└ {news_emoji} {title}"
            lines.append(news_line)
        else:
            # remplacer ├ par └ sur la dernière ligne
            lines[-1] = lines[-1].replace("├", "└", 1)

        return "\n".join(lines)

    @staticmethod
    def premium_block(
        opps_for_universe: List,
        universe: str,
        top_n: int = 5,
        min_score: float = 0.35,
        min_confidence: float = 0.65,
        min_rr: float = 2.0,
    ) -> str:
        flag = ProMessageBuilder.FLAGS.get(universe, universe)

        premium = [
            o for o in opps_for_universe
            if o.universe == universe
            and abs(o.score) >= min_score
            and o.confidence >= min_confidence
            and (not o.risk_reward or o.risk_reward >= min_rr)
        ]

        buys = sorted(
            [o for o in premium if o.score > 0],
            key=lambda o: o.score, reverse=True,
        )[:top_n]
        sells = sorted(
            [o for o in premium if o.score < 0],
            key=lambda o: abs(o.score), reverse=True,
        )[:top_n]

        if not buys and not sells:
            return ""

        lines = [f"\n{flag}\n{ProMessageBuilder.DIVIDER}"]

        if buys:
            lines.append("\n🟢 <b>TOP ACHATS</b>\n")
            for i, o in enumerate(buys, 1):
                lines.append(ProMessageBuilder.premium_signal(o, i))
                lines.append("")

        if sells:
            lines.append("\n🔴 <b>TOP VENTES</b>\n")
            for i, o in enumerate(sells, 1):
                lines.append(ProMessageBuilder.premium_signal(o, i))
                lines.append("")

        return "\n".join(lines)

    @staticmethod
    def opportunities(opps: List, universe: str, top_n: int = 5) -> str:
        return ProMessageBuilder.premium_block(opps, universe, top_n=top_n)

    @staticmethod
    def market_summary(
        opps_all: List,
        total_analyzed: int,
        premium_count: int,
        stats: Optional[Dict] = None,
    ) -> str:
        strong_buy = sum(1 for o in opps_all if o.action == "STRONG_BUY")
        buy = sum(1 for o in opps_all if o.action == "BUY")
        strong_sell = sum(1 for o in opps_all if o.action == "STRONG_SELL")
        sell = sum(1 for o in opps_all if o.action == "SELL")

        lines = [
            f"\n📊 <b>RÉSUMÉ GLOBAL</b>",
            f"{ProMessageBuilder.DIVIDER}",
            f"📈 Analysés : <b>{total_analyzed}</b> · 💎 Premium : <b>{premium_count}</b>",
            f"🟢🟢 {strong_buy} · 🟢 {buy} · 🔴 {sell} · 🔴🔴 {strong_sell}",
        ]

        if stats and stats.get("total", 0) > 0:
            wr = stats["win_rate"] * 100
            pf = stats["profit_factor"]
            pf_str = "∞" if pf == float("inf") else f"{pf:.2f}"
            exp = stats["expectancy"] * 100
            lines.append("")
            lines.append(
                f"📊 <b>TRACK RECORD</b> — {stats['total']} trades · "
                f"WR <b>{wr:.0f}%</b> · PF <b>{pf_str}</b> · Exp <b>{exp:+.2f}%</b>"
            )

        return "\n".join(lines)

    @staticmethod
    def alert_flash(opp) -> str:
        """Alerte flash — 1 signal = 4 lignes max."""
        is_buy = opp.action in ("BUY", "STRONG_BUY")
        emoji = "🚀" if opp.action == "STRONG_BUY" else \
                "🟢" if opp.action == "BUY" else \
                "⚠️" if opp.action == "STRONG_SELL" else "🔴"

        action_fr = {
            "STRONG_BUY": "ACHAT FORT",
            "BUY": "ACHAT",
            "SELL": "VENTE",
            "STRONG_SELL": "VENTE FORTE",
        }.get(opp.action, "?")

        url = chart_link(opp.ticker, opp.universe)
        ticker_link = f'<a href="{url}">{opp.ticker}</a>'

        up_str = ""
        if opp.upside_pct is not None:
            sign = "+" if opp.upside_pct > 0 else ""
            up_str = f" · {sign}{opp.upside_pct:.0f}%"

        lines = [
            f"{emoji} <b>{ticker_link}</b> · <b>{action_fr}</b> · {opp.price:.2f}${up_str}",
        ]

        if opp.ml_proba_up is not None:
            p = opp.ml_proba_up if is_buy else (1 - opp.ml_proba_up)
            lines.append(f"🤖 IA {p*100:.0f}% · Conf {opp.confidence*100:.0f}%")

        lines.append(f"📌 {opp.primary_reason}")

        if opp.stop_loss and opp.take_profit:
            lines.append(
                f"🎯 TP {opp.take_profit:.2f}$ · 🛑 SL {opp.stop_loss:.2f}$"
            )

        if opp.top_news_title and abs(opp.news_score or 0) > 0.15:
            e = "📰📈" if opp.news_score > 0 else "📰📉"
            title = opp.top_news_title[:60] + ("…" if len(opp.top_news_title) > 60 else "")
            if opp.top_news_url:
                lines.append(f'{e} <a href="{opp.top_news_url}">{title}</a>')
            else:
                lines.append(f"{e} {title}")

        return "\n".join(lines)

    @staticmethod
    def footer() -> str:
        return (
            f"\n{ProMessageBuilder.DIVIDER}\n"
            f"🤖 AlphaForge Pro · {datetime.now().strftime('%H:%M')}\n"
            f"<i>Cliquez sur un ticker pour voir le chart</i>"
        )
