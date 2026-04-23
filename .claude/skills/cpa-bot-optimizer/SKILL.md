---
name: cpa-bot-optimizer
description: Analyse et améliore itérativement le bot CPA Alpha Scanner — diagnostic des performances, identification des patterns perdants, proposition de tuning des paramètres, validation par backtest, déploiement automatique sur GitHub. USE PROACTIVELY quand nouvelles données de trades clôturés arrivent, que le win rate stagne, ou sur demande explicite ("optimise le bot", "améliore la perf", "tune", "analyse les stats").
---

# CPA Bot Optimizer

Skill d'optimisation continue du bot de trading algorithmique CPA Alpha Scanner.

## 🎯 Mission

Améliorer **itérativement et méthodiquement** la performance du bot en se basant sur les données de trading RÉELLES (pas sur des intuitions).

## ⚡ Quand activer ce skill

- L'utilisateur demande explicitement :
  - "optimise le bot" / "améliore la performance"
  - "analyse les stats du bot"
  - "tune les paramètres"
  - "pourquoi le bot perd"
- **Proactivement** :
  - Après chaque nouvel ensemble de 10+ trades clôturés
  - Quand le win rate chute sous 45 % sur 20+ trades
  - Quand un pattern répétitif de pertes apparaît

## 🔬 Workflow rigoureux (obligatoire dans cet ordre)

### ÉTAPE 1 — DIAGNOSTIC (ne jamais la sauter)

Récupérer les données factuelles :

```bash
# Analyse automatique via le script dédié
python .claude/skills/cpa-bot-optimizer/scripts/analyze_performance.py
```

Ce script lit :
- `dashboard/data/signals.json` (état actuel)
- `data/signals/*.json` (historique quotidien du tracker)
- Retourne un rapport structuré JSON

**Métriques à collecter** :
- Win rate global + par univers + par action type
- Profit factor, expectancy, Sharpe
- Distribution des P&L (histogramme)
- Durée moyenne avant TP / SL
- Score moyen des gagnants vs perdants
- Confidence moyenne des gagnants vs perdants
- R/R réalisé vs R/R théorique
- Taux de time-stop (signals expirés)

### ÉTAPE 2 — ANALYSE (identifier les patterns)

Répondre à ces questions clés :

1. **Les SELL ont-ils un win rate plus faible que les BUY ?** → réduire la pondération SHORT
2. **Un univers sous-performe ?** (ex: CAC40 win rate 30 %) → le désactiver ou resserrer
3. **Un secteur sous-performe ?** → filtre sectoriel
4. **Les signaux à confiance 65-68 % perdent plus que ceux à 75 %+ ?** → remonter PREMIUM_MIN_CONFIDENCE
5. **Le TP est atteint en < 5 jours pour 80 % des gagnants ?** → réduire MAX_HOLD
6. **Les SL sont touchés immédiatement (< 2 jours) ?** → SL trop serré, élargir ATR multiplier
7. **Les perdants ont un score absolu moyen < 0.45 ?** → remonter PREMIUM_MIN_SCORE

**Jamais proposer un changement sans data backing.**

### ÉTAPE 3 — PROPOSITION

Formuler les changements avec ce format EXACT :

```markdown
## Proposition de tuning #N

### Hypothèse
[Description du pattern identifié avec chiffres]

### Changement
| Paramètre | Avant | Après | Raison |
|-----------|-------|-------|--------|
| PREMIUM_MIN_CONFIDENCE | 0.66 | 0.70 | 12/18 perdants avaient conf < 0.70 |

### Impact attendu
- Win rate : +X à +Y points
- Volume signaux : -Z %
- Profit factor : +W

### Risque
[Contre-partie négative possible]
```

Ne JAMAIS cumuler plus de 2-3 changements par itération. Sinon impossible d'attribuer l'effet.

### ÉTAPE 4 — BACKTEST DE VALIDATION

Modifier le backtest pour refléter les nouveaux paramètres :

```bash
python tools/run_backtest.py
```

Vérifier :
- Win rate du backtest s'améliore-t-il ?
- Sharpe augmente-t-il ?
- Profit factor > 1.3 ?

**Si le backtest est pire → REJETER le changement et revenir à l'hypothèse.**

### ÉTAPE 5 — DÉPLOIEMENT (seulement si backtest valide)

```bash
git add config/settings.py src/models/opportunity_detector.py
git commit -m "tune: <paramètre> <valeur> - justification en 1 ligne"
git push newremote master
```

Puis lancer un scan test manuel :

```bash
gh workflow run bot_loop.yml --repo nadnad250/cpa-alpha-scanner -f mode=once
```

### ÉTAPE 6 — MONITORING POST-DÉPLOIEMENT

Noter dans un fichier `.claude/skills/cpa-bot-optimizer/log.md` :
- Date du changement
- Paramètres modifiés
- Métriques avant / après (backtest)
- Hypothèse validée / infirmée (à vérifier après 20+ nouveaux trades)

## 📚 Références

- `references/optimization-playbook.md` — Techniques d'optimisation pros
- `references/parameter-guide.md` — Tous les paramètres tunables + leurs ranges sains
- `scripts/analyze_performance.py` — Analyseur automatique
- `scripts/propose_tuning.py` — Suggère des changements basés sur les stats

## ⚠️ RÈGLES DE SÉCURITÉ — NE JAMAIS LES ENFREINDRE

1. **Jamais de changement > 20 %** d'un paramètre en une fois (ex: confiance 0.66 → 0.80 = NON, 0.66 → 0.72 = OK)
2. **Jamais toucher les poids CPA** (W1, W2, W3, W4) sans backtest complet
3. **Jamais désactiver les stop-loss** ni les filtres ML
4. **Jamais réduire le R/R minimum sous 1.8**
5. **Toujours committer un seul changement à la fois** (pour traçabilité)
6. **Jamais overfitter** sur < 50 trades clôturés (échantillon trop petit)
7. **Toujours documenter** la raison du changement dans le commit

## 🎭 Ton / style

- **Honnête et data-driven** — ne jamais prétendre que les changements sont magiques
- **Sobre** — pas de marketing, pas d'emoji dans les analyses
- **Précis** — citer les chiffres exacts ("sur 23 trades, win rate 43.5 %" pas "win rate médiocre")
- **Conservateur** — préférer un petit changement validé à un grand changement risqué
