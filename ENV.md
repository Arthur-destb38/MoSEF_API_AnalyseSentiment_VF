# Variables d'environnement (.env)

Un fichier `.env` à la racine du projet permet de configurer clés et identifiants. **Aucune variable n’est obligatoire** pour faire tourner l’app en local (SQLite sera utilisé si `DATABASE_URL` est absent).

Le fichier `.env` ne doit **pas** être versionné (il est dans `.gitignore`). Créer le fichier à la main en s’inspirant des variables ci‑dessous.

---

## Dashboard (Streamlit)

| Variable | Description |
|---------|-------------|
| `APP_PASSWORD` ou `DASHBOARD_PASSWORD` | Mot de passe pour accéder au dashboard. Laisser vide = accès libre en local. |

---

## Base de données

| Variable | Description |
|---------|-------------|
| `DATABASE_URL` | URL complète PostgreSQL (ex. Supabase, Render). Ex. : `postgresql://user:password@host:5432/database`. Si absent → SQLite local. |
| `DB_HOST` / `POSTGRES_HOST` | Hôte (prioritaire si défini avec `DB_PASSWORD`). |
| `DB_PORT` / `POSTGRES_PORT` | Port (défaut `5432`). |
| `DB_NAME` / `POSTGRES_DB` | Nom de la base (défaut `postgres`). |
| `DB_USER` / `POSTGRES_USER` | Utilisateur (défaut `postgres`). |
| `DB_PASSWORD` / `POSTGRES_PASSWORD` | Mot de passe. |

**Note :** Si le mot de passe dans `DATABASE_URL` contient `$`, l’écrire en `%24` dans l’URL (ex. `pass%24word`).

---

## Scrapers (tous optionnels)

| Variable | Description |
|---------|-------------|
| `TWITTER_USERNAME` | Compte Twitter/X pour le scraper. |
| `TWITTER_PASSWORD` | Mot de passe du compte. |
| `TWITTER_NO_LOGIN` | `1` / `true` / `oui` = mode sans authentification. |
| `YOUTUBE_API_KEY` | Clé API YouTube Data v3 (Google Cloud Console). |
| `BLUESKY_USERNAME` | Handle Bluesky (ex. `tonhandle.bsky.social`). |
| `BLUESKY_APP_PASSWORD` | App Password (Paramètres Bluesky). |
| `GITHUB_TOKEN` | Personal Access Token pour les discussions GitHub. |
| `INSTAGRAM_USERNAME` | Compte Instagram. |
| `INSTAGRAM_PASSWORD` | Mot de passe Instagram. |
| `DISCORD_BOT_TOKEN` | Token du bot Discord. |
