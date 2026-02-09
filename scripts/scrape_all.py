#!/usr/bin/env python3
"""
Scrape toutes les plateformes supportées en une seule exécution.
Les posts sont enregistrés en base (PostgreSQL ou SQLite selon config).

Usage:
  python scripts/scrape_all.py           # Toutes les plateformes (inclut Selenium)
  python scripts/scrape_all.py --http-only   # Uniquement HTTP/API (fiable, pas de Chrome)

--http-only : ignore StockTwits, Twitter et YouTube Selenium. Recommandé si le script
  bloque ou si Chrome n'est pas installé. Reddit, 4chan, Bitcointalk, GitHub,
  Telegram, Bluesky (+ YouTube API si YOUTUBE_API_KEY) restent actifs.
"""

import argparse
import os
import sys
from datetime import datetime

# Racine du projet
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Charger .env avant tout import qui lit os.environ
from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

from app.storage import save_posts
from app.scrapers import (
    scrape_reddit,
    get_reddit_limits,
    scrape_stocktwits,
    get_stocktwits_limits,
    scrape_twitter,
    get_twitter_limits,
    scrape_youtube,
    get_youtube_limits,
    scrape_4chan_biz,
    get_chan4_limits,
    scrape_bitcointalk,
    get_bitcointalk_limits,
    scrape_github_discussions,
    get_github_limits,
    scrape_bluesky,
    get_bluesky_limits,
    scrape_telegram_paginated,
    scrape_telegram_simple,
    TELEGRAM_CHANNELS,
    get_telegram_limits,
)


def _log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def run_one(name: str, fetch_fn, *args, save_source: str = None, save_method: str = None, **kwargs) -> int:
    """Exécute un scraper, enregistre les posts. save_source/save_method servent pour save_posts ; kwargs → scraper."""
    try:
        _log(f"  → {name}...")
        posts = fetch_fn(*args, **kwargs)
        if not posts:
            _log(f"  ← {name}: 0 post")
            return 0
        out = save_posts(posts, source=save_source or "scrape_all", method=save_method or "batch")
        n = out.get("inserted", 0)
        _log(f"  ← {name}: {len(posts)} récupérés, {n} insérés (db: {out.get('db_type', '?')})")
        return n
    except Exception as e:
        _log(f"  ✗ {name}: {e}")
        return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape toutes les plateformes → base (PostgreSQL ou SQLite)")
    parser.add_argument("--http-only", action="store_true", help="Uniquement HTTP/API (pas de Selenium: pas StockTwits, Twitter, YouTube)")
    args = parser.parse_args()
    http_only = args.http_only

    if http_only:
        _log("=== Scrape (mode HTTP/API uniquement — pas de Selenium) ===")
    else:
        _log("=== Scrape toutes les plateformes ===")
    total_inserted = 0

    # --- Reddit (plusieurs subreddits, méthode HTTP = rapide) ---
    reddit_limits = get_reddit_limits()
    limit_reddit = reddit_limits.get("http", 500)
    for sub in ["cryptocurrency", "bitcoin", "ethereum"]:
        n = run_one(f"Reddit r/{sub}", scrape_reddit, sub, limit=limit_reddit, method="http", save_source="reddit", save_method="http")
        total_inserted += n

    # --- StockTwits (Selenium) — ignoré en --http-only ---
    if not http_only:
        st_limits = get_stocktwits_limits()
        limit_st = st_limits.get("selenium", 500)
        for symbol in ["BTC.X", "ETH.X"]:
            n = run_one(f"StockTwits {symbol}", scrape_stocktwits, symbol, limit=limit_st, method="selenium", save_source="stocktwits", save_method="selenium")
            total_inserted += n

    # --- Twitter/X (Selenium) — ignoré en --http-only ---
    if not http_only:
        tw_limits = get_twitter_limits()
        limit_tw = tw_limits.get("selenium", 500)
        n = run_one("Twitter crypto", scrape_twitter, "bitcoin crypto", limit=limit_tw, method="selenium", save_source="twitter", save_method="selenium")
        total_inserted += n

    # --- YouTube (API si clé, sinon Selenium) — en http-only on force API uniquement ---
    yt_limits = get_youtube_limits()
    limit_yt = yt_limits.get("api", 500) if http_only else max(yt_limits.get("api", 200), yt_limits.get("selenium", 100))
    if http_only and os.environ.get("YOUTUBE_API_KEY"):
        n = run_one("YouTube bitcoin crypto", scrape_youtube, "bitcoin crypto", limit=limit_yt, method="api", save_source="youtube", save_method="api")
        total_inserted += n
    elif not http_only:
        n = run_one("YouTube bitcoin crypto", scrape_youtube, "bitcoin crypto", limit=limit_yt, save_source="youtube", save_method="api")
        total_inserted += n

    # --- Telegram (tous les channels configurés, paginé) ---
    tg_limits = get_telegram_limits()
    limit_tg = tg_limits.get("paginated", 200)
    for channel in list(TELEGRAM_CHANNELS.keys())[:5]:  # max 5 channels pour limiter le temps
        n = run_one(f"Telegram {channel}", scrape_telegram_paginated, channel, max_messages=limit_tg, save_source="telegram", save_method="paginated")
        if n == 0:
            n = run_one(f"Telegram {channel} (simple)", scrape_telegram_simple, channel, limit=min(30, limit_tg), save_source="telegram", save_method="simple")
        total_inserted += n

    # --- 4chan ---
    ch4_limits = get_chan4_limits()
    limit_4chan = ch4_limits.get("http", 200)
    n = run_one("4chan crypto", scrape_4chan_biz, "crypto", limit=limit_4chan, save_source="4chan", save_method="http")
    total_inserted += n

    # --- Bitcointalk ---
    bt_limits = get_bitcointalk_limits()
    limit_bt = bt_limits.get("http", 200)
    n = run_one("Bitcointalk bitcoin", scrape_bitcointalk, "bitcoin", limit=limit_bt, save_source="bitcointalk", save_method="http")
    total_inserted += n

    # --- GitHub ---
    gh_limits = get_github_limits()
    limit_gh = gh_limits.get("api", 200)
    n = run_one("GitHub bitcoin", scrape_github_discussions, "bitcoin", limit=limit_gh, save_source="github", save_method="api")
    total_inserted += n

    # --- Bluesky ---
    bs_limits = get_bluesky_limits()
    limit_bs = bs_limits.get("api", 200)
    n = run_one("Bluesky bitcoin", scrape_bluesky, "bitcoin", limit=limit_bs, save_source="bluesky", save_method="api")
    total_inserted += n

    _log("=== Fin ===")
    _log(f"Total nouveaux posts enregistrés : {total_inserted}")


if __name__ == "__main__":
    main()
