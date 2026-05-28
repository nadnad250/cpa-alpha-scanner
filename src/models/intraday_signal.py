"""
Intraday Signal Engine — Opening Range Breakout "Stocks in Play".

Basé sur Zarattini & Aziz (SSRN 4416622 / 4729284) — l'edge intraday le mieux
documenté (Sharpe ~2.8 sur le panier filtré par Relative Volume).

Composantes du signal :
1. Relative Volume (RVOL) — FILTRE CLÉ : volume du jour / moyenne historique même heure.
   Seuls les "stocks in play" (RVOL élevé) ont un edge ORB exploitable.
2. Opening Range Breakout (ORB) — cassure de la 1ère bougie 5m (09:30-09:35 ET).
3. VWAP — confirmation de tendance (prix au-dessus/dessous du VWAP de session).
4. Gap overnight — biais directionnel (gap-and-go).

Sortie : IntradaySignal(direction, strength, rvol, or_high, or_low, vwap, ...).
"""
import logging
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# === Paramètres (overridables via settings) ===
OR_BARS = 1            # nombre de bougies 5m pour l'opening range (1 = 5min, 3 = 15min)
RVOL_MIN = 1.5         # RVOL minimum pour qualifier "stock in play"
RVOL_STRONG = 3.0      # RVOL au-delà duquel le signal est fort
GAP_MIN_PCT = 0.3      # gap overnight minimum (%) pour le biais directionnel


@dataclass
class IntradaySignal:
    ticker: str
    direction: int               # +1 long, -1 short, 0 pas de signal
    strength: float              # [0, 1] force du setup
    rvol: float                  # relative volume
    last_price: float
    or_high: float
    or_low: float
    vwap: float
    gap_pct: float
    atr5m: float                 # ATR sur bougies 5m (pour stops)
    reason: str = ""


def _session_groups(df: pd.DataFrame):
    """Découpe par jour de bourse, retourne liste (date, sous-df) triée."""
    try:
        groups = list(df.groupby(df.index.normalize()))
        return groups
    except Exception:
        return []


def _compute_vwap(session_df: pd.DataFrame) -> float:
    """VWAP de la session : Σ(typical_price × volume) / Σ(volume)."""
    tp = (session_df["High"] + session_df["Low"] + session_df["Close"]) / 3.0
    vol = session_df["Volume"].replace(0, np.nan)
    denom = vol.sum()
    if not denom or denom <= 0:
        return float(session_df["Close"].iloc[-1])
    return float((tp * session_df["Volume"]).sum() / denom)


def _atr_5m(session_df: pd.DataFrame, period: int = 14) -> float:
    """True Range moyen sur bougies 5m."""
    h, l, c = session_df["High"], session_df["Low"], session_df["Close"]
    prev_c = c.shift(1)
    tr = pd.concat([
        (h - l),
        (h - prev_c).abs(),
        (l - prev_c).abs(),
    ], axis=1).max(axis=1).dropna()
    if len(tr) == 0:
        return float((h - l).mean())
    return float(tr.tail(period).mean())


def _relative_volume(sessions, current_day, n_bars_elapsed: int) -> float:
    """
    RVOL = volume cumulé aujourd'hui (n_bars premières bougies)
           / moyenne du volume cumulé sur les mêmes n_bars des sessions passées.
    """
    if not sessions:
        return 1.0
    # Volume cumulé du jour courant sur les n_bars premières bougies
    today_df = None
    hist_cumvols = []
    for day, grp in sessions:
        cum = float(grp["Volume"].head(n_bars_elapsed).sum())
        if day == current_day:
            today_df = cum
        else:
            if cum > 0:
                hist_cumvols.append(cum)
    if today_df is None or not hist_cumvols:
        return 1.0
    baseline = np.mean(hist_cumvols[-14:])  # 14 dernières sessions
    if baseline <= 0:
        return 1.0
    return float(today_df / baseline)


