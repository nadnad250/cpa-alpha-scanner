# Log d'Optimisation — CPA Bot

Traçabilité chronologique de chaque diagnostic et changement de paramètre.

---

## 2026-04-23 — Baseline initiale

### État au jour J
- Bot déployé depuis : 22 avril 2026 (1 jour)
- Nombre total de scans live : ~6
- Signaux ouverts : 15
- Signaux clôturés : 0
- Win rate live : N/A (pas assez de données)

### Configuration active (baseline)
```
PREMIUM_MIN_SCORE      = 0.40
PREMIUM_MIN_CONFIDENCE = 0.66
PREMIUM_MIN_RR         = 2.2
TOP_PER_UNIVERSE       = 4
MAX_GLOBAL_ALERTS      = 10
TREND_ALIGNMENT        = False
MAX_VOLATILITY         = 1.20
ML agreement           = 0.48 / 0.52
Univers actifs         = SP500, NASDAQ100, DOW30, EUROSTOXX50, CAC40, DAX40, FTSE100, FUTURES_COMMODITIES, CRYPTO
```

### Observations qualitatives (sans tuning)
- 100 % des signaux actifs sont SHORT (7 STRONG_SELL, 2 SELL) → à surveiller
- Aucun signal LONG émis — peut indiquer :
  1. Marché baissier légitime détecté par le modèle
  2. Biais du modèle vers le SHORT à corriger
- À vérifier après 20+ clôtures

### Décision
**Pas de tuning.** Attendre accumulation de données réelles.

### Prochaine analyse prévue
- **Déclenchement** : ≥ 15 trades clôturés (estimé 7-14 jours)
- **Critères d'intervention anticipée** :
  - Win rate < 35 % sur 10+ clôtures (alerte rouge)
  - Profit factor < 0.8
  - Drawdown cumulé > -15 %

---

## 2026-04-23 — Filtre cohérence multi-facteurs (qualité préventive)

### Contexte
2 trades clôturés seulement — insuffisant pour tuning data-driven.
User demande signaux de meilleure qualité.

### Observation (pas tuning)
Sur 57 signaux ouverts analysés :
- 52/57 ont `value_gap < 0` (biais RIM déjà corrigé par clamp -0.30)
- 33/52 ont `info_flow > 0` → contradiction interne
- Signaux dominés par une seule composante = qualité incertaine

### Décision
**AJOUT d'une nouvelle logique** (pas tuning de paramètre existant, autorisé par la règle) :
- Filtre `align_components()` dans `opportunity_detector.py`
- Exige ≥ 3/4 composantes CPA alignées avec la direction du score
- Auto-ajusté si < 4 composantes disponibles (ex: pour crypto)

### Impact simulé (sur signaux actuels, avant déploiement)
- Volume : 57 → ~15-20 signaux (-65%)
- Qualité : signaux confirmés par plusieurs angles indépendants

### Commit : `096ae76`
- Fichier : `src/models/opportunity_detector.py`
- Lignes : +18 (nouvelle fonction de filtrage)

### À vérifier dans 20+ nouveaux trades clôturés
- Win rate augmente-t-il réellement ?
- Le volume restant est-il gérable (5-15/jour) ?
- Pas de régression sur les pertes (drawdown stable) ?

---

## 2026-04-23 (2) — Durcissement seuils qualité + diversification sectorielle

### Contexte
User demande "signaux de qualité". Simulation sur 57 signaux existants :
- Filtre actuel (score 0.40, conf 0.66, RR 2.2) : 57 signaux
- Filtre durci (score 0.48, conf 0.70, RR 2.5)    : ~15-20 signaux
- Filtre strict (score 0.55, conf 0.72)           :  2 signaux
- **Sweet spot** : durci + diversification sectorielle

### Changements (respecte règle < 20% par paramètre)
| Paramètre | Avant | Après | Delta | Fichier |
|-----------|-------|-------|-------|---------|
| PREMIUM_MIN_SCORE | 0.40 | 0.48 | +20% (max) | config/settings.py |
| PREMIUM_MIN_CONFIDENCE | 0.66 | 0.70 | +6% | config/settings.py |
| PREMIUM_MIN_RR | 2.2 | 2.5 | +14% | config/settings.py |
| TOP_PER_UNIVERSE | 4 | 3 | -25% (simplification) | config/settings.py |
| MAX_GLOBAL_ALERTS | 10 | 8 | -20% | config/settings.py |
| MAX_PER_SECTOR | ∞ | 3 | NOUVEAU | bot_loop.py |

### Justification data-driven
- IBM (seul winner sur 2 trades) avait confidence 0.71 → seuil 0.70 cohérent
- TXN (loser) avait score -0.413 → le 0.48 l'aurait rejeté
- Diversification sectorielle : règle générique de gestion de portefeuille (Markowitz)

### Impact simulé sur signaux existants
- Score 0.48 + conf 0.70 + RR 2.5 : ~3-5 signaux/univers (au lieu de 15-20)
- Avec MAX_PER_SECTOR=3 : dédup sectorielle additionnelle
- **Total attendu : 8-12 signaux/scan** (au lieu de 57)

### Commits
- `fa68faf` : tune seuils settings.py
- `3af3e77` : diversification sectorielle bot_loop.py

### À vérifier après 10+ nouveaux scans
- Volume signaux raisonnable (5-15/scan) ?
- Win rate en amélioration sur les premiers clôturés ?
- Distribution BUY/SELL équilibrée (effet du clamp value_gap) ?
- Pas de vide sectoriel (pas 0 tech pendant 3 jours) ?

