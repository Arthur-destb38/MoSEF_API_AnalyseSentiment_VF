"""
StockTwits Scraper - Selenium (bypass Cloudflare)
"""

import os
import time
import random
import re
import json
import tempfile
from datetime import datetime
from typing import Optional

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.common.action_chains import ActionChains
    from bs4 import BeautifulSoup
    SELENIUM_OK = True
except ImportError:
    SELENIUM_OK = False

try:
    from app.storage import save_posts
except Exception:
    save_posts = None

LIMITS = {"selenium": 1000}


def get_limits():
    """Retourne les limites par methode"""
    return LIMITS


def _find_chrome_binary() -> Optional[str]:
    paths = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Google Chrome 2.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        "/usr/bin/google-chrome",
        "/usr/bin/chromium",
    ]
    for path in paths:
        if os.path.isfile(path):
            return path
    return None


def filter_posts_by_date(posts: list, start_date: Optional[str] = None, end_date: Optional[str] = None) -> list:
    if not start_date and not end_date:
        return posts
    
    filtered = []
    start_dt = datetime.fromisoformat(start_date) if start_date else None
    end_dt = datetime.fromisoformat(end_date) if end_date else None
    
    for post in posts:
        created_at = post.get("created_utc")
        if not created_at:
            continue
        
        try:
            if isinstance(created_at, str):
                try:
                    post_dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                except:
                    post_dt = datetime.fromtimestamp(float(created_at))
            elif isinstance(created_at, (int, float)):
                post_dt = datetime.fromtimestamp(created_at)
            else:
                continue
            
            if start_dt and post_dt.date() < start_dt.date():
                continue
            if end_dt and post_dt.date() > end_dt.date():
                continue
            
            filtered.append(post)
        except Exception:
            continue
    
    return filtered


def scrape_stocktwits(symbol: str, limit: int = 100, method: str = "selenium", enhanced: bool = False, start_date: Optional[str] = None, end_date: Optional[str] = None) -> list:
    """
    Scrape StockTwits avec Selenium (bypass Cloudflare)
    Note: HTTP ne fonctionne pas (Cloudflare), seul Selenium est disponible

    Args:
        symbol: Symbole crypto (ex: BTC.X, ETH.X)
        limit: Nombre de posts souhaites
        method: Ignore (toujours selenium)

    Returns:
        Liste de posts avec human_label (Bullish/Bearish/None)
    """
    if not SELENIUM_OK:
        print("Selenium non installe")
        return []

    posts = []
    seen_ids = set()
    fetch_limit = limit * 2 if (start_date or end_date) else limit
    fetch_limit = min(fetch_limit, LIMITS["selenium"])

    chrome_binary = _find_chrome_binary()
    if not chrome_binary:
        print("Erreur Chrome StockTwits: aucun Chrome système trouvé. Installez Google Chrome (ou Chrome 2) dans Applications.")
        return []
    options = Options()
    options.binary_location = chrome_binary
    temp_profile = tempfile.mkdtemp(prefix="selenium_stocktwits_")
    options.add_argument(f"--user-data-dir={temp_profile}")
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-software-rasterizer")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-background-networking")
    options.add_argument("--disable-default-apps")
    options.add_argument("--disable-sync")
    options.add_argument("--no-first-run")
    options.add_argument("--disable-renderer-backgrounding")
    options.add_argument("--disable-features=VizDisplayCompositor")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--remote-debugging-port=0")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_experimental_option("prefs", {
        "profile.default_content_setting_values.notifications": 2,
        "credentials_enable_service": False,
        "profile.password_manager_enabled": False,
    })

    try:
        driver = webdriver.Chrome(options=options)
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
        })
        driver.execute_cdp_cmd("Network.setUserAgentOverride", {
            "userAgent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })
    except Exception as e:
        print(f"Erreur Chrome StockTwits: {e}")
        return []

    try:
        url = f"https://stocktwits.com/symbol/{symbol}"
        print(f"Loading {url}...")
        driver.get(url)
        time.sleep(random.uniform(5, 8))

        posts = extract_json_data(driver, fetch_limit)
        if posts:
            seen_ids.update(p.get('id') for p in posts if p.get('id'))

        if posts and len(posts) >= fetch_limit:
            posts = filter_posts_by_date(posts, start_date, end_date)
            driver.quit()
            return posts[:limit]

        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "article"))
            )
        except:
            pass

        time.sleep(2)

        if len(posts) < fetch_limit:
            remaining = fetch_limit - len(posts)
            additional_posts = enhanced_scroll_and_parse(driver, [], seen_ids, remaining, enhanced)
            posts.extend(additional_posts)
            
            unique_posts = []
            seen = set()
            for p in posts:
                p_id = p.get('id')
                if p_id and p_id not in seen:
                    seen.add(p_id)
                    unique_posts.append(p)
                elif not p_id:
                    text_hash = hash(p.get('title', '')[:50])
                    if text_hash not in seen:
                        seen.add(text_hash)
                        unique_posts.append(p)
            posts = unique_posts

        posts = filter_posts_by_date(posts, start_date, end_date)
        print(f"Done: {len(posts)} posts")

    except Exception as e:
        print(f"Erreur StockTwits Selenium: {e}")
    finally:
        driver.quit()

    posts = posts[:limit]
    return posts


