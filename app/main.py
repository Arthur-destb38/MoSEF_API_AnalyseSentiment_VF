"""
API Crypto Sentiment - Projet MoSEF 2024-2025
Sources: Reddit + StockTwits
Modeles: FinBERT + CryptoBERT
"""

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime
import time

from app.scrapers import scrape_reddit, scrape_stocktwits, get_reddit_limits, get_stocktwits_limits
from app.scrapers import scrape_telegram_simple, scrape_telegram_paginated, TELEGRAM_CHANNELS, get_telegram_limits
from app.nlp import SentimentAnalyzer
from app.prices import CryptoPrices
from app.utils import clean_text
from app.storage import save_posts, get_all_posts, export_to_csv, export_to_json, get_stats

app = FastAPI(
    title="Crypto Sentiment API",
    description="Analyse sentiment crypto avec Reddit/StockTwits et FinBERT/CryptoBERT",
    version="2.0"
)
templates = Jinja2Templates(directory="templates")

# Instances globales
finbert_analyzer = None
cryptobert_analyzer = None
prices_client = CryptoPrices()


def get_analyzer(model: str = "finbert"):
    global finbert_analyzer, cryptobert_analyzer
    if model == "cryptobert":
        if cryptobert_analyzer is None:
            cryptobert_analyzer = SentimentAnalyzer("cryptobert")
        return cryptobert_analyzer
    else:
        if finbert_analyzer is None:
            finbert_analyzer = SentimentAnalyzer("finbert")
        return finbert_analyzer


# ===================== ENUMS =====================

class SourceEnum(str, Enum):
    reddit = "reddit"
    stocktwits = "stocktwits"
    telegram = "telegram"

class MethodEnum(str, Enum):
    http = "http"
    selenium = "selenium"

class ModelEnum(str, Enum):
    finbert = "finbert"
    cryptobert = "cryptobert"


# ===================== MODELS =====================

class ScrapeRequest(BaseModel):
    source: SourceEnum = Field(default=SourceEnum.reddit)
    method: MethodEnum = Field(default=MethodEnum.http, description="http (rapide) ou selenium (lent)")
    symbol: str = Field(default="Bitcoin", description="Subreddit ou symbole StockTwits (BTC.X)")
    limit: int = Field(default=50, ge=10, le=1000)

class AnalyzeRequest(BaseModel):
    source: SourceEnum = Field(default=SourceEnum.reddit)
    method: MethodEnum = Field(default=MethodEnum.http, description="http ou selenium")
    model: ModelEnum = Field(default=ModelEnum.finbert)
    crypto_id: str = Field(default="bitcoin", description="ID CoinGecko")
    symbol: str = Field(default="Bitcoin", description="Subreddit ou symbole StockTwits")
    limit: int = Field(default=50, ge=10, le=1000)

class AnalyzeBothRequest(BaseModel):
    method: MethodEnum = Field(default=MethodEnum.http, description="Methode pour Reddit")
    model: ModelEnum = Field(default=ModelEnum.finbert)
    crypto_id: str = Field(default="bitcoin")
    subreddit: str = Field(default="Bitcoin")
    stocktwits_symbol: str = Field(default="BTC.X")
    limit_reddit: int = Field(default=50, ge=10, le=1000)
    limit_stocktwits: int = Field(default=50, ge=10, le=300)

class CompareModelsRequest(BaseModel):
    source: SourceEnum = Field(default=SourceEnum.stocktwits)
    method: MethodEnum = Field(default=MethodEnum.http)
    symbol: str = Field(default="BTC.X")
    limit: int = Field(default=50, ge=10, le=300)


# ===================== CRYPTO CONFIG =====================

CRYPTO_CONFIG = {
    "bitcoin": {"sub": "Bitcoin", "stocktwits": "BTC.X"},
    "ethereum": {"sub": "ethereum", "stocktwits": "ETH.X"},
    "solana": {"sub": "solana", "stocktwits": "SOL.X"},
    "cardano": {"sub": "cardano", "stocktwits": "ADA.X"},
    "dogecoin": {"sub": "dogecoin", "stocktwits": "DOGE.X"},
    "ripple": {"sub": "xrp", "stocktwits": "XRP.X"},
}


# ===================== PAGES HTML =====================

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    prices = prices_client.get_multiple_prices(["bitcoin", "ethereum", "solana"])
    limits = get_scraping_limits()
    return templates.TemplateResponse("index.html", {
        "request": request,
        "prices": prices,
        "limits": limits
    })


@app.get("/compare", response_class=HTMLResponse)
async def compare_page(request: Request):
    return templates.TemplateResponse("compare.html", {"request": request})


