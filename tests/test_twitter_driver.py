"""
Tests du driver Chrome pour le scraper Twitter.
Lance: python -m pytest tests/test_twitter_driver.py -v
Ou: .venv/bin/python tests/test_twitter_driver.py
"""
import os
import sys

# Charger .env
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()


def test_imports():
    """Vérifie que les modules Twitter scraper sont importables."""
    from app.scrapers.twitter_scraper import setup_driver, UC_OK, SELENIUM_OK
    assert UC_OK or SELENIUM_OK, "Au moins Selenium ou undetected_chromedriver doit être disponible"


def test_setup_driver_creates_and_quits():
    """Vérifie que setup_driver() crée un driver utilisable (ouvre about:blank et ferme)."""
    from app.scrapers.twitter_scraper import setup_driver
    driver = setup_driver()
    assert driver is not None, "setup_driver() doit retourner un driver"
    try:
        driver.get("about:blank")
        assert "about" in driver.current_url or driver.current_url == "about:blank"
    finally:
        driver.quit()


if __name__ == "__main__":
    test_imports()
    print("Test imports: OK")
    test_setup_driver_creates_and_quits()
    print("Test driver: OK")
    print("Tous les tests sont passés.")
