# Crypto Sentiment Analysis

> Projet de Master MoSEF 2024-2025 — Université Paris 1 Panthéon-Sorbonne

## À propos du projet

Ce projet explore la relation entre le **sentiment des réseaux sociaux** et les **prix des cryptomonnaies**. L'idée est simple : les discussions sur Reddit et StockTwits reflètent-elles l'humeur du marché crypto ? Et surtout, peut-on utiliser ce sentiment pour anticiper les mouvements de prix ?

Pour répondre à ces questions, nous avons construit un pipeline complet qui :

1. **Collecte** les posts en temps réel depuis Reddit et StockTwits
2. **Analyse** le sentiment avec deux modèles de NLP spécialisés (FinBERT et CryptoBERT)
3. **Compare** les performances des modèles grâce aux labels humains de StockTwits
4. **Étudie** la relation sentiment-prix avec des outils économétriques (Granger, VAR)

---

## Pourquoi ce projet ?

Le marché crypto est particulièrement sensible au sentiment. Un tweet d'Elon Musk peut faire bouger le Bitcoin de plusieurs pourcents en quelques minutes. Mais au-delà des célébrités, qu'en est-il du sentiment "de base" des investisseurs particuliers ?

Notre hypothèse : le sentiment agrégé des discussions sur les réseaux sociaux contient de l'information sur les mouvements futurs des prix.

---

## Comment ça marche ?

### Les sources de données

**Reddit** — On scrape les subreddits dédiés à chaque crypto (r/Bitcoin, r/ethereum, etc.) via l'API JSON publique. C'est rapide et on peut récupérer jusqu'à 1000 posts d'un coup.

**StockTwits** — C'est le Twitter de la finance. L'avantage majeur ? Les utilisateurs tagguent eux-mêmes leurs messages comme "Bullish" 🐂 ou "Bearish" 🐻. Ces labels humains nous permettent de valider nos modèles de sentiment !

### Les modèles de sentiment

On utilise deux modèles pré-entraînés basés sur BERT :

**FinBERT** — Développé par Prosus AI, ce modèle a été entraîné sur des news financières. Il classifie les textes en Positive / Negative / Neutral. C'est notre baseline "finance générale".

**CryptoBERT** — Le modèle star du projet ! Développé par ElKulako, il a été entraîné spécifiquement sur 3.2 millions de posts crypto (StockTwits, Reddit, Twitter, Telegram). Il comprend le jargon crypto : "to the moon", "HODL", "diamond hands"... Les labels sont Bullish / Bearish / Neutral.

### L'analyse économétrique

Une fois le sentiment calculé, on le confronte aux prix réels via :

- **Test ADF** : On vérifie que nos séries sont stationnaires (sinon les résultats sont biaisés)
- **Causalité de Granger** : Le sentiment d'aujourd'hui prédit-il les rendements de demain ?
- **Modèle VAR** : Pour capturer les interactions dynamiques entre sentiment et prix

---

## Installation

### Prérequis

- Python 3.10 ou plus récent
- Poetry (gestionnaire de dépendances Python)

### Étapes

```bash
# Cloner le repo
git clone https://github.com/Arthur-destb38/Projet_API.git
cd Projet_API

# Installer Poetry si nécessaire
pip install poetry

# Installer toutes les dépendances
poetry install
```

La première installation prend quelques minutes car elle télécharge PyTorch et les Transformers (~2 Go).

---

## Lancement

### Interface Streamlit (recommandé)

C'est l'interface principale du projet, avec des visualisations interactives :

```bash
poetry run streamlit run streamlit_app.py
```

L'application s'ouvre automatiquement sur `http://localhost:8501`

### API FastAPI

Pour ceux qui préfèrent une API REST ou veulent intégrer le projet dans un autre système :

```bash
poetry run uvicorn app.main:app --reload
```

- Interface web : `http://127.0.0.1:8000`
- Documentation Swagger : `http://127.0.0.1:8000/docs`

---

## Fonctionnalités

### Page "Analyse"

Analyse le sentiment d'une crypto en particulier. Tu choisis :
- La **source** (Reddit ou StockTwits)
- Le **modèle** (FinBERT ou CryptoBERT)
- La **crypto** (Bitcoin, Ethereum, Solana...)
- Le **nombre de posts** à analyser

Résultats : score moyen, distribution Bullish/Bearish/Neutral, histogramme des scores, et tableau détaillé des posts.

### Page "Comparaison"

Compare FinBERT vs CryptoBERT sur les mêmes posts. Utilise StockTwits pour avoir les labels humains et calculer l'accuracy de chaque modèle !