# ===================== HELPER =====================

def get_scraping_limits():
    """Retourne toutes les limites de scraping"""
    return {
        "reddit": get_reddit_limits(),
        "stocktwits": get_stocktwits_limits(),
        "telegram": get_telegram_limits()
    }


# ===================== API ENDPOINTS =====================

@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


@app.get("/telegram/channels", tags=["Telegram"])
async def list_telegram_channels():
    """Liste les channels Telegram crypto disponibles"""
    return {
        "channels": TELEGRAM_CHANNELS,
        "count": len(TELEGRAM_CHANNELS)
    }


@app.get("/telegram/scrape/{channel}", tags=["Telegram"])
async def scrape_telegram_channel(channel: str, limit: int = 50):
    """
    Scrape un channel Telegram spécifique
    
    **Channels populaires:**
    - whale_alert_io: Alertes de gros mouvements
    - bitcoinnews: News Bitcoin
    - CoinMarketCapAnnouncements: Annonces CoinMarketCap
    
    **Limites:**
    - Simple (≤30 posts): rapide
    - Paginé (>30 posts): plus lent mais jusqu'à 500 posts
    """
    start = time.time()
    
    if limit > 30:
        posts = scrape_telegram_paginated(channel, limit)
    else:
        posts = scrape_telegram_simple(channel, limit)
    
    # Adapter format
    for p in posts:
        p['title'] = p.get('text', '')
    
    elapsed = round(time.time() - start, 2)
    
    # Sauvegarde
    storage_result = save_posts(posts, source="telegram", method="http")
    
    return {
        "source": "Telegram",
        "channel": channel,
        "posts_count": len(posts),
        "time_seconds": elapsed,
        "storage": storage_result,
        "posts": posts[:10]
    }


@app.get("/limits", tags=["Info"])
async def get_limits():
    """
    Limites de scraping par plateforme et methode
    
    Pour eviter les bans:
    - Reddit HTTP: max 1000 posts
    - Reddit Selenium: max 200 posts
    - StockTwits Selenium: max 300 posts (seule methode disponible)
    - Telegram: max 30 (simple) ou 500 (paginé)
    """
    return {
        "reddit": {
            "http": {"max": 1000, "description": "API JSON rapide"},
            "selenium": {"max": 200, "description": "Navigateur lent mais robuste"}
        },
        "stocktwits": {
            "selenium": {"max": 300, "description": "Seule methode (Cloudflare)"},
            "http": {"max": 0, "description": "Non disponible (Cloudflare)"}
        },
        "telegram": {
            "simple": {"max": 30, "description": "Scraping basique rapide"},
            "paginated": {"max": 500, "description": "Avec pagination (plus lent)"}
        }
    }


@app.post("/scrape", tags=["Scraping"])
async def scrape(req: ScrapeRequest):
    """
    Scrape posts depuis Reddit ou StockTwits
    
    **Reddit:**
    - http: max 1000 posts, rapide (~1-5s)
    - selenium: max 200 posts, lent (~10-30s)
    
    **StockTwits:**
    - selenium uniquement: max 300 posts (~10-30s)
    - Labels humains Bullish/Bearish inclus!
    """
    start = time.time()
    
    if req.source == SourceEnum.stocktwits:
        # StockTwits = Selenium uniquement
        posts = scrape_stocktwits(req.symbol, limit=req.limit)
        source_name = "StockTwits"
        method_used = "selenium"
    elif req.source == SourceEnum.telegram:
        # Telegram - utiliser pagination si > 30 posts
        if req.limit > 30:
            posts = scrape_telegram_paginated(req.symbol, req.limit)
        else:
            posts = scrape_telegram_simple(req.symbol, req.limit)
        # Adapter format pour compatibilité
        for p in posts:
            p['title'] = p.get('text', '')
        source_name = "Telegram"
        method_used = "http"
    else:
        posts = scrape_reddit(req.symbol, limit=req.limit, method=req.method.value)
        source_name = "Reddit"
        method_used = req.method.value
    
    elapsed = round(time.time() - start, 2)
    
    # 💾 Sauvegarde automatique dans la base de données
    storage_result = save_posts(posts, source=source_name.lower(), method=method_used)
    
    # Stats labels humains (StockTwits)
    human_labels = {"Bullish": 0, "Bearish": 0, "None": 0}
    for p in posts:
        label = p.get("human_label")
        if label:
            human_labels[label] = human_labels.get(label, 0) + 1
        else:
            human_labels["None"] += 1
    
    return {
        "source": source_name,
        "method": method_used,
        "symbol": req.symbol,
        "posts_count": len(posts),
        "time_seconds": elapsed,
        "storage": storage_result,
        "human_labels": human_labels if req.source == SourceEnum.stocktwits else None,
        "posts": posts[:10]  # Sample
    }


