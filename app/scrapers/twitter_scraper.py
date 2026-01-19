"""
Twitter/X Scraper - Selenium avec login (methode Jose)
Scrape les tweets crypto via recherche avancee
"""

import time
import random
import re
import urllib.parse
import os
import json
from datetime import datetime
from pathlib import Path

try:
    from app.storage import save_posts
except Exception:
    save_posts = None

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.common.action_chains import ActionChains
    from bs4 import BeautifulSoup
    SELENIUM_OK = True
except ImportError:
    SELENIUM_OK = False

# Limites avec login (methode Jose)
LIMITS = {
    "selenium": 2000,  # Avec login on peut aller jusqu'a 2000
    "no_login": 100    # Sans login, limite aux profils publics
}

# Fichier pour sauvegarder les cookies
COOKIES_FILE = Path(__file__).parent.parent.parent / "data" / "twitter_cookies.json"


def get_limits():
    """Retourne les limites par methode"""
    return LIMITS


class TwitterConfig:
    """Configuration pour la recherche Twitter (style Jose)"""
    def __init__(
        self,
        query: str,
        min_replies: int = None,
        min_likes: int = None,
        min_reposts: int = None,
        start_date: str = None,  # Format: YYYY-MM-DD
        end_date: str = None,    # Format: YYYY-MM-DD
        sort_mode: str = "live"  # "live" (recents) ou "top" (populaires)
    ):
        self.query = query
        self.min_replies = min_replies
        self.min_likes = min_likes
        self.min_reposts = min_reposts
        self.start_date = start_date
        self.end_date = end_date
        self.sort_mode = sort_mode
    
    @property
    def search_url(self) -> str:
        """Construct the advanced search URL (code Jose)"""
        encoded_query = urllib.parse.quote(self.query)
        base = f"https://x.com/search?q={encoded_query}"
        
        filters = []
        if self.min_replies:
            filters.append(f"min_replies%3A{self.min_replies}")
        if self.min_likes:
            filters.append(f"min_faves%3A{self.min_likes}")
        if self.min_reposts:
            filters.append(f"min_retweets%3A{self.min_reposts}")
        if self.start_date:
            filters.append(f"since%3A{self.start_date}")
        if self.end_date:
            filters.append(f"until%3A{self.end_date}")
        
        if filters:
            base += "%20" + "%20".join(filters)
        
        return f"{base}&src=typed_query&f={self.sort_mode}"


def save_cookies(driver):
    """Sauvegarder les cookies pour reutilisation"""
    cookies = driver.get_cookies()
    COOKIES_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(COOKIES_FILE, 'w') as f:
        json.dump(cookies, f)
    print(f"Cookies sauvegardes dans {COOKIES_FILE}")


def load_cookies(driver):
    """Charger les cookies sauvegardes"""
    if COOKIES_FILE.exists():
        with open(COOKIES_FILE, 'r') as f:
            cookies = json.load(f)
        for cookie in cookies:
            try:
                driver.add_cookie(cookie)
            except Exception:
                pass
        return True
    return False


