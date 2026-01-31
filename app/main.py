"""
API Crypto Sentiment - Projet MoSEF 2024-2025
Universite Paris 1 Pantheon-Sorbonne

Sources: Reddit, StockTwits, Twitter, YouTube, Telegram, Bluesky
Modeles NLP: FinBERT, CryptoBERT
"""

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime
from typing import Optional, List
import time

# Scrapers
from app.scrapers import (
    scrape_reddit,
    scrape_stocktwits,
    scrape_twitter,
    scrape_youtube,
    scrape_telegram_simple,
    scrape_telegram_paginated,
    scrape_bluesky,
)

# NLP et utils
from app.nlp import SentimentAnalyzer
from app.prices import CryptoPrices
from app.utils import clean_text
from app.storage import save_posts, get_all_posts, export_to_csv, export_to_json, get_stats


# ===================== CONFIG =====================

app = FastAPI(
    title="Crypto Sentiment API",
    description="Analyse de sentiment crypto via scraping et NLP",
    version="1.0"
)

templates = Jinja2Templates(directory="templates")

# Instances globales (lazy loading)
finbert_analyzer = None
cryptobert_analyzer = None
prices_client = CryptoPrices()


def get_analyzer(model: str = "finbert"):
    """Charge le modele NLP (une seule fois en memoire)"""
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
    """Plateformes disponibles pour le scraping"""
    reddit = "reddit"
    stocktwits = "stocktwits"
    twitter = "twitter"
    youtube = "youtube"
    telegram = "telegram"
    bluesky = "bluesky"


class ModelEnum(str, Enum):
    """Modeles NLP disponibles"""
    finbert = "finbert"
    cryptobert = "cryptobert"


# ===================== LIMITES PAR PLATEFORME =====================

PLATFORM_CONFIG = {
    "reddit": {
        "method": "http",
        "max_posts": 1000,
        "description": "API JSON Reddit"
    },
    "stocktwits": {
        "method": "selenium",
        "max_posts": 1000,
        "description": "Selenium (Cloudflare)"
    },
    "twitter": {
        "method": "selenium",
        "max_posts": 2000,
        "description": "Selenium avec cookies"
    },
    "youtube": {
        "method": "api",
        "max_posts": 500,
        "description": "API YouTube"
    },
    "telegram": {
        "method": "http",
        "max_posts": 500,
        "description": "HTTP avec pagination"
    },
    "bluesky": {
        "method": "api",
        "max_posts": 200,
        "description": "API Bluesky"
    }
}


# ===================== CRYPTO CONFIG =====================

CRYPTO_CONFIG = {
    "bitcoin": {"symbol": "BTC", "subreddit": "Bitcoin", "stocktwits": "BTC.X"},
    "ethereum": {"symbol": "ETH", "subreddit": "ethereum", "stocktwits": "ETH.X"},
    "solana": {"symbol": "SOL", "subreddit": "solana", "stocktwits": "SOL.X"},
    "cardano": {"symbol": "ADA", "subreddit": "cardano", "stocktwits": "ADA.X"},
    "dogecoin": {"symbol": "DOGE", "subreddit": "dogecoin", "stocktwits": "DOGE.X"},
    "ripple": {"symbol": "XRP", "subreddit": "xrp", "stocktwits": "XRP.X"},
}


# ===================== MODELS PYDANTIC =====================

class ScrapeRequest(BaseModel):
    """Requete de scraping - une plateforme, plusieurs cryptos possibles"""
    source: SourceEnum = Field(default=SourceEnum.reddit, description="Plateforme a scraper")
    cryptos: List[str] = Field(default=["bitcoin"], description="Liste de cryptos")
    limit: int = Field(default=50, ge=10, le=2000, description="Nombre de posts par crypto")


class AnalyzeRequest(BaseModel):
    """Requete d'analyse complete (scraping + sentiment)"""
    source: SourceEnum = Field(default=SourceEnum.reddit)
    crypto: str = Field(default="bitcoin")
    model: ModelEnum = Field(default=ModelEnum.finbert)
    limit: int = Field(default=50, ge=10, le=1000)


class CompareRequest(BaseModel):
    """Requete de comparaison FinBERT vs CryptoBERT"""
    source: SourceEnum = Field(default=SourceEnum.reddit)
    crypto: str = Field(default="bitcoin")
    limit: int = Field(default=50, ge=10, le=500)


# ===================== HELPER SCRAPING =====================

