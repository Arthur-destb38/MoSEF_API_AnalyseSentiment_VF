"""
API Crypto Sentiment - Projet MoSEF 2024-2025
Universite Paris 1 Pantheon-Sorbonne

Sources: Reddit, StockTwits, Twitter, YouTube
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
)

# NLP et utils
from app.nlp import SentimentAnalyzer
from app.prices import CryptoPrices
from app.utils import clean_text
from app.storage import save_posts, export_to_csv, export_to_json, get_stats


# ===================== CONFIG FASTAPI =====================

app = FastAPI(
    title="Crypto Sentiment API",
    description="Analyse de sentiment crypto via scraping et NLP",
    version="1.0"
)

templates = Jinja2Templates(directory="templates")


# ===================== INSTANCES GLOBALES =====================

finbert_analyzer = None
cryptobert_analyzer = None
prices_client = CryptoPrices()


def get_analyzer(model: str = "finbert"):
    """Charge le modele NLP (lazy loading)"""
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
    """Plateformes disponibles"""
    reddit = "reddit"
    stocktwits = "stocktwits"
    twitter = "twitter"
    youtube = "youtube"


class ModelEnum(str, Enum):
    """Modeles NLP"""
    finbert = "finbert"
    cryptobert = "cryptobert"


# ===================== CONFIG PLATEFORMES =====================

PLATFORM_CONFIG = {
    "reddit": {"method": "http", "max_posts": 1000},
    "stocktwits": {"method": "selenium", "max_posts": 1000},
    "twitter": {"method": "selenium", "max_posts": 2000},
    "youtube": {"method": "api", "max_posts": 500},
}


# ===================== CONFIG CRYPTOS =====================

CRYPTO_CONFIG = {
    "bitcoin": {"symbol": "BTC", "subreddit": "Bitcoin", "stocktwits": "BTC.X"},
    "ethereum": {"symbol": "ETH", "subreddit": "ethereum", "stocktwits": "ETH.X"},
    "solana": {"symbol": "SOL", "subreddit": "solana", "stocktwits": "SOL.X"},
    "cardano": {"symbol": "ADA", "subreddit": "cardano", "stocktwits": "ADA.X"},
}


# ===================== MODELS PYDANTIC =====================

class ScrapeRequest(BaseModel):
    """Requete de scraping"""
    source: SourceEnum = Field(default=SourceEnum.reddit)
    crypto: str = Field(default="bitcoin", description="Crypto a scraper")
    limit: int = Field(default=50, ge=10, le=2000)


class SentimentRequest(BaseModel):
    """Requete d'analyse sentiment"""
    texts: List[str] = Field(description="Liste de textes a analyser")
    model: ModelEnum = Field(default=ModelEnum.finbert)


class AnalyzeRequest(BaseModel):
    """Requete d'analyse complete"""
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
    """Scrape une plateforme pour une crypto"""
    posts = []

    if source == "reddit":
        posts = scrape_reddit(crypto_conf["subreddit"], limit=limit, method="http")
    elif source == "stocktwits":
        posts = scrape_stocktwits(crypto_conf["stocktwits"], limit=limit)
    elif source == "twitter":
        posts = scrape_twitter(crypto_conf["symbol"], limit=limit)
    elif source == "youtube":
        posts = scrape_youtube(crypto_conf["symbol"], limit=limit)

    return posts


# ===================== PAGE HTML =====================

@app.get("/", response_class=HTMLResponse, tags=["Pages"])
async def home(request: Request):
    """Page d'accueil"""
    prices = prices_client.get_multiple_prices(["bitcoin", "ethereum", "solana"])
    return templates.TemplateResponse("index.html", {
        "request": request,
        "prices": prices,
        "platforms": PLATFORM_CONFIG
    })


# ===================== ENDPOINTS INFO =====================

@app.get("/health", tags=["Info"])
async def health():
    """Health check"""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


@app.get("/limits", tags=["Info"])
async def get_limits():
    """Limites de scraping par plateforme"""
    return PLATFORM_CONFIG


# ===================== ENDPOINT SCRAPING =====================