def extract_json_data(driver, limit: int) -> list:
    posts = []

    try:
        soup = BeautifulSoup(driver.page_source, "lxml")
        script = soup.find("script", {"id": "__NEXT_DATA__"})

        if not script or not script.string:
            return []

        data = json.loads(script.string)
        page_props = data.get("props", {}).get("pageProps", {})

        messages = (
            page_props.get("stream", {}).get("messages", []) or
            page_props.get("messages", []) or
            page_props.get("initialMessages", []) or
            []
        )

        for msg in messages[:limit]:
            sentiment = msg.get("entities", {}).get("sentiment", {})
            human_label = sentiment.get("basic") if sentiment else None
            likes_data = msg.get("likes", {})
            likes = likes_data.get("total", 0) if isinstance(likes_data, dict) else 0

            posts.append({
                "id": str(msg.get("id", "")),
                "title": msg.get("body", ""),
                "text": "",
                "score": likes,
                "created_utc": msg.get("created_at"),
                "source": "stocktwits",
                "method": "selenium",
                "human_label": human_label
            })

    except json.JSONDecodeError:
        pass
    except Exception:
        pass

    return posts


def parse_html_posts(page_source: str, seen_ids: set) -> list:
    posts = []
    soup = BeautifulSoup(page_source, "lxml")

    selectors = [
        "article",
        "[class*='MessageCard']",
        "[class*='StreamMessage']",
        "[data-testid='message']",
        "div[class*='Message']"
    ]

    messages = []
    for selector in selectors:
        messages = soup.select(selector)
        if messages:
            break

    for msg in messages:
        try:
            msg_id = (
                msg.get("data-id") or
                msg.get("id") or
                msg.get("data-message-id") or
                str(hash(msg.get_text()[:50]))
            )

            if msg_id in seen_ids:
                continue
            seen_ids.add(msg_id)

            body = ""
            for body_selector in ["[class*='body']", "[class*='Body']", "p", ".message-text"]:
                body_el = msg.select_one(body_selector)
                if body_el:
                    body = body_el.get_text(strip=True)
                    break

            if not body:
                body = msg.get_text(strip=True)[:500]

            if not body or len(body) < 5:
                continue

            human_label = None
            msg_html = str(msg).lower()

            if "bullish" in msg_html:
                human_label = "Bullish"
            elif "bearish" in msg_html:
                human_label = "Bearish"

            likes = 0
            likes_el = msg.select_one("[class*='like'] span, [class*='Like'] span")
            if likes_el:
                match = re.search(r"(\d+)", likes_el.get_text())
                if match:
                    likes = int(match.group(1))

            time_el = msg.select_one("time, [datetime]")
            timestamp = time_el.get("datetime") if time_el else None

            posts.append({
                "id": msg_id,
                "title": body[:500],
                "text": "",
                "score": likes,
                "created_utc": timestamp,
                "source": "stocktwits",
                "method": "selenium",
                "human_label": human_label
            })

        except Exception:
            continue

    return posts


