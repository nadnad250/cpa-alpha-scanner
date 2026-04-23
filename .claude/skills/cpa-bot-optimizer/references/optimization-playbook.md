# Playbook d'Optimisation — Techniques de Pros Quant

Techniques éprouvées pour améliorer un bot de trading algorithmique. Trié par niveau de difficulté / risque.

## 🟢 NIVEAU 1 — Optimisations safes (à faire en premier)

### 1.1 Resserrement des filtres d'entrée

**Principe** : moins de trades mais de meilleure qualité.

**Comment** :
- Remonter `PREMIUM_MIN_SCORE` de 0.40 → 0.45 si win rate < 50 %
- Remonter `PREMIUM_MIN_CONFIDENCE` de 0.66 → 0.70 si winners ont conf moyenne > 0.75

**Effet typique** : -30 % de volume, +5-8 points de win rate.

### 1.2 Filtre sectoriel / universe

**Principe** : éliminer les univers qui saignent.

**Comment** :
- Si un univers a win rate < 35 % sur ≥ 10 trades → le retirer de `UNIVERSES`
- Classique : désactiver `CRYPTO` si volatilité extrême ruine les stops

**Effet typique** : amélioration propre mais attention au survivor bias.

### 1.3 Time-stop adaptatif

**Principe** : si un trade ne bouge pas en N jours, le fermer.

**Comment** : dans le tracker, ajouter fermeture forcée à `MAX_HOLD_DAYS` (actuellement 21).
- Si 40 %+ des signals expirent → réduire à 14 jours
- Si gagnants atteignent TP en moyenne à 8 jours → réduire à 15 jours

**Effet typique** : libère du capital plus vite, Sharpe ↑.

## 🟡 NIVEAU 2 — Optimisations intermédiaires

### 2.1 Filtre volumétrique

**Principe** : éviter les tickers illiquides où le slippage tue la stratégie.

**Comment** : ajouter dans `opportunity_detector.py` :

```python
if df['Volume'].tail(20).mean() < MIN_AVG_VOLUME:
    return None  # trop illiquide
```

Seuils :
- Stocks US : volume ≥ 500k/jour
- Stocks EU : volume ≥ 100k/jour
- Crypto : turnover ≥ 10M USD/jour

### 2.2 Filtre spread bid-ask

**Principe** : éviter les tickers avec spread large.

**Formule** : `spread_pct = (ask - bid) / mid`
- Rejeter si `spread_pct > 0.5 %` (actions liquides)
- Rejeter si `spread_pct > 2 %` (small caps)

### 2.3 Corrélation entre signaux

**Principe** : éviter d'ouvrir 5 positions hyper-corrélées (tech US en même temps).

**Comment** :
- Calculer matrice corrélation 60 jours entre tickers actifs
- Rejeter un nouveau signal si `max(corr avec positions existantes) > 0.85`

**Effet** : réduit le drawdown maximal en cas de flash crash sectoriel.

### 2.4 Ajustement ATR dynamique

**Principe** : stop-loss adapté au régime de volatilité.

**Formule actuelle** : `SL = entry - K × ATR(14)` avec K = 1.0-1.5

**Amélioration** :
- Vol basse (ATR/prix < 1.5 %) → K = 1.0 (stop serré)
- Vol moyenne (1.5-3 %) → K = 1.5
- Vol haute (> 3 %) → K = 2.0 (stop large)

## 🔴 NIVEAU 3 — Optimisations avancées (avec précaution)

### 3.1 Régime de marché (bull / bear / chop)

**Principe** : désactiver certaines stratégies selon le régime.

**Détection** :
- Bull : SP500 > MM200 ET MM50 > MM200 ET VIX < 18
- Bear : SP500 < MM200 ET VIX > 25
- Chop : entre les deux

**Règles** :
- Bull → tous les signaux, poids `info_flow` majoré
- Chop → poids `mean_reversion` majoré
- Bear → désactiver BUY signals sauf `STRONG_BUY` avec conf > 0.80

### 3.2 Rebalancement des poids CPA selon performance

**Principe** : augmenter progressivement le poids des composantes qui réussissent.

**Comment** (lourd, 50+ trades par composante) :
- Analyser quel signal (value_gap vs info_flow) explique le mieux les gagnants
- Ajuster W1-W4 de ±0.03 en faveur du signal dominant
- Backtester après chaque ajustement

### 3.3 Machine learning sur les stats du bot

**Principe** : entraîner un classifieur secondaire qui apprend à distinguer les winners des losers.

**Features** : tous les champs signals.json (score, confidence, sector, universe, vol, etc.)

**Label** : status (tp_hit / sl_hit)

**Modèle** : logistic regression ou XGBoost simple

**Usage** : rejeter un signal si le classifieur prédit `P(loss) > 0.6`

**Risque** : overfitting si < 200 trades.

### 3.4 Position sizing adaptatif (Kelly confiant)

**Principe** : taille proportionnelle à la confiance.

**Formule** : `position = base × (confidence - 0.5) × 2`
- confidence 0.70 → 40 % du base
- confidence 0.85 → 70 % du base
- confidence > 0.90 → 80 % (cap)

## 🎯 Métriques à surveiller

Après chaque tuning, vérifier que :

| Métrique | Seuil bon | Seuil alarme |
|----------|-----------|--------------|
| Win rate | > 52 % | < 45 % |
| Profit factor | > 1.4 | < 1.1 |
| Sharpe annualisé | > 1.2 | < 0.5 |
| Max drawdown | < -15 % | > -25 % |
| Expectancy | > +0.5 %/trade | < 0 %/trade |
| Hit rate TP sur gagnants | > 60 % | < 40 % |

## 🚨 Signaux d'alarme qui imposent un rollback immédiat

- Win rate chute > 10 points après un tuning
- Profit factor < 0.9 sur 10 trades post-tuning
- Drawdown > -20 % sur 30 jours
- Expectancy négative persistante

En cas de rollback : `git revert <commit>` puis re-push.
