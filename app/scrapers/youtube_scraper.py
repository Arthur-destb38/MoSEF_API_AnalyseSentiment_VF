"""
YouTube Scraper
"""

import os
import time
import random
import re
from datetime import datetime
from typing import List, Dict, Optional

try:
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    YOUTUBE_API_OK = True
except ImportError:
    YOUTUBE_API_OK = False

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

LIMITS = {"api": 500, "selenium": 100}

CRYPTO_CHANNELS = {
    "bitcoin": [
        "UCY0xL8V6NzzFcwzHCgB8orQ",  # BitcoinMagazine
        "UCqK_GSMbpiV8spgD3ZGloSw",  # Coin Bureau
    ],
    "ethereum": [
        "UCqK_GSMbpiV8spgD3ZGloSw",  # Coin Bureau
    ],
    "crypto_general": [
        "UCqK_GSMbpiV8spgD3ZGloSw",  # Coin Bureau
        "UC4sS8q8E5ayyghbhiPon4uw",  # DataDash
    ]
}

CRYPTO_KEYWORDS = {
    "bitcoin": "Bitcoin BTC crypto",
    "ethereum": "Ethereum ETH crypto",
    "solana": "Solana SOL crypto",
    "cardano": "Cardano ADA crypto",
    "dogecoin": "Dogecoin DOGE crypto",
}


def get_limits():
    """Retourne les limites par methode"""
    return LIMITS


def human_delay(min_s=1, max_s=3):
    time.sleep(random.uniform(min_s, max_s))


