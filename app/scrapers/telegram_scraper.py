"""
Telegram Public Channel Scraper
Sans API / Sans compte dev - Méthode web scraping

Pour le projet Crypto Sentiment API - MoSEF
"""

import requests
from bs4 import BeautifulSoup
import time
import re
from datetime import datetime
from typing import Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============ CHANNELS CRYPTO POPULAIRES ============

CRYPTO_CHANNELS = {
    # News & Annonces
    "CoinMarketCapAnnouncements": "Annonces CoinMarketCap",
    "caborance": "Crypto Annonces FR",
    "bitcoinnews": "Bitcoin News",
    "cryptonewscom": "CryptoNews",
    
    # Whale Alerts & Trading
    "whale_alert_io": "Whale Alert - Gros mouvements",
    "WhaleTankCrypto": "Whale Tank",
    
    # Communautés
    "Bitcoin": "Bitcoin Official",
    "ethereum": "Ethereum",
    "solaborance": "Solana",
    
    # Trading & Signals (attention: souvent du spam)
    "cryptosignalalert": "Crypto Signals",
}


# ============ MÉTHODE 1: REQUESTS SIMPLE ============

def scrape_telegram_simple(channel: str, limit: int = 30) -> list[dict]:
    """
    Scrape basique avec requests - ~20-30 messages max
    
    Args:
        channel: Nom du channel (sans @)
        limit: Nombre max de messages (plafonné à ~30)
    
    Returns:
        Liste de messages avec text, date approximative, channel
    """
    url = f"https://t.me/s/{channel}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"Erreur requête {channel}: {e}")
        return []
    
    soup = BeautifulSoup(response.text, 'html.parser')
    messages = []
    
    # Trouver tous les messages
    message_wraps = soup.find_all('div', class_='tgme_widget_message_wrap')
    
    for wrap in message_wraps[:limit]:
        try:
            # Texte du message
            text_div = wrap.find('div', class_='tgme_widget_message_text')
            if not text_div:
                continue
            
            text = text_div.get_text(strip=True)
            if not text or len(text) < 5:
                continue
            
            # Date du message
            time_tag = wrap.find('time', class_='time')
            date_str = None
            if time_tag and time_tag.get('datetime'):
                date_str = time_tag['datetime']
            
            # Vues
            views_span = wrap.find('span', class_='tgme_widget_message_views')
            views = 0
            if views_span:
                views_text = views_span.get_text(strip=True)
                views = parse_views(views_text)
            
            messages.append({
                "text": clean_text(text),
                "date": date_str,
                "views": views,
                "channel": channel,
                "source": "telegram"
            })
            
        except Exception as e:
            logger.warning(f"Erreur parsing message: {e}")
            continue
    
    logger.info(f"[{channel}] {len(messages)} messages récupérés (méthode simple)")
    return messages


# ============ MÉTHODE 2: AVEC PAGINATION (AJAX) ============

def scrape_telegram_paginated(channel: str, max_messages: int = 200) -> list[dict]:
    """
    Scrape avec pagination AJAX - jusqu'à ~200-500 messages
    
    Telegram charge les anciens messages via des requêtes AJAX
    quand on scroll. On simule ça avec le paramètre 'before'.
    
    Args:
        channel: Nom du channel
        max_messages: Nombre max de messages à récupérer
    
    Returns:
        Liste de messages
    """
    base_url = f"https://t.me/s/{channel}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "X-Requested-With": "XMLHttpRequest",
    }
    
    all_messages = []
    before_id = None
    page = 0
    max_pages = max_messages // 20 + 1  # ~20 messages par page
    
    while len(all_messages) < max_messages and page < max_pages:
        # Construire l'URL avec pagination
        if before_id:
            url = f"{base_url}?before={before_id}"
        else:
            url = base_url
        
        try:
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
        except requests.RequestException as e:
            logger.error(f"Erreur page {page}: {e}")
            break
        
        soup = BeautifulSoup(response.text, 'html.parser')
        message_wraps = soup.find_all('div', class_='tgme_widget_message_wrap')
        
        if not message_wraps:
            logger.info(f"Plus de messages après page {page}")
            break
        
        new_messages = 0
        oldest_id = None
        
        for wrap in message_wraps:
            try:
                # Récupérer l'ID du message pour la pagination
                msg_div = wrap.find('div', class_='tgme_widget_message')
                if msg_div and msg_div.get('data-post'):
                    post_id = msg_div['data-post'].split('/')[-1]
                    oldest_id = post_id
                
                # Texte
                text_div = wrap.find('div', class_='tgme_widget_message_text')
                if not text_div:
                    continue
                
                text = text_div.get_text(strip=True)
                if not text or len(text) < 5:
                    continue
                
                # Éviter les doublons
                if any(m['text'] == text for m in all_messages):
                    continue
                
                # Date
                time_tag = wrap.find('time', class_='time')
                date_str = time_tag['datetime'] if time_tag and time_tag.get('datetime') else None
                
                # Vues
                views_span = wrap.find('span', class_='tgme_widget_message_views')
                views = parse_views(views_span.get_text(strip=True)) if views_span else 0
                
                all_messages.append({
                    "text": clean_text(text),
                    "date": date_str,
                    "views": views,
                    "channel": channel,
                    "source": "telegram"
                })
                new_messages += 1
                
            except Exception as e:
                continue
        
        logger.info(f"[{channel}] Page {page}: +{new_messages} messages (total: {len(all_messages)})")
        
        if new_messages == 0 or not oldest_id:
            break
        
        before_id = oldest_id
        page += 1
        time.sleep(1)  # Rate limiting - important !
    
    return all_messages[:max_messages]


