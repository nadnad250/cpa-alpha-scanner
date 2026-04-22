# Déploiement Gratuit — GitHub Pages

## Étapes (5 minutes)

### 1. Créer un dépôt GitHub

1. Aller sur https://github.com/new
2. Nom du dépôt : `cpa-alpha-dashboard` (ou ce que vous voulez)
3. Visibilité : **Public** (requis pour GitHub Pages gratuit)
4. Cliquer **Create repository**

### 2. Pousser le code

Dans ce dossier `dashboard/`, ouvrir un terminal et taper :

```bash
git init
git add .
git commit -m "feat: CPA Alpha Scanner dashboard"
git branch -M main
git remote add origin https://github.com/VOTRE_USERNAME/cpa-alpha-dashboard.git
git push -u origin main
```

### 3. Activer GitHub Pages

1. Aller sur votre dépôt GitHub
2. **Settings** → **Pages**
3. Source : **GitHub Actions**
4. Le workflow `.github/workflows/deploy.yml` se déclenche automatiquement

### 4. Votre site est en ligne !

URL : `https://VOTRE_USERNAME.github.io/cpa-alpha-dashboard/`

---

## Mettre à jour les signaux

Pour mettre à jour les données du dashboard :

```bash
# Copier les signaux du bot vers le dashboard
python tools/export_dashboard.py

# Pousser sur GitHub (déploiement automatique)
git add data/signals.json
git commit -m "update: signaux du jour"
git push
```

---

## Configurer Firebase (Google Login + Parrainage)

### 1. Créer un projet Firebase

1. Aller sur https://console.firebase.google.com
2. **Add project** → donner un nom → créer
3. Dans **Authentication** → **Sign-in method** → activer **Google**
4. Dans **Firestore Database** → créer en mode test

### 2. Récupérer la config

1. Project Settings → **Add app** → Web
2. Copier la config Firebase
3. Remplacer les valeurs dans `assets/js/firebase-config.js`

### 3. Ajouter votre domaine GitHub Pages

Dans Firebase Console :
- **Authentication** → **Settings** → **Authorized domains**
- Ajouter : `VOTRE_USERNAME.github.io`

---

## Alternatives de déploiement gratuit

| Service | URL | Limite | Vitesse |
|---------|-----|--------|---------|
| **GitHub Pages** | `username.github.io/repo` | 1GB, 100GB/mois | ⭐⭐⭐ |
| **Netlify** | `nom.netlify.app` | 100GB/mois | ⭐⭐⭐⭐ |
| **Vercel** | `nom.vercel.app` | 100GB/mois | ⭐⭐⭐⭐⭐ |
| **Cloudflare Pages** | `nom.pages.dev` | Illimité | ⭐⭐⭐⭐⭐ |

### Déployer sur Netlify (encore plus simple)

1. Aller sur https://netlify.com
2. **Add new site** → **Deploy manually**
3. Glisser-déposer le dossier `dashboard/`
4. C'est en ligne en 30 secondes !