@app.post("/scrape/both", tags=["Scraping"])
async def scrape_both(
    subreddit: str = "Bitcoin",
    stocktwits_symbol: str = "BTC.X",
    method_reddit: MethodEnum = MethodEnum.http,
    limit_reddit: int = 50,
    limit_stocktwits: int = 50
):
    """
    Scrape Reddit ET StockTwits en une seule requete
    
    **Limites:**
    - Reddit HTTP: max 1000
    - Reddit Selenium: max 200
    - StockTwits: max 300 (Selenium)
    """
    start = time.time()
    results = {}
    
    # Reddit
    reddit_start = time.time()
    reddit_posts = scrape_reddit(subreddit, limit=limit_reddit, method=method_reddit.value)
    
    # 💾 Sauvegarde Reddit
    reddit_storage = save_posts(reddit_posts, source="reddit", method=method_reddit.value)
    
    results["reddit"] = {
        "posts_count": len(reddit_posts),
        "method": method_reddit.value,
        "time_seconds": round(time.time() - reddit_start, 2),
        "storage": reddit_storage,
        "posts": reddit_posts[:5]
    }
    
    # StockTwits
    st_start = time.time()
    st_posts = scrape_stocktwits(stocktwits_symbol, limit=limit_stocktwits)
    
    # 💾 Sauvegarde StockTwits
    st_storage = save_posts(st_posts, source="stocktwits", method="selenium")
    
    # Stats labels humains
    human_labels = {"Bullish": 0, "Bearish": 0, "None": 0}
    for p in st_posts:
        label = p.get("human_label")
        if label:
            human_labels[label] = human_labels.get(label, 0) + 1
        else:
            human_labels["None"] += 1
    
    results["stocktwits"] = {
        "posts_count": len(st_posts),
        "method": "selenium",
        "time_seconds": round(time.time() - st_start, 2),
        "storage": st_storage,
        "human_labels": human_labels,
        "posts": st_posts[:5]
    }
    
    return {
        "total_time": round(time.time() - start, 2),
        "total_posts": len(reddit_posts) + len(st_posts),
        "results": results
    }


@app.post("/sentiment", tags=["Sentiment"])
async def analyze_sentiment(texts: list[str], model: ModelEnum = ModelEnum.finbert):
    """
    Analyse sentiment de textes
    
    - **finbert**: Modele finance generale
    - **cryptobert**: Modele specifique crypto (3.2M posts)
    """
    analyzer = get_analyzer(model.value)
    results = analyzer.analyze_batch(texts)
    return {"model": model.value, "results": results}


@app.get("/prices/{crypto}", tags=["Prix"])
async def get_price(crypto: str):
    """Prix actuel via CoinGecko"""
    price = prices_client.get_price(crypto)
    if price:
        return price
    return {"error": f"Crypto {crypto} non trouvee"}


@app.post("/analyze", tags=["Analyse Complete"])
async def full_analysis(req: AnalyzeRequest):
    """
    Pipeline complet: Scraping + Sentiment + Prix
    
    **Methodes:**
    - Reddit: http (rapide, max 1000) ou selenium (lent, max 200)
    - StockTwits: selenium uniquement (max 300)
    """
    start = time.time()
    
    # Scraping
    if req.source == SourceEnum.stocktwits:
        posts = scrape_stocktwits(req.symbol, limit=req.limit)
        source_name = "StockTwits"
        method_used = "selenium"
    else:
        posts = scrape_reddit(req.symbol, limit=req.limit, method=req.method.value)
        source_name = "Reddit"
        method_used = req.method.value
    
    scrape_time = time.time() - start
    
    # Sentiment
    analyzer = get_analyzer(req.model.value)
    
    results = []
    for p in posts:
        text = clean_text(p["title"] + " " + p.get("text", ""))
        if text and len(text) > 10:
            sent = analyzer.analyze(text)
            results.append({
                "title": p["title"][:60],
                "human_label": p.get("human_label"),
                "predicted_label": sent["label"],
                "score": sent["score"]
            })
    
    sentiment_time = time.time() - start - scrape_time
    
    # Stats
    scores = [r["score"] for r in results]
    avg_score = sum(scores) / len(scores) if scores else 0
    
    labels = {"Bullish": 0, "Bearish": 0, "Neutral": 0}
    for r in results:
        labels[r["predicted_label"]] += 1
    
    # Accuracy si StockTwits
    accuracy = None
    if req.source == SourceEnum.stocktwits:
        labeled = [r for r in results if r["human_label"]]
        if labeled:
            correct = sum(1 for r in labeled if r["predicted_label"] == r["human_label"])
            accuracy = round(correct / len(labeled) * 100, 1)
    
    # Prix
    price_data = prices_client.get_price(req.crypto_id)
    
    return {
        "source": source_name,
        "method": method_used,
        "model": req.model.value,
        "crypto": req.crypto_id,
        "symbol": req.symbol,
        "posts_scraped": len(posts),
        "posts_analyzed": len(results),
        "scrape_time": round(scrape_time, 2),
        "sentiment_time": round(sentiment_time, 2),
        "total_time": round(time.time() - start, 2),
        "sentiment": {
            "average": round(avg_score, 4),
            "distribution": labels
        },
        "accuracy_vs_human": accuracy,
        "price": price_data,
        "posts": results[:20]
    }


