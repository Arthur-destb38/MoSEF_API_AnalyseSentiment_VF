"""
4chan /biz/ Scraper - Très populaire pour crypto
Format simple, pas de login, facile à scraper
"""

import requests
import time
import re
from datetime import datetime
from typing import List, Dict, Optional

LIMITS = {
    "http": 200  # 4chan permet beaucoup de requêtes
}

# Mots-clés crypto pour filtrer les threads pertinents
CRYPTO_KEYWORDS = {
    "bitcoin": ["bitcoin", "btc", "satoshi"],
    "ethereum": ["ethereum", "eth", "vitalik"],
    "solana": ["solana", "sol", "sbf"],
    "cardano": ["cardano", "ada", "charles"],
    "dogecoin": ["dogecoin", "doge", "elon"],
    "crypto": ["crypto", "cryptocurrency", "defi", "nft", "altcoin"],
}


def get_limits():
    """Retourne les limites par méthode"""
    return LIMITS


def scrape_4chan_biz(query: str = "crypto", limit: int = 50) -> List[Dict]:
    """Scrape 4chan /biz/. En cas d'erreur, retourne [] sans lever."""
    try:
        return _scrape_4chan_biz_impl(query, limit)
    except Exception as e:
        print(f"4chan scrape_4chan_biz: {e}")
        return []


def _scrape_4chan_biz_impl(query: str = "crypto", limit: int = 50) -> List[Dict]:
    posts = []
    seen_ids = set()

    # Headers pour éviter les blocks
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "application/json",
        "Referer": "https://boards.4chan.org/biz/"
    }

    try:
        # API 4chan pour récupérer les threads de /biz/
        api_url = "https://a.4cdn.org/biz/threads.json"

        print(f"4chan: Récupération des threads /biz/...")
        response = requests.get(api_url, headers=headers, timeout=10)
        response.raise_for_status()

        threads_data = response.json()

        # Parcourir les threads
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

                # Récupérer les posts du thread
                thread_url = f"https://a.4cdn.org/biz/thread/{thread_no}.json"

                try:
                    thread_response = requests.get(thread_url, headers=headers, timeout=10)
                    thread_response.raise_for_status()
                    thread_posts = thread_response.json()

                    # Parser les posts du thread
                    for post in thread_posts.get("posts", []):
                        if len(posts) >= limit:
                            break

                        post_id = str(post.get("no", ""))
                        if post_id in seen_ids:
                            continue
                        seen_ids.add(post_id)

                        # Texte du post
                        comment = post.get("com", "")
                        if not comment:
                            continue

                        # Nettoyer le HTML
                        comment = re.sub(r"<[^>]+>", "", comment)
                        comment = comment.replace("&quot;", '"').replace("&amp;", "&")
                        comment = comment.replace("&#039;", "'").replace("&lt;", "<").replace("&gt;", ">")

                        # Filtrer par mots-clés
                        comment_lower = comment.lower()
                        if not any(keyword in comment_lower for keyword in keywords):
                            continue

                        # Métriques
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
                            "likes": 0,  # 4chan n'a pas de likes
                            "retweets": replies,
                            "username": post.get("name", "Anonymous"),
                            "created_utc": created_utc,
                            "source": "4chan",
                            "method": "http",
                            "thread_no": thread_no,
                            "human_label": None
                        })

                        if len(posts) % 10 == 0:
                            print(f"  4chan: {len(posts)} posts collectés...")

                    thread_count += 1
                    time.sleep(0.5)  # Délai entre threads

                except Exception as e:
                    continue

        print(f"4chan: {len(posts)} posts recuperes depuis /biz/")
    except Exception as e:
        print(f"Erreur 4chan: {e}")
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
            
            # Nettoyer HTML
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
        
    except Exception as e:
        print(f"Erreur scraping thread {thread_no}: {e}")
    
    return posts
