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
    # News & Actualités
    "bitcoinnews": "Bitcoin News",
    "cryptonewscom": "CryptoNews",
    
    # Whale Alerts
    "whale_alert_io": "Whale Alert - Gros mouvements",
    
    # Communautés officielles
    "Bitcoin": "Bitcoin Official",
    "ethereum": "Ethereum",
}


# ============ MÉTHODE 1: REQUESTS SIMPLE ============

def scrape_telegram_simple(channel: str, limit: int = 30) -> list[dict]:
    """Scrape Telegram (simple). En cas d'erreur, retourne [] sans lever."""
    try:
        return _scrape_telegram_simple_impl(channel, limit)
    except Exception as e:
        logger.error(f"Telegram scrape_telegram_simple: {e}")
        return []


def _scrape_telegram_simple_impl(channel: str, limit: int = 30) -> list[dict]:
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

def scrape_telegram_paginated(channel: str, max_messages: int = 200, start_date: str = None, end_date: str = None) -> list[dict]:
    """Scrape Telegram (pagination). En cas d'erreur, retourne [] sans lever."""
    try:
        return _scrape_telegram_paginated_impl(channel, max_messages, start_date, end_date)
    except Exception as e:
        logger.error(f"Telegram scrape_telegram_paginated: {e}")
        return []