def scrape_youtube_api(
    query: str,
    limit: int = 50,
    api_key: str = None,
    published_after: str = None,
    published_before: str = None
) -> List[Dict]:
    if not YOUTUBE_API_OK:
        print("YouTube API non disponible. Installez: pip install google-api-python-client")
        return []
    
    if not api_key:
        api_key = os.environ.get("YOUTUBE_API_KEY")
    
    if not api_key:
        return scrape_youtube_selenium(query, min(limit, LIMITS["selenium"]))
    
    try:
        youtube = build('youtube', 'v3', developerKey=api_key)
        
        search_params = {
            'q': query,
            'type': 'video',
            'part': 'id,snippet',
            'maxResults': min(25, limit // 2),
            'order': 'relevance',
            'relevanceLanguage': 'en'
        }
        
        if published_after:
            search_params['publishedAfter'] = published_after
        if published_before:
            search_params['publishedBefore'] = published_before
        
        search_response = youtube.search().list(**search_params).execute()
        video_ids = [item['id']['videoId'] for item in search_response.get('items', [])]
        
        if not video_ids:
            return []
        
        all_comments = []
        comments_per_video = max(5, limit // len(video_ids))
        
        for video_id in video_ids:
            if len(all_comments) >= limit:
                break
            
            try:
                comments = get_video_comments_api(youtube, video_id, comments_per_video, order='relevance')
                all_comments.extend(comments)
                human_delay(0.5, 1)
            except HttpError:
                continue
        
        print(f"Done: {len(all_comments)} comments")
        return all_comments[:limit]
        
    except HttpError as e:
        print(f"YouTube API Error: {e}")
        return []


def get_video_comments_api(youtube, video_id: str, limit: int, order: str = "relevance") -> List[Dict]:
    comments = []
    next_page_token = None
    
    try:
        while len(comments) < limit:
            request = youtube.commentThreads().list(
                part='snippet',
                videoId=video_id,
                maxResults=min(100, limit - len(comments)),
                order=order,
                textFormat='plainText',
                pageToken=next_page_token
            )
            response = request.execute()
            
            items = response.get('items', [])
            if not items:
                break
            
            for item in items:
                snippet = item['snippet']['topLevelComment']['snippet']
                
                comments.append({
                    'id': item['id'],
                    'source': 'youtube',
                    'method': 'api',
                    'title': snippet.get('textDisplay', '')[:500],
                    'text': snippet.get('textDisplay', ''),
                    'score': snippet.get('likeCount', 0),
                    'created_utc': snippet.get('publishedAt'),
                    'author': snippet.get('authorDisplayName'),
                    'video_id': video_id,
                    'video_url': f"https://youtube.com/watch?v={video_id}",
                    'human_label': None,
                    'scraped_at': datetime.now().isoformat()
                })
                
                if len(comments) >= limit:
                    break
            
            next_page_token = response.get('nextPageToken')
            if not next_page_token:
                break
            
            time.sleep(0.1)
            
    except HttpError:
        pass
    except Exception:
        pass
    
    return comments


def scrape_youtube_selenium(query: str, limit: int = 50) -> List[Dict]:
    if not SELENIUM_OK:
        print("Selenium non installe")
        return []
    
    print(f"Searching '{query}'...")
    
    comments = []
    seen_ids = set()
    
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36')
    
    try:
        driver = webdriver.Chrome(options=options)
        search_url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"
        driver.get(search_url)
        human_delay(3, 5)
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        video_links = []
        
        for a in soup.find_all('a', href=True):
            href = a['href']
            if '/watch?v=' in href and href not in video_links:
                video_links.append(href)
                if len(video_links) >= 10:
                    break
        
        for video_path in video_links:
            if len(comments) >= limit:
                break
            
            video_url = f"https://www.youtube.com{video_path}"
            video_comments = scrape_video_comments_selenium(driver, video_url, seen_ids, limit - len(comments))
            comments.extend(video_comments)
        
        driver.quit()
        
    except Exception:
        pass
        try:
            driver.quit()
        except:
            pass
    
    print(f"Done: {len(comments)} comments")
    return comments


def scrape_video_comments_selenium(driver, video_url: str, seen_ids: set, limit: int) -> List[Dict]:
    comments = []
    
    try:
        driver.get(video_url)
        human_delay(4, 6)
        
        last_height = driver.execute_script("return document.documentElement.scrollHeight")
        
        for scroll_attempt in range(8):
            driver.execute_script("window.scrollTo(0, document.documentElement.scrollHeight);")
            human_delay(2, 3)
            
            driver.execute_script("window.scrollBy(0, -200);")
            human_delay(0.5, 1)
            driver.execute_script("window.scrollBy(0, 400);")
            human_delay(1, 2)
            
            new_height = driver.execute_script("return document.documentElement.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        comment_elements = soup.find_all('ytd-comment-renderer')
        
        if not comment_elements:
            comment_elements = soup.find_all(id='content-text')
        
        if not comment_elements:
            page_text = driver.page_source
            comment_pattern = r'"contentText":\{"runs":\[\{"text":"([^"]+)"\}\]'
            matches = re.findall(comment_pattern, page_text)
            for match in matches[:limit]:
                if match and len(match) > 5:
                    comment_id = hash(match)
                    if comment_id not in seen_ids:
                        seen_ids.add(comment_id)
                        comments.append({
                            'id': str(comment_id),
                            'source': 'youtube',
                            'method': 'selenium',
                            'title': match[:200],
                            'text': match,
                            'score': 0,
                            'created_utc': None,
                            'author': None,
                            'video_url': video_url,
                            'human_label': None,
                            'scraped_at': datetime.now().isoformat()
                        })
            return comments
        
        for elem in comment_elements:
            if len(comments) >= limit:
                break
            
            try:
                if hasattr(elem, 'name') and elem.name == 'ytd-comment-renderer':
                    content_elem = elem.find('yt-formatted-string', {'id': 'content-text'})
                    text = content_elem.get_text(strip=True) if content_elem else ""
                else:
                    text = elem.get_text(strip=True) if hasattr(elem, 'get_text') else str(elem)
                
                if not text or len(text) < 5:
                    continue
                
                comment_id = hash(text)
                if comment_id in seen_ids:
                    continue
                seen_ids.add(comment_id)
                
                likes = 0
                if hasattr(elem, 'find'):
                    likes_elem = elem.find('span', {'id': 'vote-count-middle'})
                    if likes_elem:
                        likes_text = likes_elem.get_text(strip=True)
                        if likes_text:
                            try:
                                likes = parse_youtube_number(likes_text)
                            except:
                                pass
                
                author = ""
                if hasattr(elem, 'find'):
                    author_elem = elem.find('a', {'id': 'author-text'})
                    if author_elem:
                        author = author_elem.get_text(strip=True)
                
                date_str = None
                if hasattr(elem, 'find'):
                    date_elem = elem.find('yt-formatted-string', {'class': 'published-time-text'})
                    if date_elem:
                        date_str = date_elem.get_text(strip=True)
                
                comments.append({
                    'id': str(comment_id),
                    'source': 'youtube',
                    'method': 'selenium',
                    'title': text[:200],
                    'text': text,
                    'score': likes,
                    'created_utc': date_str,
                    'author': author,
                    'video_url': video_url,
                    'human_label': None,
                    'scraped_at': datetime.now().isoformat()
                })
                
            except Exception as e:
                continue
                
    except Exception:
        pass
    
    return comments


def parse_youtube_number(text: str) -> int:
    text = text.strip().upper()
    if not text:
        return 0
    
    multipliers = {'K': 1000, 'M': 1000000, 'B': 1000000000}
    
    for suffix, mult in multipliers.items():
        if suffix in text:
            num = float(text.replace(suffix, '').strip())
            return int(num * mult)
    
    try:
        return int(text.replace(',', ''))
    except:
        return 0


def scrape_youtube(
    query: str,
    limit: int = 50,
    method: str = "auto",
    api_key: str = None,
    start_date: str = None,
    end_date: str = None,
    video_url: str = None,
    order: str = "relevance"
) -> List[Dict]:
    if video_url:
        return scrape_single_video(video_url, limit, api_key, order)
    
    published_after = None
    published_before = None
    
    if start_date:
        published_after = f"{start_date}T00:00:00Z"
    if end_date:
        published_before = f"{end_date}T23:59:59Z"
    
    if method == "auto":
        if api_key or os.environ.get("YOUTUBE_API_KEY"):
            method = "api"
        else:
            method = "selenium"
    
    if method == "api":
        return scrape_youtube_api(
            query, 
            min(limit, LIMITS["api"]),
            api_key,
            published_after,
            published_before
        )
    else:
        return scrape_youtube_selenium(query, min(limit, LIMITS["selenium"]))


def scrape_single_video(video_url: str, limit: int = 100, api_key: str = None, order: str = "relevance") -> List[Dict]:
    video_id = None
    patterns = [
        r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([a-zA-Z0-9_-]{11})',
        r'v=([a-zA-Z0-9_-]{11})',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, video_url)
        if match:
            video_id = match.group(1)
            break
    
    if not video_id:
        return []
    
    if not api_key:
        api_key = os.environ.get("YOUTUBE_API_KEY")
    
    if api_key and YOUTUBE_API_OK:
        try:
            youtube = build('youtube', 'v3', developerKey=api_key)
            video_info = youtube.videos().list(part='snippet,statistics', id=video_id).execute()
            video_title = ""
            if video_info.get('items'):
                v = video_info['items'][0]
                video_title = v['snippet'].get('title', '')
            
            comments = []
            next_page = None
            
            while len(comments) < limit:
                try:
                    request = youtube.commentThreads().list(
                        part='snippet',
                        videoId=video_id,
                        maxResults=min(100, limit - len(comments)),
                        order=order,
                        textFormat='plainText',
                        pageToken=next_page
                    )
                    response = request.execute()
                    
                    for item in response.get('items', []):
                        snippet = item['snippet']['topLevelComment']['snippet']
                        comments.append({
                            'id': item['id'],
                            'source': 'youtube',
                            'method': 'api',
                            'title': snippet.get('textDisplay', '')[:500],
                            'text': snippet.get('textDisplay', ''),
                            'score': snippet.get('likeCount', 0),
                            'created_utc': snippet.get('publishedAt'),
                            'author': snippet.get('authorDisplayName'),
                            'video_id': video_id,
                            'video_url': video_url,
                            'video_title': video_title,
                            'human_label': None,
                            'scraped_at': datetime.now().isoformat()
                        })
                    
                    next_page = response.get('nextPageToken')
                    if not next_page:
                        break
                        
                except HttpError:
                    break
            
            return comments
            
        except Exception:
            return []
    
    else:
        if SELENIUM_OK:
            seen_ids = set()
            options = Options()
            options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36')
            
            try:
                driver = webdriver.Chrome(options=options)
                comments = scrape_video_comments_selenium(driver, video_url, seen_ids, limit)
                driver.quit()
                return comments
            except Exception:
                return []
        
        return []


if __name__ == "__main__":
    print("Test YouTube Scraper")
    comments = scrape_youtube("Bitcoin price analysis", limit=20, method="selenium")
    
    print(f"\nResultats: {len(comments)} commentaires")
    for c in comments[:5]:
        print(f"  [{c['score']} likes] {c['title'][:60]}...")
