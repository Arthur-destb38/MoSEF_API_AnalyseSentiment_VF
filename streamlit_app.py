"""
Crypto Sentiment Dashboard
Projet MoSEF 2024-2025
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date, timedelta
import sys
import os
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.scrapers import scrape_reddit, scrape_stocktwits, scrape_twitter, get_reddit_limits, get_stocktwits_limits, get_twitter_limits
from app.scrapers import scrape_telegram_simple, scrape_telegram_paginated, TELEGRAM_CHANNELS, get_telegram_limits
from app.scrapers import scrape_4chan_biz, get_chan4_limits
from app.scrapers import scrape_bitcointalk, get_bitcointalk_limits
from app.scrapers import scrape_github_discussions, get_github_limits
from app.scrapers import scrape_bluesky, get_bluesky_limits
from app.scrapers import get_youtube_limits
from app.nlp import load_finbert, load_cryptobert, analyze_finbert, analyze_cryptobert
from app.utils import clean_text
from app.prices import get_historical_prices, CryptoPrices
from app.storage import save_posts, get_all_posts, export_to_csv, export_to_json, get_stats, DB_PATH, JSONL_PATH, _parse_created_utc_to_date

# ============ PAGE CONFIG ============

st.set_page_config(
    page_title="Crypto Sentiment",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============ PROTECTION PAR MOT DE PASSE ============
# Si APP_PASSWORD ou DASHBOARD_PASSWORD est défini (dans .env ou variables d'env cloud),
# l'utilisateur doit entrer le mot de passe pour accéder au dashboard.
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

_app_password = os.environ.get("APP_PASSWORD") or os.environ.get("DASHBOARD_PASSWORD")
if not _app_password:
    try:
        _app_password = st.secrets.get("APP_PASSWORD") or st.secrets.get("DASHBOARD_PASSWORD")
    except Exception:
        pass

if not st.session_state.authenticated:
    if not _app_password:
        # Pas de mot de passe configuré (dev local) → accès libre
        st.session_state.authenticated = True
    else:
        # Afficher la page de connexion
        st.markdown("""
        <style>
            .login-box { max-width: 380px; margin: 4rem auto; padding: 2rem;
                background: linear-gradient(135deg, rgba(30,30,46,0.95) 0%, rgba(26,26,46,0.9) 100%);
                border: 1px solid rgba(99,102,241,0.3); border-radius: 16px; }
        </style>
        """, unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.markdown("### ◈ Crypto Sentiment")
            st.caption("Entrez le mot de passe pour accéder au dashboard.")
            with st.form("login_form"):
                pwd = st.text_input("Mot de passe", type="password", placeholder="••••••••", key="login_pwd")
                submitted = st.form_submit_button("Accéder")
            if submitted:
                if pwd and pwd == _app_password:
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("Mot de passe incorrect.")
            st.stop()

# ============ CUSTOM CSS ============

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap');
    
    .stApp {
        background: linear-gradient(135deg, #0a0a0f 0%, #1a1a2e 50%, #0f0f1a 100%);
    }
    
    #MainMenu, footer, header {visibility: hidden;}
    .block-container {padding-top: 2rem;}
    
    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', sans-serif;
    }
    
    h1, h2, h3 {
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        font-weight: 700 !important;
    }
    
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #12121a 0%, #1a1a2e 100%);
        border-right: 1px solid rgba(99, 102, 241, 0.2);
    }
    
    section[data-testid="stSidebar"] .stRadio label {
        color: #a5b4fc !important;
    }
    
    .metric-card {
        background: linear-gradient(135deg, rgba(99, 102, 241, 0.1) 0%, rgba(139, 92, 246, 0.05) 100%);
        border: 1px solid rgba(99, 102, 241, 0.3);
        border-radius: 16px;
        padding: 24px;
        margin: 8px 0;
        backdrop-filter: blur(10px);
    }
    
    .metric-value {
        font-family: 'JetBrains Mono', monospace;
        font-size: 2.5rem;
        font-weight: 700;
        background: linear-gradient(135deg, #818cf8 0%, #c084fc 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin: 0;
    }
    
    .metric-label {
        color: #94a3b8;
        font-size: 0.875rem;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        margin-bottom: 8px;
    }
    
    .metric-delta {
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.875rem;
        margin-top: 8px;
    }
    
    .delta-positive { color: #4ade80; }
    .delta-negative { color: #f87171; }
    
    .dashboard-title {
        font-size: 2.5rem;
        font-weight: 700;
        background: linear-gradient(135deg, #e0e7ff 0%, #c7d2fe 50%, #a5b4fc 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem;
    }
    
    .dashboard-subtitle {
        color: #64748b;
        font-size: 1rem;
        margin-bottom: 2rem;
    }
    
    /* Bouton Voir plus / Voir moins : couleur discrète, mêmes tons violet/bleu */
    [class*="stMarkdown"]:has(.toggle-platforms-zone) + [class*="stHorizontal"] .stButton > button,
    [class*="stMarkdown"]:has(.toggle-platforms-zone) + div .stButton > button {
        background: rgba(99, 102, 241, 0.12) !important;
        color: #a5b4fc !important;
        border: 1px solid rgba(99, 102, 241, 0.3) !important;
    }
    [class*="stMarkdown"]:has(.toggle-platforms-zone) + [class*="stHorizontal"] .stButton > button:hover,
    [class*="stMarkdown"]:has(.toggle-platforms-zone) + div .stButton > button:hover {
        background: rgba(99, 102, 241, 0.22) !important;
        border-color: rgba(99, 102, 241, 0.45) !important;
    }
    .stButton > button {
        background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
        color: white;
        border: none;
        border-radius: 12px;
        padding: 12px 24px;
        font-weight: 600;
        font-size: 1rem;
        transition: all 0.3s ease;
        box-shadow: 0 4px 15px rgba(99, 102, 241, 0.3);
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(99, 102, 241, 0.4);
    }

    .stSelectbox > div > div,
    .stMultiSelect > div > div {
        background: rgba(30, 30, 46, 0.8);
        border: 1px solid rgba(99, 102, 241, 0.3);
        border-radius: 12px;
    }
    
    .stRadio > div {
        background: rgba(30, 30, 46, 0.5);
        border-radius: 12px;
        padding: 12px;
    }
    
    .stProgress > div > div {
        background: linear-gradient(90deg, #6366f1, #8b5cf6, #a855f7);
        border-radius: 10px;
    }
    
    .info-box {
        background: rgba(99, 102, 241, 0.1);
        border-left: 4px solid #6366f1;
        padding: 16px 20px;
        border-radius: 0 12px 12px 0;
        margin: 16px 0;
    }
    
    .warning-box {
        background: rgba(251, 191, 36, 0.1);
        border-left: 4px solid #fbbf24;
        padding: 16px 20px;
        border-radius: 0 12px 12px 0;
        margin: 16px 0;
    }
    
    .success-box {
        background: rgba(74, 222, 128, 0.1);
        border-left: 4px solid #4ade80;
        padding: 16px 20px;
        border-radius: 0 12px 12px 0;
        margin: 16px 0;
    }
    
    hr {
        border: none;
        height: 1px;
        background: linear-gradient(90deg, transparent, rgba(99, 102, 241, 0.3), transparent);
        margin: 2rem 0;
    }
    
    .stTabs [data-baseweb="tab-list"] {
        background: rgba(30, 30, 46, 0.5);
        border-radius: 12px;
        padding: 4px;
        gap: 4px;
    }
    
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px;
        color: #94a3b8;
        font-weight: 500;
    }
    
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
        color: white;
    }
    
    .stSlider > div > div > div {
        background: #6366f1;
    }
    
    .viewerBadge_container__1QSob {display: none;}
    
    /* Page d'accueil */
    .accueil-hero {
        text-align: center;
        padding: 2rem 1rem 2.5rem;
        max-width: 720px;
        margin: 0 auto;
    }
    .accueil-badge {
        display: inline-block;
        font-size: 0.7rem;
        font-weight: 600;
        letter-spacing: 0.1em;
        color: #818cf8;
        background: rgba(99, 102, 241, 0.15);
        border: 1px solid rgba(99, 102, 241, 0.35);
        padding: 0.35rem 0.75rem;
        border-radius: 999px;
        margin-bottom: 1.25rem;
    }
    .accueil-title {
        font-size: 3rem;
        font-weight: 800;
        background: linear-gradient(135deg, #e0e7ff 0%, #c7d2fe 40%, #a5b4fc 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin: 0 0 0.5rem 0;
        letter-spacing: -0.02em;
    }
    .accueil-tagline {
        font-size: 1.25rem;
        color: #94a3b8;
        margin: 0 0 1rem 0;
        font-weight: 500;
    }
    .accueil-desc {
        font-size: 0.95rem;
        color: #64748b;
        line-height: 1.6;
        margin: 0;
    }
    .accueil-intro {
        font-size: 1.08rem;
        color: #94a3b8;
        line-height: 1.65;
        margin: 1.5rem 0 0 0;
        padding: 1rem 1.25rem;
        background: rgba(99, 102, 241, 0.06);
        border: 1px solid rgba(99, 102, 241, 0.15);
        border-radius: 12px;
        max-width: 720px;
        margin-left: auto;
        margin-right: auto;
    }
    .accueil-intro strong { color: #c4b5fd; }
    .accueil-prices-label {
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        color: #64748b;
        margin-bottom: 0.75rem !important;
    }
    .accueil-price-card {
        background: linear-gradient(135deg, rgba(99, 102, 241, 0.08) 0%, rgba(139, 92, 246, 0.05) 100%);
        border: 1px solid rgba(99, 102, 241, 0.2);
        border-radius: 12px;
        padding: 1.25rem;
        text-align: center;
        min-height: 100px;
    }
    .accueil-price-name {
        font-size: 0.8rem;
        font-weight: 600;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .accueil-price-value {
        font-family: 'JetBrains Mono', monospace;
        font-size: 1.6rem;
        font-weight: 700;
        color: #e0e7ff;
        margin: 0.35rem 0;
    }
    .accueil-price-delta {
        font-size: 0.8rem;
        font-weight: 600;
    }
    .accueil-price-delta.up { color: #4ade80; }
    .accueil-price-delta.down { color: #f87171; }
    .accueil-features {
        display: flex;
        flex-wrap: wrap;
        justify-content: center;
        gap: 1.5rem;
        margin-top: 2.5rem;
        padding-top: 2rem;
        border-top: 1px solid rgba(99, 102, 241, 0.15);
    }
    .accueil-feature {
        font-size: 0.9rem;
        color: #94a3b8;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }
    .accueil-feature-icon { font-size: 1.1rem; }
</style>
""", unsafe_allow_html=True)

# ============ CONFIG ============

CRYPTO_LIST = {
    "Bitcoin": {"id": "bitcoin", "sub": "Bitcoin", "stocktwits": "BTC.X", "icon": "₿"},
    "Ethereum": {"id": "ethereum", "sub": "ethereum", "stocktwits": "ETH.X", "icon": "Ξ"},
    "Solana": {"id": "solana", "sub": "solana", "stocktwits": "SOL.X", "icon": "◎"},
    "Cardano": {"id": "cardano", "sub": "cardano", "stocktwits": "ADA.X", "icon": "₳"},
}

LIMITS = {
    "Reddit": {"HTTP": get_reddit_limits()["http"], "Selenium": get_reddit_limits()["selenium"]},
    "StockTwits": {"Selenium": get_stocktwits_limits()["selenium"]},
    "Twitter": {"Selenium": 100, "Login": 2000},
    "Telegram": {"Simple": get_telegram_limits()["simple"], "Paginé": get_telegram_limits()["paginated"]},
    "YouTube": {"API": 10000, "Selenium": get_youtube_limits()["selenium"]},
    "4chan": {"HTTP": get_chan4_limits()["http"]},
    "Bitcointalk": {"HTTP": get_bitcointalk_limits()["http"]},
    "GitHub": {"API": get_github_limits()["api"]},
    "Bluesky": {"API": get_bluesky_limits()["api"]}
}