def compute_intraday_signal(
    ticker: str,
    df_5m: pd.DataFrame,
    or_bars: int = OR_BARS,
    rvol_min: float = RVOL_MIN,
) -> Optional[IntradaySignal]:
    """
    Calcule le signal ORB pour un ticker à partir de ses bougies 5m.

    Retourne None si pas assez de données ou pas de setup.
    """
    if df_5m is None or len(df_5m) < 20:
        return None

    sessions = _session_groups(df_5m)
    if len(sessions) < 3:
        return None

    current_day, today = sessions[-1]
    if len(today) < or_bars + 1:
        return None  # opening range pas encore complet

    # --- Opening Range (premières or_bars bougies) ---
    or_slice = today.head(or_bars)
    or_high = float(or_slice["High"].max())
    or_low = float(or_slice["Low"].min())

    # Prix courant = dernière bougie de la session
    last = today.iloc[-1]
    last_price = float(last["Close"])

    # --- Relative Volume sur le nb de bougies écoulées aujourd'hui ---
    n_elapsed = len(today)
    rvol = _relative_volume(sessions, current_day, n_elapsed)

    # --- VWAP de session ---
    vwap = _compute_vwap(today)

    # --- Gap overnight : close session précédente → open session courante ---
    prev_day, prev = sessions[-2]
    prev_close = float(prev["Close"].iloc[-1])
    today_open = float(today["Open"].iloc[0])
    gap_pct = ((today_open - prev_close) / prev_close * 100.0) if prev_close > 0 else 0.0

    atr5m = _atr_5m(today)

    # ============================================================
    # LOGIQUE DE DÉCISION ORB
    # ============================================================
    # Filtre RVOL : pas de "stock in play" → pas de trade
    if rvol < rvol_min:
        return IntradaySignal(
            ticker=ticker, direction=0, strength=0.0, rvol=rvol,
            last_price=last_price, or_high=or_high, or_low=or_low,
            vwap=vwap, gap_pct=gap_pct, atr5m=atr5m,
            reason=f"RVOL {rvol:.1f}x < {rvol_min} (pas en jeu)",
        )

    direction = 0
    reason = ""

    # Cassure haussière : prix > OR-high ET au-dessus VWAP
    if last_price > or_high and last_price >= vwap:
        direction = 1
        reason = f"Cassure ORB haussière (RVOL {rvol:.1f}x, +VWAP)"
    # Cassure baissière : prix < OR-low ET sous VWAP
    elif last_price < or_low and last_price <= vwap:
        direction = -1
        reason = f"Cassure ORB baissière (RVOL {rvol:.1f}x, -VWAP)"
    else:
        return IntradaySignal(
            ticker=ticker, direction=0, strength=0.0, rvol=rvol,
            last_price=last_price, or_high=or_high, or_low=or_low,
            vwap=vwap, gap_pct=gap_pct, atr5m=atr5m,
            reason="Pas de cassure OR confirmée",
        )

    # Biais directionnel du gap : pénalise si cassure contre le gap
    gap_aligned = (direction > 0 and gap_pct > GAP_MIN_PCT) or \
                  (direction < 0 and gap_pct < -GAP_MIN_PCT)
    gap_against = (direction > 0 and gap_pct < -GAP_MIN_PCT) or \
                  (direction < 0 and gap_pct > GAP_MIN_PCT)

    # --- Force du signal [0, 1] ---
    # RVOL contribue le plus (le filtre clé), gap + distance VWAP en bonus
    rvol_factor = min(1.0, (rvol - rvol_min) / (RVOL_STRONG - rvol_min)) if RVOL_STRONG > rvol_min else 0.5
    vwap_dist = abs(last_price - vwap) / vwap if vwap > 0 else 0.0
    vwap_factor = min(1.0, vwap_dist / 0.02)  # saturation à 2% de distance VWAP

    strength = 0.55 * rvol_factor + 0.25 * vwap_factor
    if gap_aligned:
        strength += 0.20
        reason += " +gap"
    elif gap_against:
        strength *= 0.6   # pénalité cassure contre-gap
        reason += " (contre-gap)"
    strength = float(max(0.0, min(1.0, strength)))

    return IntradaySignal(
        ticker=ticker, direction=direction, strength=strength, rvol=rvol,
        last_price=last_price, or_high=or_high, or_low=or_low,
        vwap=vwap, gap_pct=gap_pct, atr5m=atr5m, reason=reason,
    )
