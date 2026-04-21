"""
News & sentiment — récupère les dernières news via yfinance + score simple.

Scoring lexical :
- Mots haussiers : +1 chacun (beats, upgrade, buy, strong, record, jump, rally...)
- Mots baissiers : -1 chacun (miss, downgrade, sell, weak, drop, plunge, loss...)
- Score normalisé : [-1, +1]

Cache 30 min pour éviter les appels redondants.
"""
import logging
import time
from functools import lru_cache
from typing import Dict, List, Optional

import yfinance as yf

logger = logging.getLogger(__name__)

_BULL = {
    "beat", "beats", "beating", "upgrade", "upgraded", "buy", "strong",
    "record", "surge", "surges", "jump", "jumps", "rally", "rallies",
    "growth", "grow", "expand", "expands", "bullish", "outperform",
    "gain", "gains", "rise", "rises", "profit", "profits", "exceeds",
    "breakthrough", "milestone", "accelerate", "boost", "boosts",
    "positive", "approval", "approves", "deal", "acquisition",
}

_BEAR = {
    "miss", "misses", "missed", "downgrade", "downgraded", "sell",
    "weak", "weakness", "drop", "drops", "plunge", "plunges",
    "loss", "losses", "decline", "declines", "bearish", "underperform",
    "fall", "falls", "fell", "slump", "slumps", "cut", "cuts",
    "warning", "warn", "lawsuit", "probe", "investigation", "fraud",
    "recall", "bankruptcy", "debt", "concerns", "layoff", "layoffs",
    "disappoint", "disappointing", "slowdown", "default",
}


class NewsFetcher:
    """Fetch + score sentiment des news."""

    def __init__(self, cache_ttl: int = 1800):
        self._cache: Dict[str, tuple] = {}  # ticker -> (t, data)
        self.ttl = cache_ttl

    def fetch(self, ticker: str, limit: int = 5) -> List[Dict]:
        """Retourne les {limit} dernières news {title, publisher, url}."""
        now = time.time()
        if ticker in self._cache:
            t, data = self._cache[ticker]
            if now - t < self.ttl:
                return data

        try:
            raw = yf.Ticker(ticker).news or []
        except Exception as e:
            logger.debug(f"News fetch {ticker}: {e}")
            raw = []

        items = []
        for n in raw[:limit]:
            content = n.get("content", n)
            title = content.get("title") or n.get("title", "")
            publisher = (
                content.get("provider", {}).get("displayName")
                or n.get("publisher", "")
            )
            url = (
                content.get("canonicalUrl", {}).get("url")
                or content.get("clickThroughUrl", {}).get("url")
                or n.get("link", "")
            )
            if title:
                items.append({
                    "title": title,
                    "publisher": publisher,
                    "url": url,
                })

        self._cache[ticker] = (now, items)
        return items

    def sentiment_score(self, ticker: str, limit: int = 10) -> Dict:
        """
        Score de sentiment [-1, +1] basé sur les mots-clés.
        Retourne aussi la news la plus impactante.
        """
        news = self.fetch(ticker, limit=limit)
        if not news:
            return {"score": 0.0, "count": 0, "top_news": None}

        total_score = 0.0
        scored = []
        for item in news:
            title_lower = item["title"].lower()
            bull = sum(1 for w in _BULL if w in title_lower)
            bear = sum(1 for w in _BEAR if w in title_lower)
            item_score = bull - bear
            scored.append((item_score, item))
            total_score += item_score

        # Normalisation : divisé par le nb de news
        normalized = total_score / max(len(news), 1)
        normalized = max(-1.0, min(1.0, normalized / 2))  # scale

        # News la plus impactante (absolu)
        scored.sort(key=lambda x: abs(x[0]), reverse=True)
        top_news = scored[0][1] if scored and scored[0][0] != 0 else (news[0] if news else None)

        return {
            "score": float(normalized),
            "count": len(news),
            "top_news": top_news,
        }


_global_news = NewsFetcher()


def get_news_sentiment(ticker: str) -> Dict:
    """API simple pour les autres modules."""
    return _global_news.sentiment_score(ticker)


def get_top_news(ticker: str, limit: int = 3) -> List[Dict]:
    """Retourne les dernières news brutes."""
    return _global_news.fetch(ticker, limit=limit)