# ============ CACHE ============

@st.cache_resource
def get_finbert():
    return load_finbert()

@st.cache_resource
def get_cryptobert():
    return load_cryptobert()

ACCUEIL_CRYPTO_IDS = ["bitcoin", "ethereum", "solana", "cardano"]
ACCUEIL_CRYPTO_NAMES = ["Bitcoin", "Ethereum", "Solana", "Cardano"]

@st.cache_data(ttl=300)
def get_prices():
    client = CryptoPrices()
    return client.get_multiple_prices(ACCUEIL_CRYPTO_IDS)

@st.cache_data(ttl=300)
def get_accueil_historical(days: int = 14):
    """Historique des 6 cryptos pour les mini-graphiques de la page d'accueil."""
    import time
    from app.prices import get_historical_prices
    out = {}
    for i, cid in enumerate(ACCUEIL_CRYPTO_IDS):
        data = get_historical_prices(cid, days)
        if not data and i > 0:
            time.sleep(0.4)
            data = get_historical_prices(cid, days)
        out[cid] = data or []
        if i < len(ACCUEIL_CRYPTO_IDS) - 1:
            time.sleep(0.25)
    return out

def get_model(name):
    if name == "FinBERT":
        tok, mod = get_finbert()
        return tok, mod, analyze_finbert
    else:
        tok, mod = get_cryptobert()
        return tok, mod, analyze_cryptobert

def scrape_data(source, config, limit, method, telegram_channel=None, crypto_name=None,
                twitter_min_likes=None, twitter_start_date=None, twitter_end_date=None, twitter_sort="top"):
    if source == "Reddit":
        posts = scrape_reddit(config['sub'], limit, method=method.lower())
        save_posts(posts, source="reddit", method=method.lower())
        return posts
    elif source == "Twitter":
        query = crypto_name or config.get('sub', 'Bitcoin')
        try:
            posts = scrape_twitter(
                query, limit,
                min_likes=twitter_min_likes,
                start_date=twitter_start_date,
                end_date=twitter_end_date,
                sort_mode=twitter_sort
            )
            method_used = "selenium_login" if posts else "selenium"
            save_posts(posts, source="twitter", method=method_used)
            return posts
        except Exception as e:
            import traceback
            print(f"Erreur Twitter scraping: {e}")
            print(f"Traceback: {traceback.format_exc()}")
            return []
    elif source == "Telegram":
        if limit > 30:
            posts = scrape_telegram_paginated(telegram_channel, limit)
        else:
            posts = scrape_telegram_simple(telegram_channel, limit)
        for p in posts:
            p['title'] = p.get('text', '')
        save_posts(posts, source="telegram", method="http")
        return posts
    elif source == "4chan":
        query = crypto_name or config.get('sub', 'crypto').lower()
        posts = scrape_4chan_biz(query, limit)
        save_posts(posts, source="4chan", method="http")
        return posts
    elif source == "Bitcointalk":
        query = crypto_name or config.get('sub', 'crypto').lower()
        posts = scrape_bitcointalk(query, limit)
        save_posts(posts, source="bitcointalk", method="http")
        return posts
    elif source == "GitHub":
        query = crypto_name or config.get('sub', 'crypto').lower()
        posts = scrape_github_discussions(query, limit)
        save_posts(posts, source="github", method="api")
        return posts
    elif source == "Bluesky":
        query = crypto_name or config.get('sub', 'Bitcoin').lower()
        posts = scrape_bluesky(query, limit)
        save_posts(posts, source="bluesky", method="api")
        return posts
    else:
        posts = scrape_stocktwits(config['stocktwits'], limit)
        save_posts(posts, source="stocktwits", method="selenium")
        return posts

# ============ COMPONENTS ============

