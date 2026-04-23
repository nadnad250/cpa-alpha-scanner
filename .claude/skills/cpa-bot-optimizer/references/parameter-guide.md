# Guide des Paramètres Tunables — CPA Alpha Scanner

Toutes les manettes à disposition pour optimiser le bot, avec leur range sain et l'effet attendu.

## 🎛 Fichier `config/settings.py`

| Paramètre | Range sain | Effet si ↑ | Effet si ↓ | Valeur actuelle |
|-----------|------------|-----------|-----------|----------------|
| `PREMIUM_MIN_SCORE` | 0.30 – 0.60 | Moins de signaux, win rate ↑ | Plus de signaux, win rate ↓ | 0.40 |
| `PREMIUM_MIN_CONFIDENCE` | 0.60 – 0.80 | Signaux très sélectifs | Plus de volume | 0.66 |
| `PREMIUM_MIN_RR` | 1.5 – 3.5 | R/R meilleur, moins de trades | Plus de trades, risque ↑ | 2.2 |
| `TOP_PER_UNIVERSE` | 2 – 10 | Plus de positions par univers | Plus concentré | 4 |
| `MAX_GLOBAL_ALERTS` | 5 – 20 | Plus d'alertes flash | Focus top signaux | 10 |
| `KELLY_FRACTION` | 0.10 – 0.40 | Positions plus grosses (risqué) | Plus conservateur | 0.25 |
| `MAX_POSITION` | 0.05 – 0.20 | Moins de diversification | Plus de diversification | 0.10 |

## 🎛 Poids CPA (tunables sous grande prudence)

| Poids | Composante | Range | Actuel stocks | Actuel commodities |
|-------|-----------|-------|---------------|--------------------|
| W1 | Value Gap (fondamentaux) | 0.10 – 0.50 | 0.35 | 0.15 |
| W2 | Factor Premia (Fama-French) | 0.10 – 0.40 | 0.25 | 0.20 |
| W3 | Mean Reversion (OU) | 0.10 – 0.40 | 0.20 | 0.30 |
| W4 | Information Flow (Kalman) | 0.10 – 0.40 | 0.20 | 0.35 |

**Règle d'or** : la somme doit toujours rester à 1.0. Jamais plus de 0.05 de changement par itération.

## 🎛 Filtres de qualité supplémentaires

| Paramètre | Effet |
|-----------|-------|
| `MIN_VOLUME_RATIO` | Filtre les tickers illiquides (< seuil × moyenne volume) |
| `MAX_VOLATILITY` | Évite les meme stocks / crypto extrêmes |
| `TREND_ALIGNMENT` | Si True, rejette les BUY sous MM200 et SELL au-dessus |
| `REGIME_FILTER` | Si True, ajuste la pondération selon le régime marché |

## 🎛 Paramètres ATR pour stops

Dans `src/models/stop_system.py` ou équivalent :

| Paramètre | Range | Effet |
|-----------|-------|-------|
| Multiplier TP (× ATR) | 1.5 – 4.0 | ↑ = gains plus gros mais moins atteints |
| Multiplier SL (× ATR) | 0.5 – 2.0 | ↑ = tolère plus de drawdown |
| Horizon (jours max) | 10 – 45 | ↑ = plus de temps pour atteindre TP |

## 🎛 Filtres ML

Dans `src/models/opportunity_detector.py` :

```python
# Cohérence ML : rejeter les signaux contradictoires
if final_score > 0 and ml_proba_up < SEUIL_MIN_BUY:   # actuellement 0.48
    return None
if final_score < 0 and ml_proba_up > SEUIL_MAX_SELL:  # actuellement 0.52
    return None
```

- `SEUIL_MIN_BUY` : 0.40 (permissif) à 0.60 (très strict)
- `SEUIL_MAX_SELL` : 0.40 (très strict) à 0.60 (permissif)

## 🔄 Ordre de priorité du tuning

Si plusieurs patterns détectés, procéder dans cet ordre (du moins risqué au plus risqué) :

1. **Seuils de filtrage** (score, confiance, R/R) — effet immédiat, réversible
2. **Désactivation d'univers** — si un univers pollue le win rate
3. **Filtres ML** (proba) — affecte la cohérence
4. **Multiplicateurs ATR** (stops) — affecte le risk management
5. **Poids CPA** — fondamental, à tester avec beaucoup de précaution
6. **Ajout de nouveaux filtres** (volume, volatilité custom, etc.)

## ⚠️ Red Flags — ne jamais faire

- Changer `PREMIUM_MIN_SCORE` de > 0.10 d'un coup
- Passer `PREMIUM_MIN_CONFIDENCE` > 0.80 (élimine tout)
- Pondérations W1-W4 qui ne somment pas à 1.0
- Retirer complètement un filtre ML sans backtest rigoureux
- Réduire R/R sous 1.8 (jamais rentable long-terme)
