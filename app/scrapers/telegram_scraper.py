"""
Telegram Scraper
"""

import requests
from bs4 import BeautifulSoup
import time
import re
import random
import logging
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Query
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


CRYPTO_CHANNELS = {
    "bitcoinnews": "Bitcoin News",
    "cryptonewscom": "CryptoNews",
    "whale_alert_io": "Whale Alert",
    "Bitcoin": "Bitcoin Official",
    "ethereum": "Ethereum",
}


def scrape_telegram_simple(channel: str, limit: int = 30) -> list[dict]:
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
    message_wraps = soup.find_all('div', class_='tgme_widget_message_wrap')
    
    for wrap in message_wraps[:limit]:
        try:
            text_div = wrap.find('div', class_='tgme_widget_message_text')
            if not text_div:
                continue
            
            text = text_div.get_text(strip=True)
            if not text or len(text) < 5:
                continue
            
            time_tag = wrap.find('time', class_='time')
            date_str = None
            if time_tag and time_tag.get('datetime'):
                date_str = time_tag['datetime']
            
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
    
    logger.info(f"[{channel}] {len(messages)} messages")
    return messages


def scrape_telegram_paginated(channel: str, max_messages: int = 200, start_date: str = None, end_date: str = None) -> list[dict]:
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
    max_pages = (max_messages // 20) + 50
    consecutive_empty = 0
    
    while len(all_messages) < max_messages and page < max_pages:
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
            break
        
        new_messages = 0
        oldest_id = None
        
        for wrap in message_wraps:
            try:
                msg_div = wrap.find('div', class_='tgme_widget_message')
                if msg_div and msg_div.get('data-post'):
                    post_id = msg_div['data-post'].split('/')[-1]
                    oldest_id = post_id
                
                text_div = wrap.find('div', class_='tgme_widget_message_text')
                if not text_div:
                    continue
                
                text = text_div.get_text(strip=True)
                if not text or len(text) < 5:
                    continue
                
                message_id = None
                if msg_div and msg_div.get('data-post'):
                    message_id = msg_div['data-post']
                    if any(m.get('id') == message_id for m in all_messages):
                        continue
                else:
                    if any(m.get('text') == text for m in all_messages):
                        continue
                
                time_tag = wrap.find('time', class_='time')
                date_str = None
                if time_tag and time_tag.get('datetime'):
                    date_str = time_tag['datetime']
                
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
                                if msg_date.date() > end.date():
                                    consecutive_empty = 999
                                    break
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
                    "source": "telegram"
                })
                new_messages += 1
                
            except Exception as e:
                logger.debug(f"Erreur parsing message: {e}")
                continue
        
        
        if new_messages == 0:
            consecutive_empty += 1
            if consecutive_empty >= 3:
                break
        else:
            consecutive_empty = 0
        
        if not oldest_id:
            break
        
        before_id = oldest_id
        page += 1
        
        if page % 10 == 0:
            time.sleep(2)
        else:
            time.sleep(0.8)
    
    return all_messages[:max_messages]


try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    SELENIUM_OK = True
except ImportError:
    SELENIUM_OK = False


def scrape_telegram_selenium(channel: str, max_messages: int = 1000, start_date: str = None, end_date: str = None) -> list[dict]:
    if not SELENIUM_OK:
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
        logger.info(f"Loading {url}")
        driver.get(url)
        time.sleep(3)
        
        last_height = driver.execute_script("return document.body.scrollHeight")
        scroll_attempts = 0
        max_scrolls = (max_messages // 20) + 100
        no_new_messages = 0
        
        while len(all_messages) < max_messages and scroll_attempts < max_scrolls:
            driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(random.uniform(1, 2))
            
            for i in range(5):
                driver.execute_script(f"window.scrollBy(0, {random.randint(300, 600)});")
                time.sleep(random.uniform(0.3, 0.6))
            
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
                    
                    time_tag = wrap.find('time', class_='time')
                    date_str = None
                    if time_tag and time_tag.get('datetime'):
                        date_str = time_tag['datetime']
                    
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
            else:
                no_new_messages += 1
                if no_new_messages >= 5:
                    break
            
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                no_new_messages += 1
                if no_new_messages >= 3:
                    break
            else:
                last_height = new_height
                no_new_messages = 0
            
            scroll_attempts += 1
            
            if scroll_attempts % 20 == 0:
                time.sleep(random.uniform(3, 5))
        
        driver.quit()
        logger.info(f"[{channel}] Done: {len(all_messages)} messages")
        
    except Exception as e:
        logger.error(f"Erreur Selenium Telegram: {e}")
        try:
            driver.quit()
        except:
            pass
    
    return all_messages[:max_messages]


def scrape_multiple_channels(
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
        time.sleep(2)
    
    return {
        "status": "success",
        "total_messages": len(all_data),
        "channels_scraped": len(channels),
        "stats_per_channel": stats,
        "posts": all_data
    }


def clean_text(text: str) -> str:
    text = re.sub(r'http\S+|www\.\S+', '', text)
    text = re.sub(r'@\w+', '', text)
    text = re.sub(r'[\U0001F600-\U0001F64F]{3,}', '', text)
    text = ' '.join(text.split())
    return text.strip()


def parse_views(views_str: str) -> int:
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


class TelegramScrapeRequest(BaseModel):
    channels: Optional[list[str]] = None
    limit: int = 50
    use_pagination: bool = True


def get_fastapi_router():
    router = APIRouter()
    
    @router.get("/channels")
    def list_channels():
        return {
            "channels": CRYPTO_CHANNELS,
            "count": len(CRYPTO_CHANNELS)
        }
    
    @router.get("/scrape/{channel}")
    def scrape_single_channel(
        channel: str,
        limit: int = Query(default=50, ge=1, le=500)
    ):
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
        return scrape_multiple_channels(
            channels=request.channels,
            messages_per_channel=request.limit,
            use_pagination=request.use_pagination
        )
    
    return router


if __name__ == "__main__":
    print("TEST TELEGRAM SCRAPER")
    print("\n[TEST 1] simple - whale_alert_io")
    messages = scrape_telegram_simple("whale_alert_io", limit=10)
    for msg in messages[:3]:
        print(f"  - {msg['text'][:80]}...")
    
    print("\n[TEST 2] paginated - bitcoinnews")
    messages = scrape_telegram_paginated("bitcoinnews", max_messages=50)
    print(f"  Total: {len(messages)} messages")
    
    print("\n[TEST 3] multi-channels")
    result = scrape_multiple_channels(
        channels=["whale_alert_io", "bitcoinnews"],
        messages_per_channel=30
    )
    print(f"  Total: {result['total_messages']} messages")
    print(f"  Stats: {result['stats_per_channel']}")