def render_metric_card(label, value, delta=None, delta_type="neutral"):
    delta_html = ""
    if delta:
        delta_class = "delta-positive" if delta_type == "positive" else "delta-negative" if delta_type == "negative" else ""
        delta_html = f'<div class="metric-delta {delta_class}">{delta}</div>'
    
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">{label}</div>
        <div class="metric-value">{value}</div>
        {delta_html}
    </div>
    """, unsafe_allow_html=True)


def render_header():
    st.markdown("""
    <div style="text-align: center; padding: 1rem 0 2rem 0;">
        <h1 class="dashboard-title">Crypto Sentiment Dashboard</h1>
        <p class="dashboard-subtitle">Analyse en temps réel du sentiment crypto • Reddit & StockTwits • FinBERT & CryptoBERT</p>
    </div>
    """, unsafe_allow_html=True)

# ============ PAGES ============

def page_accueil():
    """Page d'accueil : hero, présentation, prix en direct, CTA vers le dashboard."""
    st.markdown("""
    <div class="accueil-hero">
        <div class="accueil-badge">MoSEF 2025-2026</div>
        <h1 class="accueil-title">Crypto Sentiment</h1>
        <p class="accueil-tagline">Sentiment des réseaux sociaux & prix crypto</p>
        <p class="accueil-desc">Analyse en temps réel du sentiment (Reddit, Twitter, Bluesky, 4chan, GitHub…) 
        avec FinBERT & CryptoBERT. Scrape, compare et relie le sentiment aux mouvements de prix.</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    <div class="accueil-intro">
        Cet outil permet d'analyser le <strong>sentiment</strong> des discussions crypto sur plusieurs plateformes 
        (Reddit, Twitter, Bluesky, 4chan, GitHub…) et de le mettre en regard des <strong>cours</strong>. 
        Il aide à repérer d'éventuels signaux avant les mouvements de marché, à comparer les sources entre elles 
        et à exploiter des modèles de langage spécialisés (FinBERT, CryptoBERT) pour une analyse plus fine.
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown('<div style="margin: 2rem 0 1.5rem 0;"></div>', unsafe_allow_html=True)
    
    # Prix en direct + mini graphiques (3 cryptos par ligne, 2 lignes)
    st.markdown('<p class="accueil-prices-label">Prix en direct</p>', unsafe_allow_html=True)
    try:
        prices = get_prices()
        historical = get_accueil_historical(14)
    except Exception:
        prices = {}
        historical = {}
    if prices is not None:
        # Grille 2x2 : 4 cryptos (Bitcoin, Ethereum, Solana, Cardano)
        order = ACCUEIL_CRYPTO_IDS
        for row_start in range(0, len(order), 2):
            row_ids = order[row_start:row_start + 2]
            cols = st.columns(2)
            for col_idx, cid in enumerate(row_ids):
                display_name = ACCUEIL_CRYPTO_NAMES[ACCUEIL_CRYPTO_IDS.index(cid)]
                data = prices.get(cid) if prices else None
                with cols[col_idx]:
                    if data:
                        change = data.get('change_24h', 0)
                        price = data['price']
                        if price >= 1000:
                            price_str = f"${price:,.0f}"
                        elif price >= 1:
                            price_str = f"${price:,.2f}"
                        else:
                            price_str = f"${price:.4f}"
                        delta_class = "up" if change >= 0 else "down"
                        delta_html = f'<div class="accueil-price-delta {delta_class}">{change:+.2f}%</div>'
                    else:
                        price_str = "—"
                        delta_html = '<div class="accueil-price-delta">—</div>'
                    st.markdown(f"""
                    <div class="accueil-price-card">
                        <div class="accueil-price-name">{display_name.upper()}</div>
                        <div class="accueil-price-value">{price_str}</div>
                        {delta_html}
                    </div>
                    """, unsafe_allow_html=True)
                    # Mini graphique évolution (clé unique pour éviter StreamlitDuplicateElementId)
                    series = historical.get(cid) or []
                    fig = None
                    if series:
                        df = pd.DataFrame(series)
                        if not df.empty and "date" in df.columns and "price" in df.columns:
                            fig = go.Figure()
                            fig.add_trace(go.Scatter(
                                x=df["date"], y=df["price"],
                                mode="lines", line=dict(color="#818cf8", width=2),
                                fill="tozeroy", fillcolor="rgba(99, 102, 241, 0.15)"
                            ))
                    if fig is None:
                        fig = go.Figure()
                        fig.add_annotation(
                            text="Données bientôt disponibles",
                            xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False,
                            font=dict(size=12, color="#64748b")
                        )
                        fig.update_layout(xaxis=dict(visible=False), yaxis=dict(visible=False))
                    if fig is not None:
                        fig.update_layout(
                            margin=dict(l=0, r=0, t=20, b=0),
                            height=180,
                            paper_bgcolor="rgba(0,0,0,0)",
                            plot_bgcolor="rgba(0,0,0,0)",
                            xaxis=dict(showgrid=False, tickfont=dict(size=9), color="#64748b"),
                            yaxis=dict(showgrid=True, gridcolor="rgba(99,102,241,0.1)", tickfont=dict(size=9), color="#94a3b8"),
                            showlegend=False
                        )
                        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False}, key=f"accueil_chart_{cid}")
                    st.markdown('<div style="margin-bottom: 1rem;"></div>', unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="accueil-price-card" style="grid-column: 1 / -1;">
            <div class="accueil-price-name">Prix bientôt disponibles</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown('<div style="margin: 2rem 0 1rem 0;"></div>', unsafe_allow_html=True)
    
    st.markdown("""
    <div class="accueil-features">
        <div class="accueil-feature"><span class="accueil-feature-icon">📊</span> Dashboard & scraping multi-sources</div>
        <div class="accueil-feature"><span class="accueil-feature-icon">🤖</span> FinBERT & CryptoBERT</div>
        <div class="accueil-feature"><span class="accueil-feature-icon">📈</span> Analyses & documentation</div>
    </div>
    """, unsafe_allow_html=True)


def page_dashboard():
    render_header()
    
    try:
        prices = get_prices()
        if prices:
            cols = st.columns(len(prices))
            for i, (name, data) in enumerate(prices.items()):
                with cols[i]:
                    change = data.get('change_24h', 0)
                    delta_type = "positive" if change > 0 else "negative"
                    # Format prix selon la valeur
                    price = data['price']
                    if price >= 1000:
                        price_str = f"${price:,.0f}"
                    elif price >= 1:
                        price_str = f"${price:,.2f}"
                    else:
                        price_str = f"${price:.4f}"
                    render_metric_card(name.upper(), price_str, f"{change:+.2f}%", delta_type)
    except:
        st.info("Prix non disponibles")
    
    st.markdown("---")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.markdown("### Configuration")
        
        crypto = st.selectbox("Crypto", list(CRYPTO_LIST.keys()), key="dash_crypto")
        config = CRYPTO_LIST[crypto]
        
        source = st.radio("Source", ["Reddit", "StockTwits", "Twitter", "Telegram", "4chan", "Bitcointalk", "GitHub", "Bluesky"], horizontal=True, key="dash_source")
        
        if source == "Reddit":
            method = st.radio("Méthode", ["HTTP", "Selenium"], horizontal=True, key="dash_method")
            max_limit = LIMITS["Reddit"][method]
            telegram_channel = None
        elif source == "Twitter":
            method = st.radio("Mode", ["Login", "Selenium"], horizontal=True, key="dash_tw_method",
                             help="Login: recherche avancee (2000 tweets) | Selenium: profils publics (100 tweets)")
            max_limit = LIMITS["Twitter"][method]
            telegram_channel = None
            
            # Options avancees Twitter (methode Jose)
            with st.expander("Options Twitter avancees"):
                tw_sort = st.radio("Tri", ["top", "live"], horizontal=True, key="dash_tw_sort",
                                  help="top: populaires | live: recents")
                tw_min_likes = st.number_input("Min likes", min_value=0, value=0, key="dash_tw_likes",
                                              help="0 = pas de filtre")
                col_d1, col_d2 = st.columns(2)
                with col_d1:
                    tw_start = st.date_input("Date debut", value=None, key="dash_tw_start")
                with col_d2:
                    tw_end = st.date_input("Date fin", value=None, key="dash_tw_end")
            
            st.markdown("""
            <div class="info-box">
                <strong>Twitter/X</strong> — instable depuis 2023<br>
                <small>X exige le login, détecte Selenium et change son API toutes les 2–4 sem.
                Si login échoue ou sans identifiants: <b>Nitter</b> (fallback) puis profils publics.
                Mettez <code>TWITTER_USERNAME</code> et <code>TWITTER_PASSWORD</code> dans <code>.env</code> pour tenter le login.</small>
            </div>
            """, unsafe_allow_html=True)
        elif source == "Telegram":
            method = st.radio("Méthode", ["Simple", "Paginé"], horizontal=True, key="dash_method_tg")
            max_limit = LIMITS["Telegram"][method]
            telegram_channel = st.selectbox("Channel Telegram", list(TELEGRAM_CHANNELS.keys()),
                                           format_func=lambda x: f"{x} - {TELEGRAM_CHANNELS[x]}", key="dash_tg_channel")
            st.markdown(f"""
            <div class="info-box">
                <strong>Channel:</strong> @{telegram_channel}<br>
                <small>Scraping public sans API</small>
            </div>
            """, unsafe_allow_html=True)
        elif source == "4chan":
            method = "HTTP"
            max_limit = LIMITS["4chan"]["HTTP"]
            telegram_channel = None
            st.markdown("""
            <div class="success-box">
                <strong>4chan /biz/</strong> — Très actif pour crypto<br>
                <small>Scraping rapide via API, pas de login requis. Discussions anonymes sur /biz/.</small>
            </div>
            """, unsafe_allow_html=True)
        elif source == "Bitcointalk":
            method = "HTTP"
            max_limit = LIMITS["Bitcointalk"]["HTTP"]
            telegram_channel = None
            st.markdown("""
            <div class="success-box">
                <strong>Bitcointalk</strong> — Forum crypto historique<br>
                <small>Scraping via HTTP, pas de login requis. Discussions longues et détaillées sur crypto.</small>
            </div>
            """, unsafe_allow_html=True)
        elif source == "GitHub":
            method = "API"
            max_limit = LIMITS["GitHub"]["API"]
            telegram_channel = None
            st.markdown("""
            <div class="success-box">
                <strong>GitHub</strong> — Issues/Discussions projets crypto<br>
                <small>API officielle GitHub (gratuite). Discussions techniques sur projets Bitcoin, Ethereum, etc.</small>
            </div>
            """, unsafe_allow_html=True)
        elif source == "Bluesky":
            method = "API"
            max_limit = LIMITS["Bluesky"]["API"]
            telegram_channel = None
            st.markdown("""
            <div class="success-box">
                <strong>Bluesky</strong> — Recherche AT Protocol<br>
                <small>Recherche par mot-clé. Configure BLUESKY_USERNAME et BLUESKY_APP_PASSWORD dans .env.</small>
            </div>
            """, unsafe_allow_html=True)
        else:
            method = "Selenium"
            max_limit = LIMITS["StockTwits"]["Selenium"]
            telegram_channel = None
            st.markdown("""
            <div class="success-box">
                <strong>Labels humains disponibles</strong><br>
                <small>StockTwits fournit des labels Bullish/Bearish</small>
            </div>
            """, unsafe_allow_html=True)
        
        model = st.radio("Modèle NLP", ["FinBERT", "CryptoBERT"], horizontal=True, key="dash_model")
        limit = st.slider("Nombre de posts", 20, max_limit, min(50, max_limit), key="dash_limit")
        
        st.markdown(f"""
        <div class="info-box">
            <strong>Limite max:</strong> {max_limit} posts<br>
            <small>Pour éviter les bans</small>
        </div>
        """, unsafe_allow_html=True)
        
        analyze = st.button("Analyser", use_container_width=True, key="dash_analyze")
    
    # Build Twitter options if applicable
    twitter_opts = None
    if source == "Twitter":
        twitter_opts = {
            'sort': tw_sort if 'tw_sort' in dir() else 'top',
            'min_likes': tw_min_likes if tw_min_likes > 0 else None,
            'start_date': tw_start.strftime('%Y-%m-%d') if tw_start else None,
            'end_date': tw_end.strftime('%Y-%m-%d') if tw_end else None
        }
    
    with col2:
        if analyze:
            run_analysis(crypto, config, source, method, model, limit, telegram_channel, crypto, twitter_opts)
        else:
            st.markdown("""
            <div style="
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                height: 400px;
                background: rgba(30, 30, 46, 0.3);
                border-radius: 16px;
                border: 1px dashed rgba(99, 102, 241, 0.3);
            ">
                <div style="color: #64748b; font-size: 1.1rem;">Configure et lance une analyse</div>
                <div style="color: #475569; font-size: 0.9rem; margin-top: 0.5rem;">Les résultats apparaîtront ici</div>
            </div>
            """, unsafe_allow_html=True)


def run_analysis(crypto, config, source, method, model, limit, telegram_channel=None, crypto_name=None,
                 twitter_opts=None):
    with st.spinner(f"Scraping {source}..."):
        tw_opts = twitter_opts or {}
        posts = scrape_data(source, config, limit, method, telegram_channel, crypto_name,
                           twitter_min_likes=tw_opts.get('min_likes'),
                           twitter_start_date=tw_opts.get('start_date'),
                           twitter_end_date=tw_opts.get('end_date'),
                           twitter_sort=tw_opts.get('sort', 'top'))
    
    if not posts:
        st.error("Aucun post récupéré")
        return
    
    # Afficher confirmation de sauvegarde
    st.success(f"{len(posts)} posts sauvegardés dans la base de données")
    
    with st.spinner(f"Analyse avec {model}..."):
        tokenizer, mod, analyze_fn = get_model(model)
        
        results = []
        progress = st.progress(0)
        
        for i, post in enumerate(posts):
            text = clean_text(post["title"] + " " + post.get("text", ""))
            if text and len(text) > 5:
                sent = analyze_fn(text, tokenizer, mod)
            else:
                sent = {"score": 0, "label": "Neutral"}
            
            results.append({
                **post,
                "sentiment_score": sent["score"],
                "sentiment_label": sent["label"]
            })
            progress.progress((i + 1) / len(posts))
    
    st.session_state['results'] = results
    st.session_state['crypto'] = crypto
    st.session_state['config'] = config
    
    display_results(results, source, model)


def display_results(results, source, model):
    scores = [r["sentiment_score"] for r in results]
    labels = {"Bullish": 0, "Bearish": 0, "Neutral": 0}
    for r in results:
        labels[r["sentiment_label"]] += 1
    
    avg_score = np.mean(scores)
    
    st.markdown("### Résultats")
    
    cols = st.columns(4)
    with cols[0]:
        render_metric_card("Posts analysés", len(results))
    with cols[1]:
        delta_type = "positive" if avg_score > 0 else "negative"
        render_metric_card("Sentiment moyen", f"{avg_score:+.3f}", delta_type=delta_type)
    with cols[2]:
        render_metric_card("Bullish", labels['Bullish'], f"{labels['Bullish']/len(results)*100:.0f}%", "positive")
    with cols[3]:
        render_metric_card("Bearish", labels['Bearish'], f"{labels['Bearish']/len(results)*100:.0f}%", "negative")
    
    labeled = [r for r in results if r.get("human_label")]
    if labeled:
        correct = sum(1 for r in labeled if r["sentiment_label"] == r["human_label"])
        acc = correct / len(labeled) * 100
        st.markdown(f"""
        <div class="success-box">
            <strong>Accuracy vs labels humains: {acc:.1f}%</strong><br>
            <small>{correct}/{len(labeled)} prédictions correctes</small>
        </div>
        """, unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        fig = go.Figure(data=[go.Pie(
            labels=list(labels.keys()),
            values=list(labels.values()),
            hole=0.6,
            marker=dict(colors=['#4ade80', '#f87171', '#64748b']),
            textinfo='label+percent',
            textfont=dict(size=14, color='white')
        )])
        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color='white'),
            showlegend=False,
            margin=dict(t=20, b=20, l=20, r=20),
            height=300
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        fig = go.Figure(data=[go.Histogram(
            x=scores,
            nbinsx=30,
            marker=dict(color='rgba(99, 102, 241, 0.7)', line=dict(color='#818cf8', width=1))
        )])
        fig.add_vline(x=0, line_dash="dash", line_color="#64748b")
        fig.add_vline(x=avg_score, line_dash="solid", line_color="#a855f7", line_width=2)
        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color='white'),
            xaxis=dict(gridcolor='rgba(255,255,255,0.1)', title="Score"),
            yaxis=dict(gridcolor='rgba(255,255,255,0.1)', title="Count"),
            margin=dict(t=20, b=40, l=40, r=20),
            height=300
        )
        st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("### Détail des posts")
    
    df = pd.DataFrame([{
        "Texte": r["title"][:60] + "..." if len(r["title"]) > 60 else r["title"],
        "Score": round(r["sentiment_score"], 3),
        "Prédiction": r["sentiment_label"],
        "Label": r.get("human_label", "-")
    } for r in results])
    
    st.dataframe(df, use_container_width=True, height=300)
    
    col1, col2 = st.columns(2)
    with col1:
        st.download_button("Télécharger CSV", df.to_csv(index=False), "sentiment.csv", use_container_width=True)


def page_documentation():
    """Page Documentation : méthodologie, sources, modèles, références."""
    st.markdown("""
    <div style="margin-bottom: 2rem;">
        <h1 style="font-size: 2rem; font-weight: 700; color: #e0e7ff; margin-bottom: 0.5rem;">Documentation</h1>
        <p style="color: #94a3b8; font-size: 1rem;">Méthodologie, sources de données, modèles NLP et références du projet Crypto Sentiment.</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Sommaire
    st.markdown("---")
    st.markdown("### Sommaire")
    st.markdown("""
    - [1. Vue d'ensemble](#1-vue-densemble)
    - [2. Sources de données](#2-sources-de-données)
    - [3. Modèles de sentiment](#3-modèles-de-sentiment)
    - [4. Parcours utilisateur](#4-parcours-utilisateur)
    - [5. Limites et bonnes pratiques](#5-limites-et-bonnes-pratiques)
    - [6. Références](#6-références)
    - [7. Comparaison dynamique FinBERT vs CryptoBERT](#7-comparaison-dynamique-finbert-vs-cryptobert)
    """)
    st.markdown("---")
    
    st.markdown("### 1. Vue d'ensemble")
    st.markdown("""
    **Crypto Sentiment** permet de collecter des discussions crypto sur plusieurs plateformes (Reddit, Twitter, Telegram, StockTwits, 4chan, Bitcointalk, GitHub, Bluesky, YouTube), 
    de les analyser avec des modèles de langage spécialisés (**FinBERT** et **CryptoBERT**) et de comparer le sentiment aux mouvements de prix.
    
    Les données sont stockées en base (SQLite en local ou PostgreSQL en cloud) et peuvent être filtrées par source, méthode et nombre de posts pour les analyses.
    """)
    
    st.markdown("### 2. Sources de données")
    st.markdown("""
    | Source | Méthode | Max posts | Vitesse | Labels Bullish/Bearish |
    |--------|---------|-----------|---------|------------------------|
    | Reddit | HTTP | 1000 | ~1–5 s | Non |
    | Reddit | Selenium | 200 | ~10–30 s | Non |
    | Twitter | Selenium / Login | 100 / 2000 | Variable | Non |
    | Telegram | Simple / Paginé | 30 / 2000 | Variable | Non |
    | StockTwits | Selenium | 1000 | ~30–60 s | **Oui** |
    | 4chan /biz/ | HTTP | 200 | Rapide | Non |
    | Bitcointalk | HTTP | 200 | Variable | Non |
    | GitHub | API | 200 | Rapide | Non |
    | Bluesky | API | 200 | Rapide | Non |
    | YouTube | API | 10000 | Variable | Non |
    
    **Note :** StockTwits fournit des labels Bullish/Bearish natifs. 4chan utilise HTTP uniquement (pas Selenium).
    """)
    
    st.markdown("### 3. Modèles de sentiment")
    st.markdown("""
    | Modèle | Entraînement | Labels de sortie |
    |--------|---------------|------------------|
    | **FinBERT** (ProsusAI/finbert) | News financières | Positive / Negative / Neutral → score et label Bullish/Bearish/Neutral |
    | **CryptoBERT** (ElKulako/cryptobert) | ~3,2 M de posts crypto | Bullish / Bearish / Neutral |
    
    Les deux modèles renvoient un **score** (entre -1 et 1) et un **label**. CryptoBERT est entraîné sur StockTwits, Telegram, Reddit et Twitter.
    """)
    
    st.markdown("### 4. Parcours utilisateur")
    st.markdown("""
    - **Accueil :** vue d'ensemble, prix en direct (4 cryptos) et mini-graphiques d'évolution.
    - **Scraping :** choix de la plateforme (Reddit, Twitter, Telegram, StockTwits, 4chan, Bitcointalk, GitHub, Bluesky, YouTube), configuration (crypto, nombre de posts, filtres optionnels), lancement du scraping. Les posts sont enregistrés en base.
    - **Données :** consultation des posts stockés, statistiques par source/méthode, export CSV/JSON.
    - **Analyses des résultats :** filtrage des posts (source, méthode, nombre), analyse globale (FinBERT ou CryptoBERT) ou analyse multi-crypto (filtre par mots-clés par crypto).
    - **Documentation :** cette page.
    """)
    
    st.markdown("### 5. Limites et bonnes pratiques")
    st.markdown("""
    - **Reddit HTTP :** max 1000 posts, respecter ~1 req/s pour limiter les bans.
    - **Reddit Selenium :** max 200 posts, plus lent.
    - **StockTwits :** max 1000 posts avec scroll amélioré ; Cloudflare impose l'usage de Selenium.
    - **Twitter :** fortement limité sans authentification ; risque de blocage.
    - **Bluesky / GitHub :** configurer les identifiants (Bluesky) ou token (GitHub) si nécessaire.
    """)
    
    st.markdown("### 6. Références")
    st.markdown("""
    - **FinBERT :** [ProsusAI/finbert](https://huggingface.co/ProsusAI/finbert) — analyse de sentiment sur texte financier.
    - **CryptoBERT :** ElKulako/cryptobert — *IEEE Intelligent Systems* 38(4), 2023 ; entraîné sur données crypto.
    - Kraaijeveld & De Smedt (2020) — *The predictive power of Twitter sentiment* pour la relation sentiment–prix.
    """)
    
    st.markdown("---")
    st.markdown("### 7. Comparaison dynamique FinBERT vs CryptoBERT")
    st.markdown("Saisis un court texte (ou choisis un exemple) pour comparer en direct la sortie des deux modèles.")
    
    SAMPLES = [
        "Bitcoin is going to the moon, buy the dip!",
        "ETH is crashing, sell everything before it's too late.",
        "Cardano partnership announced, very bullish for ADA.",
        "The market is sideways, no clear direction.",
        "BTC at 100k by end of year, massive institutional adoption.",
    ]
    
    if "doc_compare_text" not in st.session_state:
        st.session_state.doc_compare_text = ""
    
    manual_entry = "— Saisir manuellement —"
    col_sample, col_analyze = st.columns([2, 1])
    with col_sample:
        sample_choice = st.selectbox(
            "Exemple de phrase",
            [manual_entry] + SAMPLES,
            key="doc_sample"
        )
    with col_analyze:
        st.markdown("")
        st.markdown("")
        run_compare = st.button("Comparer", type="primary", use_container_width=True, key="doc_compare_btn")
    
    # Zone "Texte à analyser" uniquement en mode saisie manuelle
    if sample_choice == manual_entry:
        text_input = st.text_area(
            "Texte à analyser",
            value=st.session_state.doc_compare_text,
            height=100,
            placeholder="Ex: Bitcoin is pumping, very bullish!",
            key="doc_compare_text"
        )
        text_to_analyze = text_input
    else:
        text_to_analyze = sample_choice
    
    if run_compare and text_to_analyze and len(text_to_analyze.strip()) >= 5:
        text_clean = clean_text(text_to_analyze.strip())
        if not text_clean or len(text_clean) < 5:
            st.warning("Texte trop court ou vide après nettoyage.")
        else:
            with st.spinner("Chargement des modèles et analyse…"):
                fin_tok, fin_mod = get_finbert()
                cry_tok, cry_mod = get_cryptobert()
                out_fin = analyze_finbert(text_clean, fin_tok, fin_mod)
                out_cry = analyze_cryptobert(text_clean, cry_tok, cry_mod)
            
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("""
                <div style="background: rgba(99, 102, 241, 0.12); border: 1px solid rgba(99, 102, 241, 0.35); border-radius: 12px; padding: 1.25rem;">
                    <div style="font-weight: 600; color: #a5b4fc; margin-bottom: 0.5rem;">FinBERT</div>
                    <div style="font-size: 1.5rem; font-weight: 700; color: #e0e7ff;">{score:+.3f}</div>
                    <div style="color: #94a3b8; font-size: 0.9rem;">Label : <strong>{label}</strong></div>
                    <div style="margin-top: 0.5rem; font-size: 0.8rem; color: #64748b;">positive {pos:.2f} · negative {neg:.2f} · neutral {neu:.2f}</div>
                </div>
                """.format(
                    score=out_fin["score"],
                    label=out_fin["label"],
                    pos=out_fin.get("probs", {}).get("positive", 0),
                    neg=out_fin.get("probs", {}).get("negative", 0),
                    neu=out_fin.get("probs", {}).get("neutral", 0),
                ), unsafe_allow_html=True)
            with c2:
                p = out_cry.get("probs", {})
                st.markdown("""
                <div style="background: rgba(139, 92, 246, 0.12); border: 1px solid rgba(139, 92, 246, 0.35); border-radius: 12px; padding: 1.25rem;">
                    <div style="font-weight: 600; color: #c4b5fd; margin-bottom: 0.5rem;">CryptoBERT</div>
                    <div style="font-size: 1.5rem; font-weight: 700; color: #e0e7ff;">{score:+.3f}</div>
                    <div style="color: #94a3b8; font-size: 0.9rem;">Label : <strong>{label}</strong></div>
                    <div style="margin-top: 0.5rem; font-size: 0.8rem; color: #64748b;">bullish {bull:.2f} · bearish {bear:.2f} · neutral {neu:.2f}</div>
                </div>
                """.format(
                    score=out_cry["score"],
                    label=out_cry["label"],
                    bull=p.get("bullish", 0),
                    bear=p.get("bearish", 0),
                    neu=p.get("neutral", 0),
                ), unsafe_allow_html=True)
            
            if out_fin["label"] != out_cry["label"]:
                st.caption("Les deux modèles donnent un label différent pour ce texte — FinBERT est entraîné sur la finance générale, CryptoBERT sur le jargon crypto.")
    elif run_compare:
        st.warning("Saisis au moins quelques mots (5 caractères minimum) puis clique sur **Comparer**.")
    
    st.markdown("---")
    st.caption("Crypto Sentiment — MoSEF 2025-2026")


# ============ PAGE DONNÉES STOCKÉES ============

def page_stored_data():
    render_header()
    st.markdown("### Données Stockées")

    # --- Description ---
    st.markdown("""
    Cette page centralise **toutes les données collectées** par le scraping (Reddit, StockTwits, Telegram, Twitter, etc.).
    Vous y trouvez les statistiques globales, des visualisations par source et méthode, l’évolution dans le temps,
    et la possibilité de filtrer, consulter et exporter les posts.
    """)
    st.markdown("---")

    # Récupérer les statistiques
    stats = get_stats()
    total = stats.get("total_posts", 0)

    if total == 0:
        st.warning("Aucune donnée en base. Collectez des posts via la page **Scraping**.")
        return

    # --- Métriques principales ---
    st.markdown("#### Vue d’ensemble")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        render_metric_card("Total Posts", f"{total:,}")
    with col2:
        first = stats.get("first_scrape") or "N/A"
        render_metric_card("Premier Scrape", str(first)[:10] if first != "N/A" else "N/A")
    with col3:
        last = stats.get("last_scrape") or "N/A"
        render_metric_card("Dernier Scrape", str(last)[:10] if last != "N/A" else "N/A")
    with col4:
        db_label = "Supabase" if stats.get("db_type") == "postgres" else "SQLite"
        render_metric_card("Base", db_label)

    st.markdown("---")

    # --- Données pour les graphiques avancés ---
    sample_posts = get_all_posts(limit=min(5000, total))

    if "data_viz_tab" not in st.session_state:
        st.session_state.data_viz_tab = "overview"

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if st.button(
            "Répartition par source",
            use_container_width=True,
            key="btn_overview",
            type="primary" if st.session_state.data_viz_tab == "overview" else "secondary"
        ):
            st.session_state.data_viz_tab = "overview"
            st.rerun()
    with col2:
        if st.button(
            "Source × Méthode",
            use_container_width=True,
            key="btn_sources",
            type="primary" if st.session_state.data_viz_tab == "sources" else "secondary"
        ):
            st.session_state.data_viz_tab = "sources"
            st.rerun()
    with col3:
        if st.button(
            "Évolution temporelle",
            use_container_width=True,
            key="btn_timeline",
            type="primary" if st.session_state.data_viz_tab == "timeline" else "secondary"
        ):
            st.session_state.data_viz_tab = "timeline"
            st.rerun()
    with col4:
        if st.button(
            "Publication des posts",
            use_container_width=True,
            key="btn_publications",
            type="primary" if st.session_state.data_viz_tab == "publications" else "secondary"
        ):
            st.session_state.data_viz_tab = "publications"
            st.rerun()

    st.markdown("---")

    # Graphiques en dessous selon le bouton sélectionné
    if st.session_state.data_viz_tab == "overview":
        st.markdown("Répartition du volume de posts **par source** (Reddit, StockTwits, Telegram, etc.).")
        if stats.get("by_source_method"):
            df_sm = pd.DataFrame(stats["by_source_method"])
            by_source = df_sm.groupby("source", as_index=False)["count"].sum()
            fig_pie = px.pie(
                by_source, values="count", names="source",
                title="Répartition par source",
                color_discrete_sequence=px.colors.qualitative.Set2
            )
            fig_pie.update_layout(
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                font_color="#e0e7ff",
                legend_font_color="#e0e7ff"
            )
            st.plotly_chart(fig_pie, use_container_width=True)
        st.markdown("---")
        st.markdown("**💡 Interprétation** — La répartition par source montre quelles plateformes alimentent le plus votre base. Une source dominante (ex. Reddit) indique un biais vers ce type de discours ; une répartition plus équilibrée donne un échantillon plus diversifié pour l’analyse de sentiment crypto.")

    elif st.session_state.data_viz_tab == "sources":
        st.markdown("Nombre de posts par **source** et **méthode** de collecte (scraper, selenium, api, etc.).")
        if stats.get("by_source_method"):
            df_stats = pd.DataFrame(stats["by_source_method"])
            fig_bar = px.bar(
                df_stats, x="source", y="count", color="method",
                barmode="group",
                title="Posts par source et méthode",
                color_discrete_sequence=["#818cf8", "#22d3ee", "#a78bfa", "#34d399"]
            )
            fig_bar.update_layout(
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                font_color="#e0e7ff",
                legend_font_color="#e0e7ff"
            )
            st.plotly_chart(fig_bar, use_container_width=True)
        st.markdown("---")
        st.markdown("**💡 Interprétation** — Chaque source peut être collectée via plusieurs méthodes (scraper, selenium, api…). Les barres groupées permettent de voir quelle méthode est la plus utilisée par source et d’identifier d’éventuels déséquilibres ou sources à renforcer.")

    elif st.session_state.data_viz_tab == "timeline":
        st.markdown("Évolution du volume de données **dans le temps** (date d’ajout en base).")
        if sample_posts:
            df_t = pd.DataFrame(sample_posts)
            if "scraped_at" in df_t.columns and df_t["scraped_at"].notna().any():
                df_t["scraped_at"] = pd.to_datetime(df_t["scraped_at"], errors="coerce")
                df_t = df_t.dropna(subset=["scraped_at"])
                df_t["date"] = df_t["scraped_at"].dt.date
                daily = df_t.groupby("date", as_index=False).size()
                fig_time = px.line(
                    daily, x="date", y="size",
                    title="Posts ajoutés par jour (échantillon)",
                    labels={"size": "Nombre de posts", "date": "Date"}
                )
                fig_time.update_layout(
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)",
                    font_color="#e0e7ff"
                )
                st.plotly_chart(fig_time, use_container_width=True)
                st.markdown("---")
                st.markdown("**💡 Interprétation** — La courbe reflète l’activité de collecte dans le temps. Les pics correspondent à des sessions de scraping intenses ; une base régulièrement alimentée donne une série plus lisse et un échantillon temporellement plus représentatif.")
            else:
                st.caption("Pas de dates de scrape disponibles pour cet échantillon.")
        else:
            st.caption("Aucune donnée pour afficher la timeline.")

    elif st.session_state.data_viz_tab == "publications":
        st.markdown("        **Distribution de la publication des posts** : répartition des dates de publication des posts dans la base.")
        if sample_posts:
            dates = []
            for p in sample_posts:
                d = _parse_created_utc_to_date(p.get("created_utc"))
                if d is not None:
                    dates.append(d)
            if dates:
                df_pub = pd.DataFrame({"date": dates})
                daily = df_pub.groupby("date", as_index=False).size()
                daily = daily.sort_values("date")
                fig_pub = px.bar(
                    daily, x="date", y="size",
                    title="Nombre de posts par date de publication",
                    labels={"size": "Nombre de posts", "date": "Date de publication"},
                    color="size",
                    color_continuous_scale="Blues"
                )
                fig_pub.update_layout(
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)",
                    font_color="#e0e7ff",
                    xaxis=dict(tickformat="%Y-%m-%d", gridcolor="rgba(255,255,255,0.1)"),
                    yaxis=dict(gridcolor="rgba(255,255,255,0.1)"),
                    showlegend=False
                )
                fig_pub.update_coloraxes(showscale=False)
                st.plotly_chart(fig_pub, use_container_width=True)
            else:
                st.caption("Aucune date de publication exploitable dans l'échantillon (created_utc absent ou invalide).")
        else:
            st.caption("Aucune donnée pour afficher la distribution.")
        st.markdown("---")
        st.markdown("**💡 Interprétation** — Ce graphique montre combien de posts ont été **publiés** (sur les plateformes sources) à chaque date. Une répartition étalée dans le temps indique un échantillon varié ; des pics sur certaines dates reflètent des moments de forte activité sur les réseaux.")


    st.markdown("---")
    st.markdown("#### Consulter les Données")

    col1, col2, col3 = st.columns(3)
    with col1:
        source_filter = st.selectbox("Source", ["Toutes", "reddit", "stocktwits", "telegram", "twitter", "youtube", "bluesky"], key="data_source")
    with col2:
        method_filter = st.selectbox("Méthode", ["Toutes", "http", "selenium", "scraper", "api", "selenium_login"], key="data_method")
    with col3:
        limit = st.number_input("Limite", min_value=10, max_value=1000, value=100, key="data_limit")

    source = source_filter if source_filter != "Toutes" else None
    method = method_filter if method_filter != "Toutes" else None
    posts = get_all_posts(source=source, method=method, limit=limit)

    if posts:
        st.success(f"{len(posts)} posts trouvés")
        df = pd.DataFrame(posts)
        st.dataframe(df, use_container_width=True)

        st.markdown("#### Exporter les Données")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Exporter en CSV", key="export_csv"):
                csv_path = export_to_csv(source=source, method=method)
                st.success(f"Exporté vers: {csv_path}")
        with col2:
            if st.button("Exporter en JSON", key="export_json"):
                json_path = export_to_json(source=source, method=method)
                st.success(f"Exporté vers: {json_path}")
    else:
        st.warning("Aucune donnée trouvée avec ces filtres.")

    st.markdown("---")
    st.markdown("#### Stockage & Fichiers")
    st.markdown("Les posts sont enregistrés en base (Supabase ou SQLite) et sauvegardés en backup dans un fichier JSONL.")
    st.code(f"""
Base: {stats.get('db_type', 'N/A')}
SQLite (local): {DB_PATH}
JSONL (backup): {JSONL_PATH}
Exports: data/exports/
    """)


