from .http_scraper import HttpScraper
from .selenium_scraper import SeleniumScraper
from .reddit_scraper import scrape_reddit, get_limits as get_reddit_limits
from .stocktwits_scraper import scrape_stocktwits, get_limits as get_stocktwits_limits
from .twitter_scraper import scrape_twitter, get_limits as get_twitter_limits
from .tiktok_scraper import scrape_tiktok, get_limits as get_tiktok_limits
from .youtube_scraper import scrape_youtube, get_limits as get_youtube_limits
from .chan4_scraper import scrape_4chan_biz, get_limits as get_chan4_limits
from .bitcointalk_scraper import scrape_bitcointalk, get_limits as get_bitcointalk_limits
from .github_scraper import scrape_github_discussions, scrape_github_issues, get_limits as get_github_limits
from .bluesky_scraper import scrape_bluesky, get_limits as get_bluesky_limits
from .telegram_scraper import (
    scrape_telegram_simple, 
    scrape_telegram_paginated,
    scrape_telegram_selenium,
    scrape_multiple_channels as scrape_telegram_multi,
    CRYPTO_CHANNELS as TELEGRAM_CHANNELS
)

def get_telegram_limits():
    return {"simple": 30, "paginated": 2000, "selenium": 5000}

__all__ = [
    "HttpScraper", 
    "SeleniumScraper", 
    "scrape_reddit", 
    "scrape_stocktwits",
    "scrape_twitter",
    "scrape_tiktok",
    "scrape_youtube",
    "scrape_4chan_biz",
    "scrape_bitcointalk",
    "scrape_github_discussions",
    "scrape_github_issues",
    "scrape_bluesky",
    "get_bluesky_limits",
    "get_reddit_limits",
    "get_stocktwits_limits",
    "get_twitter_limits",
    "get_tiktok_limits",
    "get_youtube_limits",
    "get_chan4_limits",
    "get_bitcointalk_limits",
    "get_github_limits",
    "scrape_telegram_simple",
    "scrape_telegram_paginated",
    "scrape_telegram_selenium",
    "scrape_telegram_multi",
    "TELEGRAM_CHANNELS",
    "get_telegram_limits"
]
