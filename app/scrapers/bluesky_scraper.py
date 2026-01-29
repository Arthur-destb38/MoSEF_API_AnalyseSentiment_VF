"""
Bluesky Scraper - Recherche de posts crypto via l'API AT Protocol.
Avec compte : login via atproto SDK (recommandé, évite le 403).
Sans compte : tentative API publique (souvent 403).

Pour utiliser un compte Bluesky :
1. Crée un compte sur bsky.app
2. Paramètres > App passwords : crée un mot de passe d'app
3. Dans .env : BLUESKY_USERNAME=tonhandle.bsky.social et BLUESKY_APP_PASSWORD=xxxx-xxxx-xxxx
4. Installe atproto si besoin : pip install atproto (Python <3.15)
"""

import os
import time
from typing import List, Dict

import requests

BLUESKY_API = "https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts"
LIMITS = {"api": 200}


def get_bluesky_limits() -> Dict[str, int]:
    return LIMITS


get_limits = get_bluesky_limits


def _post_view_to_dict(p, limit: int) -> Dict:
    """Convertit un PostView atproto en dict commun au dashboard."""
    uri = getattr(p, "uri", None) or (p.get("uri") if isinstance(p, dict) else "")
    author = getattr(p, "author", None) or (p.get("author") if isinstance(p, dict) else {})
    record = getattr(p, "record", None) or (p.get("record") if isinstance(p, dict) else {})

    if isinstance(author, dict):
        handle = author.get("handle") or author.get("did") or "unknown"
    else:
        handle = getattr(author, "handle", None) or getattr(author, "did", None) or "unknown"

    if hasattr(record, "text"):
        text = record.text or ""
    else:
        text = (record.get("text") if isinstance(record, dict) else "") or ""

    if not text:
        return None

    post_id = uri.split("/")[-1] if uri and "/" in uri else (uri or "")
    created = ""
    if hasattr(record, "created_at"):
        created = str(record.created_at) if record.created_at else ""
    elif isinstance(record, dict) and record.get("createdAt"):
        created = record["createdAt"]
    else:
        created = getattr(p, "indexed_at", None) or (p.get("indexedAt") if isinstance(p, dict) else "") or ""

    like_count = getattr(p, "like_count", None) or (p.get("likeCount") if isinstance(p, dict) else 0) or 0
    reply_count = getattr(p, "reply_count", None) or (p.get("replyCount") if isinstance(p, dict) else 0) or 0

    return {
        "id": post_id,
        "title": text[:300],
        "text": text[:5000],
        "score": like_count + reply_count,
        "author": handle,
        "created_utc": created,
        "source": "bluesky",
        "method": "api",
        "url": f"https://bsky.app/profile/{handle}/post/{post_id}" if post_id else "",
        "human_label": None,
    }


def scrape_bluesky_with_login(query: str, limit: int, username: str, password: str) -> List[Dict]:
    """Recherche avec compte Bluesky (atproto SDK)."""
    try:
        from atproto import Client
    except ImportError:
        print("Bluesky: pour utiliser un compte, installe 'atproto': pip install atproto (ou poetry add atproto, Python <3.15 requis).")
        return []

    posts = []
    seen_uris = set()
    cursor = None
    per_request = min(100, limit)

    try:
        client = Client()
        client.login(username, password)
        print(f"Bluesky: recherche '{query}' (compte connecté)...")

        while len(posts) < limit:
            params = {"q": query, "limit": per_request, "sort": "latest"}
            if cursor:
                params["cursor"] = cursor

            resp = client.app.bsky.feed.search_posts(params=params)
            items = getattr(resp, "posts", None) or []
            if not items and hasattr(resp, "posts"):
                items = list(resp.posts) if resp.posts else []

            for p in items:
                uri = getattr(p, "uri", None) or (p.get("uri") if isinstance(p, dict) else "")
                if uri in seen_uris:
                    continue
                seen_uris.add(uri)
                row = _post_view_to_dict(p, limit)
                if row:
                    posts.append(row)
                if len(posts) >= limit:
                    break

            cursor = getattr(resp, "cursor", None) or (resp.get("cursor") if isinstance(resp, dict) else None)
            if not cursor or not items:
                break
            time.sleep(0.3)

        print(f"Bluesky: {len(posts)} posts récupérés (auth)")
    except Exception as e:
        print(f"Bluesky (auth) erreur: {e}")
        if "LoginFailed" in str(type(e).__name__) or "Invalid" in str(e):
            print("Vérifie BLUESKY_USERNAME et BLUESKY_APP_PASSWORD dans .env (mot de passe d'app depuis Paramètres Bluesky).")

    return posts[:limit]


def scrape_bluesky(query: str = "bitcoin", limit: int = 50) -> List[Dict]:
    """
    Recherche de posts Bluesky par mot-clé (crypto).
    Si BLUESKY_USERNAME et BLUESKY_APP_PASSWORD sont définis dans .env, utilise le login (recommandé).
    Sinon tente l'API publique (souvent 403).
    """
    username = os.environ.get("BLUESKY_USERNAME", "").strip()
    password = os.environ.get("BLUESKY_APP_PASSWORD") or os.environ.get("BLUESKY_PASSWORD", "").strip()

    if username and password:
        return scrape_bluesky_with_login(query, limit, username, password)

    # Fallback: API publique sans auth (souvent 403)
    posts = []
    seen_uris = set()
    cursor = None
    per_request = min(100, limit)

    try:
        print(f"Bluesky: recherche '{query}' (sans compte, peut renvoyer 403)...")

        while len(posts) < limit:
            params = {"q": query, "limit": per_request, "sort": "latest"}
            if cursor:
                params["cursor"] = cursor

            resp = requests.get(
                BLUESKY_API,
                params=params,
                headers={
                    "Accept": "application/json",
                    "User-Agent": "Crypto-Sentiment/1.0 (Bluesky search)",
                },
                timeout=15,
            )

            if resp.status_code in (401, 403):
                print("Bluesky: accès refusé (403/401). Ajoute BLUESKY_USERNAME et BLUESKY_APP_PASSWORD dans .env pour utiliser un compte.")
                break
            resp.raise_for_status()

            data = resp.json()
            items = data.get("posts") or []

            for p in items:
                uri = p.get("uri") or ""
                if uri in seen_uris:
                    continue
                seen_uris.add(uri)
                row = _post_view_to_dict(p, limit)
                if row:
                    posts.append(row)
                if len(posts) >= limit:
                    break

            cursor = data.get("cursor")
            if not cursor or not items:
                break
            time.sleep(0.3)

        print(f"Bluesky: {len(posts)} posts récupérés")
    except requests.RequestException as e:
        print(f"Bluesky erreur réseau: {e}")
    except Exception as e:
        print(f"Bluesky erreur: {e}")

    return posts[:limit]