# ============ PAGE ANALYSES DES RÉSULTATS ============

def page_analyses_resultats():
    """Page d'analyse sentiment — même DA que la page Données."""
    render_header()
    st.markdown("### Analyse de Sentiment")

    st.markdown("""
    Cette page permet d'**analyser le sentiment** des posts stockés à l'aide de modèles NLP (FinBERT ou CryptoBERT).
    Vous pouvez lancer une **analyse globale** sur un échantillon filtré, ou **comparer le sentiment par crypto** (Bitcoin, Ethereum, etc.).
    """)
    st.markdown("---")

    stats = get_stats()
    total_posts = stats.get("total_posts", 0)

    if total_posts == 0:
        st.warning("Aucune donnée en base. Collectez d'abord des posts via **Scraping**.")
        return

    # --- Vue d'ensemble (même style que Données) ---
    st.markdown("#### Vue d'ensemble")
    sources_count = len(set(s["source"] for s in stats.get("by_source_method", [])))
    db_label = "Supabase" if stats.get("db_type") == "postgres" else "SQLite"
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        render_metric_card("Posts en base", f"{total_posts:,}")
    with col2:
        render_metric_card("Sources", str(sources_count))
    with col3:
        render_metric_card("Base", db_label)
    with col4:
        render_metric_card("Modèles", "2 modèles")
    st.caption("**Sources** = nombre de plateformes d'où viennent les posts (Reddit, Twitter, Telegram, StockTwits, etc.). **Modèles** = FinBERT et CryptoBERT.")

    st.markdown("---")

    # --- Boutons mode d'analyse ---
    if "analysis_mode" not in st.session_state:
        st.session_state.analysis_mode = "global"

    col1, col2 = st.columns(2)
    with col1:
        if st.button(
            "Analyse globale",
            use_container_width=True,
            key="btn_analysis_global",
            type="primary" if st.session_state.analysis_mode == "global" else "secondary"
        ):
            st.session_state.analysis_mode = "global"
            st.rerun()
    with col2:
        if st.button(
            "Par crypto",
            use_container_width=True,
            key="btn_analysis_crypto",
            type="primary" if st.session_state.analysis_mode == "crypto" else "secondary"
        ):
            st.session_state.analysis_mode = "crypto"
            st.rerun()

    st.markdown("---")

    SOURCES = ["reddit", "twitter", "telegram", "stocktwits", "4chan", "bitcointalk", "github", "bluesky", "youtube"]
    cryptos = {
        "Bitcoin": {"keywords": ["bitcoin", "btc"], "icon": "₿"},
        "Ethereum": {"keywords": ["ethereum", "eth"], "icon": "Ξ"},
        "Solana": {"keywords": ["solana", "sol"], "icon": "◎"},
        "Cardano": {"keywords": ["cardano", "ada"], "icon": "₳"},
    }

    # CSS global pour styliser les boutons : non-sélectionnés = gris plat, sélectionnés = violet enfoncé
    st.markdown("""
    <style>
    /* Boutons NON sélectionnés (secondary) = gris plat */
    [data-testid="stHorizontalBlock"] button[kind="secondary"] {
        border-radius: 9999px !important;
        padding: 10px 16px !important;
        font-size: 0.82rem !important;
        font-weight: 500 !important;
        border: 1px solid rgba(100, 116, 139, 0.5) !important;
        background: rgba(30, 41, 59, 0.6) !important;
        color: #94a3b8 !important;
        box-shadow: none !important;
        transition: all 0.15s ease !important;
    }
    [data-testid="stHorizontalBlock"] button[kind="secondary"]:hover {
        background: rgba(51, 65, 85, 0.8) !important;
        border-color: rgba(148, 163, 184, 0.6) !important;
        color: #e2e8f0 !important;
    }
    /* Boutons SÉLECTIONNÉS (primary) = violet enfoncé */
    [data-testid="stHorizontalBlock"] button[kind="primary"] {
        border-radius: 9999px !important;
        padding: 10px 16px !important;
        font-size: 0.82rem !important;
        font-weight: 600 !important;
        border: 2px solid #8b5cf6 !important;
        background: linear-gradient(180deg, #4c1d95 0%, #5b21b6 100%) !important;
        color: #e9d5ff !important;
        box-shadow: inset 0 3px 8px rgba(0, 0, 0, 0.5), 0 0 12px rgba(139, 92, 246, 0.4) !important;
        text-shadow: 0 1px 2px rgba(0, 0, 0, 0.4) !important;
        transition: all 0.15s ease !important;
    }
    [data-testid="stHorizontalBlock"] button[kind="primary"]:hover {
        background: linear-gradient(180deg, #5b21b6 0%, #6d28d9 100%) !important;
        box-shadow: inset 0 3px 8px rgba(0, 0, 0, 0.5), 0 0 18px rgba(139, 92, 246, 0.55) !important;
    }
    </style>
    """, unsafe_allow_html=True)

    # === MODE GLOBAL ===
    if st.session_state.analysis_mode == "global":
        st.markdown("Analyse du **sentiment sur l'ensemble des posts** (ou un sous-ensemble filtré).")
        st.markdown("#### Paramètres")

        if "glob_sources" not in st.session_state:
            st.session_state.glob_sources = ["reddit", "twitter", "telegram"]

        st.markdown("**Source(s)** — Cliquez sur une bulle pour l’ajouter ou la retirer.")
        # Boutons : primary si sélectionné (violet enfoncé), secondary sinon (gris plat)
        bubble_cols = st.columns(9)
        for i, src in enumerate(SOURCES):
            with bubble_cols[i]:
                is_selected = src in st.session_state.glob_sources
                if st.button(
                    src,
                    key=f"glob_src_{src}",
                    use_container_width=True,
                    type="primary" if is_selected else "secondary"
                ):
                    if src in st.session_state.glob_sources:
                        st.session_state.glob_sources = [s for s in st.session_state.glob_sources if s != src]
                    else:
                        st.session_state.glob_sources = st.session_state.glob_sources + [src]
                    st.rerun()


        if st.session_state.glob_sources:
            st.caption(f"**{len(st.session_state.glob_sources)} source(s) sélectionnée(s)** : {', '.join(st.session_state.glob_sources)}")

        limit = st.slider("Nombre de posts", 50, 1000, 200, 50, key="glob_limit")

        period_choice = st.selectbox(
            "Date de publication des posts",
            ["Toutes les dates", "7 derniers jours", "30 derniers jours", "Personnalisé"],
            key="glob_period"
        )
        date_from_global = None
        date_to_global = None
        if period_choice == "7 derniers jours":
            date_to_global = date.today()
            date_from_global = date_to_global - timedelta(days=7)
        elif period_choice == "30 derniers jours":
            date_to_global = date.today()
            date_from_global = date_to_global - timedelta(days=30)
        elif period_choice == "Personnalisé":
            d1, d2 = st.columns(2)
            with d1:
                date_from_global = st.date_input("Du", value=date.today() - timedelta(days=30), key="glob_date_from")
            with d2:
                date_to_global = st.date_input("Au", value=date.today(), key="glob_date_to")

        st.markdown("---")
        st.markdown("#### Modèle NLP")
        st.caption("Choisissez le modèle pour l'analyse de sentiment.")
        
        # Initialiser le modèle sélectionné
        if "glob_model" not in st.session_state:
            st.session_state.glob_model = "FinBERT"
        
        # Boutons modèle + bouton lancer
        m1, m2, m3 = st.columns([1, 1, 2])
        with m1:
            if st.button(
                "FinBERT",
                key="btn_finbert",
                use_container_width=True,
                type="primary" if st.session_state.glob_model == "FinBERT" else "secondary"
            ):
                st.session_state.glob_model = "FinBERT"
                st.rerun()
        with m2:
            if st.button(
                "CryptoBERT",
                key="btn_cryptobert",
                use_container_width=True,
                type="primary" if st.session_state.glob_model == "CryptoBERT" else "secondary"
            ):
                st.session_state.glob_model = "CryptoBERT"
                st.rerun()
        with m3:
            run_global = st.button("Lancer l'analyse", type="primary", key="glob_run", use_container_width=True)
        
        model = st.session_state.glob_model

        if run_global:
            src = st.session_state.glob_sources if st.session_state.glob_sources else None
            posts = get_all_posts(
                source=src, limit=limit,
                date_from=date_from_global, date_to=date_to_global
            )
            
            if not posts:
                st.error("Aucun post trouvé.")
            else:
                tok, mod, analyze_fn = get_model(model)
                results = []
                bar = st.progress(0, text="Analyse...")
                
                for i, p in enumerate(posts):
                    text = clean_text((p.get("title") or p.get("text") or "").strip())
                    if text and len(text) >= 5:
                        out = analyze_fn(text, tok, mod)
                        results.append({
                            "Texte": text[:100] + "…" if len(text) > 100 else text,
                            "Score": out["score"],
                            "Label": out["label"]
                        })
                    bar.progress((i + 1) / len(posts))
                bar.empty()
                
                if results:
                    df = pd.DataFrame(results)
                    mean_score = df["Score"].mean()
                    st.success(f"{len(results)} posts analysés")

                    m1, m2, m3 = st.columns(3)
                    with m1:
                        render_metric_card("Score moyen", f"{mean_score:+.3f}")
                    with m2:
                        bullish = (df["Label"] == "Bullish").sum()
                        render_metric_card("Bullish", f"{bullish} ({100 * bullish / len(df):.0f} %)")
                    with m3:
                        bearish = (df["Label"] == "Bearish").sum()
                        render_metric_card("Bearish", f"{bearish} ({100 * bearish / len(df):.0f} %)")

                    fig = px.histogram(df, x="Score", color="Label",
                                       color_discrete_map={"Bullish": "#22c55e", "Bearish": "#ef4444", "Neutral": "#6b7280"},
                                       nbins=25)
                    fig.update_layout(
                        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                        font_color="#e0e7ff", height=300,
                        xaxis=dict(gridcolor="rgba(255,255,255,0.1)"),
                        yaxis=dict(gridcolor="rgba(255,255,255,0.1)")
                    )
                    st.plotly_chart(fig, use_container_width=True)
                    st.dataframe(df, use_container_width=True, height=300)

                    st.markdown("---")
                    st.markdown("**💡 Interprétation** — Un score moyen positif indique un sentiment plutôt haussier ; négatif, plutôt baissier. La répartition Bullish / Bearish / Neutral donne le consensus. FinBERT est plus généraliste, CryptoBERT est entraîné sur du texte crypto.")
                else:
                    st.warning("Aucun texte exploitable.")

    # === MODE PAR CRYPTO ===
    else:
        st.markdown("Comparez le **sentiment par crypto** : les posts contenant les mots-clés de chaque actif sont analysés séparément.")
        st.markdown("#### Paramètres")

        # Initialiser les cryptos sélectionnées
        if "selected_cryptos" not in st.session_state:
            st.session_state.selected_cryptos = ["Bitcoin", "Ethereum"]

        st.markdown("**Crypto(s)** — Cliquez sur une bulle pour l'ajouter ou la retirer.")
        crypto_cols = st.columns(4)
        crypto_names = list(cryptos.keys())
        for i, name in enumerate(crypto_names):
            with crypto_cols[i]:
                is_selected = name in st.session_state.selected_cryptos
                icon = cryptos[name]["icon"]
                if st.button(
                    f"{icon} {name}",
                    key=f"crypto_btn_{name}",
                    use_container_width=True,
                    type="primary" if is_selected else "secondary"
                ):
                    if name in st.session_state.selected_cryptos:
                        st.session_state.selected_cryptos = [c for c in st.session_state.selected_cryptos if c != name]
                    else:
                        st.session_state.selected_cryptos = st.session_state.selected_cryptos + [name]
                    st.rerun()
        
        selected = st.session_state.selected_cryptos
        if selected:
            st.caption(f"**{len(selected)} crypto(s) sélectionnée(s)** : {', '.join(selected)}")

        limit_crypto = st.slider("Posts max", 100, 1000, 300, 50, key="crypto_limit")

        period_crypto = st.selectbox(
            "Date de publication des posts",
            ["Toutes les dates", "7 derniers jours", "30 derniers jours", "Personnalisé"],
            key="crypto_period"
        )
        date_from_crypto = None
        date_to_crypto = None
        if period_crypto == "7 derniers jours":
            date_to_crypto = date.today()
            date_from_crypto = date_to_crypto - timedelta(days=7)
        elif period_crypto == "30 derniers jours":
            date_to_crypto = date.today()
            date_from_crypto = date_to_crypto - timedelta(days=30)
        elif period_crypto == "Personnalisé":
            d1, d2 = st.columns(2)
            with d1:
                date_from_crypto = st.date_input("Du", value=date.today() - timedelta(days=30), key="crypto_date_from")
            with d2:
                date_to_crypto = st.date_input("Au", value=date.today(), key="crypto_date_to")
        
        st.markdown("---")
        st.markdown("#### Modèle NLP")
        st.caption("Choisissez le modèle pour l'analyse de sentiment.")
        
        # Initialiser le modèle sélectionné pour le mode crypto
        if "crypto_model" not in st.session_state:
            st.session_state.crypto_model = "FinBERT"
        
        # Boutons modèle + bouton lancer (même layout que Analyse globale)
        m1, m2, m3 = st.columns([1, 1, 2])
        with m1:
            if st.button(
                "FinBERT",
                key="btn_crypto_finbert",
                use_container_width=True,
                type="primary" if st.session_state.crypto_model == "FinBERT" else "secondary"
            ):
                st.session_state.crypto_model = "FinBERT"
                st.rerun()
        with m2:
            if st.button(
                "CryptoBERT",
                key="btn_crypto_cryptobert",
                use_container_width=True,
                type="primary" if st.session_state.crypto_model == "CryptoBERT" else "secondary"
            ):
                st.session_state.crypto_model = "CryptoBERT"
                st.rerun()
        with m3:
            run_crypto = st.button("Lancer la comparaison", type="primary", key="crypto_run", use_container_width=True)
        
        model_crypto = st.session_state.crypto_model

        if run_crypto:
            if not selected:
                st.warning("Sélectionnez au moins une crypto.")
            else:
                posts = get_all_posts(
                    limit=limit_crypto,
                    date_from=date_from_crypto, date_to=date_to_crypto
                )
                if not posts:
                    st.error("Aucun post en base.")
                else:
                    tok, mod, analyze_fn = get_model(model_crypto)
                    results = []
                    bar = st.progress(0, text="Analyse...")
                    
                    for i, name in enumerate(selected):
                        kw = cryptos[name]["keywords"]
                        subset = [p for p in posts if any(k in ((p.get("title") or "") + " " + (p.get("text") or "")).lower() for k in kw)]
                        
                        scores = []
                        for p in subset:
                            text = clean_text((p.get("title") or p.get("text") or "").strip())
                            if text and len(text) >= 5:
                                out = analyze_fn(text, tok, mod)
                                scores.append(out["score"])
                        
                        avg = sum(scores) / len(scores) if scores else None
                        results.append({
                            "Crypto": f"{cryptos[name]['icon']} {name}",
                            "Posts": len(scores),
                            "Score": avg
                        })
                        bar.progress((i + 1) / len(selected))
                    bar.empty()
                    
                    df = pd.DataFrame(results)
                    st.success(f"{len(selected)} cryptos analysées")

                    plot_df = df[df["Score"].notna()].copy()
                    if not plot_df.empty:
                        fig = px.bar(plot_df, x="Crypto", y="Score",
                                     color="Score",
                                     color_continuous_scale=["#ef4444", "#6b7280", "#22c55e"],
                                     color_continuous_midpoint=0)
                        fig.update_layout(
                            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                            font_color="#e0e7ff", height=350,
                            xaxis=dict(gridcolor="rgba(255,255,255,0.1)"),
                            yaxis=dict(gridcolor="rgba(255,255,255,0.1)", title="Score moyen"),
                            showlegend=False
                        )
                        st.plotly_chart(fig, use_container_width=True)

                    st.dataframe(
                        df.assign(Score=df["Score"].apply(lambda x: f"{x:+.3f}" if x is not None and not (isinstance(x, float) and np.isnan(x)) else "—")),
                        use_container_width=True,
                        hide_index=True
                    )

                    st.markdown("---")
                    st.markdown("**💡 Interprétation** — Un score plus élevé pour une crypto reflète un discours plus haussier dans les posts qui la mentionnent. Le nombre de « Posts » par crypto dépend du volume de discussions ; une crypto peu mentionnée peut donner un score basé sur peu d'occurrences.")


