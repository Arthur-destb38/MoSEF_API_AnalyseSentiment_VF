# Crypto Sentiment Analysis

*Analyse de sentiment des cryptomonnaies à partir des réseaux sociaux*

Projet de Master MoSEF 2025-2026 — Université Paris 1 Panthéon-Sorbonne

---

## Sommaire

- [À propos](#à-propos)
- [Fonctionnalités](#fonctionnalités)
- [Sources de données](#sources-de-données)
- [Installation](#installation)
- [Lancement](#lancement)
- [Variables d'environnement](#variables-denvironnement)
- [Architecture](#architecture)
- [Déploiement](#déploiement)
- [Références et auteurs](#références-et-auteurs)

---

## À propos

Ce projet vise à étudier la relation entre le sentiment exprimé sur les réseaux sociaux et l’évolution des prix des cryptomonnaies. La littérature suggère que les discussions en ligne peuvent contenir une information prédictive sur les mouvements de marché ; l’objectif est d’en tester la pertinence dans le cadre des actifs numériques.

Le pipeline repose sur les étapes suivantes :

1. **Collecte** — Récupération des données sur plusieurs plateformes (Reddit, StockTwits, Twitter, Telegram, 4chan/biz, Bitcointalk, GitHub, Bluesky, YouTube).
2. **Analyse** — Mesure du sentiment à l’aide de deux modèles pré-entraînés : FinBERT (finance générale) et CryptoBERT (spécialisé sur le lexique crypto).
3. **Validation** — Comparaison des sorties des modèles aux labels humains disponibles sur StockTwits (Bullish / Bearish).
4. **Économétrie** — Mise en œuvre de tests de stationnarité (ADF), de causalité au sens de Granger et de modèles VAR pour caractériser les liens entre sentiment et prix.

---

## Fonctionnalités

### Interface Streamlit

L’application Streamlit propose les vues suivantes :

| Page | Description |
|------|-------------|
| Accueil | Présentation du projet et accès aux différentes sections. |
| Scraping | Lancement des collectes par plateforme, avec sélection de la cryptomonnaie et des limites (nombre de posts, etc.). |
| Données | Consultation des posts stockés (PostgreSQL ou JSONL), statistiques descriptives et export CSV/JSON. |
| Analyses des résultats | Visualisations (Plotly), comparaison FinBERT / CryptoBERT, analyse par actif et résultats des tests économétriques (ADF, Granger, VAR). |
| Documentation | Méthodologie, description des sources et des modèles, références. |

### API FastAPI

Une API REST est fournie pour l’intégration du pipeline dans d’autres systèmes. Elle expose des endpoints pour le scraping, l’analyse de sentiment et la récupération des prix. La documentation interactive est disponible au format Swagger (`/docs`) et ReDoc (`/redoc`).

---

## Sources de données

Les données sont collectées sur les plateformes suivantes :

| Plateforme | Méthode | Type de données |
|------------|--------|-----------------|
| Reddit | API JSON (old.reddit.com) | Subreddits par cryptomonnaie (r/Bitcoin, r/ethereum, etc.) |
| StockTwits | Scraping (Selenium) | Messages et labels Bullish/Bearish |
| Twitter / X | Scraping (Selenium, mode sans authentification possible) | Tweets par mot-clé ou symbole |
| Telegram | API / scraping | Canaux crypto configurés |
| 4chan | Requêtes HTTP | Board /biz/ |
| Bitcointalk | Requêtes HTTP | Forums dédiés aux cryptomonnaies |
| GitHub | API | Discussions sur des dépôts crypto |
| Bluesky | API atproto | Publications crypto |
| YouTube | API Google | Commentaires sous vidéos crypto |

Les actifs supportés incluent notamment Bitcoin, Ethereum, Solana, Cardano, Dogecoin, XRP, Polkadot, Chainlink, Litecoin et Avalanche. Les subreddits et symboles StockTwits sont configurables.

---

## Installation

### Prérequis

- Python 3.10 à 3.14
- Poetry (recommandé) ou environnement virtuel `venv` avec `pip`

### Installation avec Poetry

```bash
git clone https://github.com/Arthur-destb38/Projet_API.git
cd Projet_API

# Installer Poetry si nécessaire : https://python-poetry.org/docs/#installation
# Exemple : pip install --user poetry

poetry install
# Si la commande poetry n'est pas dans le PATH :
python3 -m poetry install
```

La première installation peut prendre plusieurs minutes (téléchargement de PyTorch et Transformers, environ 2 Go).

### Installation sans Poetry

```bash
python3 -m venv .venv
source .venv/bin/activate   # Sous Windows : .venv\Scripts\activate
pip install -e .
```

Pour reproduire l’environnement à partir du lock Poetry :  
`poetry export -f requirements.txt --without-hashes | pip install -r /dev/stdin`

### Ajout d’une dépendance (Poetry)

```bash
poetry add <package>
# ou : python3 -m poetry add <package>
poetry lock
```

---

## Lancement

Les commandes doivent être exécutées dans l’environnement du projet (Poetry ou venv). Avec Poetry, préfixer par `poetry run` ou `python3 -m poetry run` si `poetry` n’est pas dans le PATH.

### Interface Streamlit

```bash
poetry run streamlit run streamlit_app.py
# ou :
python3 -m poetry run streamlit run streamlit_app.py
```

L’interface est accessible à l’adresse [http://localhost:8501](http://localhost:8501). Si le port 8501 est déjà utilisé, préciser un autre port :  
`streamlit run streamlit_app.py --server.port 8765`

### API FastAPI

```bash
poetry run uvicorn app.main:app --reload
```

- API : [http://127.0.0.1:8000](http://127.0.0.1:8000)
- Swagger : [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- ReDoc : [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

---

## Variables d'environnement

Un fichier `.env` à la racine du projet permet de configurer les clés et identifiants suivants :

| Variable | Description |
|----------|-------------|
| `APP_PASSWORD` ou `DASHBOARD_PASSWORD` | Mot de passe d’accès au dashboard Streamlit (optionnel en local). |
| `DATABASE_URL` | URL de connexion PostgreSQL (ex. Supabase) pour le stockage des posts. |
| `YOUTUBE_API_KEY` | Clé API Google pour le scraper YouTube. |
| `BLUESKY_USERNAME` / `BLUESKY_APP_PASSWORD` | Identifiants Bluesky (App Password) pour le scraper Bluesky. |
| `TWITTER_*` | Identifiants Twitter ; `TWITTER_NO_LOGIN=1` permet un mode sans authentification. |
| `INSTAGRAM_*` | Identifiants Instagram pour le scraper Instagram. |
| `DISCORD_BOT_TOKEN` | Token du bot Discord si le scraper Discord est utilisé. |

Le fichier `.env` ne doit pas être versionné (il est listé dans `.gitignore`).

---

## Architecture

```
Projet_API/
├── app/
│   ├── main.py              # API FastAPI (scraping, NLP, prix)
│   ├── nlp.py               # Chargement et inférence FinBERT / CryptoBERT
│   ├── prices.py            # Récupération des prix (CoinGecko, séries historiques)
│   ├── storage.py           # Persistance (PostgreSQL, JSONL, export CSV/JSON)
│   ├── utils.py             # Prétraitement du texte (URLs, mentions, emojis)
│   └── scrapers/
│       ├── http_scraper.py
│       ├── reddit_scraper.py
│       ├── stocktwits_scraper.py
│       ├── twitter_scraper.py
│       ├── telegram_scraper.py
│       ├── chan4_scraper.py
│       ├── bitcointalk_scraper.py
│       ├── github_scraper.py
│       ├── bluesky_scraper.py
│       ├── youtube_scraper.py
│       ├── instagram_scraper.py
│       ├── discord_scraper.py
│       ├── tiktok_scraper.py
│       └── selenium_scraper.py
├── streamlit_app.py         # Application Streamlit
├── econometrics.py          # Tests ADF, Granger, VAR
├── templates/               # Templates HTML (FastAPI)
├── data/exports/            # Exports CSV/JSON
├── pyproject.toml
├── poetry.lock
├── Dockerfile
├── render.yaml
└── .streamlit/config.toml
```

---

## Déploiement

- **Render** : le fichier `render.yaml` définit un service web (build via Poetry, démarrage de Streamlit). Les variables d’environnement (dont `APP_PASSWORD`) sont à renseigner dans le tableau de bord Render.
- **Docker** : le `Dockerfile` permet de construire une image et d’exécuter l’application en conteneur.

---

## Références et auteurs

**Références**

- CryptoBERT : [ElKulako/cryptobert](https://github.com/ElKulako/cryptobert). *CryptoBERT: A Pre-trained Language Model for Cryptocurrency Sentiment Analysis*, IEEE Intelligent Systems, 38(4), 2023.
- FinBERT : [ProsusAI/finbert](https://github.com/ProsusAI/finbert). Modèle de sentiment financier basé sur BERT.
- Kraaijeveld, O., & De Smedt, J. (2020). *The predictive power of public Twitter sentiment for forecasting cryptocurrency prices*, Journal of Computational Finance.

**Auteurs**

Projet réalisé dans le cadre du Master MoSEF (Modélisation Statistique Économique et Financière), Université Paris 1 Panthéon-Sorbonne.

- Arthur Destribats  
- Niama El Kamal  
- Matéo Martin  

*Projet à vocation académique.*
