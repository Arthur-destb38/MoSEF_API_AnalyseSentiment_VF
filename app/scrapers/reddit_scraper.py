"""
Reddit Scraper - HTTP et Selenium
"""

import requests
import time
import random
from datetime import datetime
from typing import Optional

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.chrome.options import Options
    from selenium.common.exceptions import NoSuchElementException
    from bs4 import BeautifulSoup
    SELENIUM_OK = True
except ImportError:
    SELENIUM_OK = False

try:
    from app.storage import save_posts
except Exception:
    save_posts = None

LIMITS = {"http": 1000, "selenium": 200}


def filter_posts_by_date(posts: list, start_date: Optional[str] = None, end_date: Optional[str] = None) -> list:
    """Filtre les posts par date (created_utc est un timestamp Unix)"""
    if not start_date and not end_date:
        return posts
    
    filtered = []
    start_dt = datetime.fromisoformat(start_date) if start_date else None
    end_dt = datetime.fromisoformat(end_date) if end_date else None
    
    for post in posts:
        created_utc = post.get("created_utc")
        if not created_utc:
            continue
        
        try:
            if isinstance(created_utc, (int, float)):
                post_dt = datetime.fromtimestamp(created_utc)
            elif isinstance(created_utc, str):
                try:
                    post_dt = datetime.fromisoformat(created_utc.replace('Z', '+00:00'))
                except:
                    post_dt = datetime.fromtimestamp(float(created_utc))
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


def scrape_reddit_http(subreddit: str, limit: int = 100, start_date: Optional[str] = None, end_date: Optional[str] = None) -> list:
    """Scrape Reddit via HTTP/JSON (rapide)"""
    posts = []
    after = None
    headers = {"User-Agent": "Mozilla/5.0 Chrome/120.0.0.0"}
    
    fetch_limit = limit * 2 if (start_date or end_date) else limit
    fetch_limit = min(fetch_limit, LIMITS["http"])
    
    page = 0
    base_hosts = ["https://old.reddit.com", "https://www.reddit.com"]
    base = base_hosts[0]

    while len(posts) < fetch_limit:
        url = f"{base}/r/{subreddit}/new.json"
        params = {"limit": min(100, fetch_limit - len(posts))}
        if after:
            params["after"] = after

        try:
            resp = requests.get(url, headers=headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            if base == base_hosts[0]:
                base = base_hosts[1]
                print(f"Fallback Reddit: old.reddit.com → www.reddit.com")
                continue
            print(f"Erreur Reddit HTTP page {page}: {e}")
            break
        
        children = data.get("data", {}).get("children", [])
        if not children:
            break
        
        page_posts = 0
        for child in children:
            d = child.get("data", {})
            posts.append({
                "id": d.get("id"),
                "title": d.get("title", ""),
                "text": d.get("selftext", ""),
                "score": d.get("score", 0),
                "created_utc": d.get("created_utc"),
                "source": "reddit",
                "method": "http",
                "human_label": None
            })
            page_posts += 1
            if len(posts) >= fetch_limit:
                break
        
        print(f"Page {page + 1}: {len(posts)} posts")
        
        after = data.get("data", {}).get("after")
        if not after:
            break
        
        page += 1
        time.sleep(0.3)
    
    posts = filter_posts_by_date(posts, start_date, end_date)
    return posts[:limit]


def scrape_reddit_selenium(subreddit: str, limit: int = 100, start_date: Optional[str] = None, end_date: Optional[str] = None) -> list:
    """Scrape Reddit via Selenium (simule navigateur)"""
    if not SELENIUM_OK:
        print("Selenium non installe")
        return []
    
    fetch_limit = limit * 2 if (start_date or end_date) else limit
    fetch_limit = min(fetch_limit, LIMITS["selenium"])
    posts = []
    
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--window-size=1920,1080")
    
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/120.0.0.0",
    ]
    options.add_argument(f"--user-agent={random.choice(user_agents)}")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    
    try:
        driver = webdriver.Chrome(options=options)
    except Exception as e:
        print(f"Erreur Chrome: {e}")
        return []
    
    try:
        url = f"https://old.reddit.com/r/{subreddit}/new/"
        print(f"Loading {url}")
        driver.get(url)
        time.sleep(random.uniform(2, 4))
        
        pages = 0
        max_pages = (limit // 25) + 2
        
        while len(posts) < fetch_limit and pages < max_pages:
            for _ in range(2):
                px = random.randint(300, 600)
                driver.execute_script(f"window.scrollBy(0, {px});")
                time.sleep(random.uniform(0.5, 1.0))
            
            soup = BeautifulSoup(driver.page_source, "lxml")
            elements = soup.select("div.thing.link")
            
            for elem in elements:
                if "stickied" in elem.get("class", []):
                    continue
                if "promoted" in elem.get("class", []):
                    continue
                
                post_id = elem.get("data-fullname", "")
                if any(p["id"] == post_id for p in posts):
                    continue
                
                title_el = elem.select_one("a.title")
                title = title_el.get_text(strip=True) if title_el else ""
                
                score_el = elem.select_one("div.score.unvoted")
                score_txt = score_el.get_text(strip=True) if score_el else "0"
                try:
                    score = int(score_txt) if score_txt != "•" else 0
                except:
                    score = 0
                
                time_el = elem.select_one("time")
                timestamp = time_el.get("datetime", "") if time_el else ""
                
                if title:
                    posts.append({
                        "id": post_id,
                        "title": title,
                        "text": "",
                        "score": score,
                        "created_utc": timestamp,
                        "source": "reddit",
                        "method": "selenium",
                        "human_label": None
                    })
                
                if len(posts) >= limit:
                    break
            
            try:
                next_btn = driver.find_element(By.CSS_SELECTOR, "span.next-button a")
                next_btn.click()
                time.sleep(random.uniform(2, 3))
                pages += 1
            except NoSuchElementException:
                break
        
        print(f"Done: {len(posts)} posts")
        
    except Exception as e:
        print(f"Erreur Selenium Reddit: {e}")
    finally:
        driver.quit()
    
    posts = filter_posts_by_date(posts, start_date, end_date)
    return posts[:limit]


def scrape_reddit(subreddit: str, limit: int = 100, method: str = "http", start_date: Optional[str] = None, end_date: Optional[str] = None) -> list:
    """
    Scrape Reddit avec la methode choisie
    
    Args:
        subreddit: Nom du subreddit
        limit: Nombre de posts
        method: "http" (rapide, max 1000) ou "selenium" (lent, max 200)
        start_date: Date de début (format: "YYYY-MM-DD") - optionnel
        end_date: Date de fin (format: "YYYY-MM-DD") - optionnel
    """
    if method == "selenium":
        return scrape_reddit_selenium(subreddit, limit, start_date, end_date)
    else:
        return scrape_reddit_http(subreddit, limit, start_date, end_date)


def get_limits():
    """Retourne les limites par methode"""
    return LIMITS
