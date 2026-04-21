"""Configuration centrale — variables d'environnement et constantes."""
import os

# === Telegram ===
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# === Marchés ===
UNIVERSES = ["SP500", "NASDAQ100", "DOW30", "EUROSTOXX50", "CAC40", "DAX40", "FTSE100"]

# Seuils "crème de la crème" — n'envoie QUE les signaux premium
PREMIUM_MIN_SCORE = 0.35          # score composé |.| > 0.35
PREMIUM_MIN_CONFIDENCE = 0.65     # confiance > 65%
PREMIUM_MIN_RR = 2.0              # risk/reward >= 2
TOP_PER_UNIVERSE = 5              # max 5 BUY + 5 SELL par univers
MAX_GLOBAL_ALERTS = 10            # max 10 alertes flash globales/cycle

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
