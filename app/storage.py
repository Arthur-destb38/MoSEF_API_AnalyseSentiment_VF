"""
Storage for scraped posts - PostgreSQL cloud (Supabase) ou SQLite local (fallback).
Base de données partagée sur le cloud pour que tous les utilisateurs voient les mêmes données.
"""

import hashlib
import json
import os
import sqlite3
from datetime import datetime, date
from urllib.parse import urlparse, quote, unquote, unquote_plus


def _parse_created_utc_to_date(value) -> date | None:
    """Convertit created_utc (ISO ou timestamp) en date, ou None si invalide."""
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    try:
        if "-" in s:
            return datetime.fromisoformat(s.replace("Z", "+00:00")[:10]).date()
        return datetime.utcfromtimestamp(float(s)).date()
    except (ValueError, TypeError, OSError):
        return None

# Essayer PostgreSQL (cloud) d'abord, sinon SQLite (local)
USE_POSTGRES = False
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False

_BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.path.join(_BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "scraped_posts.db")
JSONL_PATH = os.path.join(DATA_DIR, "scraped_posts.jsonl")


def _get_postgres_conn():
    """Récupère la connexion PostgreSQL depuis DATABASE_URL (Supabase, Render, etc.)"""
    # Essayer d'abord les variables séparées (plus fiable)
    db_host = os.environ.get("DB_HOST") or os.environ.get("POSTGRES_HOST")
    db_user = os.environ.get("DB_USER") or os.environ.get("POSTGRES_USER") or "postgres"
    db_password = os.environ.get("DB_PASSWORD") or os.environ.get("POSTGRES_PASSWORD")
    db_name = os.environ.get("DB_NAME") or os.environ.get("POSTGRES_DB") or "postgres"
    db_port = os.environ.get("DB_PORT") or os.environ.get("POSTGRES_PORT") or "5432"
    
    if db_host and db_password:
        try:
            print("Connexion PostgreSQL via variables d'environnement...")
            conn = psycopg2.connect(
                host=db_host,
                port=int(db_port),
                database=db_name,
                user=db_user,
                password=db_password,
                sslmode="require"
            )
            print("Connexion PostgreSQL reussie !")
            return conn
        except ImportError:
            print("psycopg2 non installe. Installe avec: pip install psycopg2-binary")
            return None
        except Exception as e:
            print(f"Erreur connexion avec variables: {e}")
            # Continue pour essayer DATABASE_URL

    # Fallback: DATABASE_URL (depuis .env ou Streamlit Secrets)
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        # Essayer Streamlit Secrets (pour déploiement cloud)
        try:
            import streamlit as st
            database_url = st.secrets.get("DATABASE_URL")
        except Exception:
            pass

    if not database_url:
        print("Aucune config PostgreSQL trouvee - utilisation de SQLite local")
        return None

    # Enlever les guillemets si présents
    database_url = database_url.strip('"').strip("'")

    # Dans Streamlit Secrets, les $$ doivent être doublés ($$$$)
    if "$$$$" in database_url:
        database_url = database_url.replace("$$$$", "$$")
    # Si le mot de passe contient $ et que c'est écrit tel quel dans l'URL, encoder en %24
    if "@" in database_url and "://" in database_url:
        scheme, rest = database_url.split("://", 1)
        if "@" in rest:
            userinfo, host_part = rest.rsplit("@", 1)
            if ":" in userinfo:
                user, password = userinfo.split(":", 1)
                if "$" in password and "%24" not in password:
                    password = password.replace("$", "%24")
                    database_url = f"{scheme}://{user}:{password}@{host_part}"

    try:
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql://", 1)

        print("Tentative de connexion PostgreSQL via DATABASE_URL...")

        # Parser l'URL à la main pour gérer les mots de passe avec : ou @ (urlparse les casse)
        # Format: postgresql://user:password@host:port/dbname
        def _parse_db_url(url: str):
            if "://" not in url or "@" not in url:
                return None
            scheme, rest = url.split("://", 1)
            userinfo, host_part = rest.rsplit("@", 1)
            if ":" not in userinfo:
                return None
            user, password = userinfo.split(":", 1)
            password = unquote_plus(unquote(password))
            # host_part = "host:5432/postgres" ou "host:5432"
            if "/" in host_part:
                host_port, db = host_part.split("/", 1)
                db = (db.split("?")[0] or "postgres").strip()
            else:
                host_port, db = host_part, "postgres"
            if ":" in host_port:
                host, p = host_port.rsplit(":", 1)
                port = int(p) if p.isdigit() else 5432
            else:
                host, port = host_port, 5432
            return {"host": host, "port": port, "database": db or "postgres", "user": user, "password": password}

        # 1) Essayer l'URL brute (marche si le mot de passe n'a pas de caractères spéciaux)
        try:
            conn = psycopg2.connect(database_url, sslmode="require")
            print("Connexion PostgreSQL reussie !")
            return conn
        except Exception:
            pass

        # 2) Connexion avec parsing manuel (mot de passe avec @, :, #, etc.)
        parsed = _parse_db_url(database_url)
        if parsed:
            try:
                conn = psycopg2.connect(
                    host=parsed["host"],
                    port=parsed["port"],
                    database=parsed["database"],
                    user=parsed["user"],
                    password=parsed["password"],
                    sslmode="require"
                )
                print("Connexion PostgreSQL reussie !")
                return conn
            except Exception as e2:
                raise e2

        # 3) Fallback urlparse (pour URLs simples)
        parsed = urlparse(database_url)
        conn = psycopg2.connect(
            host=parsed.hostname,
            port=parsed.port or 5432,
            database=parsed.path.lstrip('/').split('?')[0] or 'postgres',
            user=parsed.username or 'postgres',
            password=unquote_plus(unquote(parsed.password or '')),
            sslmode="require"
        )
        print("Connexion PostgreSQL reussie !")
        return conn

    except ImportError:
        print("psycopg2 non installe. Installe avec: pip install psycopg2-binary")
        return None
    except Exception as e:
        err_str = str(e).lower()
        print(f"Erreur connexion PostgreSQL: {e}")
        if "password authentication failed" in err_str or "authentication failed" in err_str:
            print("   → Mot de passe refusé. Va sur Supabase : Project Settings → Database.")
            print("   → Copie à nouveau l’URL de connexion (URI) ou réinitialise le mot de passe.")
            print("   → Si le mot de passe contient # @ : / etc., encode-les dans l’URL (@ → %40, : → %3A, # → %23).")
        else:
            safe_url = database_url.split("@")[-1] if "@" in database_url else database_url[:50]
            print(f"   Host: {safe_url}")
        return None