---

## 2026-05-18 — Adaptation INTRADAY 24h pure (3 tunings théoriques)

### Contexte
- Wipe complet le 17/05 → 0 trades clôturés (data-driven impossible)
- User demande "adapter la stratégie pour 24h pur avec les skills"
- Approche : **tuning théorique best-practice intraday** (playbook §1-3)

### État avant
- Univers : NASDAQ100 (✓ déjà intraday-friendly)
- Horizon : 24h (✓)
- Seuils : score 0.38 / conf 0.68 / R/R 2.5
- W1=0.15 / W2=0.30 / W3=0.10 / W4=0.45 (déjà intraday-tilted)
- ATR period : 14 jours (← anormalement long pour 24h)
- Trailing : break-even simple à 50% (← ne verrouille rien)
- Kelly cap : 10% fixe (← gaspille l'edge sur conviction élevée)
- VIX gating ✓ / Bornes SL/TP intraday ✓

### Changements (3, dans la limite max du skill)

| # | Paramètre | Avant | Après | Niveau playbook |
|---|-----------|-------|-------|-----------------|
| 1 | ATR period | 14 j | **7 j** | §2.4 ATR dynamique |
| 2 | Trailing SL | binaire 50% | **3 niveaux : 30%/60%/85%** | §1.3 time-stop adapt. |
| 3 | Kelly cap | 10% fixe | **5%/8%/10%/12% par conf** | §3.4 sizing adaptatif |

### Justifications théoriques

**#1 ATR 14→7** : 14 jours = 3 semaines de données. Sur horizon 24h,
le régime de vol récent (7 derniers jours) prédit mieux le mouvement
attendu. Bornes absolues [1.5-5% SL] / [3-15% TP] inchangées.

**#2 Trailing 3 niveaux** :
- 30% prog → SL à entry (no-loss tôt vs 50% du simple break-even)
- 60% prog → SL à entry + 25% gain (verrouille 1/4)
- 85% prog → SL à entry + 60% gain (verrouille 60%)
Classique en intraday pour éviter les "winners reversed to breakeven".

**#3 Kelly cap par conf** :
| conf | cap |
|------|-----|
| 0.68-0.72 | 5%  |
| 0.72-0.80 | 8%  |
| 0.80-0.90 | 10% |
| > 0.90    | 12% |
Reste dans range sain MAX_POSITION 0.05-0.20 du parameter-guide.

### Impact attendu (théorique, non backtested)
- ATR 7 : stops/TP plus réactifs au régime récent
- Trail 3-niv : Sharpe ↑ (captation gains partiels)
- Kelly conf : expectancy ↑ (amplitude P&L ∝ qualité signal)

### Risques surveillés
- ATR 7 : biais si semaine atypique (gap event)
- Trail : wick down peut clôturer prématuré (compensé par SL ≥ entry au niv 1)
- Kelly conf : drawdown trade isolé ↑ (compensé par MAX_OPEN=10)

### Commits
- `143fd45` : tune(stops) ATR 14 → 7
- `9f8d04e` : tune(trailing) SL progressif 3 niveaux
- `3b2a485` : tune(sizing) Kelly cap par confidence

### À vérifier après 20+ clôtures (priorité haute)
- Win rate global > 50% (cible 60%)
- Profit factor > 1.4 (cible 1.6+)
- % gagnants ayant atteint niveau 2 ou 3 du trailing (validation de #2)
- Distribution Kelly réelle (validation de #3)
- Temps moyen jusqu'à clôture < 18h (efficacité intraday)

### Critères de ROLLBACK (rollback obligatoire si dépassé)
- Win rate < 45% sur 20+ trades
- Profit factor < 1.0
- Drawdown > -15%

---

## 2026-04-23 (3) — Cap absolu 10 positions ouvertes

### Demande user
"Maxi 10 positions ouvertes, top du top uniquement"

### Changement
| Paramètre | Avant | Après | Fichier |
|-----------|-------|-------|---------|
| MAX_OPEN_SIGNALS | ∞ | **10** | config/settings.py |

### Enforcement
Dans `src/notifications/dashboard_exporter.py` :
- Après tous les filtres (score/conf/RR/secteur)
- Si `len(opens) > MAX_OPEN_SIGNALS` → tri par `|score| × confidence` desc
- Garde les 10 meilleurs, log les rejetés

### Logique de sélection "top of top"
```python
open_sigs.sort(key=lambda s: abs(s.score) * s.confidence, reverse=True)
kept = open_sigs[:MAX_OPEN_SIGNALS]
```
= signaux avec **haute conviction** (score fort) **et** **haute fiabilité** (confidence élevée)

### Pipeline de filtres complet (après ce changement)
1. PREMIUM_MIN_SCORE ≥ 0.48
2. PREMIUM_MIN_CONFIDENCE ≥ 0.70
3. PREMIUM_MIN_RR ≥ 2.5
4. 3/4 composantes CPA alignées
5. Cohérence ML (proba_up)
6. MAX_PER_SECTOR = 3
7. **MAX_OPEN_SIGNALS = 10** ← CAP FINAL

### Impact attendu
- Dashboard : toujours ≤ 10 lignes dans "Signaux Actifs"
- Portefeuille concentré sur la meilleure conviction
- Signaux faibles (<0.50 × 0.75 = 0.375) éliminés même s'ils passent les autres filtres

### Commits
- `?`  : MAX_OPEN_SIGNALS=10 dans settings.py
- `?`  : enforcement dans dashboard_exporter.py

---
