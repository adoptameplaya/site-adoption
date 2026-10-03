# Mise en place de l'espace d'administration

Le refuge gère ses fiches depuis `/admin/`. Chaque enregistrement crée un
commit sur GitHub, Netlify reconstruit, le site est à jour en quelques minutes.

**Ce qui change pour toi :** le site ne se déploie plus par glisser-déposer.
Tout passe par git. `git push` remplace le dépôt du zip.

---

## 1. Créer le dépôt GitHub

Sur github.com → **New repository**. Privé ou public, les deux marchent.
Ne coche **rien** (pas de README, pas de .gitignore) : le dépôt local existe déjà.

Puis, depuis le dossier du projet :

```bash
git remote add origin https://github.com/TON_COMPTE/TON_DEPOT.git
git branch -M main
git push -u origin main
```

## 2. Renseigner le dépôt dans la config de l'admin

Dans `admin/config.yml`, remplacer la ligne `repo:` :

```yaml
backend:
  name: github
  repo: TON_COMPTE/TON_DEPOT
```

## 3. Brancher Netlify sur le dépôt

Netlify → le projet `refuge-adoption` → **Project configuration** →
**Build & deploy** → **Link repository**, choisir le dépôt GitHub.

Netlify lit `netlify.toml` et trouve seul la commande et le dossier :

| Réglage | Valeur |
|---|---|
| Build command | `python3 build-preprod.py` |
| Publish directory | `dist/preprod` |
| Functions directory | `netlify/functions` |

## 4. Créer l'application OAuth GitHub

GitHub → **Settings** → **Developer settings** → **OAuth Apps** →
**New OAuth App**.

| Champ | Valeur |
|---|---|
| Application name | Adopta Me Playa — admin |
| Homepage URL | `https://refuge-adoption.netlify.app` |
| Authorization callback URL | `https://refuge-adoption.netlify.app/api/callback` |

Générer ensuite un **client secret** et garder les deux valeurs sous la main.

## 5. Déclarer les clés dans Netlify

Netlify → **Project configuration** → **Environment variables** → ajouter :

| Nom | Valeur |
|---|---|
| `GITHUB_CLIENT_ID` | le Client ID de l'application OAuth |
| `GITHUB_CLIENT_SECRET` | le secret généré |
| `MODO` | `preprod` pour l'instant, `produccion` le jour du lancement |

Le secret ne quitte jamais le serveur : il n'est lu que par la fonction
`callback.js`, jamais envoyé au navigateur.

## 6. Donner l'accès à la personne du refuge

Elle a besoin d'un **compte GitHub gratuit**, puis d'un accès en écriture au
dépôt : GitHub → le dépôt → **Settings** → **Collaborators** → l'inviter.

Elle se connecte ensuite sur `https://refuge-adoption.netlify.app/admin/`
avec **Login with GitHub**.

---

## Basculer en production

Le jour où les fiches d'exemple sont remplacées par de vraies :

1. Netlify → variable `MODO` → `produccion`
2. Redéployer

Ça retire le bandeau « sitio de demostración », le `noindex` et le
`Disallow: /` — tout en gardant `/admin/` hors des moteurs de recherche.

## Et si quelque chose casse

- **« Failed to load config.yml »** → la ligne `repo:` n'a pas été remplacée
- **La fenêtre de connexion se ferme sans rien faire** → la callback URL de
  l'application OAuth ne correspond pas exactement, ou les variables
  d'environnement ne sont pas posées
- **Les photos ne s'envoient pas** → l'utilisateur n'a pas l'accès en écriture
  au dépôt