def _scrape_telegram_paginated_impl(channel: str, max_messages: int = 200, start_date: str = None, end_date: str = None) -> list[dict]:
    """
    Scrape avec pagination AJAX - jusqu'à plusieurs milliers de messages

    Telegram charge les anciens messages via des requêtes AJAX
    quand on scroll. On simule ça avec le paramètre 'before'.

    Args:
        channel: Nom du channel
        max_messages: Nombre max de messages à récupérer (peut aller jusqu'à 5000+)
        start_date: Date de début (format: "YYYY-MM-DD") - optionnel
        end_date: Date de fin (format: "YYYY-MM-DD") - optionnel

    Returns:
        Liste de messages
    """
    base_url = f"https://t.me/s/{channel}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Referer": f"https://t.me/s/{channel}",
    }

    all_messages = []
    before_id = None
    page = 0
    # Augmenter le nombre max de pages pour récupérer plus de messages
    max_pages = (max_messages // 20) + 50  # Plus de marge pour la pagination
    consecutive_empty = 0

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
            # Vérifier si c'est la première page et qu'il n'y a pas de messages
            if page == 0:
                # Vérifier si le canal existe ou est privé
                if 'doesn\'t exist' in response.text.lower() or 'doesn\'t exist' in response.text:
                    logger.error(f"[{channel}] Canal n'existe pas")
                elif 'private' in response.text.lower() or 'Private' in response.text:
                    logger.error(f"[{channel}] Canal privé - impossible de scraper")
                else:
                    logger.warning(f"[{channel}] Aucun message trouvé - canal peut-être vide ou structure différente")
            else:
                logger.info(f"[{channel}] Plus de messages après page {page}")
            break

        new_messages = 0
        oldest_id = None

        for wrap in message_wraps:
            try:
                # Récupérer l'ID du message pour la pagination
                msg_div = wrap.find('div', class_='tgme_widget_message')
                if msg_div and msg_div.get('data-post'):
                    post_id = msg_div['data-post'].split('/')[-1]
                    # Garder le dernier ID trouvé (le message le plus ancien de la page)
                    oldest_id = post_id

                # Texte
                text_div = wrap.find('div', class_='tgme_widget_message_text')
                if not text_div:
                    continue

                text = text_div.get_text(strip=True)
                if not text or len(text) < 5:
                    continue

                # Éviter les doublons (par ID si disponible, sinon par texte)
                message_id = None
                if msg_div and msg_div.get('data-post'):
                    message_id = msg_div['data-post']
                    if any(m.get('id') == message_id for m in all_messages):
                        continue
                else:
                    if any(m.get('text') == text for m in all_messages):
                        continue

                # Date
                time_tag = wrap.find('time', class_='time')
                date_str = None
                if time_tag and time_tag.get('datetime'):
                    date_str = time_tag['datetime']

                # Filtrer par date si spécifié
                if start_date or end_date:
                    if date_str:
                        msg_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                        if start_date:
                            start = datetime.fromisoformat(start_date)
                            if msg_date.date() < start.date():
                                continue
                        if end_date:
                            end = datetime.fromisoformat(end_date)
                            if msg_date.date() > end.date():
                                # Si on dépasse la date de fin, on peut arrêter
                                if msg_date.date() > end.date():
                                    consecutive_empty = 999  # Force l'arrêt
                                    break
                    else:
                        # Si pas de date et qu'on filtre par date, on skip
                        continue

                # Vues
                views_span = wrap.find('span', class_='tgme_widget_message_views')
                views = parse_views(views_span.get_text(strip=True)) if views_span else 0

                all_messages.append({
                    "id": message_id,
                    "text": clean_text(text),
                    "date": date_str,
                    "views": views,
                    "channel": channel,
                    "source": "telegram"
                })
                new_messages += 1

            except Exception as e:
                logger.debug(f"Erreur parsing message: {e}")
                continue

        logger.info(f"[{channel}] Page {page + 1}: +{new_messages} messages (total: {len(all_messages)}/{max_messages})")

        if new_messages == 0:
            consecutive_empty += 1
            if consecutive_empty >= 3:  # 3 pages vides consécutives = arrêt
                logger.info(f"[{channel}] {consecutive_empty} pages vides consécutives, arrêt de la pagination")
                break
        else:
            consecutive_empty = 0

        if not oldest_id:
            logger.info(f"[{channel}] Impossible de trouver l'ID du message le plus ancien, arrêt")
            break

        before_id = oldest_id
        page += 1

        # Rate limiting adaptatif : plus lent si beaucoup de pages
        if page % 10 == 0:
            time.sleep(2)  # Pause plus longue tous les 10 pages
        else:
            time.sleep(0.8)  # Pause normale

    if len(all_messages) == 0 and page == 0:
        # Si aucun message récupéré sur la première page, vérifier le canal
        logger.warning(f"[{channel}] Aucun message récupéré. Le canal peut être:")
        logger.warning(f"  - Privé (nécessite d'être membre)")
        logger.warning(f"  - Vide (pas de messages publics)")
        logger.warning(f"  - Inexistant ou nom incorrect")
        logger.warning(f"  - Structure HTML différente")

    return all_messages[:max_messages]


# ============ MÉTHODE 3: SELENIUM (POUR PLUS DE MESSAGES) ============

def scrape_telegram_selenium(channel: str, max_messages: int = 1000, start_date: str = None, end_date: str = None) -> list[dict]:
    """Scrape Telegram (Selenium). En cas d'erreur, retourne [] sans lever."""
    try:
        return _scrape_telegram_selenium_impl(channel, max_messages, start_date, end_date)
    except Exception as e:
        logger.error(f"Telegram scrape_telegram_selenium: {e}")
        return []


def _scrape_telegram_selenium_impl(channel: str, max_messages: int = 1000, start_date: str = None, end_date: str = None) -> list[dict]:
    try:
        from selenium import webdriver
        from selenium.webdriver.common.by import By
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        import random
    except ImportError:
        logger.error("Selenium non installé. Utilisez scrape_telegram_paginated à la place.")
        return scrape_telegram_paginated(channel, max_messages, start_date, end_date)

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    all_messages = []
    seen_ids = set()

    try:
        driver = webdriver.Chrome(options=options)
        url = f"https://t.me/s/{channel}"
        logger.info(f"Selenium: Chargement {url}...")
        driver.get(url)
        time.sleep(3)

        last_height = driver.execute_script("return document.body.scrollHeight")
        scroll_attempts = 0
        max_scrolls = (max_messages // 20) + 100  # Plus de scrolls pour plus de messages
        no_new_messages = 0

        while len(all_messages) < max_messages and scroll_attempts < max_scrolls:
            # Scroll vers le haut pour charger les anciens messages
            driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(random.uniform(1, 2))

            # Scroll progressif vers le bas
            for i in range(5):
                driver.execute_script(f"window.scrollBy(0, {random.randint(300, 600)});")
                time.sleep(random.uniform(0.3, 0.6))

            # Parser les messages
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            message_wraps = soup.find_all('div', class_='tgme_widget_message_wrap')

            new_count = 0
            for wrap in message_wraps:
                try:
                    msg_div = wrap.find('div', class_='tgme_widget_message')
                    message_id = None
                    if msg_div and msg_div.get('data-post'):
                        message_id = msg_div['data-post']
                        if message_id in seen_ids:
                            continue
                        seen_ids.add(message_id)

                    text_div = wrap.find('div', class_='tgme_widget_message_text')
                    if not text_div:
                        continue

                    text = text_div.get_text(strip=True)
                    if not text or len(text) < 5:
                        continue

                    # Date
                    time_tag = wrap.find('time', class_='time')
                    date_str = None
                    if time_tag and time_tag.get('datetime'):
                        date_str = time_tag['datetime']

                    # Filtrer par date
                    if start_date or end_date:
                        if date_str:
                            msg_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                            if start_date:
                                start = datetime.fromisoformat(start_date)
                                if msg_date.date() < start.date():
                                    continue
                            if end_date:
                                end = datetime.fromisoformat(end_date)
                                if msg_date.date() > end.date():
                                    continue
                        else:
                            continue

                    views_span = wrap.find('span', class_='tgme_widget_message_views')
                    views = parse_views(views_span.get_text(strip=True)) if views_span else 0

                    all_messages.append({
                        "id": message_id,
                        "text": clean_text(text),
                        "date": date_str,
                        "views": views,
                        "channel": channel,
                        "source": "telegram",
                        "method": "selenium"
                    })
                    new_count += 1

                except Exception as e:
                    continue

            if new_count > 0:
                no_new_messages = 0
                logger.info(f"[{channel}] Scroll {scroll_attempts + 1}: +{new_count} messages (total: {len(all_messages)}/{max_messages})")
            else:
                no_new_messages += 1
                if no_new_messages >= 5:
                    logger.info(f"[{channel}] Plus de nouveaux messages après {scroll_attempts} scrolls")
                    break

            # Vérifier si on peut scroller plus
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                no_new_messages += 1
                if no_new_messages >= 3:
                    break
            else:
                last_height = new_height
                no_new_messages = 0

            scroll_attempts += 1

            # Pause anti-ban
            if scroll_attempts % 20 == 0:
                time.sleep(random.uniform(3, 5))

        driver.quit()
        logger.info(f"[{channel}] Selenium: Total {len(all_messages)} messages récupérés")

    except Exception as e:
        logger.error(f"Erreur Selenium Telegram: {e}")
        try:
            driver.quit()
        except:
            pass

    return all_messages[:max_messages]


# ============ MÉTHODE 4: MULTI-CHANNEL ============

def scrape_multiple_channels(
    channels: list[str] = None,
    messages_per_channel: int = 100,
    use_pagination: bool = True
) -> dict:
    """Scrape plusieurs channels. En cas d'erreur, retourne dict avec posts=[]."""
    try:
        return _scrape_multiple_channels_impl(channels, messages_per_channel, use_pagination)
    except Exception as e:
        logger.error(f"Telegram scrape_multiple_channels: {e}")
        return {"status": "error", "posts": [], "total_messages": 0, "channels_scraped": 0, "stats_per_channel": {}}


def _scrape_multiple_channels_impl(
    channels: list[str] = None,
    messages_per_channel: int = 100,
    use_pagination: bool = True
) -> dict:
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
    messages = scrape_telegram_paginated("bitcoinnews", max_messages=50)
    print(f"  Total: {len(messages)} messages")
    
    # Test multi-channel
    print("\n[TEST 3] Multi-channels")
    result = scrape_multiple_channels(
        channels=["whale_alert_io", "bitcoinnews"],
        messages_per_channel=30
    )
    print(f"  Total: {result['total_messages']} messages")
    print(f"  Stats: {result['stats_per_channel']}")
