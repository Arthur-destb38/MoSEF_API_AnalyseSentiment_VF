"""
Scraper Reddit via API JSON
Limite: ~1000 posts max
"""

import requests
import time


class HttpScraper:

    BASE_URL = "https://old.reddit.com"

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"
    }

    # Liste des subreddits par crypto
    SUBREDDITS = {
        "bitcoin": "Bitcoin",
        "ethereum": "ethereum",
        "solana": "solana",
        "cardano": "cardano",
        "dogecoin": "dogecoin",
        "ripple": "xrp",
        "xrp": "xrp",
        "polkadot": "polkadot",
        "chainlink": "chainlink",
        "litecoin": "litecoin",
        "avalanche": "avax",
        "polygon": "maticnetwork",
        "cosmos": "cosmosnetwork",
        "uniswap": "uniswap",
        "shiba": "SHIBArmy",
        "shiba-inu": "SHIBArmy",
        "pepe": "pepecoin",
        "arbitrum": "arbitrum",
        "optimism": "optimism",
        "near": "nearprotocol",
        "aptos": "aptos",
        "sui": "sui",
        "floki": "floki",
        "bonk": "BONK",
        # Subreddits generaux
        "crypto": "CryptoCurrency",
        "cryptomarkets": "CryptoMarkets",
        "defi": "defi",
    }

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)

    def get_subreddit(self, crypto: str) -> str:
        """Retourne le subreddit pour une crypto"""
        return self.SUBREDDITS.get(crypto.lower(), crypto)

    def list_cryptos(self) -> list:
        """Liste des cryptos disponibles"""
        return list(self.SUBREDDITS.keys())

    def scrape_subreddit(self, subreddit: str, query: str = "", limit: int = 100) -> list:
        """
        Scrape un subreddit
        limit: max 1000 (limite Reddit)
        """
        posts = []
        after = None

        # Reddit limite a 1000 posts
        limit = min(limit, 1000)

        while len(posts) < limit:
            batch_size = min(100, limit - len(posts))  # Reddit: 100 max par requete

            params = {
                "limit": batch_size,
                "sort": "new",
                "raw_json": 1
            }

            if query:
                params["q"] = query
                params["restrict_sr"] = "on"
                url = f"{self.BASE_URL}/r/{subreddit}/search.json"
            else:
                url = f"{self.BASE_URL}/r/{subreddit}/new.json"

            if after:
                params["after"] = after

            try:
                resp = self.session.get(url, params=params, timeout=15)

                if resp.status_code == 429:
                    print("Rate limit, attente 10s...")
                    time.sleep(10)
                    continue

                resp.raise_for_status()
                data = resp.json()

            except Exception as e:
                print(f"Erreur: {e}")
                break

            children = data.get("data", {}).get("children", [])

            if not children:
                break

            for child in children:
                d = child.get("data", {})

                posts.append({
                    "id": d.get("id"),
                    "title": d.get("title", ""),
                    "text": d.get("selftext", ""),
                    "score": d.get("score", 0),
                    "num_comments": d.get("num_comments", 0),
                    "created_utc": d.get("created_utc"),
                    "author": d.get("author"),
                    "url": f"https://reddit.com{d.get('permalink', '')}",
                    "subreddit": d.get("subreddit")
                })

                if len(posts) >= limit:
                    break

            after = data.get("data", {}).get("after")

            if not after:
                break

            # Pause pour eviter rate limit
            time.sleep(0.3)

        return posts

    def scrape_multiple(self, cryptos: list, limit_per_crypto: int = 50) -> dict:
        """
        Scrape plusieurs cryptos
        Retourne: {crypto: [posts]}
        """
        all_posts = {}

        for crypto in cryptos:
            sub = self.get_subreddit(crypto)
            print(f"Scraping r/{sub}...")

            posts = self.scrape_subreddit(sub, limit=limit_per_crypto)
            all_posts[crypto] = posts

            print(f"  -> {len(posts)} posts")
            time.sleep(1)  # Pause entre chaque crypto

        return all_posts

    def close(self):
        self.session.close()


if __name__ == "__main__":
    scraper = HttpScraper()

    print("Cryptos disponibles:")
    print(scraper.list_cryptos())

    print("\nTest scraping Bitcoin (20 posts):")
    posts = scraper.scrape_subreddit("Bitcoin", limit=20)
    for p in posts[:3]:
        print(f"  - {p['title'][:50]}...")

    print(f"\nTotal: {len(posts)} posts")
    scraper.close()