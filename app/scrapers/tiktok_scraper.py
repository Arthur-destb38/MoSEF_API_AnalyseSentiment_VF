"""
TikTok Scraper
"""

import time
import random
import re
import ssl
import os
from datetime import datetime

os.environ['WDM_SSL_VERIFY'] = '0'
ssl._create_default_https_context = ssl._create_unverified_context

try:
    import undetected_chromedriver as uc
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.common.action_chains import ActionChains
    from bs4 import BeautifulSoup
    SELENIUM_OK = True
    UC_OK = True
except ImportError:
    UC_OK = False
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        SELENIUM_OK = True
    except ImportError:
        SELENIUM_OK = False

try:
    from app.storage import save_posts
except Exception:
    save_posts = None

LIMITS = {"selenium": 50}


def get_limits():
    return LIMITS


def human_delay(min_sec=1.0, max_sec=3.0):
    time.sleep(random.uniform(min_sec, max_sec))


def human_scroll(driver, distance=None):
    if distance is None:
        distance = random.randint(200, 500)
    
    steps = random.randint(5, 10)
    step_size = distance // steps
    
    for _ in range(steps):
        driver.execute_script(f"window.scrollBy(0, {step_size + random.randint(-10, 10)});")
        time.sleep(random.uniform(0.1, 0.3))
    
    human_delay(0.5, 1.5)


def random_mouse_movement(driver):
    try:
        action = ActionChains(driver)
        for _ in range(random.randint(2, 4)):
            x_offset = random.randint(-100, 100)
            y_offset = random.randint(-100, 100)
            action.move_by_offset(x_offset, y_offset)
            action.pause(random.uniform(0.1, 0.3))
        action.perform()
    except:
        pass


def setup_driver(headless: bool = False):
    if UC_OK:
        try:
            options = uc.ChromeOptions()
            
            if headless:
                options.add_argument("--headless=new")
            
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--window-size=1920,1080")
            options.add_argument("--disable-notifications")
            
            # Créer le driver sans spécifier de binary_location
            driver = uc.Chrome(
                options=options,
                use_subprocess=True,
                version_main=None  # Auto-detect Chrome version
            )
            return driver
        except Exception:
            pass
    if not UC_OK and SELENIUM_OK:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        options = Options()
        
        if headless:
            options.add_argument("--headless=new")
        
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        
        user_agents = [
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        ]
        options.add_argument(f"--user-agent={random.choice(user_agents)}")
        
        try:
            driver = webdriver.Chrome(options=options)
            return driver
        except Exception:
            return None