# ============ MÉTHODE 3: MULTI-CHANNEL ============

def scrape_multiple_channels(
    channels: list[str] = None,
    messages_per_channel: int = 100,
    use_pagination: bool = True
) -> dict:
    """
    Scrape plusieurs channels d'un coup
    
    Args:
        channels: Liste de channels (défaut: CRYPTO_CHANNELS)
        messages_per_channel: Messages par channel
        use_pagination: Utiliser la pagination pour plus de messages
    
    Returns:
        Dict avec stats et tous les messages
    """
    if channels is None:
        channels = list(CRYPTO_CHANNELS.keys())
    
    all_data = []
    stats = {}
    
    scrape_func = scrape_telegram_paginated if use_pagination else scrape_telegram_simple
    
    for channel in channels:
        logger.info(f"Scraping {channel}...")
        
        messages = scrape_func(channel, messages_per_channel)
        stats[channel] = len(messages)
        all_data.extend(messages)
        
        time.sleep(2)  # Pause entre channels
    
    return {
        "status": "success",
        "total_messages": len(all_data),
        "channels_scraped": len(channels),
        "stats_per_channel": stats,
        "posts": all_data
    }


# ============ HELPERS ============

def clean_text(text: str) -> str:
    """Nettoie le texte pour l'analyse de sentiment"""
    # Supprimer les URLs
    text = re.sub(r'http\S+|www\.\S+', '', text)
    # Supprimer les mentions
    text = re.sub(r'@\w+', '', text)
    # Supprimer les emojis excessifs (garder quelques-uns)
    text = re.sub(r'[\U0001F600-\U0001F64F]{3,}', '', text)
    # Nettoyer les espaces
    text = ' '.join(text.split())
    return text.strip()


def parse_views(views_str: str) -> int:
    """Parse '1.2K' ou '5M' en nombre"""
    if not views_str:
        return 0
    
    views_str = views_str.strip().upper()
    
    try:
        if 'K' in views_str:
            return int(float(views_str.replace('K', '')) * 1000)
        elif 'M' in views_str:
            return int(float(views_str.replace('M', '')) * 1_000_000)
        else:
            return int(views_str)
    except ValueError:
        return 0


# ============ FASTAPI INTEGRATION ============

def get_fastapi_router():
    """
    Retourne un router FastAPI prêt à intégrer
    
    Usage dans ton main.py:
        from telegram_scraper import get_fastapi_router
        app.include_router(get_fastapi_router(), prefix="/telegram", tags=["Telegram"])
    """
    from fastapi import APIRouter, Query
    from pydantic import BaseModel
    from typing import Optional
    
    router = APIRouter()
    
    class TelegramScrapeRequest(BaseModel):
        channels: Optional[list[str]] = None
        limit: int = 50
        use_pagination: bool = True
    
    @router.get("/channels")
    def list_channels():
        """Liste les channels crypto disponibles"""
        return {
            "channels": CRYPTO_CHANNELS,
            "count": len(CRYPTO_CHANNELS)
        }
    
    @router.get("/scrape/{channel}")
    def scrape_single_channel(
        channel: str,
        limit: int = Query(default=50, ge=1, le=500)
    ):
        """Scrape un channel spécifique"""
        if limit > 30:
            messages = scrape_telegram_paginated(channel, limit)
        else:
            messages = scrape_telegram_simple(channel, limit)
        
        return {
            "status": "success",
            "channel": channel,
            "count": len(messages),
            "posts": messages
        }
    
    @router.post("/scrape")
    def scrape_channels(request: TelegramScrapeRequest):
        """Scrape plusieurs channels"""
        return scrape_multiple_channels(
            channels=request.channels,
            messages_per_channel=request.limit,
            use_pagination=request.use_pagination
        )
    
    return router


# ============ MAIN / TEST ============

if __name__ == "__main__":
    print("=" * 50)
    print("TEST TELEGRAM SCRAPER")
    print("=" * 50)
    
    # Test simple
    print("\n[TEST 1] Méthode simple - whale_alert_io")
    messages = scrape_telegram_simple("whale_alert_io", limit=10)
    for msg in messages[:3]:
        print(f"  - {msg['text'][:80]}...")
    
    # Test pagination
    print("\n[TEST 2] Méthode paginée - CoinMarketCapAnnouncements")
    messages = scrape_telegram_paginated("CoinMarketCapAnnouncements", max_messages=50)
    print(f"  Total: {len(messages)} messages")
    
    # Test multi-channel
    print("\n[TEST 3] Multi-channels")
    result = scrape_multiple_channels(
        channels=["whale_alert_io", "bitcoinnews"],
        messages_per_channel=30
    )
    print(f"  Total: {result['total_messages']} messages")
    print(f"  Stats: {result['stats_per_channel']}")