def scrape_platform(source: str, crypto_conf: dict, limit: int) -> list:
    """Scrape une plateforme pour une crypto donnee"""
    posts = []

    if source == "reddit":
        posts = scrape_reddit(crypto_conf["subreddit"], limit=limit, method="http")
    elif source == "stocktwits":
        posts = scrape_stocktwits(crypto_conf["stocktwits"], limit=limit)
    elif source == "twitter":
        posts = scrape_twitter(crypto_conf["symbol"], limit=limit)
    elif source == "youtube":
        posts = scrape_youtube(crypto_conf["symbol"], limit=limit)
    elif source == "telegram":
        if limit > 30:
            posts = scrape_telegram_paginated(crypto_conf["symbol"], limit)
        else:
            posts = scrape_telegram_simple(crypto_conf["symbol"], limit)
    elif source == "bluesky":
        posts = scrape_bluesky(crypto_conf["symbol"], limit=limit)

    return posts


# ===================== PAGE HTML =====================

@app.get("/", response_class=HTMLResponse, tags=["Pages"])
async def home(request: Request):
    """Page d'accueil avec interface de test"""
    prices = prices_client.get_multiple_prices(["bitcoin", "ethereum", "solana"])
    return templates.TemplateResponse("index.html", {
        "request": request,
        "prices": prices,
        "platforms": PLATFORM_CONFIG
    })


# ===================== ENDPOINTS INFO =====================

@app.get("/health", tags=["Info"])
async def health():
    """Verification que l'API fonctionne"""
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat()
    }


@app.get("/limits", tags=["Info"])
async def get_limits():
    """Limites de scraping par plateforme"""
    return PLATFORM_CONFIG


# ===================== ENDPOINT SCRAPING =====================

@app.post("/scrape", tags=["Scraping"])
async def scrape(req: ScrapeRequest):
    """
    Scrape les posts d'une plateforme pour une ou plusieurs cryptos

    - Une seule plateforme a la fois (pour eviter les bans)
    - Plusieurs cryptos possibles
    """
    start = time.time()

    # Config plateforme
    platform = PLATFORM_CONFIG.get(req.source.value)
    if not platform:
        return {"error": f"Plateforme {req.source} non supportee"}

    # Limite max
    limit = min(req.limit, platform["max_posts"])
    method_used = platform["method"]

    # Scraper chaque crypto
    all_results = {}
    total_posts = 0

    for crypto in req.cryptos:
        crypto_conf = CRYPTO_CONFIG.get(crypto, {
            "symbol": crypto.upper(),
            "subreddit": crypto,
            "stocktwits": f"{crypto.upper()}.X"
        })

        posts = scrape_platform(req.source.value, crypto_conf, limit)

        # Sauvegarder
        save_posts(posts, source=req.source.value, method=method_used)

        all_results[crypto] = {
            "posts_count": len(posts),
            "posts_sample": posts[:5]
        }
        total_posts += len(posts)

    return {
        "source": req.source.value,
        "method": method_used,
        "cryptos": req.cryptos,
        "total_posts": total_posts,
        "time_seconds": round(time.time() - start, 2),
        "results": all_results
    }


# ===================== ENDPOINT PRIX =====================

@app.get("/prices/{crypto}", tags=["Prix"])
async def get_price(crypto: str):
    """Prix actuel d'une crypto via CoinGecko"""
    price = prices_client.get_price(crypto)
    if price:
        return price
    return {"error": f"Crypto {crypto} non trouvee"}


# ===================== ENDPOINT SENTIMENT =====================

class SentimentRequest(BaseModel):
    """Requete d'analyse sentiment"""
    texts: List[str] = Field(description="Liste de textes a analyser")
    model: ModelEnum = Field(default=ModelEnum.finbert)


@app.post("/sentiment", tags=["NLP"])
async def analyze_sentiment(req: SentimentRequest):
    """
    Analyse le sentiment d'une liste de textes

    Retourne: label (Bullish/Bearish/Neutral) et score
    """
    analyzer = get_analyzer(req.model.value)
    results = []

    for text in req.texts:
        cleaned = clean_text(text)
        if cleaned and len(cleaned) > 5:
            result = analyzer.analyze(cleaned)
            results.append({
                "text": text[:50],
                "label": result["label"],
                "score": result["score"]
            })

    return {
        "model": req.model.value,
        "count": len(results),
        "results": results
    }
# ===================== ENDPOINT ANALYSE COMPLETE =====================

