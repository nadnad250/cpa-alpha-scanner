# Catalogue des Bugs Récurrents — CPA Alpha Scanner

Patterns de bugs déjà rencontrés + solutions validées. À consulter AVANT de diagnostiquer un bug nouveau.

## 🔴 CRITIQUES (bloquent le fonctionnement)

### B001 — Signal clôturé reste "open" après TP/SL touché
**Symptôme** : Prix live passe au-delà du TP/SL mais le signal reste dans "Signaux Actifs".
**Cause** : `update_live_prices.py` ne vérifie pas `current_price vs tp/sl`.
**Fix** : Auto-clôture dans le script avant l'écriture JSON.
**Fichier** : `tools/update_live_prices.py`
**Commit ref** : `f317d16`

### B002 — Cohérence tracker vs dashboard
**Symptôme** : "15 positions actives" mais 12 affichées.
**Cause** : 2 sources différentes (tracker vs signals.json).
**Fix** : Forcer `active_positions = len(open_sigs dans signals.json)`.
**Fichier** : `src/notifications/dashboard_exporter.py`
**Commit ref** : `ffa72f9`

### B003 — Pages GitHub pas mises à jour
**Symptôme** : Bot commit mais le site reste figé.
**Cause** : `GITHUB_TOKEN` ne déclenche pas les workflows auto (anti-boucle).
**Fix** : `gh workflow run deploy-pages.yml` explicite dans chaque workflow.
**Fichier** : `.github/workflows/*.yml`
**Commit ref** : `e852783`

## 🟠 HIGH (erreurs de formule)

### B101 — Win rate = wins / total
**Symptôme** : Win rate descend au fur et à mesure que les ouverts augmentent.
**Cause** : Division par `signals.length` au lieu de `closed.length`.
**Fix** : `winRate = wins / (wins + losses)`, JAMAIS `/ total`.
**Fichiers possibles** : `stats.html`, `live.html`, `app.js`.

### B102 — upside_pct utilisé comme P&L réalisé
**Symptôme** : Meilleurs trades affichent toujours la cible théorique, pas le gain réel.
**Cause** : `upside_pct` = cible au signal ≠ `pnl_pct` = réalisé après clôture.
**Fix** : Privilégier `pnl_pct` si défini, fallback sur `upside_pct` avec sign `(tp_hit ? + : -)`.

### B103 — Best et Worst trades mélangés
**Symptôme** : Même trade dans Meilleurs (+7%) ET dans Pires (-7%).
**Cause** : Sort par P&L puis `slice(0,5)` et `slice(-5)` sur mêmes données.
**Fix** : Séparation stricte par status :
```javascript
best  = closed.filter(s => s.status === 'tp_hit').sort(pnl desc);
worst = closed.filter(s => s.status === 'sl_hit').sort(pnl asc);
```
**Commit ref** : `597ed68`

## 🟡 MEDIUM (affichage incorrect)

### B201 — Doublons par (ticker, action)
**Symptôme** : `PGR STRONG_SELL` et `PGR SELL` coexistent comme 2 signaux distincts.
**Cause** : Le tracker n'a pas fusionné.
**Fix** : Dédup par `(ticker, action)` au niveau exporter.
**Commit ref** : `a9acfca`

### B202 — ALLOC à 0% ou figé à 12%
**Symptôme** : Colonne allocation toujours la même valeur.
**Cause** : Kelly non calculé OU formule capée au max.
**Fix** : Fallback quart-Kelly × score_factor avec clamp [3%, 10%].

### B203 — Composantes CPA toutes à 0
**Symptôme** : Modal détail montre `+0.000` pour Value Gap, Factor Premia, etc.
**Cause** : Opportunity n'avait pas les 4 champs ; valeurs écrasées à 0 dans tracker sync.
**Fix** : Ajouter les 4 champs au dataclass + passer depuis cpa_result.

### B204 — Prix live "en attente" alors que marché ouvert
**Symptôme** : Un ticker affiche "En attente prix live" même en heures de marché.
**Cause** : CORS proxy échoue OU fetch yfinance failed pour ce ticker.
**Fix** : Utiliser le live_prices.py Python côté bot (déjà fait).

## 🟢 LOW (UX / cosmétique)

### B301 — Barre de progression > 100% ou négative mal affichée
**Symptôme** : Marker sort du cadre quand prog > +100% ou < −100%.
**Fix** : Clamp `posOnBar = max(0, min(100, 50 + prog/2))`.

### B302 — Filtres qui laissent passer les clôturés
**Symptôme** : Filtre "Tous" affiche aussi les tp_hit au milieu.
**Cause** : Filtre sur action, pas sur status.
**Fix** : Filtrer d'abord `status === 'open'` pour l'onglet principal.

### B303 — Heures en UTC vs local mélangées
**Symptôme** : `issued_at` affiche 20:39 alors qu'il est 22:39 Paris.
**Cause** : Le bot écrit en UTC, le frontend lit sans convertir.
**Fix** : `new Date(iso).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })`.

## 🔍 Méthodologie pour un nouveau bug

1. **Reproduire** avec les vraies données (`signals.json` actuel)
2. **Grep** dans les fichiers concernés pour trouver la logique fautive
3. **Tracer** : print/console.log pour voir les valeurs réelles
4. **Fixer** dans le fichier source (Python ou JS) — pas en patch DOM
5. **Vérifier** que le fix est cohérent sur toutes les pages
6. **Commit 1 bug = 1 commit**, jamais de bundle

## ⚠️ Ne JAMAIS faire

- Cacher un bug avec un try/catch silencieux
- "Fixer" en HTML/CSS un bug de données
- Modifier signals.json manuellement (c'est le bot qui le génère)
- Changer les seuils sans consulter cpa-bot-optimizer
- Fixer plusieurs bugs dans le même commit
- Skip le backtest de validation avant déploiement
