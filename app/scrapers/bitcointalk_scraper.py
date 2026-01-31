"""
Bitcointalk Scraper
"""

import requests
import time
import re
from datetime import datetime
from typing import List, Dict, Optional
from bs4 import BeautifulSoup

LIMITS = {"http": 200}

CRYPTO_KEYWORDS = {
    "bitcoin": ["bitcoin", "btc", "satoshi", "halving"],
    "ethereum": ["ethereum", "eth", "vitalik", "smart contract"],
    "solana": ["solana", "sol", "sbf"],
    "cardano": ["cardano", "ada", "charles"],
    "dogecoin": ["dogecoin", "doge"],
    "crypto": ["crypto", "cryptocurrency", "defi", "nft", "altcoin", "blockchain"],
}


def get_limits():
    """Retourne les limites par méthode"""
    return LIMITS


def scrape_bitcointalk(query: str = "bitcoin", limit: int = 50) -> List[Dict]:
    """
    Scrape Bitcointalk pour les discussions crypto
    
    Args:
        query: Mot-clé de recherche (ex: "bitcoin", "crypto")
        limit: Nombre de posts souhaités
    
    Returns:
        Liste de posts avec texte et métriques
    """
    posts = []
    seen_ids = set()
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Referer": "https://bitcointalk.org/"
    }
    
    try:
        boards = [
            "https://bitcointalk.org/index.php?board=1.0",
            "https://bitcointalk.org/index.php?board=159.0",
            "https://bitcointalk.org/index.php?board=67.0",
        ]
        
        query_lower = query.lower()
        keywords = CRYPTO_KEYWORDS.get(query_lower, [query_lower])
        
        
        for board_url in boards:
            if len(posts) >= limit:
                break
            
            try:
                response = requests.get(board_url, headers=headers, timeout=15)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.content, "html.parser")
                
                topics = soup.find_all("td", class_="subject")
                if not topics:
                    topics = soup.find_all("a", href=re.compile(r"topic=\d+"))
                if not topics:
                    topics = soup.find_all("span", class_="subject")
                
                for topic in topics[:50]:
                    if len(posts) >= limit:
                        break
                    
                    if topic.name == "a":
                        link = topic
                        topic_url = link.get("href", "")
                    else:
                        link = topic.find("a")
                        if not link:
                            continue
                        topic_url = link.get("href", "")
                    
                    if not topic_url:
                        continue
                    
                    if not topic_url.startswith("http"):
                        topic_url = "https://bitcointalk.org/" + topic_url.lstrip("/")
                    
                    topic_title = link.get_text(strip=True) if link else topic.get_text(strip=True)
                    topic_lower = topic_title.lower()
                    if not any(keyword in topic_lower for keyword in keywords):
                        continue
                    
                    try:
                        topic_response = requests.get(topic_url, headers=headers, timeout=10)
                        topic_response.raise_for_status()
                        topic_soup = BeautifulSoup(topic_response.content, "html.parser")
                        post_divs = topic_soup.find_all("div", class_="post")
                        
                        for post_div in post_divs[:10]:
                            if len(posts) >= limit:
                                break
                            
                            post_id_el = post_div.find("a", {"name": re.compile(r"msg\d+")})
                            if post_id_el:
                                post_id = post_id_el.get("name", "")
                            else:
                                post_id = str(hash(str(post_div)[:100]))
                            
                            if post_id in seen_ids:
                                continue
                            seen_ids.add(post_id)
                            
                            post_body = post_div.find("div", class_="post")
                            if not post_body:
                                post_body = post_div
                            
                            text = post_body.get_text(separator=" ", strip=True)
                            text = re.sub(r"\s+", " ", text)
                            
                            if not text or len(text) < 10:
                                continue
                            
                            text_lower = text.lower()
                            if not any(keyword in text_lower for keyword in keywords):
                                continue
                            
                            author_el = post_div.find("b")
                            author = author_el.get_text(strip=True) if author_el else "Anonymous"
                            
                            date_el = post_div.find("div", class_="smalltext")
                            created_utc = None
                            if date_el:
                                try:
                                    created_utc = datetime.now().isoformat()
                                except:
                                    pass
                            
                            replies = 0
                            views = 0
                            
                            posts.append({
                                "id": post_id,
                                "title": topic_title[:200],
                                "text": text[:1000],
                                "score": replies + views,
                                "likes": 0,
                                "retweets": replies,
                                "username": author,
                                "created_utc": created_utc or datetime.now().isoformat(),
                                "source": "bitcointalk",
                                "method": "http",
                                "url": topic_url,
                                "human_label": None
                            })
                        
                        time.sleep(1)
                        
                    except Exception as e:
                        continue
                
                time.sleep(2)
                
            except Exception:
                continue
        
        print(f"Done: {len(posts)} posts")
        
    except Exception:
        pass
    
    return posts[:limit]