@app.post("/analyze/both", tags=["Analyse Complete"])
async def analyze_both_sources(req: AnalyzeBothRequest):
    """
    Analyse Reddit ET StockTwits pour une crypto
    
    Permet de comparer les sentiments entre les deux plateformes.
    """
    start = time.time()
    analyzer = get_analyzer(req.model.value)
    
    results = {}
    
    # Reddit
    reddit_posts = scrape_reddit(req.subreddit, limit=req.limit_reddit, method=req.method.value)
    reddit_scores = []
    reddit_labels = {"Bullish": 0, "Bearish": 0, "Neutral": 0}
    
    for p in reddit_posts:
        text = clean_text(p["title"])
        if text:
            s = analyzer.analyze(text)
            reddit_scores.append(s["score"])
            reddit_labels[s["label"]] += 1
    
    results["reddit"] = {
        "posts": len(reddit_scores),
        "method": req.method.value,
        "avg_sentiment": round(sum(reddit_scores) / len(reddit_scores), 4) if reddit_scores else 0,
        "distribution": reddit_labels
    }
    
    # StockTwits
    st_posts = scrape_stocktwits(req.stocktwits_symbol, limit=req.limit_stocktwits)
    st_scores = []
    st_labels = {"Bullish": 0, "Bearish": 0, "Neutral": 0}
    accuracy = None
    correct = 0
    labeled_count = 0
    
    for p in st_posts:
        text = clean_text(p["title"])
        if text:
            s = analyzer.analyze(text)
            st_scores.append(s["score"])
            st_labels[s["label"]] += 1
            
            if p.get("human_label"):
                labeled_count += 1
                if s["label"] == p["human_label"]:
                    correct += 1
    
    if labeled_count > 0:
        accuracy = round(correct / labeled_count * 100, 1)
    
    results["stocktwits"] = {
        "posts": len(st_scores),
        "method": "selenium",
        "avg_sentiment": round(sum(st_scores) / len(st_scores), 4) if st_scores else 0,
        "distribution": st_labels,
        "accuracy_vs_human": accuracy
    }
    
    # Prix
    price_data = prices_client.get_price(req.crypto_id)
    
    return {
        "crypto": req.crypto_id,
        "model": req.model.value,
        "total_time": round(time.time() - start, 2),
        "price": price_data,
        "results": results
    }


@app.post("/compare/models", tags=["Comparaison"])
async def compare_models(req: CompareModelsRequest):
    """
    Compare FinBERT vs CryptoBERT sur les memes posts
    
    Utilise StockTwits pour avoir les labels humains et calculer l'accuracy!
    """
    start = time.time()
    
    # Scraping
    if req.source == SourceEnum.stocktwits:
        posts = scrape_stocktwits(req.symbol, limit=req.limit)
    else:
        posts = scrape_reddit(req.symbol, limit=req.limit, method=req.method.value)
    
    # Analyseurs
    finbert = get_analyzer("finbert")
    cryptobert = get_analyzer("cryptobert")
    
    results = []
    for p in posts:
        text = clean_text(p["title"])
        if not text or len(text) < 10:
            continue
        
        fin = finbert.analyze(text)
        cry = cryptobert.analyze(text)
        
        results.append({
            "text": text[:50],
            "human_label": p.get("human_label"),
            "finbert_label": fin["label"],
            "finbert_score": fin["score"],
            "cryptobert_label": cry["label"],
            "cryptobert_score": cry["score"],
        })
    
    # Stats
    fin_scores = [r["finbert_score"] for r in results]
    cry_scores = [r["cryptobert_score"] for r in results]
    
    # Accuracy si labels disponibles
    labeled = [r for r in results if r["human_label"]]
    accuracy = {}
    if labeled:
        fin_correct = sum(1 for r in labeled if r["finbert_label"] == r["human_label"])
        cry_correct = sum(1 for r in labeled if r["cryptobert_label"] == r["human_label"])
        accuracy = {
            "finbert": round(fin_correct / len(labeled) * 100, 1),
            "cryptobert": round(cry_correct / len(labeled) * 100, 1),
            "labeled_posts": len(labeled),
            "winner": "cryptobert" if cry_correct > fin_correct else "finbert" if fin_correct > cry_correct else "tie"
        }
    
    return {
        "source": req.source.value,
        "method": req.method.value if req.source == SourceEnum.reddit else "selenium",
        "symbol": req.symbol,
        "posts_analyzed": len(results),
        "time_seconds": round(time.time() - start, 2),
        "finbert": {
            "avg_score": round(sum(fin_scores) / len(fin_scores), 4) if fin_scores else 0
        },
        "cryptobert": {
            "avg_score": round(sum(cry_scores) / len(cry_scores), 4) if cry_scores else 0
        },
        "accuracy": accuracy if accuracy else None,
        "posts": results[:15]
    }


