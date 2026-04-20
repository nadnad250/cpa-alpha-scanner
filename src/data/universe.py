"""Univers boursiers : S&P 500, Nasdaq 100, Euro Stoxx 50."""
import pandas as pd
import requests
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)


def get_sp500_tickers() -> List[str]:
    """Récupère les composants S&P 500 depuis Wikipedia."""
    try:
        url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
        tables = pd.read_html(url)
        tickers = tables[0]["Symbol"].tolist()
        # Nettoyer (BRK.B → BRK-B pour Yahoo Finance)
        return [t.replace(".", "-") for t in tickers]
    except Exception as e:
        logger.error(f"SP500 fetch error: {e}")
        return _sp500_fallback()


def get_nasdaq100_tickers() -> List[str]:
    """Récupère les composants Nasdaq 100."""
    try:
        url = "https://en.wikipedia.org/wiki/Nasdaq-100"
        tables = pd.read_html(url)
        for table in tables:
            cols = [c.lower() for c in table.columns]
            if "ticker" in cols:
                return table.iloc[:, cols.index("ticker")].dropna().tolist()
            if "symbol" in cols:
                return table.iloc[:, cols.index("symbol")].dropna().tolist()
        raise ValueError("Table Nasdaq non trouvée")
    except Exception as e:
        logger.error(f"Nasdaq100 fetch error: {e}")
        return _nasdaq100_fallback()


def get_eurostoxx50_tickers() -> List[str]:
    """Composants Euro Stoxx 50 (Yahoo Finance format)."""
    try:
        url = "https://en.wikipedia.org/wiki/Euro_Stoxx_50"
        tables = pd.read_html(url)
        for table in tables:
            cols = [str(c).lower() for c in table.columns]
            for col_name in ["ticker", "symbol", "isin"]:
                if col_name in cols:
                    data = table.iloc[:, cols.index(col_name)].dropna().tolist()
                    if len(data) > 20:
                        return [str(t).strip() for t in data]
    except Exception as e:
        logger.error(f"EuroStoxx50 fetch error: {e}")
    return _eurostoxx50_fallback()


def get_universe(name: str) -> List[str]:
    """Retourne la liste de tickers selon l'univers demandé."""
    dispatchers = {
        "SP500": get_sp500_tickers,
        "NASDAQ100": get_nasdaq100_tickers,
        "EUROSTOXX50": get_eurostoxx50_tickers,
    }
    fn = dispatchers.get(name.upper())
    if fn is None:
        raise ValueError(f"Univers inconnu: {name}. Choix: {list(dispatchers)}")
    tickers = fn()
    logger.info(f"[{name}] {len(tickers)} tickers chargés")
    return tickers


def get_all_universes() -> Dict[str, List[str]]:
    """Retourne tous les univers."""
    from config.settings import UNIVERSES
    return {u: get_universe(u) for u in UNIVERSES}


# ── Fallbacks statiques (si Wikipedia inaccessible) ──────────────────────────

def _sp500_fallback() -> List[str]:
    return [
        "AAPL","MSFT","AMZN","NVDA","GOOGL","META","TSLA","BRK-B","UNH","XOM",
        "JPM","JNJ","V","PG","MA","HD","CVX","LLY","ABBV","MRK","PEP","KO",
        "BAC","AVGO","COST","TMO","MCD","WMT","CSCO","ABT","CRM","ACN","LIN",
        "NEE","TXN","DHR","PM","RTX","BMY","AMGN","INTU","UPS","MS","HON",
        "ORCL","QCOM","GS","T","BA","CAT","SPGI","BLK","GILD","ISRG","AXP",
        "MDT","DE","SCHW","ADI","REGN","VRTX","MU","LRCX","TGT","SYK","ZTS",
        "NOW","PYPL","SBUX","MMC","CI","CB","EOG","PLD","SO","DUK","CL",
        "NSC","EMR","ETN","APD","WM","HCA","EL","BSX","PGR","AON","ITW","GD",
        "FDX","D","AIG","EW","HLT","SHW","MCO","PSA","CARR","BIIB","A","ECL",
    ]


def _nasdaq100_fallback() -> List[str]:
    return [
        "AAPL","MSFT","AMZN","NVDA","GOOGL","GOOG","META","TSLA","AVGO","ASML",
        "COST","CSCO","ADBE","PEP","NFLX","AMD","TMUS","INTC","INTU","QCOM",
        "CMCSA","HON","TXN","AMAT","ISRG","BKNG","LRCX","VRTX","REGN","MU",
        "ADP","KLAC","MDLZ","GILD","ADI","SNPS","CDNS","MELI","CTAS","ABNB",
        "PANW","CRWD","FTNT","ORLY","KDP","MAR","AZN","MNST","CHTR","IDXX",
        "WDAY","DXCM","EXC","FAST","ODFL","EA","ROST","XEL","DLTR","PAYX",
        "CPRT","KHC","BKR","ON","CEG","TTD","VRSK","ZS","ANSS","SIRI","FANG",
    ]


def _eurostoxx50_fallback() -> List[str]:
    return [
        "ADS.DE","AIR.PA","ALV.DE","ASML.AS","AZN.L","BAS.DE","BAYN.DE",
        "BBVA.MC","BNP.PA","CRH.L","CS.PA","DG.PA","DTE.DE","ENEL.MI",
        "ENI.MI","EL.PA","FP.PA","IBE.MC","IFX.DE","INGA.AS","ISP.MI",
        "ITX.MC","KER.PA","LIN.DE","MC.PA","MBG.DE","MUV2.DE","OR.PA",
        "ORA.PA","PHIA.AS","SAF.PA","SAN.PA","SAN.MC","SAP.DE","SGO.PA",
        "SIE.DE","STMPA.PA","SU.PA","TTE.PA","UCG.MI","UNA.AS","URW.AS",
        "VIE.PA","VOW3.DE","BN.PA","ABI.BR","KPN.AS","AD.AS","MT.AS",
        "EDF.PA",
    ]
