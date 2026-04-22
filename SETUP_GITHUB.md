# 🚀 Faire tourner le bot sur GitHub (100% gratuit)

Guide complet : le bot tourne sur les serveurs GitHub, publie les signaux sur votre site, envoie sur Telegram. **Sans rien garder allumé sur votre PC.**

---

## Ce que vous obtenez

```
┌──────────────────────────────────────────────────────────────┐
│ GITHUB ACTIONS (gratuit, illimité pour repos publics)        │
│                                                              │
│  Cron automatique aux heures NYSE :                          │
│    • 09:30 NY (ouverture)                                    │
│    • 11:00 NY (mid-morning)                                  │
│    • 13:30 NY (milieu)                                       │
│    • 15:30 NY (power hour)                                   │
│                                                              │
│  Chaque exécution :                                          │
│    1. Scanne 500+ actions                                    │
│    2. Envoie signaux sur Telegram ✈                          │
│    3. Commit signals.json sur le repo                        │
│    4. Déclenche le déploiement GitHub Pages                  │
└──────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────┐
│ GITHUB PAGES (gratuit)                                       │
│  Site accessible : https://USERNAME.github.io/cpa-alpha/     │
└──────────────────────────────────────────────────────────────┘
```

---

## Étape 1 — Pousser le code sur GitHub

Si ce n'est pas déjà fait :

```bash
cd C:\Users\merou\Downloads\math
git init
git add .
git commit -m "feat: CPA Alpha Scanner + Dashboard"
git branch -M main
git remote add origin https://github.com/VOTRE_USERNAME/cpa-alpha-scanner.git
git push -u origin main
```

Le repo **doit être public** pour que GitHub Actions soit gratuit de façon illimitée.

---

## Étape 2 — Configurer les secrets Telegram

Sur GitHub :
1. Aller sur votre repo → **Settings** → **Secrets and variables** → **Actions**
2. Cliquer **New repository secret**
3. Ajouter ces 2 secrets :

| Nom | Valeur |
|---|---|
| `TELEGRAM_BOT_TOKEN` | `123456:ABC-DEF...` (de @BotFather) |
| `TELEGRAM_CHAT_ID` | `987654321` (votre chat ID) |

---

## Étape 3 — Activer GitHub Pages

1. **Settings** → **Pages**
2. Source : **GitHub Actions**
3. Sauvegarder

Le workflow `deploy-pages.yml` se déclenchera automatiquement au prochain push.

---

## Étape 4 — Donner les permissions au bot

Pour que le bot puisse commiter `signals.json` :

1. **Settings** → **Actions** → **General**
2. Section **Workflow permissions**
3. Cocher **Read and write permissions**
4. Sauvegarder

---

## Étape 5 — Lancer le premier scan manuellement

1. Aller sur **Actions** dans votre repo
2. Sélectionner **AlphaForge Bot**
3. Cliquer **Run workflow** → **Run workflow**
4. Attendre ~3-5 minutes
5. Les signaux partent sur Telegram + le site se met à jour

---

## Votre site est en ligne !

URL : `https://VOTRE_USERNAME.github.io/cpa-alpha-scanner/`

Pages disponibles :
- `/` — Landing page
- `/dashboard.html` — Dashboard signaux
- `/login.html` — Connexion Google
- `/referral.html` — Parrainage & crédits

---

## Planning automatique

Le bot tourne **automatiquement** selon ce cron (heure UTC) :

| Cron | Heure NY | Objectif |
|---|---|---|
| `30 13 * * 1-5` | 09:30 | Ouverture NYSE |
| `0 15 * * 1-5`  | 11:00 | Mid-morning |
| `30 17 * * 1-5` | 13:30 | Scan principal |
| `30 19 * * 1-5` | 15:30 | Power hour |

Pour changer : éditer `.github/workflows/bot_loop.yml` → section `schedule`.

---

## Vérifier que tout marche

### A. Le bot a tourné ?
**Actions** → **AlphaForge Bot** → vérifier ✅ vert

### B. Les signaux sont arrivés sur Telegram ?
Ouvrez votre Telegram, le message apparaît dans le chat avec vos signaux.

### C. Le site est mis à jour ?
**Actions** → **Deploy Dashboard to GitHub Pages** → vérifier ✅ vert
Puis aller sur l'URL et rafraîchir.

---

## Coûts

**0€** par mois. Tout est gratuit :

| Service | Gratuit pour | Utilisation bot |
|---|---|---|
| GitHub Actions | Repos publics | illimité |
| GitHub Pages | Tous | illimité |
| Telegram Bot API | Tous | illimité |

Pour repos privés : 2000 minutes/mois gratuites = largement suffisant.

---

## Problèmes courants

### ❌ "Permission denied" au commit
→ Étape 4 non faite (Workflow permissions en Read/Write)

### ❌ Le site affiche 404
→ Étape 3 non faite, ou le repo est en privé

### ❌ Pas de signal sur Telegram
→ Vérifier les secrets `TELEGRAM_BOT_TOKEN` et `TELEGRAM_CHAT_ID`
→ Lancer `python tools/get_chat_id.py` pour récupérer votre chat_id
