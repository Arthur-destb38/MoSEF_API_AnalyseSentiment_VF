from .http_scraper import HttpScraper
from .selenium_scraper import SeleniumScraper
from .reddit_scraper import scrape_reddit, get_limits as get_reddit_limits
from .stocktwits_scraper import scrape_stocktwits, get_limits as get_stocktwits_limits
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
    "get_reddit_limits",
    "get_stocktwits_limits",
    "scrape_telegram_simple",
    "scrape_telegram_paginated",
    "scrape_telegram_multi",
    "TELEGRAM_CHANNELS",
    "get_telegram_limits"
]
