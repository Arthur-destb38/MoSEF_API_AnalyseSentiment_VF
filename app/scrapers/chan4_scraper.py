"""
4chan /biz/ Scraper
"""

import requests
import time
import re
from datetime import datetime
from typing import List, Dict, Optional

LIMITS = {"http": 200}

CRYPTO_KEYWORDS = {
    "bitcoin": ["bitcoin", "btc", "satoshi"],
    "ethereum": ["ethereum", "eth", "vitalik"],
    "solana": ["solana", "sol", "sbf"],
    "cardano": ["cardano", "ada", "charles"],
    "dogecoin": ["dogecoin", "doge", "elon"],
    "crypto": ["crypto", "cryptocurrency", "defi", "nft", "altcoin"],
}


def get_limits():
    return LIMITS


def scrape_4chan_biz(query: str = "crypto", limit: int = 50) -> List[Dict]:
    posts = []
    seen_ids = set()
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "application/json",
        "Referer": "https://boards.4chan.org/biz/"
    }
    
    try:
        api_url = "https://a.4cdn.org/biz/threads.json"
        
        response = requests.get(api_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        threads_data = response.json()
        query_lower = query.lower()
        keywords = CRYPTO_KEYWORDS.get(query_lower, [query_lower])
        
        thread_count = 0
        for page in threads_data:
            for thread in page.get("threads", []):
                if len(posts) >= limit:
                    break
                
                thread_no = thread.get("no")
                if not thread_no:
                    continue
                
                thread_url = f"https://a.4cdn.org/biz/thread/{thread_no}.json"
                
                try:
                    thread_response = requests.get(thread_url, headers=headers, timeout=10)
                    thread_response.raise_for_status()
                    thread_posts = thread_response.json()
                    
                    for post in thread_posts.get("posts", []):
                        if len(posts) >= limit:
                            break
                        
                        post_id = str(post.get("no", ""))
                        if post_id in seen_ids:
                            continue
                        seen_ids.add(post_id)
                        
                        comment = post.get("com", "")
                        if not comment:
                            continue
                        
                        # Nettoyer le HTML
                        comment = re.sub(r"<[^>]+>", "", comment)
                        comment = comment.replace("&quot;", '"').replace("&amp;", "&")
                        comment = comment.replace("&#039;", "'").replace("&lt;", "<").replace("&gt;", ">")
                        comment_lower = comment.lower()
                        if not any(keyword in comment_lower for keyword in keywords):
                            continue
                        
                        replies = post.get("replies", 0)
                        images = 1 if post.get("tim") else 0
                        
                        # Timestamp
                        timestamp = post.get("time", 0)
                        created_utc = datetime.fromtimestamp(timestamp).isoformat() if timestamp else None
                        
                        posts.append({
                            "id": post_id,
                            "title": comment[:500],
                            "text": "",
                            "score": replies + images,
                            "likes": 0,
                            "retweets": replies,
                            "username": post.get("name", "Anonymous"),
                            "created_utc": created_utc,
                            "source": "4chan",
                            "method": "http",
                            "thread_no": thread_no,
                            "human_label": None
                        })
                        
                    
                    thread_count += 1
                    time.sleep(0.5)
                    
                except Exception as e:
                    continue
        
        print(f"Done: {len(posts)} posts")
        
    except Exception:
        pass
    
    return posts[:limit]


def scrape_4chan_thread(thread_no: int, limit: int = 100) -> List[Dict]:
    """
    Scrape un thread spécifique de /biz/
    
    Args:
        thread_no: Numéro du thread
        limit: Nombre de posts souhaités
    """
    posts = []
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "application/json"
    }
    
    try:
        thread_url = f"https://a.4cdn.org/biz/thread/{thread_no}.json"
        response = requests.get(thread_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        thread_data = response.json()
        
        for post in thread_data.get("posts", [])[:limit]:
            comment = post.get("com", "")
            if not comment:
                continue
            
            comment = re.sub(r"<[^>]+>", "", comment)
            comment = comment.replace("&quot;", '"').replace("&amp;", "&")
            
            timestamp = post.get("time", 0)
            created_utc = datetime.fromtimestamp(timestamp).isoformat() if timestamp else None
            
            posts.append({
                "id": str(post.get("no", "")),
                "title": comment[:500],
                "text": "",
                "score": post.get("replies", 0),
                "likes": 0,
                "retweets": post.get("replies", 0),
                "username": post.get("name", "Anonymous"),
                "created_utc": created_utc,
                "source": "4chan",
                "method": "http",
                "thread_no": thread_no,
                "human_label": None
            })
        
    except Exception:
        pass
    
    return posts