# ============ PAGE SCRAPING ============

def page_scraping():
    """Page dédiée au scraping de données"""
    st.markdown("""
    <div style="margin-bottom: 1.5rem;">
        <h2 style="font-size: 1.8rem; font-weight: 600; color: #e0e7ff; margin-bottom: 0.3rem;">Data Scraper</h2>
        <p style="color: #64748b; font-size: 0.9rem;">Collecte de données multi-sources</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Sources avec icônes (max = max des limites par méthode pour chaque plateforme)
    _max_for = lambda name: max(LIMITS[name].values()) if name in LIMITS else 500
    sources = {
        "Reddit": {"icon": "🔴", "max": _max_for("Reddit"), "desc": "Subreddits crypto"},
        "Twitter": {"icon": "🐦", "max": _max_for("Twitter"), "desc": "Recherche avancée"},
        "YouTube": {"icon": "▶️", "max": _max_for("YouTube"), "desc": "Commentaires vidéos"},
        "Telegram": {"icon": "✈️", "max": _max_for("Telegram"), "desc": "Channels publics"},
        "StockTwits": {"icon": "📈", "max": _max_for("StockTwits"), "desc": "Labels inclus (scroll amélioré)"},
        "Bluesky": {"icon": "🦋", "max": _max_for("Bluesky"), "desc": "Recherche AT Protocol"},
        "Bitcointalk": {"icon": "💭", "max": _max_for("Bitcointalk"), "desc": "Forum historique"},
        "GitHub": {"icon": "💻", "max": _max_for("GitHub"), "desc": "Issues/Discussions"},
        "4chan": {"icon": "💬", "max": _max_for("4chan"), "desc": "HTTP /biz/ (pas Selenium)"},
    }
    
    # Sélection de la source - 3 plateformes par ligne
    if 'scrape_source' not in st.session_state:
        st.session_state.scrape_source = "Reddit"
    if 'show_more_platforms' not in st.session_state:
        st.session_state.show_more_platforms = False
    
    sources_list = list(sources.items())
    num_rows = (len(sources_list) + 2) // 3  # Arrondir vers le haut (3 par ligne)
    
    # Afficher les 2 premières lignes (6 plateformes)
    st.markdown('<div style="margin-bottom: 4px;"></div>', unsafe_allow_html=True)
    for row in range(2):
        cols = st.columns(3)
        for col_idx in range(3):
            source_idx = row * 3 + col_idx
            if source_idx < len(sources_list):
                name, info = sources_list[source_idx]
                with cols[col_idx]:
                    selected = st.session_state.scrape_source == name
                    border_color = "#6366f1" if selected else "rgba(100,100,140,0.3)"
                    bg = "rgba(99, 102, 241, 0.1)" if selected else "rgba(30, 30, 50, 0.5)"
                    st.markdown(f"""
                    <div style="
                        background: {bg};
                        border: 2px solid {border_color};
                        border-radius: 12px;
                        padding: 14px 10px;
                        text-align: center;
                        min-height: 100px;
                    ">
                        <div style="font-size: 1.5rem;">{info['icon']}</div>
                        <div style="font-weight: 600; color: {'#fff' if selected else '#a5b4fc'}; margin-top: 4px;">{name}</div>
                        <div style="font-size: 0.7rem; color: #64748b; margin-top: 2px;">{info['desc']}</div>
                        <div style="font-size: 0.65rem; color: #475569; margin-top: 2px;">{info['max']} max</div>
                    </div>
                    """, unsafe_allow_html=True)
                    btn_label = "Actif" if selected else "Sélectionner"
                    if st.button(btn_label, key=f"src_{name}", use_container_width=True, disabled=selected):
                        st.session_state.scrape_source = name
                        st.session_state.pop('scrape_results', None)
                        st.rerun()
    
    # Bouton "Voir plus" / "Voir moins" et plateformes masquées
    if num_rows > 2:
        if st.session_state.show_more_platforms:
            # D'abord les 3 cartes, puis le bouton "Voir moins" en bas
            st.markdown('<div style="margin-top: 10px; margin-bottom: 4px;"></div>', unsafe_allow_html=True)
            for row in range(2, num_rows):
                cols = st.columns(3)
                for col_idx in range(3):
                    source_idx = row * 3 + col_idx
                    if source_idx < len(sources_list):
                        name, info = sources_list[source_idx]
                        with cols[col_idx]:
                            selected = st.session_state.scrape_source == name
                            border_color = "#6366f1" if selected else "rgba(100,100,140,0.3)"
                            bg = "rgba(99, 102, 241, 0.1)" if selected else "rgba(30, 30, 50, 0.5)"
                            st.markdown(f"""
                            <div style="
                                background: {bg};
                                border: 2px solid {border_color};
                                border-radius: 12px;
                                padding: 14px 10px;
                                text-align: center;
                                min-height: 100px;
                            ">
                                <div style="font-size: 1.5rem;">{info['icon']}</div>
                                <div style="font-weight: 600; color: {'#fff' if selected else '#a5b4fc'}; margin-top: 4px;">{name}</div>
                                <div style="font-size: 0.7rem; color: #64748b; margin-top: 2px;">{info['desc']}</div>
                                <div style="font-size: 0.65rem; color: #475569; margin-top: 2px;">{info['max']} max</div>
                            </div>
                            """, unsafe_allow_html=True)
                            btn_label = "Actif" if selected else "Sélectionner"
                            if st.button(btn_label, key=f"src_{name}_more", use_container_width=True, disabled=selected):
                                st.session_state.scrape_source = name
                                st.session_state.pop('scrape_results', None)
                                st.rerun()
            # Bouton "Voir moins" en bas — pleine largeur, style discret (CSS .toggle-platforms-zone)
            st.markdown('<div class="toggle-platforms-zone" style="margin-top: 10px; margin-bottom: 6px;"></div>', unsafe_allow_html=True)
            if st.button("▲ Voir moins", use_container_width=True, key="toggle_platforms",
                         help="Masquer Bitcointalk, GitHub, 4chan"):
                st.session_state.show_more_platforms = False
                st.rerun()
        else:
            # Quand replié : bouton "Voir plus" pleine largeur, style discret
            st.markdown('<div class="toggle-platforms-zone" style="margin-top: 12px; margin-bottom: 6px;"></div>', unsafe_allow_html=True)
            if st.button("▼ Voir plus", use_container_width=True, key="toggle_platforms",
                         help="Afficher Bitcointalk, GitHub, 4chan"):
                st.session_state.show_more_platforms = True
                st.rerun()
    
    st.markdown("---")
    
    # Configuration selon la source
    source = st.session_state.scrape_source
    
    st.markdown(f"### Configuration {source}")
    
    if source == "Reddit":
        c1, c2 = st.columns(2)
        with c1:
            crypto = st.selectbox("Cryptomonnaie", list(CRYPTO_LIST.keys()), key="scr_crypto")
        with c2:
            limit = st.slider("Nombre de posts", 10, 1000, 100, key="scr_limit")
        
        # Sélecteurs de date
        st.markdown("**Filtres de date (optionnel)**")
        c3, c4 = st.columns(2)
        with c3:
            start_date = st.date_input("Date de début", value=None, key="scr_reddit_start")
        with c4:
            end_date = st.date_input("Date de fin", value=None, key="scr_reddit_end")
        
        st.info("**Méthode :** API HTTP. Récupération des posts par subreddit avec filtres de date optionnels.")
        
        if st.button("Lancer le scraping", type="primary", use_container_width=True, key="scr_btn"):
            config = CRYPTO_LIST[crypto]
            
            # Validation des dates
            today = date.today()
            if start_date and start_date > today:
                st.error("⚠️ La date de début ne peut pas être dans le futur")
                st.stop()
            if end_date and end_date > today:
                st.warning("⚠️ La date de fin est dans le futur. Les posts récents seront récupérés jusqu'à aujourd'hui.")
                end_date = today
            
            with st.spinner("Scraping Reddit en cours..."):
                posts = scrape_reddit(
                    config['sub'], limit, method='http',
                    start_date=start_date.strftime('%Y-%m-%d') if start_date else None,
                    end_date=end_date.strftime('%Y-%m-%d') if end_date else None
                )
            
            # Message d'aide si aucun post
            if not posts:
                if end_date and end_date < today:
                    st.warning(f"ℹ️ Aucun post récupéré. Les posts récents sont datés de {today.strftime('%Y-%m-%d')} ou après. La date de fin ({end_date.strftime('%Y-%m-%d')}) est dans le passé. Essayez de mettre la date de fin à aujourd'hui ou laissez-la vide pour récupérer les posts récents.")
                elif start_date:
                    st.warning(f"ℹ️ Aucun post récupéré dans la plage {start_date.strftime('%Y-%m-%d')} - {end_date.strftime('%Y-%m-%d') if end_date else 'aujourd\'hui'}. Les scrapers récupèrent d'abord les posts les plus récents.")
                else:
                    st.error("❌ Aucun post récupéré. Vérifiez le nom du subreddit et votre connexion.")
            
            st.session_state.scrape_results = {"posts": posts, "source": "reddit", "crypto": crypto}
    
    elif source == "Twitter":
        c1, c2 = st.columns(2)
        with c1:
            crypto = st.selectbox("Cryptomonnaie", list(CRYPTO_LIST.keys()), key="scr_crypto")
            limit = st.slider("Nombre de tweets", 10, 2000, 100, key="scr_limit")
        with c2:
            sort_mode = st.selectbox("Tri", ["top", "live"], format_func=lambda x: "Populaires" if x == "top" else "Récents", key="scr_sort")
            min_likes = st.number_input("Minimum de likes", 0, 10000, 0, key="scr_likes")
        
        c1, c2 = st.columns(2)
        with c1:
            start_date = st.date_input("Date de début (optionnel)", value=None, key="scr_start")
        with c2:
            end_date = st.date_input("Date de fin (optionnel)", value=None, key="scr_end")
        
        st.info("**Méthode :** Selenium ou Nitter. Tri par popularité ou récents, filtre par nombre de likes.")
        
        if st.button("Lancer le scraping", type="primary", use_container_width=True, key="scr_btn"):
            config = CRYPTO_LIST[crypto]
            with st.spinner("Scraping Twitter en cours..."):
                try:
                    posts = scrape_twitter(
                        config.get('sub', crypto), limit,
                        min_likes=min_likes if min_likes > 0 else None,
                        start_date=start_date.strftime('%Y-%m-%d') if start_date else None,
                        end_date=end_date.strftime('%Y-%m-%d') if end_date else None,
                        sort_mode=sort_mode
                    )
                    if not posts:
                        st.warning("⚠️ Aucun tweet récupéré. Twitter peut bloquer le scraping. Vérifiez les logs dans le terminal.")
                    else:
                        st.success(f"✅ {len(posts)} tweets récupérés!")
                except Exception as e:
                    st.error(f"❌ Erreur lors du scraping Twitter: {e}")
                    st.info("💡 Conseils: Vérifiez que Chrome/ChromeDriver est installé, ou utilisez le mode Nitter (fallback automatique)")
                    posts = []
            st.session_state.scrape_results = {"posts": posts, "source": "twitter", "crypto": crypto}
    
    elif source == "YouTube":
        try:
            from app.scrapers.youtube_scraper import scrape_youtube
            api_key = os.environ.get('YOUTUBE_API_KEY', '')
            
            url = st.text_input("URL de la vidéo YouTube", placeholder="https://youtube.com/watch?v=...", key="scr_url")
            
            c1, c2 = st.columns(2)
            with c1:
                yt_max = max(LIMITS["YouTube"].values())
                limit = st.slider("Nombre de commentaires", 10, yt_max, min(100, yt_max), key="scr_limit")
            with c2:
                order = st.selectbox("Tri", ["relevance", "time"], format_func=lambda x: "Populaires" if x == "relevance" else "Récents", key="scr_order")
            
            if api_key:
                st.success("Clé API YouTube configurée")
            else:
                st.warning("Clé API manquante - ajoutez YOUTUBE_API_KEY dans .env")
            
            st.info("**Méthode :** API YouTube. Commentaires de la vidéo, tri par pertinence ou date.")
            
            if st.button("Lancer le scraping", type="primary", use_container_width=True, key="scr_btn"):
                if not url:
                    st.error("Veuillez entrer une URL YouTube")
                else:
                    with st.spinner("Scraping YouTube en cours..."):
                        posts = scrape_youtube("", limit, method="api", video_url=url, order=order)
                    st.session_state.scrape_results = {"posts": posts, "source": "youtube", "crypto": "YouTube"}
        except ImportError:
            st.error("Module YouTube non disponible")
    
    elif source == "Telegram":
        c1, c2 = st.columns(2)
        with c1:
            channel = st.selectbox("Channel", list(TELEGRAM_CHANNELS.keys()), format_func=lambda x: f"@{x}", key="scr_channel")
        with c2:
            limit = st.slider("Nombre de messages", 10, 500, 100, key="scr_limit")
        
        st.caption(f"Description: {TELEGRAM_CHANNELS[channel]}")
        
        st.info("**Méthode :** Canaux publics (API). Récupération simple (< 30 msg) ou paginée pour plus de messages.")
        
        if st.button("Lancer le scraping", type="primary", use_container_width=True, key="scr_btn"):
            with st.spinner("Scraping Telegram en cours..."):
                try:
                    if limit > 30:
                        posts = scrape_telegram_paginated(channel, limit)
                    else:
                        posts = scrape_telegram_simple(channel, limit)
                    
                    if not posts:
                        st.warning(f"⚠️ Aucun message récupéré pour @{channel}")
                        st.info("**Note :** Seuls les canaux publics fonctionnels sont disponibles dans la liste.")
                    else:
                        for p in posts:
                            p['title'] = p.get('text', '')
                        st.session_state.scrape_results = {"posts": posts, "source": "telegram", "crypto": channel}
                except Exception as e:
                    st.error(f"❌ Erreur lors du scraping: {e}")
                    st.exception(e)
    
    elif source == "StockTwits":
        c1, c2 = st.columns(2)
        with c1:
            crypto = st.selectbox("Cryptomonnaie", list(CRYPTO_LIST.keys()), key="scr_crypto")
        with c2:
            max_limit = LIMITS["StockTwits"]["Selenium"]  # 1000 posts max
            limit = st.slider("Nombre de posts", 10, max_limit, min(100, max_limit), key="scr_limit")
        
        # Sélecteurs de date
        st.markdown("**Filtres de date (optionnel)**")
        c3, c4 = st.columns(2)
        with c3:
            start_date = st.date_input("Date de début", value=None, key="scr_stocktwits_start")
        with c4:
            end_date = st.date_input("Date de fin", value=None, key="scr_stocktwits_end")
        
        st.info("**Méthode :** Selenium (scroll). Les labels Bullish/Bearish sont inclus automatiquement.")
        
        if st.button("Lancer le scraping", type="primary", use_container_width=True, key="scr_btn"):
            config = CRYPTO_LIST[crypto]
            
            # Validation des dates
            today = date.today()
            if start_date and start_date > today:
                st.error("⚠️ La date de début ne peut pas être dans le futur")
                st.stop()
            if end_date and end_date > today:
                st.warning("⚠️ La date de fin est dans le futur. Les posts récents seront récupérés jusqu'à aujourd'hui.")
                end_date = today
            
            with st.spinner("Scraping StockTwits en cours..."):
                posts = scrape_stocktwits(
                    config['stocktwits'], limit,
                    start_date=start_date.strftime('%Y-%m-%d') if start_date else None,
                    end_date=end_date.strftime('%Y-%m-%d') if end_date else None
                )
            
            # Message d'aide si aucun post
            if not posts:
                if end_date and end_date < today:
                    st.warning(f"ℹ️ Aucun post récupéré. Les posts récents sont datés de {today.strftime('%Y-%m-%d')} ou après. La date de fin ({end_date.strftime('%Y-%m-%d')}) est dans le passé. Essayez de mettre la date de fin à aujourd'hui ou laissez-la vide pour récupérer les posts récents.")
                elif start_date:
                    st.warning(f"ℹ️ Aucun post récupéré dans la plage {start_date.strftime('%Y-%m-%d')} - {end_date.strftime('%Y-%m-%d') if end_date else 'aujourd\'hui'}. Les scrapers récupèrent d'abord les posts les plus récents.")
                else:
                    st.error("❌ Aucun post récupéré. Vérifiez votre connexion et que Selenium est installé.")
            
            st.session_state.scrape_results = {"posts": posts, "source": "stocktwits", "crypto": crypto}
    
    elif source == "4chan":
        c1, c2 = st.columns(2)
        with c1:
            crypto = st.selectbox("Cryptomonnaie", list(CRYPTO_LIST.keys()), key="scr_crypto")
        with c2:
            limit = st.slider("Nombre de posts", 10, 200, 50, key="scr_limit")
        
        st.info("**Méthode :** HTTP /biz/. Discussions anonymes, pas de login requis.")
        
        if st.button("Lancer le scraping", type="primary", use_container_width=True, key="scr_btn"):
            config = CRYPTO_LIST[crypto]
            with st.spinner("Scraping 4chan /biz/ en cours..."):
                query = config.get('sub', 'crypto').lower()
                posts = scrape_4chan_biz(query, limit)
            if posts:
                st.success(f"✅ {len(posts)} posts récupérés depuis 4chan /biz/")
            else:
                st.warning("⚠️ Aucun post récupéré")
            st.session_state.scrape_results = {"posts": posts, "source": "4chan", "crypto": crypto}
    
    elif source == "Bitcointalk":
        c1, c2 = st.columns(2)
        with c1:
            crypto = st.selectbox("Cryptomonnaie", list(CRYPTO_LIST.keys()), key="scr_crypto")
        with c2:
            limit = st.slider("Nombre de posts", 10, 200, 50, key="scr_limit")
        
        st.info("**Méthode :** HTTP. Forum crypto historique, pas de login requis.")
        
        if st.button("Lancer le scraping", type="primary", use_container_width=True, key="scr_btn"):
            config = CRYPTO_LIST[crypto]
            with st.spinner("Scraping Bitcointalk en cours..."):
                query = config.get('sub', 'crypto').lower()
                posts = scrape_bitcointalk(query, limit)
            if posts:
                st.success(f"✅ {len(posts)} posts récupérés depuis Bitcointalk")
            else:
                st.warning("⚠️ Aucun post récupéré")
            st.session_state.scrape_results = {"posts": posts, "source": "bitcointalk", "crypto": crypto}
    
    elif source == "GitHub":
        c1, c2 = st.columns(2)
        with c1:
            crypto = st.selectbox("Cryptomonnaie", list(CRYPTO_LIST.keys()), key="scr_crypto")
        with c2:
            limit = st.slider("Nombre de posts", 10, 200, 50, key="scr_limit")
        
        st.info("**Méthode :** API GitHub (gratuite). Issues et discussions de projets crypto.")
        
        if st.button("Lancer le scraping", type="primary", use_container_width=True, key="scr_btn"):
            config = CRYPTO_LIST[crypto]
            with st.spinner("Scraping GitHub Issues en cours..."):
                query = config.get('sub', 'crypto').lower()
                posts = scrape_github_discussions(query, limit)
            if posts:
                st.success(f"✅ {len(posts)} issues/discussions récupérées depuis GitHub")
            else:
                st.warning("⚠️ Aucun post récupéré")
            st.session_state.scrape_results = {"posts": posts, "source": "github", "crypto": crypto}
    
    elif source == "Bluesky":
        c1, c2 = st.columns(2)
        with c1:
            crypto = st.selectbox("Cryptomonnaie", list(CRYPTO_LIST.keys()), key="scr_crypto")
        with c2:
            limit = st.slider("Nombre de posts", 10, 200, 50, key="scr_limit")
        
        st.info("**Méthode :** AT Protocol (API). Configure BLUESKY_USERNAME et BLUESKY_APP_PASSWORD dans .env pour utiliser ton compte.")
        
        if st.button("Lancer le scraping", type="primary", use_container_width=True, key="scr_btn"):
            config = CRYPTO_LIST[crypto]
            with st.spinner("Scraping Bluesky en cours..."):
                query = config.get('sub', 'Bitcoin').lower()
                posts = scrape_bluesky(query, limit)
            if posts:
                st.success(f"✅ {len(posts)} posts récupérés depuis Bluesky")
            else:
                st.warning("⚠️ Aucun post récupéré. Vérifie BLUESKY_USERNAME et BLUESKY_APP_PASSWORD dans .env.")
            st.session_state.scrape_results = {"posts": posts, "source": "bluesky", "crypto": crypto}
    
    # Affichage des résultats
    st.markdown("---")
    
    if 'scrape_results' in st.session_state and st.session_state.scrape_results:
        data = st.session_state.scrape_results
        posts = data['posts']
        source_result = data.get('source', '')
        
        if not posts:
            if source_result == "bluesky":
                st.info("**Bluesky** : aucun post trouvé. Vérifie BLUESKY_USERNAME et BLUESKY_APP_PASSWORD dans .env.")
            else:
                st.error("Aucun post récupéré")
        else:
            # Stats
            labeled = sum(1 for p in posts if p.get('human_label'))
            with_score = sum(1 for p in posts if p.get('score', 0) > 0)
            
            st.markdown(f"""
            <div style="display: flex; gap: 16px; margin-bottom: 16px;">
                <div style="background: linear-gradient(135deg, rgba(99, 102, 241, 0.15), rgba(139, 92, 246, 0.1)); padding: 14px 24px; border-radius: 12px; border: 1px solid rgba(99, 102, 241, 0.3);">
                    <span style="font-size: 1.8rem; font-weight: 700; color: #a5b4fc;">{len(posts)}</span>
                    <span style="color: #94a3b8; font-size: 0.9rem; margin-left: 8px;">posts récupérés</span>
                </div>
                <div style="background: rgba(74, 222, 128, 0.1); padding: 14px 20px; border-radius: 12px; border: 1px solid rgba(74, 222, 128, 0.2);">
                    <span style="color: #4ade80; font-weight: 600;">{labeled}</span>
                    <span style="color: #64748b; font-size: 0.85rem;"> avec label</span>
                </div>
                <div style="background: rgba(251, 191, 36, 0.1); padding: 14px 20px; border-radius: 12px; border: 1px solid rgba(251, 191, 36, 0.2);">
                    <span style="color: #fbbf24; font-weight: 600;">{with_score}</span>
                    <span style="color: #64748b; font-size: 0.85rem;"> avec score</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Actions
            c1, c2, c3 = st.columns(3)
            with c1:
                if st.button("Sauvegarder en base", use_container_width=True, type="primary"):
                    result = save_posts(posts, source=data['source'], method="scraper")
                    st.success(f"{result['inserted']} posts sauvegardés")
            with c2:
                if st.button("Envoyer vers Analyse", use_container_width=True):
                    st.session_state['analyze_data'] = posts
                    st.info("Données prêtes pour l'analyse")
            with c3:
                csv_data = pd.DataFrame(posts).to_csv(index=False)
                st.download_button("Exporter CSV", csv_data, f"{data['source']}_data.csv", use_container_width=True)
            
            # Tableau
            st.markdown("<br>", unsafe_allow_html=True)
            
            def safe_date(val):
                if not val:
                    return '-'
                if isinstance(val, (int, float)):
                    try:
                        return datetime.fromtimestamp(val).strftime('%Y-%m-%d')
                    except:
                        return '-'
                return str(val)[:10] if len(str(val)) > 10 else str(val)
            
            df = pd.DataFrame([{
                "Texte": (p.get('title') or p.get('text', ''))[:100] + "..." if len(p.get('title') or p.get('text', '')) > 100 else (p.get('title') or p.get('text', '')),
                "Score": p.get('score', 0),
                "Label": p.get('human_label') or '-',
                "Auteur": (p.get('author') or '-')[:15],
                "Date": safe_date(p.get('created_utc'))
            } for p in posts[:50]])
            
            st.dataframe(df, use_container_width=True, height=400)
            
            if len(posts) > 50:
                st.caption(f"Affichage de 50 posts sur {len(posts)}")
    else:
        st.markdown("""
        <div style="
            display: flex; flex-direction: column; align-items: center; justify-content: center;
            padding: 60px 20px; background: rgba(30, 30, 50, 0.3); border-radius: 16px;
            border: 1px dashed rgba(99, 102, 241, 0.3);
        ">
            <div style="color: #64748b; font-size: 1rem;">Les résultats apparaîtront ici</div>
            <div style="color: #475569; font-size: 0.85rem; margin-top: 8px;">Sélectionnez une source et lancez le scraping</div>
        </div>
        """, unsafe_allow_html=True)


# ============ MAIN ============

def main():
    with st.sidebar:
        st.markdown("""
        <div style="text-align: center; padding: 1rem 0;">
            <div style="font-size: 2rem; color: #818cf8;">◈</div>
            <div style="font-weight: 700; color: #e0e7ff;">Crypto Sentiment</div>
            <div style="font-size: 0.75rem; color: #64748b;">MoSEF 2025-2026</div>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Dashboard masqué (page conservée dans le code)
        if st.session_state.get("nav_radio") == "Dashboard":
            st.session_state.nav_radio = "Accueil"
        if st.session_state.get("nav_radio") == "Méthodologie":
            st.session_state.nav_radio = "Documentation"
        page = st.radio(
            "Navigation",
            ["Accueil", "Scraping", "Données", "Analyses des résultats", "Documentation"],
            key="nav_radio",
            label_visibility="collapsed"
        )
    
    if "Accueil" in page:
        page_accueil()
    elif "Dashboard" in page:
        page_dashboard()
    elif "Scraping" in page:
        page_scraping()
    elif "Données" in page:
        page_stored_data()
    elif "Analyses des résultats" in page:
        page_analyses_resultats()
    elif "Documentation" in page:
        page_documentation()


if __name__ == "__main__":
    main()