def _ensure_postgres_storage():
    """Crée la table dans PostgreSQL si elle n'existe pas (utilise POSTGRES_TABLE)."""
    conn = _get_postgres_conn()
    if not conn:
        return None
    
    try:
        cur = conn.cursor()
        # Créer la même table que celle utilisée pour INSERT/SELECT (posts2 par défaut)
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {POSTGRES_TABLE} (
                uid VARCHAR(255) PRIMARY KEY,
                id TEXT,
                source TEXT,
                method TEXT,
                title TEXT,
                text TEXT,
                score INTEGER,
                created_utc TEXT,
                human_label TEXT,
                author TEXT,
                subreddit TEXT,
                url TEXT,
                num_comments INTEGER,
                scraped_at TIMESTAMP
            )
        """)
        conn.commit()
        return conn
    except Exception as e:
        print(f"Erreur création table PostgreSQL: {e}")
        conn.close()
        return None


def _ensure_sqlite_storage():
    """Fallback: SQLite local si PostgreSQL n'est pas disponible."""
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS posts (
            uid TEXT PRIMARY KEY,
            id TEXT,
            source TEXT,
            method TEXT,
            title TEXT,
            text TEXT,
            score INTEGER,
            created_utc TEXT,
            human_label TEXT,
            author TEXT,
            subreddit TEXT,
            url TEXT,
            num_comments INTEGER,
            scraped_at TEXT
        )
    """)
    return conn


# Forcer SQLite local (mettre à True pour utiliser SQLite au lieu de PostgreSQL)
FORCE_SQLITE = False

# Table Supabase/PostgreSQL à utiliser (créée automatiquement si elle n'existe pas)
POSTGRES_TABLE = "posts2"


def _get_supabase_rest_config() -> dict | None:
    """Si SUPABASE_URL + SUPABASE_SERVICE_KEY (ou anon) sont définis, retourne la config pour l'API REST."""
    url = (os.environ.get("SUPABASE_URL") or os.environ.get("SUPABASE_PROJECT_URL") or "").strip().rstrip("/")
    key = (
        os.environ.get("SUPABASE_SERVICE_KEY")
        or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        or os.environ.get("SUPABASE_SECRET_KEY")
        or os.environ.get("SUPABASE_ANON_KEY")
        or ""
    )
    try:
        import streamlit as st
        if not url:
            url = (st.secrets.get("SUPABASE_URL") or st.secrets.get("SUPABASE_PROJECT_URL") or "").strip().rstrip("/")
        if not key:
            key = (
                st.secrets.get("SUPABASE_SERVICE_KEY")
                or st.secrets.get("SUPABASE_SERVICE_ROLE_KEY")
                or st.secrets.get("SUPABASE_SECRET_KEY")
                or st.secrets.get("SUPABASE_ANON_KEY")
                or ""
            )
    except Exception:
        pass
    if url and key:
        return {"url": url, "key": key, "table": POSTGRES_TABLE}
    return None


