"""
YouTube Scraper - Commentaires crypto historiques
Utilise l'API YouTube Data v3 (gratuite: 10,000 unites/jour)
"""

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
    print("YouTube API: pip install google-api-python-client")

# Alternative sans API: scraping direct
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

# Limites
LIMITS = {
    "api": 500,      # Avec API key (limite quotidienne: ~10k requetes)
    "selenium": 100  # Sans API, scraping direct
}

# Videos crypto populaires pour bootstrap
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

# Mots-cles pour recherche
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
    """Delai aleatoire pour imiter comportement humain"""
    time.sleep(random.uniform(min_s, max_s))


# ==================== METHODE 1: API YOUTUBE (RECOMMANDEE) ====================

def scrape_youtube_api(
    query: str,
    limit: int = 50,
    api_key: str = None,
    published_after: str = None,  # Format: 2020-01-01T00:00:00Z
    published_before: str = None
) -> List[Dict]:
    """
    Scrape YouTube via l'API officielle (gratuite)
    
    Args:
        query: Terme de recherche (ex: "Bitcoin price prediction")
        limit: Nombre de commentaires souhaites
        api_key: Cle API YouTube (gratuite sur Google Cloud Console)
        published_after: Date debut ISO (ex: "2020-01-01T00:00:00Z")
        published_before: Date fin ISO
    
    Returns:
        Liste de commentaires avec metadata
    """
    if not YOUTUBE_API_OK:
        print("YouTube API non disponible. Installez: pip install google-api-python-client")
        return []
    
    if not api_key:
        import os
        api_key = os.environ.get("YOUTUBE_API_KEY")
    
    if not api_key:
        print("YouTube: Cle API requise. Definissez YOUTUBE_API_KEY ou passez api_key=")
        print("Obtenez une cle gratuite: https://console.cloud.google.com/apis/credentials")
        return scrape_youtube_selenium(query, min(limit, LIMITS["selenium"]))
    
    try:
        youtube = build('youtube', 'v3', developerKey=api_key)
        
        # 1. Rechercher des videos
        search_params = {
            'q': query,
            'type': 'video',
            'part': 'id,snippet',
            'maxResults': min(25, limit // 2),  # ~2 commentaires par video
            'order': 'relevance',
            'relevanceLanguage': 'en'
        }
        
        if published_after:
            search_params['publishedAfter'] = published_after
        if published_before:
            search_params['publishedBefore'] = published_before
        
        print(f"YouTube API: Recherche videos pour '{query}'...")
        search_response = youtube.search().list(**search_params).execute()
        
        video_ids = [item['id']['videoId'] for item in search_response.get('items', [])]
        print(f"YouTube API: {len(video_ids)} videos trouvees")
        
        if not video_ids:
            return []
        
        # 2. Recuperer les commentaires de chaque video
        all_comments = []
        comments_per_video = max(5, limit // len(video_ids))
        
        for video_id in video_ids:
            if len(all_comments) >= limit:
                break
            
            try:
                comments = get_video_comments_api(youtube, video_id, comments_per_video)
                all_comments.extend(comments)
                print(f"  Video {video_id}: {len(comments)} commentaires")
                human_delay(0.5, 1)
            except HttpError as e:
                if 'commentsDisabled' in str(e):
                    print(f"  Video {video_id}: commentaires desactives")
                continue
        
        print(f"YouTube API: Total {len(all_comments)} commentaires")
        return all_comments[:limit]
        
    except HttpError as e:
        print(f"YouTube API Error: {e}")
        return []


def get_video_comments_api(youtube, video_id: str, limit: int) -> List[Dict]:
    """Recupere les commentaires d'une video via l'API"""
    comments = []
    
    try:
        request = youtube.commentThreads().list(
            part='snippet',
            videoId=video_id,
            maxResults=min(100, limit),
            order='relevance',
            textFormat='plainText'
        )
        response = request.execute()
        
        for item in response.get('items', []):
            snippet = item['snippet']['topLevelComment']['snippet']
            
            comments.append({
                'id': item['id'],
                'source': 'youtube',
                'method': 'api',
                'title': snippet.get('textDisplay', '')[:500],  # Limite taille
                'text': snippet.get('textDisplay', ''),
                'score': snippet.get('likeCount', 0),
                'created_utc': snippet.get('publishedAt'),
                'author': snippet.get('authorDisplayName'),
                'video_id': video_id,
                'video_url': f"https://youtube.com/watch?v={video_id}",
                'human_label': None,
                'scraped_at': datetime.now().isoformat()
            })
            
    except Exception as e:
        print(f"Erreur commentaires video {video_id}: {e}")
    
    return comments


# ==================== METHODE 2: SELENIUM (SANS API) ====================

def scrape_youtube_selenium(query: str, limit: int = 50) -> List[Dict]:
    """
    Scrape YouTube sans API via Selenium
    Plus lent mais ne necessite pas de cle API
    """
    if not SELENIUM_OK:
        print("Selenium non installe")
        return []
    
    print(f"YouTube Selenium: Recherche '{query}'...")
    
    comments = []
    seen_ids = set()
    
    # Setup Chrome
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36')
    
    try:
        driver = webdriver.Chrome(options=options)
        
        # Recherche YouTube
        search_url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"
        driver.get(search_url)
        human_delay(3, 5)
        
        # Recuperer les liens des videos
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        video_links = []
        
        for a in soup.find_all('a', href=True):
            href = a['href']
            if '/watch?v=' in href and href not in video_links:
                video_links.append(href)
                if len(video_links) >= 10:
                    break
        
        print(f"YouTube Selenium: {len(video_links)} videos trouvees")
        
        # Scraper les commentaires de chaque video
        for video_path in video_links:
            if len(comments) >= limit:
                break
            
            video_url = f"https://www.youtube.com{video_path}"
            video_comments = scrape_video_comments_selenium(driver, video_url, seen_ids, limit - len(comments))
            comments.extend(video_comments)
            print(f"  {video_path}: {len(video_comments)} commentaires")
        
        driver.quit()
        
    except Exception as e:
        print(f"YouTube Selenium Error: {e}")
        try:
            driver.quit()
        except:
            pass
    
    print(f"YouTube Selenium: Total {len(comments)} commentaires")
    return comments


def scrape_video_comments_selenium(driver, video_url: str, seen_ids: set, limit: int) -> List[Dict]:
    """Scrape les commentaires d'une video YouTube via Selenium"""
    comments = []
    
    try:
        driver.get(video_url)
        human_delay(4, 6)
        
        # Scroll plusieurs fois pour charger les commentaires (YouTube lazy load)
        last_height = driver.execute_script("return document.documentElement.scrollHeight")
        
        for scroll_attempt in range(8):  # Plus de scrolls
            # Scroll down
            driver.execute_script("window.scrollTo(0, document.documentElement.scrollHeight);")
            human_delay(2, 3)
            
            # Scroll up un peu puis down (trigger le chargement)
            driver.execute_script("window.scrollBy(0, -200);")
            human_delay(0.5, 1)
            driver.execute_script("window.scrollBy(0, 400);")
            human_delay(1, 2)
            
            new_height = driver.execute_script("return document.documentElement.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height
        
        # Parser les commentaires
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # YouTube utilise plusieurs structures possibles
        # Methode 1: ytd-comment-renderer
        comment_elements = soup.find_all('ytd-comment-renderer')
        
        # Methode 2: chercher par ID content-text
        if not comment_elements:
            comment_elements = soup.find_all(id='content-text')
        
        # Methode 3: chercher dans le HTML brut avec regex
        if not comment_elements:
            import re
            page_text = driver.page_source
            # Chercher les commentaires dans le JSON embarque
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
                # Extraire le texte du commentaire
                if hasattr(elem, 'name') and elem.name == 'ytd-comment-renderer':
                    content_elem = elem.find('yt-formatted-string', {'id': 'content-text'})
                    text = content_elem.get_text(strip=True) if content_elem else ""
                else:
                    text = elem.get_text(strip=True) if hasattr(elem, 'get_text') else str(elem)
                
                if not text or len(text) < 5:
                    continue
                
                # ID unique
                comment_id = hash(text)
                if comment_id in seen_ids:
                    continue
                seen_ids.add(comment_id)
                
                # Extraire les likes
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
                
                # Extraire l'auteur
                author = ""
                if hasattr(elem, 'find'):
                    author_elem = elem.find('a', {'id': 'author-text'})
                    if author_elem:
                        author = author_elem.get_text(strip=True)
                
                # Extraire la date
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
                
    except Exception as e:
        print(f"Erreur video {video_url}: {e}")
    
    return comments


def parse_youtube_number(text: str) -> int:
    """Parse les nombres YouTube (ex: '1.2K' -> 1200)"""
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


# ==================== FONCTION PRINCIPALE ====================

def scrape_youtube(
    query: str,
    limit: int = 50,
    method: str = "auto",
    api_key: str = None,
    start_date: str = None,  # Format: YYYY-MM-DD
    end_date: str = None
) -> List[Dict]:
    """
    Fonction principale pour scraper YouTube
    
    Args:
        query: Terme de recherche
        limit: Nombre de commentaires
        method: "api", "selenium", ou "auto"
        api_key: Cle API YouTube (optionnel)
        start_date: Date debut (YYYY-MM-DD)
        end_date: Date fin (YYYY-MM-DD)
    
    Returns:
        Liste de commentaires
    """
    # Convertir dates au format ISO si fournies
    published_after = None
    published_before = None
    
    if start_date:
        published_after = f"{start_date}T00:00:00Z"
    if end_date:
        published_before = f"{end_date}T23:59:59Z"
    
    # Choisir la methode
    if method == "auto":
        import os
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


# ==================== TEST ====================

if __name__ == "__main__":
    print("Test YouTube Scraper")
    print("=" * 50)
    
    # Test sans API (Selenium)
    comments = scrape_youtube("Bitcoin price analysis", limit=20, method="selenium")
    
    print(f"\nResultats: {len(comments)} commentaires")
    for c in comments[:5]:
        print(f"  [{c['score']} likes] {c['title'][:60]}...")
