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

# === Seuils "EDGE PRO" — ultra-sélectifs pour win rate élevé ===
PREMIUM_MIN_SCORE      = 0.45     # score composé |.| > 0.45 (était 0.35)
PREMIUM_MIN_CONFIDENCE = 0.72     # confiance > 72% (était 65%)
PREMIUM_MIN_RR         = 2.5      # risk/reward >= 2.5x (était 2.0)
TOP_PER_UNIVERSE       = 3        # max 3 BUY + 3 SELL par univers (qualité > quantité)
MAX_GLOBAL_ALERTS      = 8        # max 8 alertes flash globales/cycle (était 10)

# === Filtres de qualité supplémentaires ===
MIN_ML_AGREEMENT       = 0.70     # La proba ML doit confirmer fortement la direction
MIN_VOLUME_RATIO       = 0.8      # Volume récent / moyenne ≥ 0.8 (évite illiquide)
MAX_VOLATILITY         = 0.80     # Volatilité annuelle max 80% (évite meme stocks)
TREND_ALIGNMENT        = True     # Signal doit être aligné avec la tendance MM200
REGIME_FILTER          = True     # Rejette les signaux en régime défavorable
CORRELATION_MAX        = 0.85     # Évite 2 signaux trop corrélés (>85%)

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