def _get_connection():
    """Retourne une connexion PostgreSQL (cloud), Supabase REST, ou SQLite (local)."""
    if FORCE_SQLITE:
        return _ensure_sqlite_storage(), "sqlite"

    if POSTGRES_AVAILABLE:
        conn = _ensure_postgres_storage()
        if conn:
            return conn, "postgres"

    # Fallback : API REST Supabase (Project URL + clé API, pas besoin du mot de passe PostgreSQL)
    rest = _get_supabase_rest_config()
    if rest:
        print("Connexion via API REST Supabase (Project URL + clé API).")
        return rest, "supabase_rest"

    return _ensure_sqlite_storage(), "sqlite"


def _post_uid(post: dict, source: str, method: str) -> str:
    post_id = str(post.get("id") or "").strip()
    if post_id:
        base = f"{source}:{method}:{post_id}"
    else:
        base = f"{source}:{method}:{post.get('title', '')}:{post.get('created_utc', '')}"
    return hashlib.sha1(base.encode("utf-8")).hexdigest()


def _append_jsonl(post: dict) -> None:
    """Backup JSONL local (optionnel)."""
    try:
        with open(JSONL_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(post, ensure_ascii=True) + "\n")
    except Exception:
        pass  # Ignore si pas de permissions


def _save_posts_supabase_rest(posts: list, source: str | None, method: str | None, rest: dict) -> dict:
    """Sauvegarde via l'API REST Supabase (Project URL + clé). Doublons ignorés (upsert)."""
    import requests
    base = rest["url"]
    key = rest["key"]
    table = rest["table"]
    endpoint = f"{base}/rest/v1/{table}"
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=ignore-duplicates",
    }
    scraped_at = datetime.utcnow()
    inserted = 0
    for post in posts:
        p_source = source or post.get("source") or "unknown"
        p_method = method or post.get("method") or "unknown"
        uid = _post_uid(post, p_source, p_method)
        row = {
            "uid": uid,
            "id": str(post.get("id") or ""),
            "source": p_source,
            "method": p_method,
            "title": post.get("title", "") or "",
            "text": post.get("text", "") or "",
            "score": int(post.get("score") or 0),
            "created_utc": str(post.get("created_utc") or ""),
            "human_label": post.get("human_label"),
            "author": post.get("author"),
            "subreddit": post.get("subreddit"),
            "url": post.get("url"),
            "num_comments": int(post.get("num_comments")) if post.get("num_comments") is not None else None,
            "scraped_at": scraped_at.isoformat(),
        }
        try:
            r = requests.post(endpoint, json=row, headers=headers, timeout=15)
            if r.status_code in (200, 201, 204):
                inserted += 1
            elif r.status_code == 409:
                pass  # doublon ignoré
            elif r.status_code == 404:
                print("   Table posts2 introuvable. Crée-la dans Supabase (Table Editor ou SQL).")
                break
        except Exception as e:
            print(f"   Erreur API Supabase: {e}")
            break
    return {"inserted": inserted, "total": len(posts), "db_type": "supabase_rest"}


