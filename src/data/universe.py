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


def get_dow30_tickers() -> List[str]:
    return _dow30_fallback()


def get_cac40_tickers() -> List[str]:
    return _cac40_fallback()


def get_dax40_tickers() -> List[str]:
    return _dax40_fallback()


def get_ftse100_tickers() -> List[str]:
    return _ftse100_fallback()


def get_universe(name: str) -> List[str]:
    """Retourne la liste de tickers selon l'univers demandé."""
    dispatchers = {
        "SP500": get_sp500_tickers,
        "NASDAQ100": get_nasdaq100_tickers,
        "DOW30": get_dow30_tickers,
        "EUROSTOXX50": get_eurostoxx50_tickers,
        "CAC40": get_cac40_tickers,
        "DAX40": get_dax40_tickers,
        "FTSE100": get_ftse100_tickers,
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


def _dow30_fallback() -> List[str]:
    """Dow Jones 30."""
    return [
        "AAPL","AMGN","AXP","BA","CAT","CRM","CSCO","CVX","DIS","DOW",
        "GS","HD","HON","IBM","INTC","JNJ","JPM","KO","MCD","MMM",
        "MRK","MSFT","NKE","PG","TRV","UNH","V","VZ","WBA","WMT",
    ]


def _cac40_fallback() -> List[str]:
    """CAC 40 Paris."""
    return [
        "AC.PA","AI.PA","AIR.PA","ALO.PA","BN.PA","BNP.PA","CA.PA","CAP.PA",
        "CS.PA","DG.PA","DSY.PA","EL.PA","EN.PA","ENGI.PA","ERF.PA","GLE.PA",
        "HO.PA","KER.PA","LR.PA","MC.PA","ML.PA","OR.PA","ORA.PA","PUB.PA",
        "RI.PA","RMS.PA","RNO.PA","SAF.PA","SAN.PA","SGO.PA","STLAP.PA",
        "STMPA.PA","SU.PA","SW.PA","TEP.PA","TTE.PA","URW.AS","VIE.PA",
        "VIV.PA","WLN.PA",
    ]


def _dax40_fallback() -> List[str]:
    """DAX 40 Allemagne."""
    return [
        "ADS.DE","AIR.DE","ALV.DE","BAS.DE","BAYN.DE","BEI.DE","BMW.DE",
        "BNR.DE","CBK.DE","CON.DE","1COV.DE","DB1.DE","DBK.DE","DHER.DE",
        "DTE.DE","DTG.DE","DWNI.DE","EOAN.DE","FME.DE","FRE.DE","HEI.DE",
        "HEN3.DE","HFG.DE","IFX.DE","LIN.DE","MBG.DE","MRK.DE","MTX.DE",
        "MUV2.DE","P911.DE","PAH3.DE","QIA.DE","RWE.DE","SAP.DE","SHL.DE",
        "SIE.DE","SRT3.DE","SY1.DE","VOW3.DE","ZAL.DE",
    ]


def _ftse100_fallback() -> List[str]:
    """FTSE 100 Londres (sous-sélection des majors liquides)."""
    return [
        "AZN.L","SHEL.L","HSBA.L","ULVR.L","RIO.L","GSK.L","BP.L","VOD.L",
        "LLOY.L","BARC.L","NWG.L","DGE.L","REL.L","BATS.L","NG.L","PRU.L",
        "GLEN.L","AAL.L","BHP.L","CRH.L","LSEG.L","RKT.L","CPG.L","TSCO.L",
        "AHT.L","BA.L","EXPN.L","FLTR.L","HL.L","IAG.L","IMB.L","IHG.L",
        "III.L","JD.L","LAND.L","LGEN.L","MRO.L","NXT.L","PRU.L","PSON.L",
        "RR.L","SBRY.L","SDR.L","SGE.L","SGRO.L","SN.L","SSE.L","STAN.L",
        "SVT.L","TW.L","UU.L","WTB.L",
    ]
