# Crypto Sentiment Analysis

*Projet Master MoSEF 2025-2026 — Université Paris 1 Panthéon-Sorbonne*

---

## Contexte

La littérature en finance suggère que le sentiment exprimé sur les réseaux sociaux peut contenir une information prédictive sur les mouvements de marché. Dans le cadre des actifs numériques (cryptomonnaies), les discussions en ligne (Reddit, Twitter, forums, etc.) sont particulièrement actives et constituent une source de données potentiellement exploitable pour l’analyse de sentiment et la relation avec l’évolution des prix.

Ce projet s’inscrit dans le Master MoSEF (Modélisation Statistique Économique et Financière) de l’Université Paris 1 Panthéon-Sorbonne. Il s’appuie notamment sur des travaux tels que Kraaijeveld & De Smedt (2020) sur le pouvoir prédictif du sentiment Twitter pour les prix des cryptomonnaies, et sur des modèles de langue pré-entraînés dédiés (FinBERT, CryptoBERT).

---

## Objectif

L’objectif est d’**étudier la relation entre le sentiment exprimé sur les réseaux sociaux et l’évolution des prix des cryptomonnaies**, et d’en tester la pertinence dans un cadre reproductible :

- **Collecter** des données de discussion (posts, tweets, messages) sur plusieurs plateformes, pour plusieurs actifs (Bitcoin, Ethereum, Solana, etc.).
- **Mesurer le sentiment** à l’aide de modèles NLP pré-entraînés (FinBERT pour la finance générale, CryptoBERT pour le lexique crypto).
- **Valider** les sorties des modèles en les comparant aux labels humains lorsqu’ils existent (ex. Bullish/Bearish sur StockTwits).
- **Caractériser les liens** entre sentiment et prix via des outils économétriques (stationnarité, causalité de Granger, modèles VAR).

---

## Méthodologie

### Pipeline

1. **Collecte** — Récupération des données via API (Reddit, GitHub, Bluesky, YouTube avec clé API, Telegram) ou scraping HTTP/Selenium (StockTwits, Twitter/X, 4chan/biz, Bitcointalk, Instagram, Discord, TikTok). Les posts sont stockés en base (PostgreSQL ou SQLite) avec métadonnées (plateforme, actif, date, texte).
2. **Prétraitement** — Nettoyage du texte (URLs, mentions, emojis) puis passage dans les modèles de sentiment.
3. **Analyse NLP** — Deux modèles : **FinBERT** (finance générale) et **CryptoBERT** (spécialisé crypto). Comparaison des scores et, si possible, validation sur les labels StockTwits.
4. **Économétrie** — Tests de stationnarité (ADF), causalité au sens de Granger, modèles VAR pour étudier les relations sentiment–prix (implémentés dans `econometrics.py`).

### Sources de données

| Plateforme   | Méthode              | Données                          |
|-------------|----------------------|-----------------------------------|
| Reddit      | API JSON             | Subreddits par cryptomonnaie      |
| StockTwits  | Selenium             | Messages + labels Bullish/Bearish |
| Twitter / X | Selenium (ou sans login) | Tweets par mot-clé/symbole   |
| Telegram    | API / scraping       | Canaux crypto                     |
| 4chan       | HTTP                 | Board /biz/                       |
| Bitcointalk | HTTP                 | Forums crypto                     |
| GitHub      | API                  | Issues/discussions dépôts crypto  |
| Bluesky     | API atproto          | Publications crypto               |
| YouTube     | API Google           | Commentaires vidéos crypto        |

Actifs supportés (liste non exhaustive) : Bitcoin, Ethereum, Solana, Cardano, Dogecoin, XRP, Polkadot, Chainlink, Litecoin, Avalanche.

### Outils

- **Interface** : application **Streamlit** (dashboard : scraping, données, visualisations, comparaison FinBERT/CryptoBERT, résultats économétriques).
- **API** : **FastAPI** pour intégration externe (endpoints scraping, NLP, prix ; doc Swagger `/docs`, ReDoc `/redoc`).
- **Stack** : Python 3.10+, Poetry, PyTorch/Transformers pour les modèles, CoinGecko pour les prix.

---

## Structure du projet

