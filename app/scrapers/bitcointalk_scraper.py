"""
Bitcointalk Scraper - Forum crypto historique
Scrape les discussions depuis bitcointalk.org
"""

import requests
import time
import re
from datetime import datetime
from typing import List, Dict, Optional
from bs4 import BeautifulSoup

LIMITS = {
    "http": 200  # Limite raisonnable pour éviter les blocks
}

# Mots-clés crypto pour filtrer les discussions pertinentes
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
    """Scrape Bitcointalk. En cas d'erreur, retourne [] sans lever."""
    try:
        return _scrape_bitcointalk_impl(query, limit)
    except Exception as e:
        print(f"Bitcointalk scrape_bitcointalk: {e}")
        return []


def _scrape_bitcointalk_impl(query: str = "bitcoin", limit: int = 50) -> List[Dict]:
    posts = []
    seen_ids = set()

    # Headers pour éviter les blocks
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Referer": "https://bitcointalk.org/"
    }

    try:
        # Bitcointalk a plusieurs boards, on va scraper les boards crypto populaires
        boards = [
            "https://bitcointalk.org/index.php?board=1.0",  # Bitcoin Discussion
            "https://bitcointalk.org/index.php?board=159.0",  # Altcoins
            "https://bitcointalk.org/index.php?board=67.0",  # Economics
        ]

        query_lower = query.lower()
        keywords = CRYPTO_KEYWORDS.get(query_lower, [query_lower])

        print(f"Bitcointalk: Scraping boards pour '{query}'...")

        for board_url in boards:
            if len(posts) >= limit:
                break

            try:
                print(f"Bitcointalk: Accès à {board_url}...")
                response = requests.get(board_url, headers=headers, timeout=15)
                response.raise_for_status()

                soup = BeautifulSoup(response.content, "html.parser")

                # Trouver les topics (discussions) - plusieurs sélecteurs possibles
                topics = soup.find_all("td", class_="subject")
                if not topics:
                    # Alternative: chercher les liens vers les topics
                    topics = soup.find_all("a", href=re.compile(r"topic=\d+"))
                if not topics:
                    # Autre alternative: span avec class subject
                    topics = soup.find_all("span", class_="subject")

                for topic in topics[:50]:  # Limiter à 50 topics par board
                    if len(posts) >= limit:
                        break

                    # Lien vers le topic
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

                    # Filtrer par mots-clés
                    topic_lower = topic_title.lower()
                    if not any(keyword in topic_lower for keyword in keywords):
                        continue

                    # Récupérer les posts du topic
                    try:
                        topic_response = requests.get(topic_url, headers=headers, timeout=10)
                        topic_response.raise_for_status()
                        topic_soup = BeautifulSoup(topic_response.content, "html.parser")

                        # Parser les posts du topic
                        post_divs = topic_soup.find_all("div", class_="post")

                        for post_div in post_divs[:10]:  # Max 10 posts par topic
                            if len(posts) >= limit:
                                break

                            # ID du post
                            post_id_el = post_div.find("a", {"name": re.compile(r"msg\d+")})
                            if post_id_el:
                                post_id = post_id_el.get("name", "")
                            else:
                                post_id = str(hash(str(post_div)[:100]))

                            if post_id in seen_ids:
                                continue
                            seen_ids.add(post_id)

                            # Texte du post
                            post_body = post_div.find("div", class_="post")
                            if not post_body:
                                post_body = post_div

                            # Nettoyer le texte
                            text = post_body.get_text(separator=" ", strip=True)
                            text = re.sub(r"\s+", " ", text)  # Normaliser les espaces

                            if not text or len(text) < 10:
                                continue

                            # Filtrer par mots-clés dans le contenu
                            text_lower = text.lower()
                            if not any(keyword in text_lower for keyword in keywords):
                                continue

                            # Auteur
                            author_el = post_div.find("b")
                            author = author_el.get_text(strip=True) if author_el else "Anonymous"

                            # Date (format Bitcointalk)
                            date_el = post_div.find("div", class_="smalltext")
                            created_utc = None
                            if date_el:
                                date_text = date_el.get_text(strip=True)
                                # Parser la date Bitcointalk (ex: "Today at 10:30:00 AM")
                                try:
                                    # Format simple pour l'instant
                                    created_utc = datetime.now().isoformat()
                                except:
                                    pass

                            # Métriques (réponses dans le topic)
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

                            if len(posts) % 10 == 0:
                                print(f"  Bitcointalk: {len(posts)} posts collectés...")

                        time.sleep(1)  # Délai entre topics

                    except Exception as e:
                        continue

                time.sleep(2)  # Délai entre boards

            except Exception as e:
                print(f"  Erreur board {board_url}: {e}")
                continue

        print(f"Bitcointalk: {len(posts)} posts recuperes")

    except Exception as e:
        print(f"Erreur Bitcointalk: {e}")
        import traceback
        traceback.print_exc()
    
    return posts[:limit]