@app.post("/compare/sources", tags=["Comparaison"])
async def compare_sources(
    crypto_id: str = "bitcoin",
    limit: int = 50,
    model: ModelEnum = ModelEnum.finbert,
    method_reddit: MethodEnum = MethodEnum.http
):
    """
    Compare Reddit vs StockTwits pour la meme crypto
    """
    config = CRYPTO_CONFIG.get(crypto_id, {"sub": "Bitcoin", "stocktwits": "BTC.X"})
    analyzer = get_analyzer(model.value)
    
    results = {}
    
    # Reddit
    start = time.time()
    reddit_posts = scrape_reddit(config["sub"], limit=limit, method=method_reddit.value)
    reddit_scores = []
    for p in reddit_posts:
        text = clean_text(p["title"])
        if text:
            s = analyzer.analyze(text)
            reddit_scores.append(s["score"])
    
    results["reddit"] = {
        "posts": len(reddit_scores),
        "method": method_reddit.value,
        "time": round(time.time() - start, 2),
        "avg_sentiment": round(sum(reddit_scores) / len(reddit_scores), 4) if reddit_scores else 0
    }
    
    # StockTwits
    start = time.time()
    st_posts = scrape_stocktwits(config["stocktwits"], limit=limit)
    st_scores = []
    for p in st_posts:
        text = clean_text(p["title"])
        if text:
            s = analyzer.analyze(text)
            st_scores.append(s["score"])
    
    results["stocktwits"] = {
        "posts": len(st_scores),
        "method": "selenium",
        "time": round(time.time() - start, 2),
        "avg_sentiment": round(sum(st_scores) / len(st_scores), 4) if st_scores else 0
    }
    
    return {
        "crypto": crypto_id,
        "model": model.value,
        "results": results
    }


# ===================== ENDPOINTS STOCKAGE =====================

@app.get("/storage/stats", tags=["Stockage"])
async def storage_stats():
    """
    Statistiques sur les données stockées
    
    Retourne le nombre total de posts sauvegardés, répartition par source/méthode,
    et dates du premier et dernier scrape.
    """
    return get_stats()


@app.get("/storage/posts", tags=["Stockage"])
async def get_stored_posts(
    source: str | None = None,
    method: str | None = None,
    limit: int = 100
):
    """
    Récupérer les posts stockés avec filtres optionnels
    
    - **source**: reddit ou stocktwits
    - **method**: http ou selenium
    - **limit**: nombre max de résultats
    """
    posts = get_all_posts(source=source, method=method, limit=limit)
    return {
        "count": len(posts),
        "source_filter": source,
        "method_filter": method,
        "posts": posts
    }


@app.get("/storage/export/csv", tags=["Stockage"])
async def export_csv(
    source: str | None = None,
    method: str | None = None
):
    """
    Exporter les données en CSV
    
    Génère un fichier CSV dans data/exports/ avec tous les posts filtrés.
    """
    filepath = export_to_csv(source=source, method=method)
    return {
        "success": True,
        "filepath": filepath,
        "message": f"Données exportées avec succès"
    }


@app.get("/storage/export/json", tags=["Stockage"])
async def export_json(
    source: str | None = None,
    method: str | None = None
):
    """
    Exporter les données en JSON
    
    Génère un fichier JSON dans data/exports/ avec tous les posts filtrés.
    """
    filepath = export_to_json(source=source, method=method)
    return {
        "success": True,
        "filepath": filepath,
        "message": f"Données exportées avec succès"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
