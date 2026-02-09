#!/usr/bin/env python3
"""
Reddit : 200 posts par crypto (subreddit), enregistrement en base.
Les doublons sont ignorés (ON CONFLICT DO NOTHING / INSERT OR IGNORE).
Usage : depuis la racine du projet : python scripts/scrape_reddit_200.py
"""

import os
import sys
from datetime import datetime

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

from app.storage import save_posts
from app.scrapers import scrape_reddit

# 200 posts par subreddit (crypto). Subreddits principaux crypto.
REDDIT_SUBS = [
    "cryptocurrency",
    "bitcoin",
    "ethereum",
    "solana",
    "cardano",
]
LIMIT_PER_CRYPTO = 200
METHOD = "http"


def _log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def main() -> None:
    _log("=== Reddit : 200 posts par crypto → base (doublons exclus) ===")
    total_inserted = 0

    for sub in REDDIT_SUBS:
        try:
            _log(f"  → r/{sub} (max {LIMIT_PER_CRYPTO} posts)...")
            posts = scrape_reddit(sub, limit=LIMIT_PER_CRYPTO, method=METHOD)
            if not posts:
                _log(f"  ← r/{sub}: 0 post")
                continue
            out = save_posts(posts, source="reddit", method=METHOD)
            n = out.get("inserted", 0)
            total_inserted += n
            _log(f"  ← r/{sub}: {len(posts)} récupérés, {n} nouveaux insérés (db: {out.get('db_type', '?')})")
        except Exception as e:
            _log(f"  ✗ r/{sub}: {e}")

    _log("=== Fin ===")
    _log(f"Total nouveaux posts enregistrés : {total_inserted}")


if __name__ == "__main__":
    main()