def twitter_login(driver, username: str, password: str) -> bool:
    """
    Se connecter a Twitter/X
    
    Args:
        driver: Selenium WebDriver
        username: Nom d'utilisateur ou email Twitter
        password: Mot de passe
    
    Returns:
        True si login reussi
    """
    try:
        print("Twitter: Connexion en cours...")
        
        # Aller sur la page de login
        driver.get("https://x.com/i/flow/login")
        human_delay(3, 5)
        
        # Entrer le username
        username_input = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'input[autocomplete="username"]'))
        )
        
        # Taper comme un humain
        for char in username:
            username_input.send_keys(char)
            time.sleep(random.uniform(0.05, 0.15))
        
        human_delay(0.5, 1)
        
        # Cliquer sur Next
        next_buttons = driver.find_elements(By.XPATH, "//span[contains(text(), 'Next')]")
        if next_buttons:
            next_buttons[0].click()
        else:
            username_input.send_keys(Keys.RETURN)
        
        human_delay(2, 3)
        
        # Parfois Twitter demande une verification (email ou username)
        page_text = driver.page_source.lower()
        if "verify" in page_text or "confirm" in page_text:
            # Essayer de trouver un autre input
            verify_inputs = driver.find_elements(By.CSS_SELECTOR, 'input[data-testid="ocfEnterTextTextInput"]')
            if verify_inputs:
                for char in username:
                    verify_inputs[0].send_keys(char)
                    time.sleep(random.uniform(0.05, 0.15))
                verify_inputs[0].send_keys(Keys.RETURN)
                human_delay(2, 3)
        
        # Entrer le password
        password_input = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'input[type="password"]'))
        )
        
        for char in password:
            password_input.send_keys(char)
            time.sleep(random.uniform(0.05, 0.15))
        
        human_delay(0.5, 1)
        
        # Cliquer sur Login
        login_buttons = driver.find_elements(By.XPATH, "//span[contains(text(), 'Log in')]")
        if login_buttons:
            login_buttons[0].click()
        else:
            password_input.send_keys(Keys.RETURN)
        
        human_delay(4, 6)
        
        # Verifier si login reussi
        current_url = driver.current_url
        if "home" in current_url or "x.com" in current_url:
            # Verifier qu'on n'est plus sur la page de login
            if "login" not in current_url and "flow" not in current_url:
                print("Twitter: Connexion reussie!")
                save_cookies(driver)
                return True
        
        # Verifier si on est connecte autrement
        page_source = driver.page_source
        if "Home" in page_source and "Post" in page_source:
            print("Twitter: Connexion reussie!")
            save_cookies(driver)
            return True
        
        print("Twitter: Echec connexion - verifier les identifiants")
        return False
        
    except Exception as e:
        print(f"Twitter login error: {e}")
        return False


def is_logged_in(driver) -> bool:
    """Verifier si on est connecte"""
    try:
        driver.get("https://x.com/home")
        human_delay(4, 5)
        
        page_source = driver.page_source.lower()
        
        # Indicateurs de NON connexion (prioritaires)
        logged_out_indicators = [
            "google_sign_in", "apple_sign_in", "create your account", 
            "sign up", "don't have an account", "log in to x",
            "sign in to x", "join x today"
        ]
        
        for ind in logged_out_indicators:
            if ind in page_source:
                return False
        
        # Indicateurs de connexion
        logged_in_indicators = [
            "tweettext", "tweet-text", "data-testid=\"tweet\"",
            "primarycolumn", "sidebar", "compose-tweet"
        ]
        
        for ind in logged_in_indicators:
            if ind in page_source:
                return True
        
        # Verifier l'URL
        if "home" in driver.current_url and "login" not in driver.current_url:
            # Double check - chercher le bouton Post/Tweet
            if "post" in page_source or "tweet" in page_source:
                return True
        
        return False
        
    except Exception:
        return False


def human_delay(min_sec=0.5, max_sec=1.5):
    """Delai aleatoire pour imiter comportement humain"""
    time.sleep(random.uniform(min_sec, max_sec))


def human_scroll(driver, distance=None):
    """Scroll avec mouvement humain (pas lineaire)"""
    if distance is None:
        distance = random.randint(300, 700)
    
    # Scroll en plusieurs petits mouvements
    steps = random.randint(3, 6)
    step_size = distance // steps
    
    for _ in range(steps):
        driver.execute_script(f"window.scrollBy(0, {step_size + random.randint(-20, 20)});")
        time.sleep(random.uniform(0.05, 0.15))
    
    human_delay(0.3, 0.8)


def setup_driver():
    """Configure Chrome avec options anti-detection"""
    options = Options()
    
    # Mode headless
    options.add_argument("--headless=new")
    
    # Options de base
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    
    # Anti-detection
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    # User agents realistes
    user_agents = [
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    ]
    options.add_argument(f"--user-agent={random.choice(user_agents)}")
    
    # Preferences pour paraitre plus reel
    prefs = {
        "profile.default_content_setting_values.notifications": 2,
        "credentials_enable_service": False,
        "profile.password_manager_enabled": False
    }
    options.add_experimental_option("prefs", prefs)
    
    try:
        driver = webdriver.Chrome(options=options)
        
        # Override navigator.webdriver
        driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            'source': '''
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en']
                });
            '''
        })
        
        return driver
    except Exception as e:
        print(f"Erreur Chrome: {e}")
        return None