```
projet-api-VF/
├── app/
│   ├── main.py              # API FastAPI (scraping, NLP, prix)
│   ├── nlp.py               # FinBERT / CryptoBERT
│   ├── prices.py            # Prix (CoinGecko)
│   ├── storage.py           # Persistance PostgreSQL / SQLite / JSONL
│   ├── utils.py             # Prétraitement texte
│   └── scrapers/            # Reddit, Twitter, Telegram, 4chan, etc.
├── streamlit_app.py         # Application Streamlit
├── econometrics.py          # Tests ADF, Granger, VAR
├── templates/               # Page d'accueil API (HTML)
├── data/exports/            # Exports CSV/JSON
├── scripts/                 # Scraping en lot (scrape_all.py, test_scrape_5.py, …)
├── tests/                   # Tests unitaires
├── slideapi/                # Supports de présentation (LaTeX)
├── ENV.md                   # Variables d'environnement
├── pyproject.toml / poetry.lock
├── Dockerfile / render.yaml
└── .streamlit/config.toml
```

---

## Résultats / état actuel

- **Dashboard Streamlit** opérationnel : accueil, scraping par plateforme, consultation des données (PostgreSQL ou SQLite), visualisations (Plotly), comparaison FinBERT/CryptoBERT, résultats des tests économétriques (ADF, Granger, VAR), documentation intégrée.
- **API FastAPI** opérationnelle : endpoints pour le scraping, l’analyse de sentiment et la récupération des prix ; documentation interactive (Swagger, ReDoc).
- **Scrapers** implémentés pour les plateformes listées ci-dessus ; stockage unifié en base ; export CSV/JSON possible.
- **Déploiement** : configuration Render (`render.yaml`) et image Docker (`Dockerfile`) disponibles.

### Installation et lancement

**Démarrage rapide (macOS / Linux)** :

```bash
git clone https://github.com/Arthur-destb38/projet-api-VF.git
cd projet-api-VF
./run.sh
```

Le script vérifie Python 3.10+, crée un `.env` si besoin, crée le venv, installe les dépendances (Poetry ou pip) et lance Streamlit sur [http://localhost:8501](http://localhost:8501).

**Avec Poetry** :

```bash
poetry install
poetry run streamlit run streamlit_app.py
poetry run uvicorn app.main:app --reload   # API : http://127.0.0.1:8000
```

**Variables d’environnement** : copier `.env.example` en `.env` et renseigner les variables optionnelles (base de données, clés API YouTube/Bluesky/Twitter, etc.). Détail dans [ENV.md](ENV.md). Aucune variable n’est obligatoire pour faire tourner l’app en local (SQLite par défaut).

**Scraping en lot** :

- `./scrape_all.sh` — toutes les plateformes (certaines nécessitent Chrome/Selenium).
- `./scrape_all.sh --http-only` — Reddit, 4chan, Bitcointalk, GitHub, Telegram, Bluesky (sans Selenium).
- `./test_scrape_5.sh` — test rapide (quelques posts sur 5 plateformes).

---

## Perspectives

- **Extension des sources** : intégration d’autres plateformes ou flux (e.g. Discord, TikTok déjà partiellement présents ; agrégation de news).
- **Enrichissement NLP** : fine-tuning des modèles sur des données crypto labellisées ; prise en compte des emojis et du ton (sarcasme).
- **Modélisation** : extension des modèles VAR ; prédiction de rendements à court terme à partir des séries de sentiment ; backtests simples.
- **Production** : renforcement des tests unitaires et d’intégration ; monitoring et logs ; optimisation des requêtes et du cache.
- **Documentation** : tutoriel pas à pas pour reproduire les résultats économétriques à partir du dashboard.

---

**Références** — CryptoBERT : [ElKulako/cryptobert](https://github.com/ElKulako/cryptobert) ; FinBERT : [ProsusAI/finbert](https://github.com/ProsusAI/finbert) ; Kraaijeveld & De Smedt (2020), *The predictive power of public Twitter sentiment for forecasting cryptocurrency prices*, Journal of Computational Finance.

**Auteurs** — Arthur Destribats, Niama El Kamal, Matéo Martin — Master MoSEF, Université Paris 1 Panthéon-Sorbonne. *Projet à vocation académique.*
# MoSEF_FinanceQuantitative_Projet2_EnCours_V1
