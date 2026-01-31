"""
Instagram Scraper - Instaloader (recommandé) + Selenium (fallback)

Instaloader est la méthode la plus fiable pour scraper Instagram.
Nécessite souvent un login pour éviter les rate limits.
"""

import time
from datetime import datetime
from typing import Optional

# Essayer Instaloader d'abord
INSTALOADER_OK = False
try:
    import instaloader
    INSTALOADER_OK = True
except ImportError:
    INSTALOADER_OK = False

# Fallback Selenium
SELENIUM_OK = False
try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from bs4 import BeautifulSoup
    SELENIUM_OK = True
except ImportError:
    SELENIUM_OK = False

LIMITS = {
    "instaloader": 100,  # Limite recommandée pour éviter ban
    "selenium": 50       # Plus restrictif avec Selenium
}


def get_limits():
    """Retourne les limites par méthode"""
    return LIMITS


def scrape_instagram_hashtag(hashtag: str, limit: int = 50, username: str = None, password: str = None) -> list:
    """
    Scrape Instagram via hashtag (ex: #bitcoin, #crypto)
    
    Args:
        hashtag: Hashtag à scraper (sans le #)
        limit: Nombre de posts souhaités
        username: Username Instagram (optionnel, recommandé pour éviter rate limits)
        password: Password Instagram (optionnel)
    
    Returns:
        Liste de posts Instagram
    """
    if INSTALOADER_OK:
        return scrape_instagram_instaloader(hashtag, limit, username, password)
    elif SELENIUM_OK:
        return scrape_instagram_selenium(hashtag, limit)
    else:
        print("Instaloader et Selenium non disponibles. Installe avec: pip install instaloader")
        return []


def scrape_instagram_instaloader(hashtag: str, limit: int, username: str = None, password: str = None) -> list:
    """
    Scrape Instagram avec Instaloader (méthode recommandée)
    """
    posts = []

    try:
        # Créer l'instance Instaloader avec session
        L = instaloader.Instaloader(
            download_pictures=False,
            download_videos=False,
            download_video_thumbnails=False,
            download_geotags=False,
            download_comments=False,
            save_metadata=False,
            compress_json=False,
            max_connection_attempts=3
        )

        # Login si credentials fournis (OBLIGATOIRE depuis 2024)
        if username and password:
            try:
                print(f"Instagram: Connexion avec {username}...")
                # Essayer de charger une session existante d'abord
                try:
                    L.load_session_from_file(username)
                    print("Instagram: Session existante chargee!")
                except FileNotFoundError:
                    # Pas de session, faire un login
                    L.login(username, password)
                    # Sauvegarder la session pour la prochaine fois
                    L.save_session_to_file()
                    print("Instagram: Connexion reussie et session sauvegardee!")
            except instaloader.exceptions.TwoFactorAuthRequiredException:
                print("Instagram: 2FA active - entrez le code dans le terminal")
                code = input("Code 2FA: ")
                try:
                    L.two_factor_login(code)
                    L.save_session_to_file()
                    print("Instagram: Connexion 2FA reussie!")
                except Exception as e2:
                    print(f"Instagram: Echec 2FA: {e2}")
                    return []
            except instaloader.exceptions.BadCredentialsException:
                print("Instagram: Identifiants incorrects")
                return []
            except instaloader.exceptions.ConnectionException as e:
                print(f"Instagram: Erreur de connexion: {e}")
                print("   Vérifiez votre connexion internet")
                return []
            except Exception as e:
                print(f"Instagram: Echec login: {e}")
                print("   Causes possibles:")
                print("   - Compte bloqué temporairement")
                print("   - 2FA activé (non géré automatiquement)")
                print("   - Instagram détecte l'automatisation")
                print("   - Identifiants incorrects")
                return []
        else:
            print("Instagram: Pas de login fourni")
            print("   Instagram exige maintenant un login pour scraper les hashtags")
            print("   Ajoute INSTAGRAM_USERNAME et INSTAGRAM_PASSWORD dans .env")
            return []

        # Vérifier que la session est active en testant le profil
        try:
            test_profile = instaloader.Profile.from_username(L.context, username)
            print(f"Instagram: Session active verifiee (@{test_profile.username}, {test_profile.followers} followers)")
        except Exception as e:
            print(f"Instagram: Session peut-etre invalide: {e}")
            # Réessayer le login
            try:
                print("Instagram: Nouvelle tentative de login...")
                L.login(username, password)
                L.save_session_to_file()
                print("Instagram: Re-login reussi!")
            except Exception as e2:
                print(f"Instagram: Re-login echoue: {e2}")
                return []

        # Scraper le hashtag - utiliser le contexte avec session
        print(f"Instagram: Scraping #{hashtag}...")
        try:
            # Essayer d'abord avec le contexte de session
            hashtag_obj = instaloader.Hashtag.from_name(L.context, hashtag)
        except Exception as e:
            print(f"Erreur acces hashtag: {e}")
            print("   Instagram peut bloquer l'accès aux hashtags même avec login")
            print("   Tentative alternative: scraper via profil...")
            return []

        count = 0
        for post in hashtag_obj.get_posts():
            if count >= limit:
                break

            try:
                # Récupérer les infos du post
                caption = post.caption or ""
                likes = post.likes
                comments = post.comments
                timestamp = post.date_utc
                owner = post.owner_username
                shortcode = post.shortcode
                url = f"https://www.instagram.com/p/{shortcode}/"

                posts.append({
                    "id": shortcode,
                    "title": caption[:500] if caption else "",
                    "text": "",
                    "score": likes + comments,
                    "likes": likes,
                    "retweets": comments,  # Compatibilité avec format Twitter
                    "username": owner,
                    "created_utc": timestamp.isoformat() if timestamp else None,
                    "source": "instagram",
                    "method": "instaloader",
                    "url": url,
                    "human_label": None
                })

                count += 1
                if count % 10 == 0:
                    print(f"  {count}/{limit} posts récupérés...")

                # Délai pour éviter rate limit
                time.sleep(1)

            except Exception as e:
                print(f"  Erreur sur post {count}: {e}")
                continue

        print(f"Instagram: {len(posts)} posts recuperes avec Instaloader")

    except Exception as e:
        print(f"Erreur Instaloader: {e}")
        # Fallback Selenium si disponible
        if SELENIUM_OK:
            print("Instagram: Fallback vers Selenium...")
            return scrape_instagram_selenium(hashtag, limit)

    return posts