def scrape_twitter(
    query: str, 
    limit: int = 50, 
    method: str = "selenium",
    username: str = None,
    password: str = None,
    min_likes: int = None,
    min_replies: int = None,
    start_date: str = None,
    end_date: str = None,
    sort_mode: str = "top"  # "top" (populaires) ou "live" (recents)
) -> list:
    """
    Scrape Twitter/X pour les tweets crypto
    
    2 modes:
    1. AVEC LOGIN (methode Jose): Utilise la recherche avancee, jusqu'a 2000 tweets
    2. SANS LOGIN: Scrape les profils publics, max 100 tweets
    
    Args:
        query: Terme de recherche (ex: "Bitcoin", "$BTC", "crypto")
        limit: Nombre de tweets souhaites
        method: "selenium" (avec ou sans login)
        username: Username Twitter (optionnel, pour mode login)
        password: Password Twitter (optionnel, pour mode login)
        min_likes: Filtrer tweets avec minimum X likes
        min_replies: Filtrer tweets avec minimum X replies  
        start_date: Date debut (YYYY-MM-DD)
        end_date: Date fin (YYYY-MM-DD)
        sort_mode: "top" (populaires) ou "live" (recents)
    
    Returns:
        Liste de tweets
    """
    if not SELENIUM_OK:
        print("Selenium non installe")
        return []
    
    # Recuperer credentials depuis env si pas fournis
    if not username:
        username = os.environ.get("TWITTER_USERNAME")
    if not password:
        password = os.environ.get("TWITTER_PASSWORD")
    
    # Verifier si on a des cookies sauvegardes
    cookies_exist = COOKIES_FILE.exists()
    
    # Si on a des cookies OU des credentials, utiliser le mode login (Jose)
    if cookies_exist or (username and password):
        print(f"Twitter: Mode login (cookies={cookies_exist}, creds={bool(username)})")
        return scrape_twitter_with_login(
            query=query,
            limit=min(limit, LIMITS["selenium"]),
            username=username or "cookie_user",
            password=password or "cookie_pass",
            min_likes=min_likes,
            min_replies=min_replies,
            start_date=start_date,
            end_date=end_date,
            sort_mode=sort_mode
        )
    
    # Sinon, mode sans login (profils publics)
    print("Twitter: Mode sans login (pas de cookies ni credentials)")
    limit = min(limit, LIMITS["no_login"])
    
    # Mapper query vers comptes influents
    crypto_accounts = get_crypto_accounts(query)
    
    print(f"Twitter (sans login): Scraping {len(crypto_accounts)} comptes crypto pour '{query}'...")
    
    all_posts = []
    seen_ids = set()
    
    for account in crypto_accounts:
        if len(all_posts) >= limit:
            break
            
        posts = scrape_twitter_profile(account, limit // len(crypto_accounts) + 5, seen_ids, query)
        all_posts.extend(posts)
        print(f"  @{account}: {len(posts)} tweets")
    
    all_posts = all_posts[:limit]
    
    if save_posts and all_posts:
        save_posts(all_posts, source="twitter", method="selenium")
    
    print(f"Twitter: Total {len(all_posts)} tweets scraped")
    return all_posts


def scrape_twitter_with_login(
    query: str,
    limit: int,
    username: str,
    password: str,
    min_likes: int = None,
    min_replies: int = None,
    start_date: str = None,
    end_date: str = None,
    sort_mode: str = "top"
) -> list:
    """
    Scraper Twitter avec login (methode Jose)
    Utilise la recherche avancee pour scraper jusqu'a 2000 tweets
    
    sort_mode: "top" (populaires) ou "live" (recents)
    """
    posts = []
    seen_ids = set()
    
    driver = setup_driver()
    if not driver:
        return []
    
    try:
        # Essayer de charger les cookies existants
        driver.get("https://x.com")
        human_delay(2, 3)
        
        cookies_loaded = load_cookies(driver)
        if cookies_loaded:
            print("Twitter: Cookies charges, verification...")
            driver.refresh()
            human_delay(3, 4)
        
        # Verifier si on est connecte
        logged_in = is_logged_in(driver)
        
        if not logged_in:
            # Login necessaire
            print("Twitter: Login necessaire...")
            if not twitter_login(driver, username, password):
                print("Twitter: Echec login, passage en mode sans login")
                driver.quit()
                return scrape_twitter(query, min(limit, 100))  # Fallback
            
            # Re-verifier apres login
            logged_in = is_logged_in(driver)
            if not logged_in:
                print("Twitter: Login semble avoir echoue")
                driver.quit()
                return []
        
        print("Twitter: Connecte! Lancement recherche avancee...")
        
        # Construire l'URL de recherche (code Jose)
        config = TwitterConfig(
            query=query,
            min_likes=min_likes,
            min_replies=min_replies,
            start_date=start_date,
            end_date=end_date,
            sort_mode=sort_mode
        )
        
        search_url = config.search_url
        print(f"Twitter: URL recherche: {search_url}")
        
        driver.get(search_url)
        human_delay(4, 6)
        
        # Verifier si la recherche fonctionne
        if is_login_wall(driver):
            print("Twitter: Session expiree, re-login...")
            if twitter_login(driver, username, password):
                driver.get(search_url)
                human_delay(4, 6)
            else:
                driver.quit()
                return []
        
        # Scroll et collecter les tweets
        scroll_count = 0
        max_scrolls = min(limit // 10, 200)  # Environ 10 tweets par scroll
        no_new_tweets_count = 0
        
        print(f"Twitter: Scraping jusqu'a {limit} tweets (max {max_scrolls} scrolls)...")
        
        while len(posts) < limit and scroll_count < max_scrolls:
            # Parser les tweets actuels
            new_posts = parse_tweets(driver.page_source, seen_ids, "")
            
            if new_posts:
                posts.extend(new_posts)
                no_new_tweets_count = 0
                print(f"  Scroll {scroll_count + 1}: {len(posts)} tweets total")
            else:
                no_new_tweets_count += 1
                if no_new_tweets_count >= 5:
                    print("Twitter: Plus de nouveaux tweets trouves")
                    break
            
            # Scroll humain
            human_scroll(driver, distance=random.randint(500, 900))
            human_delay(1.5, 3)
            
            scroll_count += 1
            
            # Pause plus longue tous les 20 scrolls pour eviter detection
            if scroll_count % 20 == 0:
                print(f"  Pause anti-ban... ({len(posts)} tweets)")
                human_delay(5, 10)
        
        posts = posts[:limit]
        
        if save_posts and posts:
            save_posts(posts, source="twitter", method="selenium_login")
        
        print(f"Twitter: Total {len(posts)} tweets scraped avec login")
        
    except Exception as e:
        print(f"Twitter scrape error: {e}")
    finally:
        driver.quit()
    
    return posts


def get_crypto_accounts(query: str) -> list:
    """Retourne les comptes Twitter pertinents pour une crypto"""
    query_lower = query.lower().replace("$", "")
    
    # Comptes generaux crypto
    general = ["whale_alert", "CoinDesk", "Cointelegraph", "BitcoinMagazine"]
    
    # Comptes specifiques par crypto
    specific = {
        "btc": ["saborskater", "michael_saylor", "DocumentingBTC"],
        "bitcoin": ["saborskater", "michael_saylor", "DocumentingBTC"],
        "eth": ["VitalikButerin", "sassal0x", "ethereum"],
        "ethereum": ["VitalikButerin", "sassal0x", "ethereum"],
        "sol": ["solaboradotcom", "aaborsh_sol"],
        "solana": ["solaboradotcom", "aaborsh_sol"],
        "doge": ["elonmusk", "dogecoin"],
        "dogecoin": ["elonmusk", "dogecoin"],
        "xrp": ["Ripple", "baborgarlinghouse"],
        "ripple": ["Ripple", "baborgarlinghouse"],
    }
    
    accounts = general.copy()
    for key, accts in specific.items():
        if key in query_lower:
            accounts.extend(accts)
            break
    
    return accounts[:5]  # Max 5 comptes


def scrape_twitter_profile(username: str, limit: int, seen_ids: set, keyword: str = "") -> list:
    """Scrape le profil public d'un utilisateur Twitter"""
    posts = []
    
    driver = setup_driver()
    if not driver:
        return []
    
    try:
        url = f"https://x.com/{username}"
        driver.get(url)
        human_delay(3, 5)
        
        # Verifier si le profil existe et est public
        if "This account doesn't exist" in driver.page_source:
            driver.quit()
            return []
        
        if is_login_wall(driver):
            # Twitter peut demander login meme pour profils publics maintenant
            driver.quit()
            return []
        
        # Scroll et collect
        scroll_count = 0
        max_scrolls = 5
        
        while len(posts) < limit and scroll_count < max_scrolls:
            new_posts = parse_tweets(driver.page_source, seen_ids, keyword)
            posts.extend(new_posts)
            
            human_scroll(driver)
            human_delay(1, 2)
            scroll_count += 1
        
    except Exception as e:
        print(f"Erreur profil @{username}: {e}")
    finally:
        driver.quit()
    
    return posts[:limit]


def is_login_wall(driver) -> bool:
    """Detecte si Twitter demande un login"""
    page_source = driver.page_source.lower()
    
    indicators = [
        "log in to x",
        "sign in to x",
        "sign up for x",
        "create your account",
        "log in to twitter",
        "don't miss what's happening"
    ]
    
    return any(ind in page_source for ind in indicators)


def parse_tweets(page_source: str, seen_ids: set, keyword: str = "") -> list:
    """Extraire les tweets du HTML, filtrer par keyword si fourni"""
    posts = []
    soup = BeautifulSoup(page_source, "lxml")
    keyword_lower = keyword.lower() if keyword else ""
    
    # Selecteurs pour les tweets
    tweet_selectors = [
        "article[data-testid='tweet']",
        "article[role='article']",
        "[data-testid='tweet']",
        "div[data-testid='tweetText']"
    ]
    
    tweets = []
    for selector in tweet_selectors:
        tweets = soup.select(selector)
        if tweets:
            break
    
    for tweet in tweets:
        try:
            # ID unique
            tweet_link = tweet.select_one("a[href*='/status/']")
            if tweet_link:
                href = tweet_link.get("href", "")
                match = re.search(r"/status/(\d+)", href)
                tweet_id = match.group(1) if match else str(hash(tweet.get_text()[:50]))
            else:
                tweet_id = str(hash(tweet.get_text()[:50]))
            
            if tweet_id in seen_ids:
                continue
            seen_ids.add(tweet_id)
            
            # Texte du tweet
            text_el = tweet.select_one("[data-testid='tweetText']")
            text = text_el.get_text(strip=True) if text_el else ""
            
            if not text:
                # Fallback
                text = tweet.get_text(strip=True)[:500]
            
            if not text or len(text) < 5:
                continue
            
            # Filtrer par keyword si fourni
            if keyword_lower and keyword_lower not in text.lower():
                continue
            
            # Engagement metrics
            likes = extract_metric(tweet, "like")
            retweets = extract_metric(tweet, "retweet")
            
            # Timestamp
            time_el = tweet.select_one("time")
            timestamp = time_el.get("datetime") if time_el else None
            
            # Username
            username_el = tweet.select_one("[data-testid='User-Name'] a")
            username = ""
            if username_el:
                username = username_el.get_text(strip=True)
            
            posts.append({
                "id": tweet_id,
                "title": text[:500],
                "text": "",
                "score": likes + retweets,
                "likes": likes,
                "retweets": retweets,
                "username": username,
                "created_utc": timestamp,
                "source": "twitter",
                "method": "selenium",
                "human_label": None
            })
            
        except Exception:
            continue
    
    return posts


def extract_metric(tweet, metric_type: str) -> int:
    """Extraire les metriques (likes, retweets)"""
    try:
        el = tweet.select_one(f"[data-testid='{metric_type}'] span span")
        if el:
            text = el.get_text(strip=True)
            # Parser "1.2K", "500", etc
            if "K" in text.upper():
                return int(float(text.upper().replace("K", "")) * 1000)
            elif "M" in text.upper():
                return int(float(text.upper().replace("M", "")) * 1000000)
            else:
                return int(text) if text.isdigit() else 0
    except:
        pass
    return 0


def scrape_nitter(query: str, limit: int = 50) -> list:
    """
    Scrape via Nitter (frontend Twitter open-source)
    Nitter ne requiert pas de login
    """
    posts = []
    seen_ids = set()
    
    # Instances Nitter actives (janvier 2026)
    nitter_instances = [
        "nitter.privacydev.net",
        "nitter.poast.org",
        "nitter.lucabased.xyz",
        "nitter.woodland.cafe",
        "nitter.esmailelbob.xyz",
        "nitter.d420.de",
        "nitter.1d4.us",
    ]
    
    driver = setup_driver()
    if not driver:
        return []
    
    try:
        for instance in nitter_instances:
            try:
                search_query = query.replace(" ", "+")
                url = f"https://{instance}/search?f=tweets&q={search_query}"
                
                print(f"Nitter: Trying {instance}...")
                driver.get(url)
                human_delay(3, 5)
                
                # Verifier si l'instance marche
                page_lower = driver.page_source.lower()
                if "error" in page_lower or "502" in page_lower or "503" in page_lower or "blocked" in page_lower:
                    print(f"Nitter {instance} down, trying next...")
                    continue
                
                # Parser les tweets Nitter
                soup = BeautifulSoup(driver.page_source, "lxml")
                
                # Selecteurs Nitter (plusieurs versions)
                tweet_items = (
                    soup.select(".timeline-item") or
                    soup.select(".tweet-body") or
                    soup.select("div.tweet") or
                    soup.select("article")
                )
                
                if not tweet_items:
                    print(f"Nitter {instance}: aucun tweet trouve, trying next...")
                    continue
                
                for item in tweet_items[:limit * 2]:  # Parser plus pour filtrer
                    try:
                        # Texte - plusieurs selecteurs
                        text = ""
                        for text_sel in [".tweet-content", ".tweet-body", ".content", "p"]:
                            text_el = item.select_one(text_sel)
                            if text_el:
                                text = text_el.get_text(strip=True)
                                if text and len(text) > 10:
                                    break
                        
                        if not text or len(text) < 10:
                            continue
                        
                        # Filtrer les tweets non pertinents
                        if "nitter" in text.lower() or "instance" in text.lower():
                            continue
                        
                        # ID
                        tweet_id = None
                        for link_sel in ["a.tweet-link", "a[href*='/status/']", ".tweet-date a"]:
                            link = item.select_one(link_sel)
                            if link:
                                href = link.get("href", "")
                                match = re.search(r"/status/(\d+)", href)
                                if match:
                                    tweet_id = match.group(1)
                                    break
                        
                        if not tweet_id:
                            tweet_id = str(hash(text[:50]))
                        
                        if tweet_id in seen_ids:
                            continue
                        seen_ids.add(tweet_id)
                        
                        # Stats - likes, retweets, replies
                        likes = 0
                        retweets = 0
                        
                        # Chercher dans les stats icons
                        for stat in item.select(".tweet-stat, .icon-container"):
                            stat_text = stat.get_text(strip=True).lower()
                            stat_num = re.search(r"(\d+)", stat_text)
                            if stat_num:
                                num = int(stat_num.group(1))
                                if "like" in stat_text or "heart" in str(stat):
                                    likes = num
                                elif "retweet" in stat_text or "rt" in stat_text:
                                    retweets = num
                        
                        # Timestamp
                        timestamp = None
                        time_el = item.select_one(".tweet-date a, time, [title]")
                        if time_el:
                            timestamp = time_el.get("title") or time_el.get("datetime") or time_el.get_text(strip=True)
                        
                        # Username
                        username = ""
                        user_el = item.select_one(".username, .fullname, a[href^='/']")
                        if user_el:
                            username = user_el.get_text(strip=True)
                        
                        posts.append({
                            "id": tweet_id,
                            "title": text[:500],
                            "text": "",
                            "score": likes + retweets,
                            "likes": likes,
                            "retweets": retweets,
                            "username": username,
                            "created_utc": timestamp,
                            "source": "twitter",
                            "method": "nitter",
                            "human_label": None
                        })
                        
                        if len(posts) >= limit:
                            break
                            
                    except Exception as e:
                        continue
                
                if posts:
                    print(f"Nitter: {len(posts)} tweets via {instance}")
                    break
                else:
                    print(f"Nitter {instance}: parsing failed, trying next...")
                    
            except Exception as e:
                print(f"Nitter {instance} error: {e}")
                continue
        
    except Exception as e:
        print(f"Erreur Nitter: {e}")
    finally:
        driver.quit()
    
    if save_posts:
        save_posts(posts, source="twitter", method="nitter")
    
    return posts
