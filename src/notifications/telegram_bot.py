"""
Notifications Telegram — envoi d'alertes et rapports quotidiens.
"""
import logging
import os
import time
from typing import List, Optional
import requests

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"


class TelegramNotifier:
    """Envoie des messages formatés via l'API Telegram Bot."""

    def __init__(
        self,
        token: Optional[str] = None,
        chat_id: Optional[str] = None,
    ):
        self.token = token or os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID", "")

    def _url(self, method: str) -> str:
        return TELEGRAM_API.format(token=self.token, method=method)

    def send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        """Envoie un message texte."""
        if not self.token or not self.chat_id:
            logger.error("Telegram: token ou chat_id manquant")
            return False
        try:
            resp = requests.post(
                self._url("sendMessage"),
                json={
                    "chat_id": self.chat_id,
                    "text": text,
                    "parse_mode": parse_mode,
                    "disable_web_page_preview": True,
                },
                timeout=15,
            )
            if not resp.ok:
                logger.error(f"Telegram error: {resp.text}")
                return False
            return True
        except Exception as e:
            logger.error(f"Telegram send failed: {e}")
            return False

    def send_chunk(self, text: str, max_length: int = 4096) -> bool:
        """Découpe les longs messages en morceaux."""
        if len(text) <= max_length:
            return self.send_message(text)
        chunks = [text[i:i+max_length] for i in range(0, len(text), max_length)]
        for chunk in chunks:
            if not self.send_message(chunk):
                return False
            time.sleep(0.3)
        return True

    def send_daily_report(
        self,
        results_by_universe: dict,
        top_n: int = 10,
    ) -> bool:
        """Envoie le rapport CPA quotidien complet."""
        from datetime import datetime
        date_str = datetime.now().strftime("%d/%m/%Y %H:%M")

        header = (
            f"<b>🧮 Rapport CPA — {date_str}</b>\n"
            f"<i>Composite Predictive Alpha Scanner</i>\n"
            f"{'─' * 32}\n\n"
        )

        body = ""
        for universe, results in results_by_universe.items():
            if not results:
                continue
            top = sorted(results, key=lambda r: r.alpha, reverse=True)[:top_n]
            body += f"\n<b>📈 {universe} — Top {len(top)}</b>\n\n"
            for i, r in enumerate(top, 1):
                signal_bar = self._signal_bar(r.alpha)
                upside = f" | +{r.upside_pct:.0f}%" if r.upside_pct and r.upside_pct > 0 else ""
                body += (
                    f"{i}. <code>{r.ticker:<8}</code> {signal_bar} "
                    f"α={r.alpha:+.3f}{upside}\n"
                    f"   🎯 Conf:{r.confidence:.0%} | "
                )
                parts = []
                if r.value_gap is not None:
                    parts.append(f"VG={r.value_gap:+.2f}")
                if r.factor_premia is not None:
                    parts.append(f"FF={r.factor_premia:+.2f}")
                if r.mean_reversion is not None:
                    parts.append(f"OU={r.mean_reversion:+.2f}")
                if r.info_flow is not None:
                    parts.append(f"KF={r.info_flow:+.2f}")
                body += " ".join(parts) + "\n\n"

        footer = (
            f"\n{'─' * 32}\n"
            f"<i>⚠️ À titre informatif uniquement. DYOR.</i>\n"
            f"<i>Modèle: RIM+Bayes | FF5+MOM | OU-MLE | Kalman</i>"
        )

        full_message = header + body + footer
        return self.send_chunk(full_message)

    def send_alert(
        self,
        ticker: str,
        alpha: float,
        reason: str,
        price: Optional[float] = None,
        upside: Optional[float] = None,
    ) -> bool:
        """Envoie une alerte instantanée pour un signal fort."""
        emoji = "🚀" if alpha > 0.15 else ("📉" if alpha < -0.15 else "📊")
        msg = (
            f"{emoji} <b>ALERTE CPA — {ticker}</b>\n"
            f"Alpha: <b>{alpha:+.4f}</b>\n"
        )
        if price:
            msg += f"Prix: {price:.2f}\n"
        if upside:
            msg += f"Potentiel: {upside:+.1f}%\n"
        msg += f"Signal: {reason}"
        return self.send_message(msg)

    def send_error(self, error: str) -> bool:
        """Alerte d'erreur système."""
        return self.send_message(f"⛔ <b>Erreur Scanner CPA</b>\n<code>{error}</code>")

    @staticmethod
    def _signal_bar(alpha: float) -> str:
        """Barre visuelle du signal."""
        if alpha > 0.20:
            return "🟢🟢🟢"
        elif alpha > 0.10:
            return "🟢🟢⬜"
        elif alpha > 0.05:
            return "🟢⬜⬜"
        elif alpha > -0.05:
            return "⬜⬜⬜"
        elif alpha > -0.10:
            return "🔴⬜⬜"
        elif alpha > -0.20:
            return "🔴🔴⬜"
        else:
            return "🔴🔴🔴"
