"""
Agent Scanner — parcourt tout l'univers boursier et calcule les signaux CPA.

Gère la parallélisation, le cache, et les erreurs par action.
"""
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Optional, Tuple
from datetime import datetime

import numpy as np
import pandas as pd

from src.data.universe import get_universe
from src.data.fetcher import fetch_prices, fetch_fundamentals, fetch_fama_french_factors
from src.models.cpa import CPACalculator, CPAResult
from config.settings import (
    DATA_PERIOD, TOP_N_SIGNALS, ALPHA_THRESHOLD,
    W1, W2, W3, W4, LAMBDA_RISK, RISK_FREE_RATE, KELLY_FRACTION,
)

logger = logging.getLogger(__name__)

MAX_WORKERS = 8          # threads parallèles
BATCH_SIZE = 20          # tickers par batch pour yfinance


class ScannerAgent:
    """
    Agent principal de scan.

    Workflow:
    1. Charge l'univers de tickers
    2. Télécharge les prix en batch
    3. Télécharge les fondamentaux en parallèle
    4. Calcule le CPA pour chaque titre
    5. Retourne le classement trié par alpha
    """

    def __init__(self, universe: str = "SP500"):
        self.universe = universe
        self.calculator = CPACalculator(
            w1=W1, w2=W2, w3=W3, w4=W4,
            lambda_risk=LAMBDA_RISK,
            risk_free=RISK_FREE_RATE,
            kelly_fraction=KELLY_FRACTION,
        )
        self.ff_factors: Optional[pd.DataFrame] = None
        self.results: List[CPAResult] = []

    def run(self, max_tickers: Optional[int] = None) -> List[CPAResult]:
        """Lance le scan complet de l'univers."""
        start_time = datetime.now()
        logger.info(f"[ScannerAgent] Démarrage scan {self.universe}")

        # 1. Univers
        tickers = get_universe(self.universe)
        if max_tickers:
            tickers = tickers[:max_tickers]
        logger.info(f"[ScannerAgent] {len(tickers)} tickers à analyser")

        # 2. Facteurs Fama-French
        logger.info("[ScannerAgent] Chargement facteurs FF5+MOM...")
        self.ff_factors = fetch_fama_french_factors()

        # 3. Prix en batch
        logger.info("[ScannerAgent] Téléchargement des prix...")
        all_prices = self._fetch_prices_batched(tickers)

        # 4. Benchmark (SPY ou MSCI pour Eurostoxx)
        benchmark = self._get_benchmark()

        # 5. Analyse en parallèle
        logger.info("[ScannerAgent] Calcul CPA en parallèle...")
        self.results = self._analyze_parallel(tickers, all_prices, benchmark)

        # 6. Tri
        self.results.sort(key=lambda r: r.alpha, reverse=True)

        elapsed = (datetime.now() - start_time).seconds
        logger.info(
            f"[ScannerAgent] Terminé en {elapsed}s — "
            f"{len(self.results)} résultats"
        )
        return self.results

    def top_signals(self, n: int = TOP_N_SIGNALS, threshold: float = ALPHA_THRESHOLD) -> List[CPAResult]:
        """Retourne les N meilleurs signaux au-dessus du seuil."""
        return [r for r in self.results if r.alpha >= threshold][:n]

    def bottom_signals(self, n: int = 10) -> List[CPAResult]:
        """Retourne les N pires signaux (vente/éviter)."""
        return sorted(self.results, key=lambda r: r.alpha)[:n]

    def _fetch_prices_batched(self, tickers: List[str]) -> Dict[str, pd.Series]:
        """Télécharge les prix par batch pour éviter les timeouts."""
        all_prices = {}
        for i in range(0, len(tickers), BATCH_SIZE):
            batch = tickers[i:i + BATCH_SIZE]
            try:
                prices_df = fetch_prices(batch, period=DATA_PERIOD)
                for t in batch:
                    if t in prices_df.columns:
                        s = prices_df[t].dropna()
                        if len(s) > 30:
                            all_prices[t] = s
            except Exception as e:
                logger.warning(f"Batch {i//BATCH_SIZE} error: {e}")
            time.sleep(0.2)
        logger.info(f"[ScannerAgent] Prix chargés: {len(all_prices)}/{len(tickers)}")
        return all_prices

    def _analyze_parallel(
        self,
        tickers: List[str],
        all_prices: Dict[str, pd.Series],
        benchmark: Optional[pd.Series],
    ) -> List[CPAResult]:
        """Analyse chaque titre en parallèle."""
        results = []
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {
                executor.submit(
                    self._analyze_ticker,
                    t,
                    all_prices.get(t, pd.Series(dtype=float)),
                    benchmark,
                ): t
                for t in tickers
            }
            for future in as_completed(futures):
                ticker = futures[future]
                try:
                    result = future.result(timeout=30)
                    if result:
                        results.append(result)
                except Exception as e:
                    logger.debug(f"{ticker} analysis failed: {e}")
        return results

    def _analyze_ticker(
        self,
        ticker: str,
        prices: pd.Series,
        benchmark: Optional[pd.Series],
    ) -> Optional[CPAResult]:
        """Analyse un seul titre."""
        try:
            fundamentals = fetch_fundamentals(ticker)
            if "error" in fundamentals:
                return None
            if not fundamentals.get("price"):
                return None

            result = self.calculator.compute(
                ticker=ticker,
                prices=prices,
                fundamentals=fundamentals,
                ff_factors=self.ff_factors,
                benchmark_prices=benchmark,
                universe=self.universe,
            )
            result.sector = fundamentals.get("sector", "")
            return result
        except Exception as e:
            logger.debug(f"{ticker}: {e}")
            return None

    def _get_benchmark(self) -> Optional[pd.Series]:
        """Retourne le benchmark selon l'univers."""
        benchmark_map = {
            "SP500": "SPY",
            "NASDAQ100": "QQQ",
            "EUROSTOXX50": "FEZ",
        }
        ticker = benchmark_map.get(self.universe, "SPY")
        try:
            prices = fetch_prices([ticker], period=DATA_PERIOD)
            if ticker in prices.columns:
                return prices[ticker].dropna()
        except Exception:
            pass
        return None
