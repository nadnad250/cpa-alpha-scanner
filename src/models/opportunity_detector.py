"""
Détecteur d'opportunités — version corrigée (logique cohérente + filtres stricts).

Combine :
1. CPA (signal quantitatif)
2. ML Ensemble (probabilité 21j)
3. Régime de marché
4. Stop/TP via ATR (volatilité réelle)

Règles de cohérence :
- Une opportunité BUY ne peut pas avoir ml_proba_up < 0.45
- Une opportunité SELL ne peut pas avoir ml_proba_up > 0.55
- Labels alignés avec le SIGNE du composant dominant
"""
import logging
import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import Optional, Dict, List

from .cpa import CPAResult
from .ml_ensemble import MLEnsembleDetector, MLSignal
from .stop_system import compute_stops

try:
    from src.data.news_fetcher import get_news_sentiment
except Exception:
    get_news_sentiment = None

logger = logging.getLogger(__name__)


@dataclass
class Opportunity:
    ticker: str
    score: float
    action: str
    confidence: float
    price: Optional[float] = None
    target_price: Optional[float] = None
    upside_pct: Optional[float] = None

    cpa_alpha: Optional[float] = None
    ml_proba_up: Optional[float] = None
    ml_proba_strong: Optional[float] = None

    primary_reason: str = ""
    secondary_reasons: List[str] = field(default_factory=list)
    risk_flags: List[str] = field(default_factory=list)

    kelly_position: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    atr: Optional[float] = None
    risk_reward: Optional[float] = None

    sector: str = ""
    universe: str = ""

    # News & sentiment
    news_score: Optional[float] = None      # [-1, +1]
    top_news_title: Optional[str] = None
    top_news_url: Optional[str] = None


