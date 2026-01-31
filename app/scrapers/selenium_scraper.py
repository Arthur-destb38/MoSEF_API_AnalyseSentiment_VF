"""
Scraper Reddit avec Selenium (methode cours)
Simule un comportement humain
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import NoSuchElementException
from bs4 import BeautifulSoup
import time
import random
from datetime import datetime, timedelta
import re


class SeleniumScraper:

    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/120.0.0.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Firefox/121.0",
    ]

    def __init__(self, headless: bool = True):
        self.headless = headless
        self.driver = None
        self.demo_mode = False

    def _setup_driver(self):
        options = Options()

        if self.headless:
            options.add_argument("--headless=new")

        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument(f"--user-agent={random.choice(self.USER_AGENTS)}")
        options.add_argument("--window-size=1920,1080")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])

        try:
            self.driver = webdriver.Chrome(options=options)
            self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            })
        except Exception as e:
            print(f"Selenium pas dispo: {e}")
            self.demo_mode = True

    def _random_delay(self, min_s=1.0, max_s=3.0):
        time.sleep(random.uniform(min_s, max_s))

    def _scroll(self, times=2):
        for _ in range(times):
            px = random.randint(300, 600)
            self.driver.execute_script(f"window.scrollBy(0, {px});")
            self._random_delay(0.5, 1.0)

    def _parse_post(self, elem) -> dict:
        try:
            title_el = elem.select_one("a.title")
            title = title_el.get_text(strip=True) if title_el else ""

            score_el = elem.select_one("div.score.unvoted")
            score_txt = score_el.get_text(strip=True) if score_el else "0"
            try:
                score = int(score_txt) if score_txt != "•" else 0
            except:
                score = 0

            comments_el = elem.select_one("a.comments")
            comments_txt = comments_el.get_text(strip=True) if comments_el else "0"
            match = re.search(r"(\d+)", comments_txt)
            num_comments = int(match.group(1)) if match else 0

            time_el = elem.select_one("time")
            timestamp = time_el.get("datetime", "") if time_el else ""

            author_el = elem.select_one("a.author")
            author = author_el.get_text(strip=True) if author_el else "[deleted]"

            url = title_el.get("href", "") if title_el else ""
            if url.startswith("/"):
                url = f"https://reddit.com{url}"

            return {
                "id": elem.get("data-fullname", ""),
                "title": title,
                "text": "",
                "score": score,
                "num_comments": num_comments,
                "created_utc": timestamp,
                "author": author,
                "url": url
            }
        except:
            return None

    def scrape_subreddit(self, subreddit: str, crypto: str = "", limit: int = 50) -> list[dict]:
        if self.driver is None and not self.demo_mode:
            self._setup_driver()

        if self.demo_mode:
            return self._demo_posts(crypto or subreddit, limit)

        posts = []
        url = f"https://old.reddit.com/r/{subreddit}/new/"

        try:
            self.driver.get(url)
            self._random_delay(2, 4)

            pages = 0
            max_pages = (limit // 25) + 2

            while len(posts) < limit and pages < max_pages:
                self._scroll(2)

                soup = BeautifulSoup(self.driver.page_source, "lxml")
                elements = soup.select("div.thing.link")

                for elem in elements:
                    if "stickied" in elem.get("class", []):
                        continue
                    if "promoted" in elem.get("class", []):
                        continue

                    post = self._parse_post(elem)
                    if post and post["title"]:
                        posts.append(post)

                    if len(posts) >= limit:
                        break

                try:
                    next_btn = self.driver.find_element(By.CSS_SELECTOR, "span.next-button a")
                    next_btn.click()
                    self._random_delay(2, 3)
                    pages += 1
                except NoSuchElementException:
                    break

            return posts[:limit]

        except Exception as e:
            print(f"Erreur scraping: {e}")
            return self._demo_posts(crypto or subreddit, limit)

    def _demo_posts(self, crypto: str, limit: int) -> list[dict]:
        templates = [
            f"{crypto} looking strong today",
            f"Just bought more {crypto}",
            f"What do you think about {crypto}?",
            f"{crypto} to the moon",
            f"Sold my {crypto}, bad decision?",
            f"{crypto} price prediction",
            f"Why {crypto} will fail",
            f"{crypto} adoption growing",
        ]

        posts = []
        base_date = datetime.now()

        for i in range(limit):
            posts.append({
                "id": f"demo_{i}",
                "title": random.choice(templates),
                "text": "",
                "score": random.randint(1, 500),
                "num_comments": random.randint(0, 100),
                "created_utc": (base_date - timedelta(hours=i*2)).isoformat(),
                "author": f"user_{random.randint(1, 100)}",
                "url": f"https://reddit.com/r/{crypto}/demo_{i}"
            })

        return posts

    def close(self):
        if self.driver:
            self.driver.quit()
            self.driver = None