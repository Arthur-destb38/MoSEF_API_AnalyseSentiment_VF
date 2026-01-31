"""
Instagram Scraper
"""

import time
from datetime import datetime
from typing import Optional

INSTALOADER_OK = False
try:
    import instaloader
    INSTALOADER_OK = True
except ImportError:
    INSTALOADER_OK = False

SELENIUM_OK = False
try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from bs4 import BeautifulSoup
    SELENIUM_OK = True
except ImportError:
    SELENIUM_OK = False

LIMITS = {"instaloader": 100, "selenium": 50}


def get_limits():
    return LIMITS


def scrape_instagram_hashtag(hashtag: str, limit: int = 50, username: str = None, password: str = None) -> list:
    if INSTALOADER_OK:
        return scrape_instagram_instaloader(hashtag, limit, username, password)
    elif SELENIUM_OK:
        return scrape_instagram_selenium(hashtag, limit)
    else:
        return []


def scrape_instagram_instaloader(hashtag: str, limit: int, username: str = None, password: str = None) -> list:
    posts = []
    
    try:
        L = instaloader.Instaloader(
            download_pictures=False,
            download_videos=False,
            download_video_thumbnails=False,
            download_geotags=False,
            download_comments=False,
            save_metadata=False,
            compress_json=False,
            max_connection_attempts=3
        )
        
        if username and password:
            try:
                try:
                    L.load_session_from_file(username)
                except FileNotFoundError:
                    L.login(username, password)
                    L.save_session_to_file()
            except instaloader.exceptions.TwoFactorAuthRequiredException:
                code = input("Code 2FA: ")
                try:
                    L.two_factor_login(code)
                    L.save_session_to_file()
                except Exception:
                    return []
            except instaloader.exceptions.BadCredentialsException:
                return []
            except instaloader.exceptions.ConnectionException:
                return []
            except Exception:
                return []
        else:
            return []
        
        try:
            test_profile = instaloader.Profile.from_username(L.context, username)
        except Exception:
            try:
                L.login(username, password)
                L.save_session_to_file()
            except Exception:
                return []
        
        try:
            hashtag_obj = instaloader.Hashtag.from_name(L.context, hashtag)
        except Exception:
            return []
        
        count = 0
        for post in hashtag_obj.get_posts():
            if count >= limit:
                break
            
            try:
                caption = post.caption or ""
                likes = post.likes
                comments = post.comments
                timestamp = post.date_utc
                owner = post.owner_username
                shortcode = post.shortcode
                url = f"https://www.instagram.com/p/{shortcode}/"
                
                posts.append({
                    "id": shortcode,
                    "title": caption[:500] if caption else "",
                    "text": "",
                    "score": likes + comments,
                    "likes": likes,
                    "retweets": comments,
                    "username": owner,
                    "created_utc": timestamp.isoformat() if timestamp else None,
                    "source": "instagram",
                    "method": "instaloader",
                    "url": url,
                    "human_label": None
                })
                
                count += 1
                time.sleep(1)
                
            except Exception:
                continue
        
        print(f"Done: {len(posts)} posts")
        
    except Exception:
        if SELENIUM_OK:
            return scrape_instagram_selenium(hashtag, limit)
    
    return posts


def scrape_instagram_selenium(hashtag: str, limit: int) -> list:
    posts = []
    
    if not SELENIUM_OK:
        return []
    
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    try:
        driver = webdriver.Chrome(options=options)
        url = f"https://www.instagram.com/explore/tags/{hashtag}/"
        
        driver.get(url)
        time.sleep(5)
        
        for i in range(min(limit // 9, 5)):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
        
        soup = BeautifulSoup(driver.page_source, "lxml")
        post_links = soup.select("a[href*='/p/']")
        seen_ids = set()
        
        for link in post_links[:limit * 2]:
            href = link.get("href", "")
            if "/p/" in href and href not in seen_ids:
                seen_ids.add(href)
                shortcode = href.split("/p/")[-1].rstrip("/")
                
                posts.append({
                    "id": shortcode,
                    "title": "",
                    "text": "",
                    "score": 0,
                    "likes": 0,
                    "retweets": 0,
                    "username": "",
                    "created_utc": None,
                    "source": "instagram",
                    "method": "selenium",
                    "url": f"https://www.instagram.com{href}",
                    "human_label": None
                })
                
                if len(posts) >= limit:
                    break
        
        driver.quit()
        print(f"Done: {len(posts)} posts")
        
    except Exception:
        pass
    
    return posts


def scrape_instagram_profile(username: str, limit: int = 50, insta_username: str = None, insta_password: str = None) -> list:
    if INSTALOADER_OK:
        return scrape_profile_instaloader(username, limit, insta_username, insta_password)
    else:
        return []


def scrape_profile_instaloader(username: str, limit: int, insta_username: str = None, insta_password: str = None) -> list:
    posts = []
    
    try:
        L = instaloader.Instaloader(
            download_pictures=False,
            download_videos=False,
            download_video_thumbnails=False,
            download_geotags=False,
            download_comments=False,
            save_metadata=False
        )
        
        if insta_username and insta_password:
            try:
                L.login(insta_username, insta_password)
            except:
                pass
        
        profile = instaloader.Profile.from_username(L.context, username)
        
        count = 0
        for post in profile.get_posts():
            if count >= limit:
                break
            
            caption = post.caption or ""
            posts.append({
                "id": post.shortcode,
                "title": caption[:500],
                "text": "",
                "score": post.likes + post.comments,
                "likes": post.likes,
                "retweets": post.comments,
                "username": username,
                "created_utc": post.date_utc.isoformat() if post.date_utc else None,
                "source": "instagram",
                "method": "instaloader",
                "url": f"https://www.instagram.com/p/{post.shortcode}/",
                "human_label": None
            })
            
            count += 1
            time.sleep(0.5)
        
        print(f"Done: {len(posts)} posts")
        
    except Exception:
        pass
    
    return posts