def save_posts(posts: list, source: str | None = None, method: str | None = None) -> dict:
    """
    Persist scraped posts to PostgreSQL (cloud), Supabase REST API, ou SQLite (local).
    Returns basic stats.
    """
    if not posts:
        db_type = "postgres" if POSTGRES_AVAILABLE and os.environ.get("DATABASE_URL") else "sqlite"
        return {"inserted": 0, "total": 0, "db_type": db_type}

    conn, db_type = _get_connection()
    if not conn:
        return {"inserted": 0, "total": 0, "db_type": "none", "error": "No database connection"}

    if db_type == "supabase_rest":
        return _save_posts_supabase_rest(posts, source, method, conn)

    cur = conn.cursor()
    inserted = 0
    scraped_at = datetime.utcnow()

    for post in posts:
        p_source = source or post.get("source") or "unknown"
        p_method = method or post.get("method") or "unknown"
        uid = _post_uid(post, p_source, p_method)

        row = (
            uid,
            str(post.get("id") or ""),
            p_source,
            p_method,
            post.get("title", ""),
            post.get("text", ""),
            int(post.get("score") or 0),
            str(post.get("created_utc") or ""),
            post.get("human_label"),
            post.get("author"),
            post.get("subreddit"),
            post.get("url"),
            int(post.get("num_comments")) if post.get("num_comments") is not None else None,
            scraped_at,
        )

        if db_type == "postgres":
            cur.execute(f"""
                INSERT INTO {POSTGRES_TABLE} (
                    uid, id, source, method, title, text, score, created_utc,
                    human_label, author, subreddit, url, num_comments, scraped_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (uid) DO NOTHING
            """, row)
        else:
            cur.execute("""
                INSERT OR IGNORE INTO posts (
                    uid, id, source, method, title, text, score, created_utc,
                    human_label, author, subreddit, url, num_comments, scraped_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, row)

        if cur.rowcount == 1:
            inserted += 1
            _append_jsonl({
                "uid": uid,
                "id": row[1],
                "source": row[2],
                "method": row[3],
                "title": row[4],
                "text": row[5],
                "score": row[6],
                "created_utc": row[7],
                "human_label": row[8],
                "author": row[9],
                "subreddit": row[10],
                "url": row[11],
                "num_comments": row[12],
                "scraped_at": row[13].isoformat() if hasattr(row[13], 'isoformat') else str(row[13]),
            })

    conn.commit()
    conn.close()

    return {"inserted": inserted, "total": len(posts), "db_type": db_type}


def _get_all_posts_supabase_rest(
    rest: dict,
    source: str | list[str] | None,
    method: str | None,
    limit: int | None,
    date_from: date | None,
    date_to: date | None,
) -> list[dict]:
    """Récupère les posts via l'API REST Supabase."""
    import requests
    endpoint = f"{rest['url']}/rest/v1/{rest['table']}"
    headers = {"apikey": rest["key"], "Authorization": f"Bearer {rest['key']}"}
    params = {"order": "scraped_at.desc", "limit": str(min((limit or 5000) * 2, 15000))}
    if source:
        if isinstance(source, list):
            params["source"] = "in.(" + ",".join(source) + ")"
        else:
            params["source"] = f"eq.{source}"
    if method:
        params["method"] = f"eq.{method}"
    try:
        r = requests.get(endpoint, headers=headers, params=params, timeout=30)
        if r.status_code != 200:
            return []
        posts = r.json()
    except Exception:
        return []
    if date_from is not None or date_to is not None:
        filtered = []
        for p in posts:
            d = _parse_created_utc_to_date(p.get("created_utc"))
            if d is None:
                continue
            if date_from is not None and d < date_from:
                continue
            if date_to is not None and d > date_to:
                continue
            filtered.append(p)
        posts = filtered[:limit] if limit else filtered
    return posts[:limit] if limit else posts


def get_all_posts(
    source: str | list[str] | None = None,
    method: str | None = None,
    limit: int | None = None,
    date_from: date | str | None = None,
    date_to: date | str | None = None,
) -> list[dict]:
    """Retrieve posts with optional filtering by source(s), method and publication date."""
    conn, db_type = _get_connection()
    if not conn:
        return []

    # Normaliser source : liste ou None
    sources = None
    if source is not None:
        if isinstance(source, list):
            sources = [s for s in source if s]
        else:
            sources = [source] if source else None

    # Normaliser les dates (str YYYY-MM-DD -> date)
    d_from = None
    d_to = None
    if date_from is not None:
        d_from = date_from if isinstance(date_from, date) else datetime.strptime(str(date_from)[:10], "%Y-%m-%d").date()
    if date_to is not None:
        d_to = date_to if isinstance(date_to, date) else datetime.strptime(str(date_to)[:10], "%Y-%m-%d").date()

    if db_type == "supabase_rest":
        return _get_all_posts_supabase_rest(conn, sources, method, limit, d_from, d_to)

    # Quand on filtre par date, on récupère plus de lignes puis on filtre en Python
    fetch_limit = limit
    if (d_from is not None or d_to is not None) and (limit is None or limit > 0):
        fetch_limit = (limit or 5000) * 3
        fetch_limit = min(fetch_limit, 15000)

    cur = conn.cursor()

    if db_type == "postgres":
        query = f"SELECT * FROM {POSTGRES_TABLE} WHERE 1=1"
        params = []
        if sources:
            query += " AND source IN %s"
            params.append(tuple(sources))
        if method:
            query += " AND method = %s"
            params.append(method)
        query += " ORDER BY scraped_at DESC"
        if fetch_limit:
            query += f" LIMIT {fetch_limit}"
        cur.execute(query, params)
        columns = [desc[0] for desc in cur.description]
        posts = [dict(zip(columns, row)) for row in cur.fetchall()]
    else:
        query = "SELECT * FROM posts WHERE 1=1"
        params = []
        if sources:
            placeholders = ",".join("?" * len(sources))
            query += f" AND source IN ({placeholders})"
            params.extend(sources)
        if method:
            query += " AND method = ?"
            params.append(method)
        query += " ORDER BY scraped_at DESC"
        if fetch_limit:
            query += f" LIMIT {fetch_limit}"
        cur.execute(query, params)
        columns = [desc[0] for desc in cur.description]
        posts = [dict(zip(columns, row)) for row in cur.fetchall()]

    conn.close()

    if d_from is not None or d_to is not None:
        filtered = []
        for p in posts:
            d = _parse_created_utc_to_date(p.get("created_utc"))
            if d is None:
                continue
            if d_from is not None and d < d_from:
                continue
            if d_to is not None and d > d_to:
                continue
            filtered.append(p)
        posts = filtered[:limit] if limit else filtered

    return posts


def export_to_csv(filename: str | None = None, source: str | None = None, method: str | None = None) -> str:
    """Export posts to CSV file."""
    import csv
    
    posts = get_all_posts(source=source, method=method)
    
    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        suffix = f"_{source}" if source else ""
        suffix += f"_{method}" if method else ""
        filename = f"scrapes{suffix}_{timestamp}.csv"
    
    export_path = os.path.join(DATA_DIR, "exports", filename)
    os.makedirs(os.path.dirname(export_path), exist_ok=True)
    
    if not posts:
        return export_path
    
    with open(export_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=posts[0].keys())
        writer.writeheader()
        writer.writerows(posts)
    
    return export_path


def export_to_json(filename: str | None = None, source: str | None = None, method: str | None = None) -> str:
    """Export posts to JSON file."""
    posts = get_all_posts(source=source, method=method)
    
    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        suffix = f"_{source}" if source else ""
        suffix += f"_{method}" if method else ""
        filename = f"scrapes{suffix}_{timestamp}.json"
    
    export_path = os.path.join(DATA_DIR, "exports", filename)
    os.makedirs(os.path.dirname(export_path), exist_ok=True)
    
    with open(export_path, "w", encoding="utf-8") as f:
        json.dump(posts, f, indent=2, ensure_ascii=False)
    
    return export_path


def get_stats() -> dict:
    """Get statistics about stored posts."""
    conn, db_type = _get_connection()
    if not conn:
        return {"total_posts": 0, "db_type": "none"}

    if db_type == "supabase_rest":
        import requests
        endpoint = f"{conn['url']}/rest/v1/{conn['table']}"
        headers = {"apikey": conn["key"], "Authorization": f"Bearer {conn['key']}"}
        try:
            r = requests.get(endpoint, headers=headers, params={"limit": "10000"}, timeout=30)
            if r.status_code != 200:
                return {"total_posts": 0, "by_source_method": [], "first_scrape": None, "last_scrape": None, "db_type": "supabase_rest"}
            posts = r.json()
        except Exception:
            return {"total_posts": 0, "by_source_method": [], "first_scrape": None, "last_scrape": None, "db_type": "supabase_rest"}
        by_sm = {}
        for p in posts:
            s, m = p.get("source") or "?", p.get("method") or "?"
            by_sm[(s, m)] = by_sm.get((s, m), 0) + 1
        scraped = [p.get("scraped_at") for p in posts if p.get("scraped_at")]
        return {
            "total_posts": len(posts),
            "by_source_method": [{"source": s, "method": m, "count": c} for (s, m), c in by_sm.items()],
            "first_scrape": min(scraped) if scraped else None,
            "last_scrape": max(scraped) if scraped else None,
            "db_type": "supabase_rest",
        }

    cur = conn.cursor()

    if db_type == "postgres":
        cur.execute(f"SELECT COUNT(*) FROM {POSTGRES_TABLE}")
        total = cur.fetchone()[0]
        
        cur.execute(f"SELECT source, method, COUNT(*) as count FROM {POSTGRES_TABLE} GROUP BY source, method")
        by_source_method = [{"source": row[0], "method": row[1], "count": row[2]} for row in cur.fetchall()]
        
        cur.execute(f"SELECT MIN(scraped_at), MAX(scraped_at) FROM {POSTGRES_TABLE}")
        dates = cur.fetchone()
    else:
        cur.execute("SELECT COUNT(*) FROM posts")
        total = cur.fetchone()[0]
        
        cur.execute("SELECT source, method, COUNT(*) as count FROM posts GROUP BY source, method")
        by_source_method = [{"source": row[0], "method": row[1], "count": row[2]} for row in cur.fetchall()]
        
        cur.execute("SELECT MIN(scraped_at), MAX(scraped_at) FROM posts")
        dates = cur.fetchone()
    
    conn.close()
    
    return {
        "total_posts": total,
        "by_source_method": by_source_method,
        "first_scrape": str(dates[0]) if dates[0] else None,
        "last_scrape": str(dates[1]) if dates[1] else None,
        "db_type": db_type
    }
