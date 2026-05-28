"""
Agent Scanner — moteur INTRADAY Opening Range Breakout (Stocks in Play).

Remplace l'ancien pipeline CPA/fondamental (sans edge intraday) par un moteur
ORB sur bougies 5 minutes. Conserve les signatures publiques (run,
all_universe_opportunities, all_prices) pour que tout le pipeline aval
(Telegram, dashboard, tracker) reste inchangé.

Bascule possible via settings.STRATEGY_MODE :
- "intraday_orb" (défaut) → ORB 5m
- "cpa"                    → ancien modèle fondamental (legacy)
"""
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Optional
from datetime import datetime

import pandas as pd

from src.data.universe import get_universe
from src.data.intraday_fetcher import fetch_intraday_5m
from src.models.intraday_signal import compute_intraday_signal
from src.models.intraday_detector import detect_from_signal
from src.models.opportunity_detector import Opportunity

try:
    from config.settings import STRATEGY_MODE, ORB_BARS, RVOL_MIN, INTRADAY_HISTORY_DAYS
except ImportError:
    STRATEGY_MODE = "intraday_orb"
    ORB_BARS = 1
    RVOL_MIN = 1.5
    INTRADAY_HISTORY_DAYS = 20

logger = logging.getLogger(__name__)
MAX_WORKERS = 6
BATCH_SIZE = 30


class ScannerAgent:
    """Scanner intraday ORB."""

    def __init__(self, universe: str = "NASDAQ100"):
        self.universe = universe
        self.results: list = []                 # compat (vide en mode ORB)
        self.opportunities: List[Opportunity] = []
        self.all_prices: Dict[str, pd.Series] = {}

    def run(self, max_tickers: Optional[int] = None) -> list:
        start = datetime.now()
        logger.info(f"[ScannerAgent] Démarrage INTRADAY ORB — {self.universe}")

        tickers = get_universe(self.universe)
        if max_tickers:
            tickers = tickers[:max_tickers]
        logger.info(f"[ScannerAgent] {len(tickers)} tickers")

        # Fetch bougies 5m (multi-ticker batché)
        intraday_data = self._fetch_intraday_batched(tickers)
        logger.info(f"[ScannerAgent] Données 5m : {len(intraday_data)} tickers")

        # Expose les séries de close 5m pour le filtre corrélation
        self.all_prices = {
            t: df["Close"].dropna()
            for t, df in intraday_data.items()
            if "Close" in df.columns and len(df) > 20
        }

        # Analyse ORB en parallèle
        self.opportunities = self._analyze_parallel(intraday_data)
        self.opportunities.sort(key=lambda o: abs(o.score), reverse=True)

        # results = liste des tickers analysés (métrique d'affichage downstream)
        self.results = list(intraday_data.keys())

        elapsed = (datetime.now() - start).seconds
        logger.info(
            f"[ScannerAgent] {elapsed}s — {len(self.opportunities)} opportunités ORB"
        )
        return self.results

    def all_universe_opportunities(self) -> List[Opportunity]:
        return sorted(self.opportunities, key=lambda o: abs(o.score), reverse=True)

    def top_opportunities(self, n: int = 10) -> List[Opportunity]:
        return self.all_universe_opportunities()[:n]

    # ── Fetch intraday batché ────────────────────────────────────────
    def _fetch_intraday_batched(self, tickers: List[str]) -> Dict[str, pd.DataFrame]:
        out: Dict[str, pd.DataFrame] = {}
        for i in range(0, len(tickers), BATCH_SIZE):
            batch = tickers[i:i + BATCH_SIZE]
            try:
                data = fetch_intraday_5m(batch, period_days=INTRADAY_HISTORY_DAYS)
                out.update(data)
            except Exception as e:
                logger.warning(f"Intraday batch error: {e}")
            time.sleep(0.3)
        return out

    # ── Analyse parallèle ────────────────────────────────────────────
    def _analyze_parallel(self, intraday_data: Dict[str, pd.DataFrame]) -> List[Opportunity]:
        opportunities: List[Opportunity] = []
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {
                executor.submit(self._analyze_one, t, df): t
                for t, df in intraday_data.items()
            }
            for future in as_completed(futures):
                ticker = futures[future]
                try:
                    opp = future.result(timeout=30)
                    if opp:
                        opportunities.append(opp)
                except Exception as e:
                    logger.debug(f"{ticker}: {e}")
        return opportunities

    def _analyze_one(self, ticker: str, df_5m: pd.DataFrame) -> Optional[Opportunity]:
        try:
            sig = compute_intraday_signal(
                ticker, df_5m, or_bars=ORB_BARS, rvol_min=RVOL_MIN,
            )
            if sig is None or sig.direction == 0:
                return None
            return detect_from_signal(sig, universe=self.universe, sector="")
        except Exception as e:
            logger.debug(f"{ticker} analyze fail: {e}")
            return None
