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
# Univers réduit (~130 tickers NDX + movers) → on calibre pour
# laisser passer ~5-10 premium par scan (ratio ~10-15% des opps brutes).
# Test du 28/04 : 60 opps brutes / 98 analysés, 0 premium avec 0.42/0.72/2.8 trop strict.
# Recalibrés pour le scoring ORB (28/05) : l'ORB produit RR≈2.2 et un score
# qui démarre à 0.20 (baseline cassure) + 0.80×strength.
PREMIUM_MIN_SCORE      = 0.32     # 0.38 → 0.32 : laisse passer les bons setups ORB
PREMIUM_MIN_CONFIDENCE = 0.68     # inchangé : exige un setup confirmé
PREMIUM_MIN_RR         = 2.0      # 2.5 → 2.0 : l'ORB cible 2.2R (sinon tout filtré)
TOP_PER_UNIVERSE       = 10       # un seul univers maintenant
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

# === VIX GATING (B2) — capital preservation en risk-off ===
# Si VIX > VIX_RISK_OFF, on désactive les nouveaux SHORT (squeeze risk)
# et on divise la taille des positions par 2.
VIX_RISK_OFF           = 25.0
VIX_PANIC              = 35.0     # > VIX_PANIC : aucun nouveau signal envoyé

# === TRAILING BREAK-EVEN (B3) ===
# Quand le live_price atteint TRAIL_TRIGGER_PCT × (TP - Entry), on remonte
# le SL au prix d'entrée (verrouille no-loss).
TRAIL_TRIGGER_PCT      = 0.50     # 50% du chemin vers TP

# === STRATÉGIE INTRADAY ORB (Opening Range Breakout "Stocks in Play") ===
# Remplace l'ancien modèle CPA/fondamental (0% win rate, 92% trades flat).
# Edge documenté : Zarattini & Aziz (SSRN 4416622/4729284), Sharpe ~2.8.
STRATEGY_MODE          = "intraday_orb"   # "intraday_orb" | "cpa" (legacy)
ORB_BARS               = 1        # bougies 5m pour l'opening range (1=5min, 3=15min)
RVOL_MIN               = 1.5      # Relative Volume min pour "stock in play"
INTRADAY_HISTORY_DAYS  = 20       # jours de 5m pour baseline RVOL (~14 sessions)

# === HORIZON INTRADAY ===
# ORB : on tient de l'ouverture jusqu'au close (~6.5h de session).
# Le time-stop ferme la position le jour même (pas d'overnight = edge intraday).
HORIZON_HOURS          = 7        # ≈ une session US (09:30→16:00 + marge)
MAX_HOLD_HOURS         = 7        # alias explicite

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

# Poids CPA — INTRADAY (Bug #4 : fix biais all-SELL)
# Ancien (swing/multi-day) : 0.35 / 0.25 / 0.20 / 0.20
# Le OU mean-reversion (W3) crée un biais SELL structurel sur le NASDAQ
# car les NDX caps sont quasi-toujours au-dessus de leur moyenne long-terme.
# Sur intraday, momentum (info_flow Kalman) prime largement sur value/OU.
W1 = 0.15   # Value Gap            (0.35 → 0.15) : fondamental compte peu sur 24h
W2 = 0.30   # Factor Premia        (0.25 → 0.30) : momentum FF/MOM moyen-terme
W3 = 0.10   # Mean Reversion (OU)  (0.20 → 0.10) : réduit pour éviter biais SELL
W4 = 0.45   # Information Flow     (0.20 → 0.45) : KALMAN = ROI de l'intraday

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
