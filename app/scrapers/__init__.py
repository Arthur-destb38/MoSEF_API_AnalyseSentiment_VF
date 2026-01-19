from .http_scraper import HttpScraper
from .selenium_scraper import SeleniumScraper
from .reddit_scraper import scrape_reddit, get_limits as get_reddit_limits
from .stocktwits_scraper import scrape_stocktwits, get_limits as get_stocktwits_limits
from .twitter_scraper import scrape_twitter, get_limits as get_twitter_limits
from .tiktok_scraper import scrape_tiktok, get_limits as get_tiktok_limits
from .youtube_scraper import scrape_youtube, get_limits as get_youtube_limits
from .telegram_scraper import (
    scrape_telegram_simple, 
    scrape_telegram_paginated,
    scrape_multiple_channels as scrape_telegram_multi,
    CRYPTO_CHANNELS as TELEGRAM_CHANNELS
)

def get_telegram_limits():
    return {"simple": 30, "paginated": 500}

__all__ = [
    "HttpScraper", 
    "SeleniumScraper", 
    "scrape_reddit", 
    "scrape_stocktwits",
    "scrape_twitter",
    "scrape_tiktok",
    "scrape_youtube",
    "get_reddit_limits",
    "get_stocktwits_limits",
    "get_twitter_limits",
    "get_tiktok_limits",
    "get_youtube_limits",
    "scrape_telegram_simple",
    "scrape_telegram_paginated",
    "scrape_telegram_multi",
    "TELEGRAM_CHANNELS",
    "get_telegram_limits"
]
