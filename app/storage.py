"""
Storage for scraped posts - PostgreSQL cloud (Supabase) ou SQLite local (fallback).
Base de données partagée sur le cloud pour que tous les utilisateurs voient les mêmes données.
"""

import hashlib
import json
import os
import sqlite3
from datetime import datetime
from urllib.parse import urlparse, quote, unquote

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
            print(f"🔌 Connexion PostgreSQL via variables d'environnement...")
            conn = psycopg2.connect(
                host=db_host,
                port=int(db_port),
                database=db_name,
                user=db_user,
                password=db_password,
                sslmode="require"
            )
            print("✅ Connexion PostgreSQL réussie !")
            return conn
        except ImportError:
            print("❌ psycopg2 non installé. Installe avec: pip install psycopg2-binary")
            return None
        except Exception as e:
            print(f"⚠️  Erreur connexion avec variables: {e}")
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
        print("⚠️  Aucune config PostgreSQL trouvée - utilisation de SQLite local")
        return None
    
    # Enlever les guillemets si présents
    database_url = database_url.strip('"').strip("'")
    
    # Dans Streamlit Secrets, les $$ doivent être doublés ($$$$)
    # On les convertit en $$ pour l'URL
    if "$$$$" in database_url:
        database_url = database_url.replace("$$$$", "$$")
    
    try:
        # Si l'URL commence par postgres://, convertir en postgresql://
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql://", 1)
        
        print(f"🔌 Tentative de connexion PostgreSQL via DATABASE_URL...")
        
        # Essayer avec l'URL telle quelle d'abord
        try:
            conn = psycopg2.connect(database_url, sslmode="require")
            print("✅ Connexion PostgreSQL réussie !")
            return conn
        except Exception:
            # Si ça échoue, essayer de parser et utiliser paramètres séparés
            parsed = urlparse(database_url)
            conn = psycopg2.connect(
                host=parsed.hostname,
                port=parsed.port or 5432,
                database=parsed.path.lstrip('/') or 'postgres',
                user=parsed.username or 'postgres',
                password=parsed.password or '',
                sslmode="require"
            )
            print("✅ Connexion PostgreSQL réussie (via paramètres) !")
            return conn
            
    except ImportError:
        print("❌ psycopg2 non installé. Installe avec: pip install psycopg2-binary")
        return None
    except Exception as e:
        print(f"❌ Erreur connexion PostgreSQL: {e}")
        safe_url = database_url.split("@")[-1] if "@" in database_url else database_url[:50]
        print(f"   Host: {safe_url}")
        print(f"   Vérifie: 1) Le mot de passe est correct 2) Le projet Supabase est actif")
        return None


def _ensure_postgres_storage():
    """Crée la table dans PostgreSQL si elle n'existe pas."""
    conn = _get_postgres_conn()
    if not conn:
        return None
    
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS posts (
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


def _get_connection():
    """Retourne une connexion PostgreSQL (cloud) ou SQLite (local)."""
    # Essayer PostgreSQL d'abord
    if POSTGRES_AVAILABLE:
        conn = _ensure_postgres_storage()
        if conn:
            return conn, "postgres"
    
    # Fallback SQLite
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


def save_posts(posts: list, source: str | None = None, method: str | None = None) -> dict:
    """
    Persist scraped posts to PostgreSQL (cloud) ou SQLite (local).
    Returns basic stats.
    """
    if not posts:
        db_type = "postgres" if POSTGRES_AVAILABLE and os.environ.get("DATABASE_URL") else "sqlite"
        return {"inserted": 0, "total": 0, "db_type": db_type}

    conn, db_type = _get_connection()
    if not conn:
        return {"inserted": 0, "total": 0, "db_type": "none", "error": "No database connection"}

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
            cur.execute("""
                INSERT INTO posts (
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


def get_all_posts(source: str | None = None, method: str | None = None, limit: int | None = None) -> list[dict]:
    """Retrieve all posts from the database with optional filtering."""
    conn, db_type = _get_connection()
    if not conn:
        return []
    
    cur = conn.cursor()
    
    if db_type == "postgres":
        query = "SELECT * FROM posts WHERE 1=1"
        params = []
        
        if source:
            query += " AND source = %s"
            params.append(source)
        
        if method:
            query += " AND method = %s"
            params.append(method)
        
        query += " ORDER BY scraped_at DESC"
        
        if limit:
            query += f" LIMIT {limit}"
        
        cur.execute(query, params)
        columns = [desc[0] for desc in cur.description]
        posts = [dict(zip(columns, row)) for row in cur.fetchall()]
    else:
        query = "SELECT * FROM posts WHERE 1=1"
        params = []
        
        if source:
            query += " AND source = ?"
            params.append(source)
        
        if method:
            query += " AND method = ?"
            params.append(method)
        
        query += " ORDER BY scraped_at DESC"
        
        if limit:
            query += f" LIMIT {limit}"
        
        cur.execute(query, params)
        columns = [desc[0] for desc in cur.description]
        posts = [dict(zip(columns, row)) for row in cur.fetchall()]
    
    conn.close()
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
    
    cur = conn.cursor()
    
    if db_type == "postgres":
        cur.execute("SELECT COUNT(*) FROM posts")
        total = cur.fetchone()[0]
        
        cur.execute("SELECT source, method, COUNT(*) as count FROM posts GROUP BY source, method")
        by_source_method = [{"source": row[0], "method": row[1], "count": row[2]} for row in cur.fetchall()]
        
        cur.execute("SELECT MIN(scraped_at), MAX(scraped_at) FROM posts")
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