@app.post("/analyze", tags=["Analyse"])
async def full_analysis(req: AnalyzeRequest):
    """
    Pipeline complet: Scraping + Analyse sentiment
    """
    start = time.time()

    # Config
    platform = PLATFORM_CONFIG.get(req.source.value)
    limit = min(req.limit, platform["max_posts"])
    crypto_conf = CRYPTO_CONFIG.get(req.crypto, {
        "symbol": req.crypto.upper(),
        "subreddit": req.crypto,
        "stocktwits": f"{req.crypto.upper()}.X"
    })

    # 1. Scraping
    posts = scrape_platform(req.source.value, crypto_conf, limit)
    scrape_time = round(time.time() - start, 2)

    # 2. Analyse sentiment
    analyzer = get_analyzer(req.model.value)
    results = []
    labels = {"Bullish": 0, "Bearish": 0, "Neutral": 0}
    scores = []

    for p in posts:
        text = clean_text(p.get("title", "") + " " + p.get("text", ""))
        if text and len(text) > 10:
            sent = analyzer.analyze(text)
            scores.append(sent["score"])
            labels[sent["label"]] += 1
            results.append({
                "title": p.get("title", "")[:60],
                "label": sent["label"],
                "score": sent["score"],
                "human_label": p.get("human_label")
            })

    # Stats
    avg_score = round(sum(scores) / len(scores), 4) if scores else 0

    # Accuracy si labels humains
    accuracy = None
    labeled = [r for r in results if r["human_label"]]
    if labeled:
        correct = sum(1 for r in labeled if r["label"] == r["human_label"])
        accuracy = round(correct / len(labeled) * 100, 1)

    # Prix
    price_data = prices_client.get_price(req.crypto)

    return {
        "source": req.source.value,
        "method": platform["method"],
        "model": req.model.value,
        "crypto": req.crypto,
        "posts_analyzed": len(results),
        "scrape_time": scrape_time,
        "total_time": round(time.time() - start, 2),
        "sentiment": {
            "average": avg_score,
            "distribution": labels
        },
        "accuracy_vs_human": accuracy,
        "price": price_data,
        "posts": results[:20]
    }


# ===================== ENDPOINT COMPARAISON =====================

@app.post("/compare/models", tags=["Comparaison"])
async def compare_models(req: CompareRequest):
    """
    Compare FinBERT vs CryptoBERT sur les memes posts
    """
    start = time.time()

    # Config
    platform = PLATFORM_CONFIG.get(req.source.value)
    limit = min(req.limit, platform["max_posts"])
    crypto_conf = CRYPTO_CONFIG.get(req.crypto, {
        "symbol": req.crypto.upper(),
        "subreddit": req.crypto,
        "stocktwits": f"{req.crypto.upper()}.X"
    })

    # Scraping
    posts = scrape_platform(req.source.value, crypto_conf, limit)

    # Analyse avec les deux modeles
    finbert = get_analyzer("finbert")
    cryptobert = get_analyzer("cryptobert")

    results = []
    for p in posts:
        text = clean_text(p.get("title", ""))
        if not text or len(text) < 10:
            continue

        fin = finbert.analyze(text)
        cry = cryptobert.analyze(text)

        results.append({
            "text": text[:50],
            "human_label": p.get("human_label"),
            "finbert": {"label": fin["label"], "score": round(fin["score"], 3)},
            "cryptobert": {"label": cry["label"], "score": round(cry["score"], 3)}
        })

    # Stats
    fin_scores = [r["finbert"]["score"] for r in results]
    cry_scores = [r["cryptobert"]["score"] for r in results]

    # Accuracy si labels humains
    accuracy = None
    labeled = [r for r in results if r["human_label"]]
    if labeled:
        fin_correct = sum(1 for r in labeled if r["finbert"]["label"] == r["human_label"])
        cry_correct = sum(1 for r in labeled if r["cryptobert"]["label"] == r["human_label"])
        accuracy = {
            "finbert": round(fin_correct / len(labeled) * 100, 1),
            "cryptobert": round(cry_correct / len(labeled) * 100, 1),
            "labeled_posts": len(labeled),
            "winner": "cryptobert" if cry_correct > fin_correct else "finbert" if fin_correct > cry_correct else "egalite"
        }

    return {
        "source": req.source.value,
        "crypto": req.crypto,
        "posts_analyzed": len(results),
        "time_seconds": round(time.time() - start, 2),
        "finbert_avg": round(sum(fin_scores) / len(fin_scores), 4) if fin_scores else 0,
        "cryptobert_avg": round(sum(cry_scores) / len(cry_scores), 4) if cry_scores else 0,
        "accuracy": accuracy,
        "posts": results[:15]
    }


# ===================== ENDPOINTS STOCKAGE =====================

@app.get("/storage/stats", tags=["Stockage"])
async def storage_stats():
    """Statistiques sur les donnees stockees"""
    return get_stats()


@app.get("/storage/posts", tags=["Stockage"])
async def get_stored_posts(source: Optional[str] = None, limit: int = 100):
    """Recuperer les posts stockes"""
    posts = get_all_posts(source=source, limit=limit)
    return {
        "count": len(posts),
        "source_filter": source,
        "posts": posts
    }


@app.get("/storage/export/csv", tags=["Stockage"])
async def export_csv_endpoint(source: Optional[str] = None):
    """Exporter en CSV"""
    filepath = export_to_csv(source=source)
    return {"success": True, "filepath": filepath}


@app.get("/storage/export/json", tags=["Stockage"])
async def export_json_endpoint(source: Optional[str] = None):
    """Exporter en JSON"""
    filepath = export_to_json(source=source)
    return {"success": True, "filepath": filepath}


# ===================== MAIN =====================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)