#!/usr/bin/env python3
"""
Vérifie que la table posts2 sur Supabase contient des posts (API REST).
Usage : python scripts/verify_supabase_posts.py
"""

import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

def main():
    url = (os.environ.get("SUPABASE_URL") or os.environ.get("SUPABASE_PROJECT_URL") or "").strip().rstrip("/")
    key = (
        os.environ.get("SUPABASE_SERVICE_KEY")
        or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        or os.environ.get("SUPABASE_SECRET_KEY")
        or os.environ.get("SUPABASE_ANON_KEY")
        or ""
    )
    if not url or not key:
        print("SUPABASE_URL et SUPABASE_SERVICE_KEY (ou SUPABASE_SECRET_KEY) doivent être dans le .env")
        return
    import requests
    endpoint = f"{url}/rest/v1/posts2"
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}
    try:
        r = requests.get(endpoint, headers=headers, params={"order": "scraped_at.desc", "limit": "5"}, timeout=15)
        if r.status_code == 404:
            print("La table posts2 n'existe pas sur Supabase. Crée-la (Table Editor ou SQL).")
            return
        if r.status_code != 200:
            print(f"Erreur API: {r.status_code} - {r.text[:200]}")
            return
        posts = r.json()
        total_r = r.headers.get("Content-Range")
        if total_r and "/" in total_r:
            total = total_r.split("/")[-1]
            print(f"Total posts dans posts2 (Supabase) : {total}")
        else:
            print(f"Posts récupérés : {len(posts)} (ajoute Prefer: count=exact pour le total)")
        if posts:
            print("\nDerniers posts (max 5) :")
            for i, p in enumerate(posts[:5], 1):
                print(f"  {i}. [{p.get('source')}] {p.get('title', p.get('text', ''))[:60]}...")
        else:
            print("Aucun post dans la table pour l’instant. Lance un scrape (test_scrape_5.sh ou scrape_reddit_200.sh).")
    except Exception as e:
        print(f"Erreur : {e}")

if __name__ == "__main__":
    main()
