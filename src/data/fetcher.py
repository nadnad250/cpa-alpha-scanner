"""Récupération des données de prix et fondamentaux via yfinance."""
import os
import logging
import hashlib
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional

import pandas as pd
import numpy as np
import yfinance as yf

logger = logging.getLogger(__name__)

CACHE_DIR = "data/cache"
CACHE_TTL_HOURS = 6


# ── Cache ──────────────────────────────────────────────────────────────────────

def _cache_path(key: str) -> str:
    os.makedirs(CACHE_DIR, exist_ok=True)
    h = hashlib.md5(key.encode()).hexdigest()[:12]
    return os.path.join(CACHE_DIR, f"{h}.pkl")


def _cache_valid(path: str) -> bool:
    if not os.path.exists(path):
        return False
    age = datetime.now() - datetime.fromtimestamp(os.path.getmtime(path))
    return age < timedelta(hours=CACHE_TTL_HOURS)


# ── Prix ───────────────────────────────────────────────────────────────────────

def fetch_prices(tickers: List[str], period: str = "3y") -> pd.DataFrame:
    """Retourne un DataFrame de prix de clôture ajustés."""
    cache_key = f"prices_{'-'.join(sorted(tickers)[:10])}_{period}"
    path = _cache_path(cache_key)
    if _cache_valid(path):
        return pd.read_pickle(path)

    logger.info(f"Téléchargement prix pour {len(tickers)} tickers...")
    try:
        raw = yf.download(
            tickers,
            period=period,
            auto_adjust=True,
            progress=False,
            threads=True,
        )
        if isinstance(raw.columns, pd.MultiIndex):
            prices = raw["Close"]
        else:
            prices = raw[["Close"]]
        prices = prices.dropna(how="all", axis=1)
        prices.to_pickle(path)
        return prices
    except Exception as e:
        logger.error(f"Erreur téléchargement prix: {e}")
        return pd.DataFrame()


def fetch_returns(tickers: List[str], period: str = "3y") -> pd.DataFrame:
    """Retourne les rendements journaliers (log-returns)."""
    prices = fetch_prices(tickers, period)
    if prices.empty:
        return pd.DataFrame()
    returns = np.log(prices / prices.shift(1)).dropna()
    return returns


# ── Fondamentaux ──────────────────────────────────────────────────────────────

def fetch_fundamentals(ticker: str) -> Dict:
    """Récupère les données fondamentales d'une action."""
    cache_key = f"fundamentals_{ticker}"
    path = _cache_path(cache_key)
    if _cache_valid(path):
        import pickle
        with open(path, "rb") as f:
            return pickle.load(f)

    try:
        stock = yf.Ticker(ticker)
        info = stock.info or {}

        # Bilans pour Residual Income Model
        balance = stock.balance_sheet
        income = stock.income_stmt
        cashflow = stock.cashflow

        book_value = _extract_book_value(balance)
        roe_history = _compute_roe_history(balance, income)

        data = {
            "ticker": ticker,
            "price": info.get("currentPrice") or info.get("regularMarketPrice"),
            "book_value_per_share": info.get("bookValue"),
            "shares_outstanding": info.get("sharesOutstanding"),
            "beta": info.get("beta", 1.0),
            "market_cap": info.get("marketCap"),
            "roe": info.get("returnOnEquity"),
            "roe_history": roe_history,
            "book_value_total": book_value,
            "earnings_growth": info.get("earningsGrowth"),
            "revenue_growth": info.get("revenueGrowth"),
            "gross_margin": info.get("grossMargins"),
            "operating_margin": info.get("operatingMargins"),
            "debt_to_equity": info.get("debtToEquity"),
            "current_ratio": info.get("currentRatio"),
            "sector": info.get("sector", "Unknown"),
            "industry": info.get("industry", "Unknown"),
            "currency": info.get("currency", "USD"),
        }

        import pickle
        with open(path, "wb") as f:
            pickle.dump(data, f)
        return data
    except Exception as e:
        logger.warning(f"Fondamentaux {ticker}: {e}")
        return {"ticker": ticker, "error": str(e)}


def _extract_book_value(balance: pd.DataFrame) -> Optional[float]:
    """Extrait la valeur comptable totale depuis le bilan."""
    if balance is None or balance.empty:
        return None
    for col_name in ["Stockholders Equity", "Total Stockholder Equity",
                     "Common Stock Equity", "Total Equity"]:
        if col_name in balance.index:
            vals = balance.loc[col_name].dropna()
            if not vals.empty:
                return float(vals.iloc[0])
    return None


def _compute_roe_history(balance: pd.DataFrame, income: pd.DataFrame) -> List[float]:
    """Calcule l'historique ROE sur les derniers exercices."""
    roes = []
    if balance is None or income is None:
        return roes
    try:
        for net_name in ["Net Income", "Net Income Common Stockholders"]:
            if net_name in income.index:
                net_income = income.loc[net_name]
                break
        else:
            return roes

        for eq_name in ["Stockholders Equity", "Total Stockholder Equity",
                        "Common Stock Equity"]:
            if eq_name in balance.index:
                equity = balance.loc[eq_name]
                break
        else:
            return roes

        common_cols = net_income.index.intersection(equity.index)
        for col in sorted(common_cols)[:4]:
            e = equity.get(col)
            n = net_income.get(col)
            if e and n and e != 0:
                roes.append(float(n / e))
    except Exception:
        pass
    return roes


# ── Facteurs Fama-French ──────────────────────────────────────────────────────

def fetch_fama_french_factors() -> Optional[pd.DataFrame]:
    """
    Récupère les facteurs Fama-French 5 + Momentum.
    Source: pandas-datareader (Kenneth French Data Library).
    """
    cache_key = "ff5_momentum"
    path = _cache_path(cache_key)
    if _cache_valid(path):
        return pd.read_pickle(path)

    try:
        import pandas_datareader.data as web
        ff5 = web.DataReader("F-F_Research_Data_5_Factors_2x3", "famafrench")[0] / 100
        mom = web.DataReader("F-F_Momentum_Factor", "famafrench")[0] / 100
        mom.columns = ["MOM"]
        factors = ff5.join(mom, how="inner")
        factors.index = pd.to_datetime(factors.index.to_timestamp())
        factors.to_pickle(path)
        logger.info(f"Facteurs FF5+MOM: {len(factors)} observations")
        return factors
    except Exception as e:
        logger.error(f"Erreur facteurs FF: {e}")
        return None