class OpportunityDetector:
    def __init__(
        self,
        w_cpa: float = 0.50,
        w_ml: float = 0.35,
        w_regime: float = 0.15,
        min_score: float = 0.20,
        min_confidence: float = 0.55,
    ):
        self.w_cpa = w_cpa
        self.w_ml = w_ml
        self.w_regime = w_regime
        self.min_score = min_score
        self.min_confidence = min_confidence
        self.ml = MLEnsembleDetector(horizon=21)

    def detect(
        self,
        cpa_result: CPAResult,
        prices: pd.Series,
        fundamentals: Dict,
    ) -> Optional[Opportunity]:
        if cpa_result.confidence < 0.3:
            return None

        cpa_score = np.tanh(cpa_result.alpha * 3)
        ml_signal = self.ml.fit_predict(prices, fundamentals)
        ml_score = ml_signal.ensemble_score if ml_signal else 0.0
        ml_conf = ml_signal.confidence if ml_signal else 0.5
        ml_proba_up = ml_signal.proba_up if ml_signal else 0.5

        regime_score = self._regime_score(prices, cpa_result)

        # Sentiment des news (optionnel mais utile)
        news_info = {"score": 0.0, "count": 0, "top_news": None}
        if get_news_sentiment:
            try:
                news_info = get_news_sentiment(cpa_result.ticker)
            except Exception as e:
                logger.debug(f"News {cpa_result.ticker}: {e}")
        news_score = news_info.get("score", 0.0)

        # Score final incluant 10% sur les news
        final_score = (
            self.w_cpa * cpa_score
            + self.w_ml * ml_score
            + self.w_regime * regime_score
            + 0.10 * news_score   # bonus/malus news
        )

        confidence = (
            0.4 * cpa_result.confidence
            + 0.4 * ml_conf
            + 0.2 * min(1.0, regime_score + 0.5)
        )

        # Seuil
        if abs(final_score) < self.min_score or confidence < self.min_confidence:
            return None

        # COHÉRENCE ML : rejeter les signaux contradictoires
        if final_score > 0 and ml_proba_up < 0.45:
            return None  # BUY rejeté si ML bearish
        if final_score < 0 and ml_proba_up > 0.55:
            return None  # SELL rejeté si ML bullish

        action = self._decide_action(final_score)

        opp = Opportunity(
            ticker=cpa_result.ticker,
            score=float(final_score),
            action=action,
            confidence=float(confidence),
            price=cpa_result.price,
            target_price=cpa_result.intrinsic_value,
            upside_pct=cpa_result.upside_pct,
            cpa_alpha=cpa_result.alpha,
            ml_proba_up=ml_proba_up,
            ml_proba_strong=ml_signal.proba_strong_up if ml_signal else None,
            kelly_position=cpa_result.kelly_position,
            sector=cpa_result.sector,
            universe=cpa_result.universe,
        )

        # Stop / TP via ATR (plus précis que vol simple)
        if cpa_result.price:
            stops = compute_stops(prices, cpa_result.price, action)
            opp.stop_loss = stops["stop_loss"]
            opp.take_profit = stops["take_profit"]
            opp.atr = stops["atr"]
            opp.risk_reward = stops["risk_reward"]

        opp.primary_reason, opp.secondary_reasons = self._build_reasons(
            cpa_result, ml_signal, regime_score, final_score
        )
        opp.risk_flags = self._risk_flags(prices, fundamentals)

        # News
        opp.news_score = float(news_score)
        top_news = news_info.get("top_news")
        if top_news:
            opp.top_news_title = top_news.get("title", "")[:100]
            opp.top_news_url = top_news.get("url", "")

        return opp

    def _decide_action(self, score: float) -> str:
        if score > 0.40:
            return "STRONG_BUY"
        elif score > 0.20:
            return "BUY"
        elif score > -0.20:
            return "HOLD"
        elif score > -0.40:
            return "SELL"
        else:
            return "STRONG_SELL"

    def _regime_score(self, prices: pd.Series, cpa: CPAResult) -> float:
        if len(prices) < 63:
            return 0.0
        returns = np.log(prices / prices.shift(1)).dropna()
        score = 0.0
        ret_3m = float(returns.tail(63).sum())
        score += np.clip(ret_3m * 2, -0.5, 0.5)
        vol = float(returns.tail(21).std() * np.sqrt(252))
        if vol < 0.30:
            score += 0.2
        elif vol > 0.60:
            score -= 0.3
        dd = (prices.tail(63) / prices.tail(63).cummax() - 1).min()
        if dd > -0.10:
            score += 0.15
        return float(np.clip(score, -1, 1))

    def _build_reasons(
        self, cpa: CPAResult, ml: Optional[MLSignal],
        regime: float, final_score: float,
    ) -> tuple:
        """Labels cohérents avec le SIGNE de chaque composant."""
        # Label selon signe : positif = acheter, négatif = éviter
        labels_pos = {
            "value": "Sous-évaluée vs fondamentaux (potentiel hausse)",
            "factor": "Qualité fondamentale forte (ROE/marges)",
            "mean_rev": "Correction excessive — rebond attendu",
            "info": "Momentum positif soutenu",
        }
        labels_neg = {
            "value": "Surévaluée vs fondamentaux (risque baisse)",
            "factor": "Fondamentaux dégradés (marges/ROE faibles)",
            "mean_rev": "Tendance étendue — correction attendue",
            "info": "Momentum négatif / flux vendeur",
        }

        components = {
            "value": cpa.value_gap or 0,
            "factor": cpa.factor_premia or 0,
            "mean_rev": cpa.mean_reversion or 0,
            "info": cpa.info_flow or 0,
        }

        # Composant dominant cohérent avec le score final
        if final_score > 0:
            candidates = {k: v for k, v in components.items() if v > 0}
            labels = labels_pos
        else:
            candidates = {k: v for k, v in components.items() if v < 0}
            labels = labels_neg

        if not candidates:
            candidates = components
            labels = labels_pos if final_score > 0 else labels_neg

        dominant = max(candidates, key=lambda k: abs(candidates[k]))
        primary = labels[dominant]

        # Raisons secondaires
        secondary = []
        if ml:
            if final_score > 0 and ml.proba_up > 0.60:
                secondary.append(f"IA : {ml.proba_up*100:.0f}% hausse sur 21 jours")
            if final_score < 0 and ml.proba_up < 0.40:
                secondary.append(f"IA : {(1-ml.proba_up)*100:.0f}% baisse sur 21 jours")
            if final_score > 0 and ml.proba_strong_up > 0.50:
                secondary.append(f"Probabilité +5% : {ml.proba_strong_up*100:.0f}%")

        if cpa.upside_pct is not None:
            if final_score > 0 and cpa.upside_pct > 15:
                secondary.append(f"Potentiel théorique +{cpa.upside_pct:.0f}%")
            elif final_score < 0 and cpa.upside_pct < -15:
                secondary.append(f"Surcote théorique {cpa.upside_pct:.0f}%")

        if regime > 0.3:
            secondary.append("Régime de marché favorable")
        elif regime < -0.3:
            secondary.append("Régime de marché défavorable")

        return primary, secondary

    def _risk_flags(self, prices: pd.Series, fundamentals: Dict) -> List[str]:
        flags = []
        returns = np.log(prices / prices.shift(1)).dropna()
        if len(returns) >= 21:
            vol = returns.tail(21).std() * np.sqrt(252)
            if vol > 0.6:
                flags.append(f"⚠️ Haute volatilité ({vol*100:.0f}% ann.)")
        if len(prices) >= 252:
            dd = float((prices.tail(252) / prices.tail(252).cummax() - 1).min())
            if dd < -0.30:
                flags.append(f"⚠️ Drawdown récent {dd*100:.0f}%")
        debt_eq = fundamentals.get("debt_to_equity") or 0
        if debt_eq and debt_eq > 200:
            flags.append(f"⚠️ Dette élevée (D/E {debt_eq:.0f}%)")
        op_margin = fundamentals.get("operating_margin") or 0.1
        if op_margin < 0:
            flags.append("⚠️ Rentabilité opérationnelle négative")
        return flags
