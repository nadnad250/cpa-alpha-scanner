"""
Agent Reporter — génère les rapports et orchestre les notifications Telegram.
"""
import logging
import json
import os
from datetime import datetime
from typing import List, Dict, Optional

from src.models.cpa import CPAResult
from src.notifications.telegram_bot import TelegramNotifier
from config.settings import TOP_N_SIGNALS, ALPHA_THRESHOLD

logger = logging.getLogger(__name__)

REPORTS_DIR = "data/reports"


class ReporterAgent:
    """
    Formate et envoie les rapports CPA via Telegram.
    Sauvegarde aussi les résultats en JSON local.
    """

    def __init__(self):
        self.notifier = TelegramNotifier()
        os.makedirs(REPORTS_DIR, exist_ok=True)

    def report(
        self,
        results_by_universe: Dict[str, List[CPAResult]],
        send_telegram: bool = True,
    ) -> str:
        """Génère et envoie le rapport complet."""
        report_text = self._build_text_report(results_by_universe)

        # Sauvegarde locale JSON
        self._save_json(results_by_universe)

        # Envoi Telegram
        if send_telegram:
            ok = self.notifier.send_daily_report(
                results_by_universe, top_n=TOP_N_SIGNALS
            )
            if ok:
                logger.info("Rapport Telegram envoyé")
            else:
                logger.error("Échec envoi Telegram")

        return report_text

    def alert_strong_signals(
        self,
        results: List[CPAResult],
        threshold: float = 0.20,
    ):
        """Envoie des alertes instantanées pour les signaux très forts."""
        strong = [r for r in results if abs(r.alpha) >= threshold]
        for r in strong[:5]:  # max 5 alertes
            self.notifier.send_alert(
                ticker=r.ticker,
                alpha=r.alpha,
                reason=self._signal_reason(r),
                price=r.price,
                upside=r.upside_pct,
            )

    def _build_text_report(
        self,
        results_by_universe: Dict[str, List[CPAResult]],
    ) -> str:
        """Construit le rapport texte complet."""
        lines = [
            "=" * 60,
            f"RAPPORT CPA — {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "=" * 60,
        ]
        for universe, results in results_by_universe.items():
            if not results:
                continue
            top = sorted(results, key=lambda r: r.alpha, reverse=True)[:TOP_N_SIGNALS]
            lines.append(f"\n{'─'*40}")
            lines.append(f"UNIVERS: {universe} ({len(results)} analysés)")
            lines.append(f"{'─'*40}")
            lines.append(
                f"{'#':<3} {'Ticker':<10} {'Alpha':>8} "
                f"{'VG':>7} {'FF':>7} {'OU':>7} {'KF':>7} "
                f"{'Conf':>6} {'Sect':<20}"
            )
            lines.append("-" * 80)
            for i, r in enumerate(top, 1):
                lines.append(
                    f"{i:<3} {r.ticker:<10} {r.alpha:>+8.4f} "
                    f"{r.value_gap or 0:>7.3f} "
                    f"{r.factor_premia or 0:>7.3f} "
                    f"{r.mean_reversion or 0:>7.3f} "
                    f"{r.info_flow or 0:>7.3f} "
                    f"{r.confidence:>6.0%} "
                    f"{r.sector[:20]:<20}"
                )
        return "\n".join(lines)

    def _save_json(self, results_by_universe: Dict[str, List[CPAResult]]):
        """Sauvegarde les résultats en JSON."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        filepath = os.path.join(REPORTS_DIR, f"cpa_{timestamp}.json")
        data = {}
        for universe, results in results_by_universe.items():
            data[universe] = [
                {
                    "ticker": r.ticker,
                    "alpha": r.alpha,
                    "confidence": r.confidence,
                    "price": r.price,
                    "intrinsic_value": r.intrinsic_value,
                    "upside_pct": r.upside_pct,
                    "value_gap": r.value_gap,
                    "factor_premia": r.factor_premia,
                    "mean_reversion": r.mean_reversion,
                    "info_flow": r.info_flow,
                    "kelly_position": r.kelly_position,
                    "sector": r.sector,
                    "computed_at": r.computed_at,
                }
                for r in results
            ]
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        logger.info(f"Rapport JSON sauvegardé: {filepath}")

    @staticmethod
    def _signal_reason(r: CPAResult) -> str:
        """Résumé textuel du signal le plus fort."""
        components = {
            "Value Gap": r.value_gap or 0,
            "Factor Premia": r.factor_premia or 0,
            "Mean Reversion": r.mean_reversion or 0,
            "Info Flow": r.info_flow or 0,
        }
        dominant = max(components, key=lambda k: abs(components[k]))
        val = components[dominant]
        direction = "sous-évalué" if val > 0 else "sur-évalué"
        return f"{dominant} ({val:+.3f}) → {direction}"