def scrape_instagram_selenium(hashtag: str, limit: int) -> list:
    """
    Scrape Instagram avec Selenium (fallback, moins fiable)
    """
    posts = []

    if not SELENIUM_OK:
        return []

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    try:
        driver = webdriver.Chrome(options=options)
        url = f"https://www.instagram.com/explore/tags/{hashtag}/"

        print(f"Instagram: Accès à {url}...")
        driver.get(url)
        time.sleep(5)

        # Scroller pour charger les posts
        for i in range(min(limit // 9, 5)):  # ~9 posts par scroll
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)

        # Parser les posts
        soup = BeautifulSoup(driver.page_source, "lxml")

        # Selecteurs Instagram (peuvent changer)
        post_links = soup.select("a[href*='/p/']")
        seen_ids = set()

        for link in post_links[:limit * 2]:
            href = link.get("href", "")
            if "/p/" in href and href not in seen_ids:
                seen_ids.add(href)
                shortcode = href.split("/p/")[-1].rstrip("/")

                posts.append({
                    "id": shortcode,
                    "title": "",
                    "text": "",
                    "score": 0,
                    "likes": 0,
                    "retweets": 0,
                    "username": "",
                    "created_utc": None,
                    "source": "instagram",
                    "method": "selenium",
                    "url": f"https://www.instagram.com{href}",
                    "human_label": None
                })

                if len(posts) >= limit:
                    break

        driver.quit()
        print(f"Instagram: {len(posts)} posts recuperes avec Selenium")

    except Exception as e:
        print(f"Erreur Selenium Instagram: {e}")

    return posts


def scrape_instagram_profile(username: str, limit: int = 50, insta_username: str = None, insta_password: str = None) -> list:
    """
    Scrape un profil Instagram spécifique
    """
    if INSTALOADER_OK:
        return scrape_profile_instaloader(username, limit, insta_username, insta_password)
    else:
        print("Instaloader requis pour scraper des profils")
        return []


def scrape_profile_instaloader(username: str, limit: int, insta_username: str = None, insta_password: str = None) -> list:
    """Scrape un profil Instagram avec Instaloader"""
    posts = []

    try:
        L = instaloader.Instaloader(
            download_pictures=False,
            download_videos=False,
            download_video_thumbnails=False,
            download_geotags=False,
            download_comments=False,
            save_metadata=False
        )

        if insta_username and insta_password:
            try:
                L.login(insta_username, insta_password)
            except:
                pass

        print(f"Instagram: Scraping profil @{username}...")
        profile = instaloader.Profile.from_username(L.context, username)

        count = 0
        for post in profile.get_posts():
            if count >= limit:
                break

            caption = post.caption or ""
            posts.append({
                "id": post.shortcode,
                "title": caption[:500],
                "text": "",
                "score": post.likes + post.comments,
                "likes": post.likes,
                "retweets": post.comments,
                "username": username,
                "created_utc": post.date_utc.isoformat() if post.date_utc else None,
                "source": "instagram",
                "method": "instaloader",
                "url": f"https://www.instagram.com/p/{post.shortcode}/",
                "human_label": None
            })

            count += 1
            time.sleep(0.5)

        print(f"Instagram: {len(posts)} posts du profil @{username}")

    except Exception as e:
        print(f"Erreur scraping profil: {e}")
    
    return posts
