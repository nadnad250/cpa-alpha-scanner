"""
Intraday Detector — convertit un IntradaySignal (ORB) en Opportunity.

Respecte EXACTEMENT le contrat Opportunity attendu par tout le pipeline aval
(Telegram, dashboard, tracker, auto-close, trailing). Les champs fondamentaux
(value_gap, factor_premia…) restent None — le dashboard les gère via getattr.

Stop/TP : basés sur l'Opening Range (pas l'ATR journalier) :
- stop = côté opposé de l'OR (fill-réaliste)
- TP   = entry ± R_target × risk  (R par défaut 2.0)
- risk borné à [0.6%, 3%] du prix (intraday-réaliste)
"""
import logging
from typing import Optional

from .intraday_signal import IntradaySignal
from .opportunity_detector import Opportunity

logger = logging.getLogger(__name__)

# Bornes risk intraday (% du prix d'entrée)
MIN_RISK_PCT = 0.006     # 0.6% min (stop pas trop serré = bruit)
MAX_RISK_PCT = 0.030     # 3% max (au-delà = pas intraday)
R_TARGET = 2.2           # TP = entry ± R_TARGET × risk (marge > PREMIUM_MIN_RR=2.0)


def _decide_action(score: float) -> str:
    """Mêmes seuils que OpportunityDetector pour cohérence aval."""
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


def detect_from_signal(
    sig: IntradaySignal,
    universe: str = "NASDAQ100",
    sector: str = "",
) -> Optional[Opportunity]:
    """
    Mappe un IntradaySignal vers une Opportunity prête pour le pipeline.
    Retourne None si pas de direction (pas de cassure / RVOL insuffisant).
    """
    if sig is None or sig.direction == 0 or sig.strength <= 0:
        return None

    entry = sig.last_price
    if entry <= 0:
        return None

    is_long = sig.direction > 0

    # --- Stop = côté opposé de l'Opening Range ---
    raw_stop = sig.or_low if is_long else sig.or_high
    risk = abs(entry - raw_stop)
    risk_pct = risk / entry if entry > 0 else 0.0

    # Borne le risk à [0.6%, 3%]
    risk_pct = max(MIN_RISK_PCT, min(MAX_RISK_PCT, risk_pct))
    risk = entry * risk_pct

    if is_long:
        stop_loss = entry - risk
        take_profit = entry + R_TARGET * risk
    else:
        stop_loss = entry + risk
        take_profit = entry - R_TARGET * risk

    rr = R_TARGET  # par construction

    # --- Score signé pour _decide_action (seuils 0.20/0.40) ---
    # strength [0,1] → magnitude [0.20, 1.0] ; STRONG dès strength ≥ 0.25
    magnitude = 0.20 + 0.80 * sig.strength
    score = sig.direction * magnitude

    action = _decide_action(score)
    if action == "HOLD":
        return None

    # --- Confidence : doit dépasser PREMIUM_MIN_CONFIDENCE (0.68) ---
    confidence = 0.65 + 0.34 * sig.strength   # [0.65, 0.99]

    # --- Upside théorique (vers le TP) ---
    if is_long:
        upside_pct = (take_profit - entry) / entry * 100.0
    else:
        upside_pct = (entry - take_profit) / entry * 100.0

    opp = Opportunity(
        ticker=sig.ticker,
        score=float(score),
        action=action,
        confidence=float(confidence),
        price=float(entry),
        target_price=float(take_profit),
        upside_pct=round(float(upside_pct), 1),
        cpa_alpha=None,
        ml_proba_up=None,
        ml_proba_strong=None,
        primary_reason=sig.reason or "Opening Range Breakout",
        secondary_reasons=[
            f"RVOL {sig.rvol:.1f}x",
            f"VWAP {'au-dessus' if entry >= sig.vwap else 'en-dessous'}",
            f"Gap {sig.gap_pct:+.1f}%",
        ],
        risk_flags=[],
        kelly_position=None,   # rempli par dashboard_exporter (cap dynamique conf)
        stop_loss=float(stop_loss),
        take_profit=float(take_profit),
        atr=float(sig.atr5m),
        risk_reward=float(rr),
        sector=sector or "",
        universe=universe,
        news_score=None,
        top_news_title=None,
        top_news_url=None,
        # Champs CPA laissés None (dashboard les gère)
        value_gap=None,
        factor_premia=None,
        mean_reversion=None,
        info_flow=None,
    )
    return opp
