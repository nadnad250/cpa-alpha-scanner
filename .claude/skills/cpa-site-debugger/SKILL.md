---
name: cpa-site-debugger
description: Auditeur et correcteur de bugs du site CPA Alpha Scanner. Détecte les incohérences entre signals.json et l'affichage, les erreurs de calcul (win rate, P&L), les problèmes d'état (signal clôturé qui reste actif), les filtres qui ne marchent pas, les statistiques incorrectes. USE PROACTIVELY quand l'utilisateur dit "bug", "catastrophe", "c'est pas logique", "ne se met pas à jour", "win rate faux", "signal qui reste", "audit site", ou rapporte une incohérence visuelle entre données et affichage.
---

# CPA Site Debugger

Skill spécialisé pour **auditer et corriger systématiquement** les bugs du site CPA Alpha Scanner.

## 🎯 Mission

Le dashboard web a plusieurs pages qui lisent le même `signals.json` mais l'affichent différemment. Chaque page peut avoir des bugs de cohérence, de calcul, ou de logique métier. Ce skill détecte et corrige ces bugs **un par un**, avec preuve par code.

## ⚡ Quand activer

- L'utilisateur dit :
  - "bug", "problème", "catastrophe", "c'est pas logique"
  - "ne se met pas à jour", "reste affiché"
  - "win rate faux", "stats fausses"
  - "doublons", "apparaît deux fois"
  - "filtre ne marche pas"
  - "audit le site", "vérifie tout"
- **Proactivement** après tout changement majeur du pipeline bot → dashboard
- Après chaque bug rapporté (= fait partie d'un écosystème, y'en a souvent d'autres)

## 🗂 Inventaire des pages à vérifier

```
dashboard/
├── index.html          # Landing (live ticker, stats d'accueil)
├── dashboard.html      # Tableau des signaux actifs (⭐ principal)
├── stats.html          # Métriques avancées (Sharpe, Sortino, heatmap…)
├── live.html           # Tracker live (clôturés + ouverts)
├── profile.html        # Badges + compteurs user
├── referral.html       # Parrainage + points
├── pricing.html        # Plans Stripe
├── login.html          # Firebase auth
└── legal.html          # Légal statique (peu de bugs)
```

Chaque page sauf `login`/`legal`/`pricing` consomme `data/signals.json`.

## 🔬 Workflow obligatoire

### ÉTAPE 1 — DIAGNOSTIC (ne jamais sauter)

Lancer le script d'audit automatique :

```bash
python .claude/skills/cpa-site-debugger/scripts/audit_site.py
```

Ce script :
- Charge `dashboard/data/signals.json`
- Calcule les **vraies valeurs** attendues (open count, win rate, top gainer, etc.)
- Parse tous les HTML (ou leur JS) pour extraire les **règles d'affichage**
- Produit un rapport de **divergences**

### ÉTAPE 2 — CATÉGORISATION DES BUGS

Classifier chaque bug trouvé :

| Catégorie | Exemple | Priorité |
|-----------|---------|----------|
| **Data inconsistency** | 12 signaux affichés mais 15 positions actives | 🔴 CRITIQUE |
| **Status mismanagement** | TP touché mais statut encore "open" | 🔴 CRITIQUE |
| **Formula error** | Win rate = wins/total au lieu de wins/(wins+losses) | 🟠 HIGH |
| **Duplicate display** | Même trade dans Meilleurs ET Pires | 🟠 HIGH |
| **Filter broken** | Filtre BUY affiche aussi les SELL | 🟠 HIGH |
| **Stale data** | Stats pas mises à jour après auto-close | 🟡 MEDIUM |
| **UI glitch** | Barre de progression mal colorée | 🟢 LOW |

### ÉTAPE 3 — CORRECTION (un bug à la fois)

Pour chaque bug :
1. **Identifier la source exacte** (fichier + ligne)
2. **Reproduire le bug** (avec données réelles du signals.json)
3. **Corriger avec justification**
4. **Tester** que le fix ne casse pas autre chose
5. **Commiter** avec message clair : `fix(bug-name): description`

**⚠️ JAMAIS plusieurs fixes dans le même commit** — sinon impossible de tracer ce qui a marché.

### ÉTAPE 4 — VÉRIFICATION CROSS-PAGE

Pour chaque bug corrigé, vérifier que la correction est **cohérente sur toutes les pages** :
- Si on change la formule win rate dans stats.html → vérifier dashboard.html + live.html
- Si on change l'affichage d'un status → vérifier tous les rendus de status

### ÉTAPE 5 — DÉPLOIEMENT

```bash
git push newremote master
# Le workflow deploy-pages.yml se déclenche automatiquement
```

### ÉTAPE 6 — MONITORING POST-FIX

Relancer `audit_site.py` après déploiement pour confirmer que **tous les bugs sont bien partis**.

## 🔍 Checklist des bugs connus / récurrents

Voir `references/bug-catalogue.md` pour les patterns fréquents :
- TP/SL non détectés par le tracker
- Dédoublonnage imparfait (ticker + action)
- Win rate sur total au lieu de closed
- Signal clôturé qui reste en liste active
- Filtres avec `||` au lieu de `??` (null handling)
- Progression > 100% affichée incorrectement
- Heures en UTC vs local confondues
- Prix live comparé à entry au lieu de current_price

## 📊 Règles de cohérence sacrées

| Invariant | Formule | Où vérifier |
|-----------|---------|-------------|
| Open count | `signals.filter(s => s.status === 'open').length` | Doit être identique sur dashboard + stats + live |
| Win rate | `wins / (wins + losses)` | **JAMAIS** `wins / total` (total inclut les ouverts) |
| Total P&L | `Σ pnl_pct` sur closed uniquement | Pas de confusion avec `upside_pct` |
| Best trades | `filter(tp_hit).sort(pnl desc)` | Tp_hit SEULEMENT |
| Worst trades | `filter(sl_hit).sort(pnl asc)` | Sl_hit SEULEMENT |
| Live P&L | Agrège les `pnl_pct_live` des ouverts | Utilise pnl_pct (réalisé) pour clôturés |

## 🎭 Ton / style

- **Méthodique** — un bug à la fois, pas de patchs en bloc
- **Preuve par code** — toujours citer le fichier:ligne et montrer la ligne fautive
- **Conservateur** — préférer un fix ciblé à une refonte
- **Testeur** — vérifier le fix avec données réelles avant de commiter
