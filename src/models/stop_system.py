"""
Système avancé Stop-Loss / Take-Profit basé sur ATR + volatilité.

Méthode :
- ATR(14) = Average True Range sur 14 jours → mesure le mouvement typique
- Stop-Loss   = prix - k_sl * ATR  (k_sl ajusté selon volatilité)
- Take-Profit = prix + k_tp * ATR  (R/R ratio >= 2:1 minimum)
- Pour SELL : logique inversée

Bonus :
- Filtre "no-stop trop serré" : min 3% du prix
- Max Stop 15% du prix (évite les coupures traumatiques)
- Risk/Reward calculé explicitement
"""
import numpy as np
import pandas as pd
from typing import Dict


def _atr(prices: pd.Series, period: int = 14) -> float:
    """ATR approximé depuis les Close (pas de High/Low → proxy)."""
    if len(prices) < period + 1:
        return float(prices.iloc[-1]) * 0.02 if len(prices) > 0 else 0.0
    # Proxy ATR : |close[t] - close[t-1]|
    moves = prices.diff().abs().dropna()
    atr = float(moves.tail(period).mean())
    return atr


def _realized_vol(prices: pd.Series, window: int = 21) -> float:
    returns = np.log(prices / prices.shift(1)).dropna()
    if len(returns) < window:
        return 0.02
    return float(returns.tail(window).std())


def compute_stops(
    prices: pd.Series,
    entry_price: float,
    action: str,
    target_rr: float = 2.5,
) -> Dict[str, float]:
    """
    Calcule SL/TP ajustés selon la volatilité (ATR).

    Règles :
    - k_sl adaptatif : 1.5× ATR (faible vol) à 2.5× ATR (haute vol)
    - k_tp = k_sl × target_rr (minimum R/R 2.5:1)
    - SL min 3%, max 15% du prix
    - TP min 5%, max 40% du prix
    """
    atr = _atr(prices, period=14)
    vol = _realized_vol(prices, window=21)

    # k_sl adaptatif selon volatilité annualisée
    vol_ann = vol * np.sqrt(252)
    if vol_ann < 0.25:
        k_sl = 1.5
    elif vol_ann < 0.45:
        k_sl = 2.0
    else:
        k_sl = 2.5

    k_tp = k_sl * target_rr

    is_buy = action in ("BUY", "STRONG_BUY")

    if is_buy:
        stop = entry_price - k_sl * atr
        take = entry_price + k_tp * atr
    else:
        stop = entry_price + k_sl * atr
        take = entry_price - k_tp * atr

    # Contraintes absolues
    min_sl_dist = entry_price * 0.03
    max_sl_dist = entry_price * 0.15
    min_tp_dist = entry_price * 0.05
    max_tp_dist = entry_price * 0.40

    sl_dist = abs(entry_price - stop)
    tp_dist = abs(take - entry_price)

    sl_dist = max(min_sl_dist, min(max_sl_dist, sl_dist))
    tp_dist = max(min_tp_dist, min(max_tp_dist, tp_dist))

    if is_buy:
        stop = entry_price - sl_dist
        take = entry_price + tp_dist
    else:
        stop = entry_price + sl_dist
        take = entry_price - tp_dist

    rr = tp_dist / sl_dist if sl_dist > 0 else 0.0

    return {
        "stop_loss": float(stop),
        "take_profit": float(take),
        "atr": float(atr),
        "risk_reward": float(rr),
    }


def trailing_stop(
    prices: pd.Series,
    entry_price: float,
    current_stop: float,
    action: str,
    trail_atr_k: float = 2.0,
) -> float:
    """
    Stop suiveur : remonte le stop si le prix progresse.
    N'abaisse JAMAIS le stop (on verrouille les gains).
    """
    atr = _atr(prices, period=14)
    current_price = float(prices.iloc[-1])
    is_buy = action in ("BUY", "STRONG_BUY")

    if is_buy:
        new_stop = current_price - trail_atr_k * atr
        return max(current_stop, new_stop)
    else:
        new_stop = current_price + trail_atr_k * atr
        return min(current_stop, new_stop)
