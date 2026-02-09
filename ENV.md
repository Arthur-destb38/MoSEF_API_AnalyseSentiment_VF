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

**Alternative sans mot de passe PostgreSQL (API REST Supabase) :** si la connexion avec `DATABASE_URL` échoue (ex. « password authentication failed »), tu peux utiliser l’**endpoint API** du projet au lieu du mot de passe :

| Variable | Description |
|---------|-------------|
| `SUPABASE_URL` | URL du projet (ex. `https://kocmirnpyfcjuhuadalj.supabase.co`). Dans Supabase : **Settings** → **API** → **Project URL**. |
| `SUPABASE_SERVICE_KEY` ou `SUPABASE_SECRET_KEY` ou `SUPABASE_ANON_KEY` | Clé API (Secret key = privilégiée). **Settings** → **API** → **Secret keys** → copier la clé. Nom exact dans `.env` : `SUPABASE_SERVICE_KEY=...` ou `SUPABASE_SECRET_KEY=...`. |

Si ces deux variables sont définies, l’app utilisera l’API REST pour enregistrer et lire les posts (plus besoin de `DATABASE_URL`). La table `posts2` doit exister dans ton projet (créée une fois via l’onglet **Table Editor** ou **SQL** si besoin).

**Note :** Si le mot de passe contient des caractères spéciaux, les encoder dans l’URL : `@` → `%40`, `:` → `%3A`, `#` → `%23`, `$` → `%24`, `/` → `%2F`.

**Si tu as « password authentication failed » :**
1. Va sur [Supabase](https://app.supabase.com) → ton projet → **Project Settings** → **Database**.
2. Dans **Connection string**, copie l’URL **URI** (ou **Session mode** avec port 5432).
3. Remplace le mot de passe dans l’URL par celui affiché (ou clique sur **Reset database password** et utilise le nouveau).
4. Colle l’URL dans ton `.env` : `DATABASE_URL=postgresql://postgres.xxx:TON_MOT_DE_PASSE@db.xxx.supabase.co:5432/postgres` (sans espace, sans guillemets inutiles). Si le mot de passe a des caractères spéciaux, encode-les comme ci‑dessus.

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
