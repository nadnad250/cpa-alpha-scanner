"""Configuration centrale — variables d'environnement et constantes."""
import os

# === Telegram ===
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# === Marchés ===
UNIVERSES = [
    "SP500", "NASDAQ100", "DOW30",
    "EUROSTOXX50", "CAC40", "DAX40", "FTSE100",
    "FUTURES_COMMODITIES",    # NQ, ES, GC (or), CL (pétrole), NG, devises, agri
    "CRYPTO",                 # BTC, ETH, SOL, etc.
]

# === Seuils "EDGE PRO" — qualité > quantité ===
PREMIUM_MIN_SCORE      = 0.48     # 0.40 → 0.48 : exige plus de conviction (+20%)
PREMIUM_MIN_CONFIDENCE = 0.70     # 0.66 → 0.70 : IBM (winner) avait 0.71
PREMIUM_MIN_RR         = 2.5      # 2.2 → 2.5 : seuil standard pros
TOP_PER_UNIVERSE       = 3        # 4 → 3 : qualité > quantité
MAX_GLOBAL_ALERTS      = 8        # 10 → 8 : focus sur les meilleurs

# Diversification sectorielle — max N signaux ouverts par secteur
# Évite 10 signaux tech en même temps (risque concentration)
MAX_PER_SECTOR         = 3

# Cap absolu sur positions ouvertes simultanées — TOP DU TOP
# Le bot peut générer 50 signaux premium, mais seul le top 10 passe.
# Garantit un portefeuille concentré sur la meilleure conviction.
MAX_OPEN_SIGNALS       = 10

# Historique des signaux clôturés conservés dans signals.json
# Évite que le fichier grossisse à l'infini (chaque jour +10-20 clôtures).
# Au-delà, les plus anciens sont retirés mais restent dans data/signals/YYYY-MM-DD.json
MAX_CLOSED_HISTORY     = 200

# === Filtres de qualité (soft — n'éliminent plus, juste pénalisent score) ===
MIN_VOLUME_RATIO       = 0.5      # Relaxé pour futures/crypto
MAX_VOLATILITY         = 1.20     # Crypto peut monter à ~100-120% vol annuelle
TREND_ALIGNMENT        = False    # Désactivé — MM200 trop contraignant pour commodités
REGIME_FILTER          = True
CORRELATION_MAX        = 0.85

# Poids CPA ajustés par type d'actif (futures/crypto = plus technique, moins fondamental)
CPA_WEIGHTS_STOCKS     = (0.35, 0.25, 0.20, 0.20)  # Value, Factor, MeanRev, InfoFlow
CPA_WEIGHTS_COMMODITY  = (0.15, 0.20, 0.30, 0.35)  # Plus de MeanRev + InfoFlow pour futures
CPA_WEIGHTS_CRYPTO     = (0.05, 0.15, 0.35, 0.45)  # Presque 100% technique pour crypto

# === Modèle CPA ===
RISK_FREE_RATE = float(os.getenv("RISK_FREE_RATE", "0.045"))   # 4.5%
COST_OF_EQUITY = float(os.getenv("COST_OF_EQUITY", "0.09"))   # 9%
TERMINAL_GROWTH = 0.025                                          # 2.5%
FORECAST_HORIZON = 5                                             # années

# Poids CPA — optimisés via back-test
W1 = 0.35   # Value Gap
W2 = 0.25   # Factor Premia
W3 = 0.20   # Mean Reversion (OU)
W4 = 0.20   # Information Flow (Kalman)

LAMBDA_RISK = 0.10  # pénalité variance

# === Fama-French ===
FF_ROLLING_WINDOW = 60  # mois pour régression bêta

# === Ornstein-Uhlenbeck ===
OU_LOOKBACK_DAYS = 252  # 1 an de trading

# === Kalman ===
KALMAN_DECAY = 0.95   # delta — demi-vie signal info

# === Kelly ===
KELLY_FRACTION = 0.25   # quart-Kelly (conservateur)
MAX_POSITION = 0.10     # 10% max par position

# === Alertes ===
TOP_N_SIGNALS = 15      # top N actions par univers
ALPHA_THRESHOLD = 0.05  # seuil minimum alpha (5%)

# === Données ===
DATA_PERIOD = "3y"       # période historique yfinance
CACHE_DIR = "data/cache"

# === Dashboard Web ===
# Chemin vers le fichier signals.json du dashboard web.
# Laisser vide ("") pour utiliser le chemin automatique (../vitrine  2/dashboard/data/signals.json)
# Ou définir DASHBOARD_PATH dans .env.local pour personnaliser.
DASHBOARD_PATH = os.getenv("DASHBOARD_PATH", "")
