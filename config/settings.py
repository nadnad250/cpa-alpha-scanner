"""Configuration centrale — variables d'environnement et constantes."""
import os

# === Telegram ===
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# === Marchés — NASDAQ TOP UNIQUEMENT (intraday agressif) ===
# Focus exclusif : NASDAQ 100 (mega-caps tech haute liquidité, mouvements 2-5%/jour)
# Pas de SP500/Europe/futures/crypto : trop dilué pour 5%/jour.
# Le NDX-100 = ~100 tickers déjà filtrés par capitalisation et volume.
UNIVERSES = ["NASDAQ100"]

# === Seuils "EDGE INTRADAY AGRESSIF" — objectif 5%/jour ===
# Univers réduit (~100 tickers) → on peut relâcher légèrement le score
# mais ON RENFORCE confidence + R/R pour viser quality intraday.
PREMIUM_MIN_SCORE      = 0.42     # 0.48 → 0.42 : univers + petit, signaux + rares
PREMIUM_MIN_CONFIDENCE = 0.72     # 0.70 → 0.72 : exige forte conviction
PREMIUM_MIN_RR         = 2.8      # 2.5 → 2.8 : pour 5%/jour il faut R/R élevé
TOP_PER_UNIVERSE       = 10       # 3 → 10 : un seul univers maintenant
MAX_GLOBAL_ALERTS      = 10       # aligné sur MAX_OPEN_SIGNALS

# Diversification sectorielle — au sein du NASDAQ
# NDX-100 = 60% tech → on doit forcer quelques non-tech (consumer, biotech)
MAX_PER_SECTOR         = 4

# Cap absolu sur positions ouvertes simultanées — TOP DU TOP
MAX_OPEN_SIGNALS       = 10

# === DÉDUP TELEGRAM ===
# Ne jamais renvoyer un signal pour un ticker déjà en position ouverte.
# Le bot scanne 4×/jour, mais ne notifie que les nouveautés.
TELEGRAM_DEDUP_HOURS   = 24       # cooldown par (ticker, action)

# === HORIZON INTRADAY ===
# Le bot opère en intraday : tout signal doit être clôturé dans 24h max.
# Si TP/SL pas atteints en 24h → auto-clôture au prix courant (time stop).
HORIZON_HOURS          = 24
MAX_HOLD_HOURS         = 24       # alias explicite

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
