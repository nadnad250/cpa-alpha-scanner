"""
Messages Telegram — format PRO ultra-clair.
Seulement la crème de la crème : top 5 BUY + top 5 SELL par univers.
"""
from datetime import datetime
from typing import List


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
    def startup() -> str:
        now = datetime.now().strftime("%d/%m/%Y %H:%M")
        return (
            f"🟢 <b>ALPHAFORGE PRO</b>\n"
            f"{ProMessageBuilder.DIVIDER}\n"
            f"📅 {now}\n"
            f"🎯 Mode : <b>Crème de la crème</b>\n"
            f"🧠 CPA + ML + ATR + Kelly"
        )

    @staticmethod
    def market_open_banner() -> str:
        return (
            f"🔔 <b>SIGNAUX PREMIUM DU JOUR</b>\n"
            f"{ProMessageBuilder.DIVIDER}\n"
            f"<i>Seules les meilleures opportunités sont affichées.</i>"
        )

    @staticmethod
    def premium_signal(o, rank: int) -> str:
        """
        Format pro ultra-concis (6 lignes max) :

        🟢 #1 · AAPL · 185.20$
        ├ Action : ACHAT FORT
        ├ Score : 0.72 · Conf 85%
        ├ Raison : Sous-évaluée vs fondamentaux
        ├ IA 21j : 72% hausse · P(+5%) 65%
        ├ 🎯 TP 195.40$ · 🛑 SL 178.10$ · R/R 2.5
        └ 💼 Allocation Kelly : 3.2%
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
        }.get(o.action, "NEUTRE")

        price_str = f"{o.price:.2f}$" if o.price else "?"
        up_str = ""
        if o.upside_pct is not None and abs(o.upside_pct) > 1:
            sign = "+" if o.upside_pct > 0 else ""
            up_str = f" · 🎯 {sign}{o.upside_pct:.0f}%"

        lines = [
            f"{emoji} <b>#{rank} · {o.ticker}</b> · <b>{price_str}</b>{up_str}",
            f"├ <b>{action_fr}</b> · Score {o.score:+.2f} · Conf {o.confidence*100:.0f}%",
            f"├ {o.primary_reason}",
        ]

        # Ligne ML
        if o.ml_proba_up is not None:
            dir_ml = "hausse" if is_buy else "baisse"
            p = o.ml_proba_up if is_buy else (1 - o.ml_proba_up)
            ml_line = f"├ 🤖 IA 21j : <b>{p*100:.0f}%</b> {dir_ml}"
            if o.ml_proba_strong and o.ml_proba_strong > 0.4 and is_buy:
                ml_line += f" · P(+5%) <b>{o.ml_proba_strong*100:.0f}%</b>"
            lines.append(ml_line)

        # Stop / TP / R/R
        if o.stop_loss and o.take_profit:
            rr = f"{o.risk_reward:.1f}" if o.risk_reward else "—"
            lines.append(
                f"├ 🎯 TP <b>{o.take_profit:.2f}$</b> · 🛑 SL <b>{o.stop_loss:.2f}$</b> · R/R {rr}"
            )

        # Kelly
        if o.kelly_position and o.kelly_position > 0.005 and is_buy:
            lines.append(f"└ 💼 Allocation : <b>{o.kelly_position*100:.1f}%</b>")
        elif o.risk_flags:
            lines.append(f"└ {o.risk_flags[0]}")
        else:
            # remplace le ├ de la dernière ligne par └
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
        """Affiche TOP BUY + TOP SELL d'un univers (séparés)."""
        flag = ProMessageBuilder.FLAGS.get(universe, universe)

        # Filtre premium
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
            return ""  # pas d'affichage si aucun signal premium

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
        """Alias rétro-compatible pour le bot_loop existant."""
        return ProMessageBuilder.premium_block(opps, universe, top_n=top_n)

    @staticmethod
    def market_summary(opps_all: List, total_analyzed: int, premium_count: int) -> str:
        strong_buy = sum(1 for o in opps_all if o.action == "STRONG_BUY")
        buy = sum(1 for o in opps_all if o.action == "BUY")
        strong_sell = sum(1 for o in opps_all if o.action == "STRONG_SELL")
        sell = sum(1 for o in opps_all if o.action == "SELL")

        return (
            f"\n📊 <b>RÉSUMÉ GLOBAL</b>\n"
            f"{ProMessageBuilder.DIVIDER}\n"
            f"📈 Analysés : <b>{total_analyzed}</b>\n"
            f"💎 Signaux premium : <b>{premium_count}</b>\n\n"
            f"🟢🟢 Achat fort : <b>{strong_buy}</b>\n"
            f"🟢 Achat : <b>{buy}</b>\n"
            f"🔴 Vente : <b>{sell}</b>\n"
            f"🔴🔴 Vente forte : <b>{strong_sell}</b>"
        )

    @staticmethod
    def alert_flash(opp) -> str:
        """Alerte flash ultra-condensée (les 5-10 meilleurs signaux de la session)."""
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

        lines = [
            f"{emoji} <b>ALERTE — {opp.ticker}</b> · <b>{action_fr}</b>",
            f"{ProMessageBuilder.DIVIDER}",
            f"💵 {opp.price:.2f}$" + (
                f" · 🎯 {'+' if opp.upside_pct>0 else ''}{opp.upside_pct:.0f}%"
                if opp.upside_pct else ""
            ),
        ]
        if opp.ml_proba_up is not None:
            p = opp.ml_proba_up if is_buy else (1 - opp.ml_proba_up)
            dir_ml = "hausse" if is_buy else "baisse"
            lines.append(f"🤖 IA : {p*100:.0f}% {dir_ml} sur 21j")
        lines.append(f"📌 {opp.primary_reason}")
        if opp.stop_loss and opp.take_profit:
            lines.append(
                f"🎯 TP {opp.take_profit:.2f}$ · 🛑 SL {opp.stop_loss:.2f}$"
            )
        if opp.risk_flags:
            lines.append(opp.risk_flags[0])
        return "\n".join(lines)

    @staticmethod
    def footer() -> str:
        return (
            f"\n{ProMessageBuilder.DIVIDER}\n"
            f"🤖 AlphaForge Pro · {datetime.now().strftime('%H:%M')}\n"
            f"🧠 Info uniquement — DYOR"
        )
