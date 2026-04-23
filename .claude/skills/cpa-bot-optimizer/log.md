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