Spoiler : CryptoBERT gagne généralement de 10-15% sur les données crypto 😉

### Page "Multi-crypto"

Analyse plusieurs cryptos en parallèle pour voir laquelle a le meilleur sentiment. Pratique pour avoir une vue d'ensemble du marché.

### Page "Économétrie"

Tests statistiques pour étudier la relation sentiment ↔ prix :
- Stationnarité des séries (ADF)
- Causalité de Granger dans les deux sens
- Conclusions automatiques

### Page "Méthodologie"

Documentation technique : sources de données, modèles, pipeline, références académiques.

---

## Cryptos supportées

| Crypto | Subreddit | Symbole StockTwits |
|--------|-----------|-------------------|
| Bitcoin | r/Bitcoin | BTC.X |
| Ethereum | r/ethereum | ETH.X |
| Solana | r/solana | SOL.X |
| Cardano | r/cardano | ADA.X |
| Dogecoin | r/dogecoin | DOGE.X |
| Ripple | r/xrp | XRP.X |
| Polkadot | r/polkadot | DOT.X |
| Chainlink | r/chainlink | LINK.X |
| Litecoin | r/litecoin | LTC.X |
| Avalanche | r/avax | AVAX.X |

---

## Architecture du code

```
Projet_API/
├── app/
│   ├── main.py                    # API FastAPI avec tous les endpoints
│   ├── nlp.py                     # Chargement et inference FinBERT/CryptoBERT
│   ├── prices.py                  # Récupération des prix via CoinGecko
│   ├── utils.py                   # Nettoyage de texte (URLs, mentions, emojis)
│   └── scrapers/
│       ├── http_scraper.py        # Classe de base pour le scraping HTTP
│       ├── reddit_scraper.py      # Scraping Reddit via l'API JSON
│       ├── stocktwits_scraper.py  # Scraping StockTwits
│       └── selenium_scraper.py    # Scraping dynamique avec Selenium
│
├── streamlit_app.py               # Interface utilisateur Streamlit
├── econometrics.py                # Tests ADF, Granger, VAR
├── templates/                     # Pages HTML pour l'interface FastAPI
│   ├── index.html
│   └── compare.html
│
├── pyproject.toml                 # Dépendances Poetry
└── poetry.lock                    # Versions exactes des packages
```

---

## Points techniques intéressants

### Scraping Reddit sans API officielle

Reddit a rendu son API payante en 2023. On contourne le problème en utilisant l'endpoint JSON de old.reddit.com (`/r/{sub}/new.json`) qui reste accessible. On gère la pagination avec le paramètre `after` pour récupérer plus de posts.

### Labels humains StockTwits

C'est la feature killer pour la validation ! Les utilisateurs StockTwits peuvent (optionnellement) indiquer s'ils sont Bullish ou Bearish sur un post. Ça nous donne un ground truth pour mesurer l'accuracy de nos modèles.

### Gestion des modèles lourds

FinBERT et CryptoBERT font plusieurs centaines de Mo chacun. On utilise le cache de Streamlit (`@st.cache_resource`) pour ne les charger qu'une seule fois en mémoire.

### Nettoyage de texte

Les posts Reddit et StockTwits sont bruités : URLs, mentions @user, emojis, caractères spéciaux... Le module `utils.py` nettoie tout ça avant l'analyse de sentiment.

---

## Limites et améliorations possibles

- **Données historiques** : On analyse le sentiment en temps réel, mais pour l'économétrie on aurait besoin de séries plus longues
- **Rate limiting** : Reddit peut bloquer si on scrape trop vite
- **Biais de sélection** : Les utilisateurs qui postent ne sont pas représentatifs de tous les investisseurs
- **Latence** : StockTwits utilise Selenium (navigateur headless), c'est lent (~10-30s)

---

## Références

- **CryptoBERT** : ElKulako/cryptobert — *"CryptoBERT: A Pre-trained Language Model for Cryptocurrency Sentiment Analysis"*, IEEE Intelligent Systems 38(4), 2023
- **FinBERT** : ProsusAI/finbert — Modèle de sentiment financier basé sur BERT
- Kraaijeveld, O., & De Smedt, J. (2020). *"The predictive power of public Twitter sentiment for forecasting cryptocurrency prices"*, Journal of Computational Finance

---

## Auteurs

Projet réalisé dans le cadre du Master MoSEF (Modélisation Statistiques Économiques et Financières), Université Paris 1 Panthéon-Sorbonne.

- Arthur Destribats
- Niama El Kamal
- Matéo Martin
---

## Licence

Projet académique