def scrape_tiktok(hashtag: str, limit: int = 30, method: str = "selenium") -> list:
    if not SELENIUM_OK:
        print("Selenium non installé")
        return []
    
    posts = []
    seen_ids = set()
    limit = min(limit, LIMITS["selenium"])
    
    # Nettoyer le hashtag
    hashtag = hashtag.replace("#", "").replace("$", "").lower()
    
    driver = setup_driver()
    if not driver:
        return []
    
    try:
        url = f"https://www.tiktok.com/tag/{hashtag}"
        print(f"Loading {url}")
        
        driver.get(url)
        
        # Attendre chargement (TikTok est lent)
        human_delay(5, 8)
        
        # Vérifier si on est bloqué
        if is_blocked(driver):
            driver.quit()
            return []
        
        random_mouse_movement(driver)
        human_delay(1, 2)
        
        scroll_count = 0
        max_scrolls = (limit // 3) + 5
        no_new_count = 0
        
        while len(posts) < limit and scroll_count < max_scrolls:
            # Parser les vidéos visibles
            new_posts = parse_tiktok_videos(driver.page_source, seen_ids, hashtag)
            
            if new_posts:
                posts.extend(new_posts)
                no_new_count = 0
            else:
                no_new_count += 1
                if no_new_count >= 3:
                    break
            
            # Scroll humain (très lent)
            human_scroll(driver)
            
            # Pause aléatoire longue
            human_delay(2, 4)
            
            # Mouvement de souris occasionnel
            if random.random() > 0.5:
                random_mouse_movement(driver)
            
            scroll_count += 1
        
        print(f"Done: {len(posts)} videos")
        
    except Exception:
        pass
    finally:
        driver.quit()
    
    posts = posts[:limit]
    
    if save_posts and posts:
        save_posts(posts, source="tiktok", method="selenium")
    
    return posts


def is_blocked(driver) -> bool:
    page_source = driver.page_source.lower()
    
    indicators = [
        "captcha",
        "verify",
        "robot",
        "unusual traffic",
        "access denied",
        "please wait",
        "checking your browser",
        "too many requests"
    ]
    
    return any(ind in page_source for ind in indicators)


def parse_tiktok_videos(page_source: str, seen_ids: set, hashtag: str) -> list:
    """Extraire les infos des vidéos TikTok"""
    posts = []
    soup = BeautifulSoup(page_source, "lxml")
    
    # Sélecteurs pour les vidéos TikTok (peuvent changer)
    video_selectors = [
        "[data-e2e='challenge-item']",
        "[class*='DivItemContainer']",
        "[class*='video-feed-item']",
        "div[class*='tiktok-'][class*='item']",
        "article",
    ]
    
    videos = []
    for selector in video_selectors:
        videos = soup.select(selector)
        if videos:
            break
    
    if not videos:
        videos = soup.find_all("a", href=re.compile(r"/video/\d+"))
    
    for video in videos:
        try:
            # ID de la vidéo
            video_id = None
            
            # Chercher l'ID dans les liens
            link = video.find("a", href=re.compile(r"/video/\d+")) or video
            if link and link.get("href"):
                href = link.get("href", "")
                match = re.search(r"/video/(\d+)", href)
                if match:
                    video_id = match.group(1)
            
            if not video_id:
                video_id = str(hash(str(video)[:100]))
            
            if video_id in seen_ids:
                continue
            seen_ids.add(video_id)
            
            description = ""
            desc_selectors = [
                "[data-e2e='video-desc']",
                "[class*='desc']",
                "[class*='caption']",
                "span[class*='tiktok-']",
            ]
            for sel in desc_selectors:
                desc_el = video.select_one(sel)
                if desc_el:
                    description = desc_el.get_text(strip=True)
                    if description and len(description) > 5:
                        break
            
            if not description:
                description = video.get_text(strip=True)[:200]
            
            if not description or len(description) < 3:
                continue
            
            # Métriques (likes, vues, commentaires)
            likes = extract_metric(video, ["like", "heart"])
            views = extract_metric(video, ["view", "play"])
            comments = extract_metric(video, ["comment", "reply"])
            shares = extract_metric(video, ["share", "repost"])
            
            username = ""
            user_el = video.select_one("[data-e2e='video-author-uniqueid'], [class*='author'], a[href*='/@']")
            if user_el:
                username = user_el.get_text(strip=True)
                if not username and user_el.get("href"):
                    match = re.search(r"/@([^/\?]+)", user_el.get("href", ""))
                    if match:
                        username = match.group(1)
            
            posts.append({
                "id": video_id,
                "title": description[:500],
                "text": "",
                "score": likes + shares,
                "likes": likes,
                "views": views,
                "comments": comments,
                "shares": shares,
                "username": username,
                "hashtag": hashtag,
                "created_utc": datetime.now().isoformat(),  # TikTok ne donne pas facilement la date
                "source": "tiktok",
                "method": "selenium",
                "human_label": None
            })
            
        except Exception as e:
            continue
    
    return posts


def extract_metric(element, keywords: list) -> int:
    try:
        element_html = str(element).lower()
        element_text = element.get_text().lower()
        
        for keyword in keywords:
            # Chercher un élément avec ce mot-clé
            for el in element.find_all(True):
                el_text = el.get_text(strip=True)
                el_class = " ".join(el.get("class", []))
                
                if keyword in el_class.lower() or keyword in el_text.lower():
                    numbers = re.findall(r"([\d.,]+)\s*([KMB])?", el_text, re.IGNORECASE)
                    for num_str, suffix in numbers:
                        try:
                            num = float(num_str.replace(",", ""))
                            if suffix:
                                suffix = suffix.upper()
                                if suffix == "K":
                                    num *= 1000
                                elif suffix == "M":
                                    num *= 1000000
                                elif suffix == "B":
                                    num *= 1000000000
                            return int(num)
                        except:
                            continue
    except:
        pass
    return 0


# Hashtags crypto populaires sur TikTok
CRYPTO_HASHTAGS = {
    "bitcoin": ["bitcoin", "btc", "bitcoinnews"],
    "ethereum": ["ethereum", "eth", "ethereumnews"],
    "crypto": ["crypto", "cryptocurrency", "cryptotok"],
    "trading": ["cryptotrading", "daytrading", "trading"],
    "nft": ["nft", "nfts", "nftart"],
    "defi": ["defi", "decentralizedfinance"],
    "solana": ["solana", "sol"],
    "dogecoin": ["dogecoin", "doge"],
}


def get_hashtags_for_crypto(crypto_name: str) -> list:
    crypto_lower = crypto_name.lower()
    
    for key, hashtags in CRYPTO_HASHTAGS.items():
        if key in crypto_lower or crypto_lower in key:
            return hashtags
    
    return [crypto_lower, "crypto"]
