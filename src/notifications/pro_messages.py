"""
Messages Telegram ultra-pro — simples, clairs, actionnables.
Une phrase = une décision. Pas de jargon technique visible.
"""
from datetime import datetime
from typing import List, Dict, Optional


class ProMessageBuilder:
    """Construit des messages Telegram lisibles et orientés action."""

    DIVIDER = "━━━━━━━━━━━━━━━━━━━━━━━━"

    @staticmethod
    def startup() -> str:
        now = datetime.now().strftime("%d/%m/%Y — %H:%M")
        return (
            f"🟢 <b>AlphaForge — EN LIGNE</b>\n"
            f"{ProMessageBuilder.DIVIDER}\n"
            f"📅 {now}\n"
            f"<i>Analyse des marchés en cours…</i>"
        )

    @staticmethod
    def market_open_banner() -> str:
        return (
            f"🔔 <b>SIGNAUX DU JOUR</b>\n"
            f"{ProMessageBuilder.DIVIDER}"
        )

    @staticmethod
    def top_signals(results: List, universe: str, top_n: int = 10) -> str:
        """
        Format simple et actionnable :
        #1 🟢 ACHAT AAPL 185.20$ (+12%)
        → Sous-évaluée de 18% selon fondamentaux
        """
        top = sorted(results, key=lambda r: r.alpha, reverse=True)[:top_n]
        if not top:
            return f"ℹ️ Aucun signal {universe}"

        flag = {"SP500": "🇺🇸 SP500", "NASDAQ100": "💻 NASDAQ", "EUROSTOXX50": "🇪🇺 EUROSTOXX"}.get(universe, universe)

        lines = [f"\n<b>{flag}</b>\n"]

        for i, r in enumerate(top, 1):
            action = ProMessageBuilder._action(r.alpha)
            price_str = f"{r.price:.2f}$" if r.price else "?"

            # Potentiel
            upside_str = ""
            if r.upside_pct is not None:
                if r.upside_pct > 0:
                    upside_str = f"  <b>+{r.upside_pct:.0f}%</b> potentiel"
                else:
                    upside_str = f"  <b>{r.upside_pct:.0f}%</b>"

            lines.append(
                f"<b>#{i}</b> {action} <b>{r.ticker}</b> · {price_str}{upside_str}"
            )

            # Une phrase claire : pourquoi ?
            reason = ProMessageBuilder._simple_reason(r)
            lines.append(f"   → <i>{reason}</i>")
            lines.append("")

        return "\n".join(lines)

    @staticmethod
    def market_summary(results_by_universe: Dict) -> str:
        strong_buy = sum(1 for rs in results_by_universe.values() for r in rs if r.alpha > 0.15)
        buy = sum(1 for rs in results_by_universe.values() for r in rs if 0.05 < r.alpha <= 0.15)
        sell = sum(1 for rs in results_by_universe.values() for r in rs if r.alpha < -0.05)
        total = sum(len(r) for r in results_by_universe.values())

        return (
            f"📊 <b>RÉSUMÉ</b>\n"
            f"{ProMessageBuilder.DIVIDER}\n"
            f"📈 {total} actions analysées\n"
            f"🚀 {strong_buy} opportunités fortes\n"
            f"🟢 {buy} achats possibles\n"
            f"🔴 {sell} à éviter"
        )

    @staticmethod
    def alert_flash(ticker: str, alpha: float, reason: str,
                    price: Optional[float] = None,
                    upside: Optional[float] = None) -> str:
        action = ProMessageBuilder._action(alpha)
        msg = [
            f"🚨 <b>ALERTE {ticker}</b>",
            f"{ProMessageBuilder.DIVIDER}",
            f"{action}",
        ]
        if price:
            msg.append(f"💵 Prix : <b>{price:.2f}$</b>")
        if upside:
            msg.append(f"🎯 Potentiel : <b>+{upside:.0f}%</b>")
        msg.append(f"\n💡 <b>Pourquoi ?</b>\n{reason}")
        return "\n".join(msg)

    @staticmethod
    def footer() -> str:
        return (
            f"{ProMessageBuilder.DIVIDER}\n"
            f"🤖 AlphaForge · {datetime.now().strftime('%H:%M')}\n"
            f"<i>⚠️ Information, pas un conseil. Décidez vous-même.</i>"
        )

    # ── Méthodes privées ──────────────────────────────────────────────────────

    @staticmethod
    def _action(alpha: float) -> str:
        """Retourne l'action claire selon le signal."""
        if alpha > 0.20:
            return "🟢🟢 <b>FORT ACHAT</b>"
        elif alpha > 0.10:
            return "🟢 <b>ACHAT</b>"
        elif alpha > 0.05:
            return "🟡 <b>OPPORTUNITÉ</b>"
        elif alpha > -0.05:
            return "⚪ <b>NEUTRE</b>"
        elif alpha > -0.15:
            return "🔴 <b>ÉVITER</b>"
        else:
            return "🔴🔴 <b>VENDRE</b>"

    @staticmethod
    def _simple_reason(r) -> str:
        """
        Une phrase claire et humaine expliquant POURQUOI cette recommandation.
        Pas de jargon : juste l'essentiel.
        """
        components = {
            "value": r.value_gap or 0,
            "factor": r.factor_premia or 0,
            "mean_rev": r.mean_reversion or 0,
            "info": r.info_flow or 0,
        }
        # Trouver le signal dominant
        dominant = max(components, key=lambda k: abs(components[k]))
        val = components[dominant]

        # Phrases claires selon le signal dominant
        if dominant == "value":
            if val > 0.08:
                return f"Très sous-évaluée : prix bien en dessous de sa valeur réelle"
            elif val > 0:
                return f"Sous-évaluée selon ses fondamentaux financiers"
            elif val < -0.08:
                return f"Surévaluée : prix trop élevé vs fondamentaux"
            else:
                return f"Valorisation proche de la valeur intrinsèque"

        elif dominant == "factor":
            if val > 0:
                return f"Profil qualité + valeur favorable historiquement"
            else:
                return f"Profil défavorable selon les facteurs de risque"

        elif dominant == "mean_rev":
            if val > 0:
                return f"Sur-vendue à court terme — rebond attendu"
            else:
                return f"Sur-achetée — correction probable"

        elif dominant == "info":
            if val > 0:
                return f"Momentum fort et élan positif sur les dernières semaines"
            else:
                return f"Tendance baissière et flux d'ordres négatif"

        return "Signal neutre — attendre une meilleure configuration"