def enhanced_scroll_and_parse(driver, posts: list, seen_ids: set, limit: int, enhanced: bool = False) -> list:
    last_height = driver.execute_script("return document.body.scrollHeight")
    scroll_attempts = 0
    consecutive_no_new = 0
    max_scrolls = (limit // 10) + 10 if enhanced else (limit // 15) + 5
    actions = ActionChains(driver)
    initial_count = len(posts)
    
    while len(posts) < (initial_count + limit) and scroll_attempts < max_scrolls:
        new_posts = parse_html_posts(driver.page_source, seen_ids)
        
        if new_posts:
            posts.extend(new_posts)
            consecutive_no_new = 0
        else:
            consecutive_no_new += 1
            if consecutive_no_new >= 5:
                break

        if len(posts) >= (initial_count + limit):
            break

        if enhanced:
            scroll_amount = random.randint(300, 600)
            driver.execute_script(f"window.scrollBy(0, {scroll_amount});")
            try:
                body = driver.find_element(By.TAG_NAME, "body")
                actions.move_to_element(body).perform()
            except:
                pass
            
            time.sleep(random.uniform(0.8, 1.5))
        else:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(random.uniform(1.5, 2.5))

        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            scroll_attempts += 1
            if scroll_attempts >= 3:
                try:
                    load_more = driver.find_element(By.XPATH, "//button[contains(text(), 'Load') or contains(text(), 'More')]")
                    if load_more.is_displayed():
                        load_more.click()
                        time.sleep(2)
                        scroll_attempts = 0
                        continue
                except:
                    pass
                break
        else:
            scroll_attempts = 0
            last_height = new_height

    return posts


def intercept_api_requests(driver, symbol: str, limit: int) -> list:
    posts = []
    
    try:
        driver.execute_cdp_cmd('Network.enable', {})
        logs = driver.get_log('performance')
        
        for log in logs:
            try:
                message = json.loads(log['message'])['message']
                if message['method'] == 'Network.responseReceived':
                    url = message['params']['response']['url']
                    if 'api.stocktwits.com' in url or '/messages' in url or '/stream' in url:
                        request_id = message['params']['requestId']
                        try:
                            response = driver.execute_cdp_cmd('Network.getResponseBody', {'requestId': request_id})
                            if response and 'body' in response:
                                body_data = json.loads(response['body'])
                                api_posts = parse_api_response(body_data, limit - len(posts))
                                posts.extend(api_posts)
                        except Exception:
                            pass
            except:
                continue
                
    except Exception:
        pass
    
    return posts


def parse_api_response(data: dict, limit: int) -> list:
    posts = []
    
    try:
        messages = (
            data.get('messages', []) or
            data.get('stream', {}).get('messages', []) or
            data.get('data', {}).get('messages', []) or
            []
        )
        
        for msg in messages[:limit]:
            sentiment = msg.get("entities", {}).get("sentiment", {})
            human_label = sentiment.get("basic") if sentiment else None
            
            likes_data = msg.get("likes", {})
            likes = likes_data.get("total", 0) if isinstance(likes_data, dict) else 0
            
            posts.append({
                "id": str(msg.get("id", "")),
                "title": msg.get("body", ""),
                "text": "",
                "score": likes,
                "created_utc": msg.get("created_at"),
                "source": "stocktwits",
                "method": "selenium",
                "human_label": human_label
            })
    except Exception:
        pass
    
    return posts