@app.post("/scrape", tags=["Scraping"])
async def scrape(req: ScrapeRequest):
    """Scrape les posts d'une plateforme pour une crypto"""
    start = time.time()

    platform = PLATFORM_CONFIG.get(req.source.value)
    limit = min(req.limit, platform["max_posts"])

    crypto_conf = CRYPTO_CONFIG.get(req.crypto, {
        "symbol": req.crypto.upper(),
        "subreddit": req.crypto,
        "stocktwits": f"{req.crypto.upper()}.X"
    })

    posts = scrape_platform(req.source.value, crypto_conf, limit)

    # Sauvegarder
    save_posts(posts, source=req.source.value, method=platform["method"])

    return {
        "source": req.source.value,
        "method": platform["method"],
        "crypto": req.crypto,
        "posts_count": len(posts),
        "time_seconds": round(time.time() - start, 2),
        "sample": posts[:10]
    }


# ===================== ENDPOINT PRIX =====================

@app.get("/prices/{crypto}", tags=["Prix"])
async def get_price(crypto: str):
    """Prix actuel via CoinGecko"""
    price = prices_client.get_price(crypto)
    if price:
        return price
    return {"error": f"Crypto {crypto} non trouvee"}


# ===================== ENDPOINT SENTIMENT =====================

@app.post("/sentiment", tags=["NLP"])
async def analyze_sentiment(req: SentimentRequest):
    """Analyse le sentiment d'une liste de textes"""
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

    return {"model": req.model.value, "count": len(results), "results": results}


# ===================== ENDPOINT ANALYSE COMPLETE =====================

@app.post("/analyze", tags=["Analyse"])
async def full_analysis(req: AnalyzeRequest):
    """Pipeline complet: Scraping + Sentiment"""
    start = time.time()

    platform = PLATFORM_CONFIG.get(req.source.value)
    limit = min(req.limit, platform["max_posts"])
    crypto_conf = CRYPTO_CONFIG.get(req.crypto, {
        "symbol": req.crypto.upper(),
        "subreddit": req.crypto,
        "stocktwits": f"{req.crypto.upper()}.X"
    })

    # Scraping
    posts = scrape_platform(req.source.value, crypto_conf, limit)
    scrape_time = round(time.time() - start, 2)

    # Analyse sentiment
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

    avg_score = round(sum(scores) / len(scores), 4) if scores else 0

    # Accuracy si labels humains
    accuracy = None
    labeled = [r for r in results if r["human_label"]]
    if labeled:
        correct = sum(1 for r in labeled if r["label"] == r["human_label"])
        accuracy = round(correct / len(labeled) * 100, 1)

    price_data = prices_client.get_price(req.crypto)

    return {
        "source": req.source.value,
        "method": platform["method"],
        "model": req.model.value,
        "crypto": req.crypto,
        "posts_analyzed": len(results),
        "scrape_time": scrape_time,
        "total_time": round(time.time() - start, 2),
        "sentiment": {"average": avg_score, "distribution": labels},
        "accuracy_vs_human": accuracy,
        "price": price_data,
        "posts": results[:20]
    }


# ===================== ENDPOINT COMPARAISON =====================

@app.post("/compare/models", tags=["Comparaison"])
async def compare_models(req: CompareRequest):
    """Compare FinBERT vs CryptoBERT"""
    start = time.time()

    platform = PLATFORM_CONFIG.get(req.source.value)
    limit = min(req.limit, platform["max_posts"])
    crypto_conf = CRYPTO_CONFIG.get(req.crypto, {
        "symbol": req.crypto.upper(),
        "subreddit": req.crypto,
        "stocktwits": f"{req.crypto.upper()}.X"
    })

    posts = scrape_platform(req.source.value, crypto_conf, limit)

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

    fin_scores = [r["finbert"]["score"] for r in results]
    cry_scores = [r["cryptobert"]["score"] for r in results]

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
    """Stats sur les donnees stockees"""
    return get_stats()


@app.get("/storage/export/csv", tags=["Stockage"])
async def export_csv_endpoint(source: Optional[str] = None):
    """Export CSV"""
    filepath = export_to_csv(source=source)
    return {"success": True, "filepath": filepath}


@app.get("/storage/export/json", tags=["Stockage"])
async def export_json_endpoint(source: Optional[str] = None):
    """Export JSON"""
    filepath = export_to_json(source=source)
    return {"success": True, "filepath": filepath}


# ===================== MAIN =====================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)