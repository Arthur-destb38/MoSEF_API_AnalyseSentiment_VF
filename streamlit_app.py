"""
Crypto Sentiment Dashboard
Projet MoSEF 2024-2025
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.scrapers import scrape_reddit, scrape_stocktwits, get_reddit_limits, get_stocktwits_limits
from app.nlp import load_finbert, load_cryptobert, analyze_finbert, analyze_cryptobert
from app.utils import clean_text
from app.prices import get_historical_prices, CryptoPrices
from app.storage import save_posts, get_all_posts, export_to_csv, export_to_json, get_stats

try:
    from econometrics import run_full_analysis, run_demo_analysis
    ECONO_OK = True
except ImportError:
    ECONO_OK = False

# ============ PAGE CONFIG ============

st.set_page_config(
    page_title="Crypto Sentiment",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="expanded"
)

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
</style>
""", unsafe_allow_html=True)

# ============ CONFIG ============

CRYPTO_LIST = {
    "Bitcoin": {"id": "bitcoin", "sub": "Bitcoin", "stocktwits": "BTC.X", "icon": "₿"},
    "Ethereum": {"id": "ethereum", "sub": "ethereum", "stocktwits": "ETH.X", "icon": "Ξ"},
    "Solana": {"id": "solana", "sub": "solana", "stocktwits": "SOL.X", "icon": "◎"},
    "Cardano": {"id": "cardano", "sub": "cardano", "stocktwits": "ADA.X", "icon": "₳"},
    "Dogecoin": {"id": "dogecoin", "sub": "dogecoin", "stocktwits": "DOGE.X", "icon": "Ð"},
    "XRP": {"id": "ripple", "sub": "xrp", "stocktwits": "XRP.X", "icon": "✕"},
}

LIMITS = {
    "Reddit": {"HTTP": get_reddit_limits()["http"], "Selenium": get_reddit_limits()["selenium"]},
    "StockTwits": {"Selenium": get_stocktwits_limits()["selenium"]}
}

# ============ CACHE ============

@st.cache_resource
def get_finbert():
    return load_finbert()

@st.cache_resource
def get_cryptobert():
    return load_cryptobert()

@st.cache_data(ttl=300)
def get_prices():
    client = CryptoPrices()
    return client.get_multiple_prices(["bitcoin", "ethereum", "solana", "cardano", "dogecoin"])

def get_model(name):
    if name == "FinBERT":
        tok, mod = get_finbert()
        return tok, mod, analyze_finbert
    else:
        tok, mod = get_cryptobert()
        return tok, mod, analyze_cryptobert

def scrape_data(source, config, limit, method):
    if source == "Reddit":
        posts = scrape_reddit(config['sub'], limit, method=method.lower())
        # 💾 Sauvegarde automatique
        save_posts(posts, source="reddit", method=method.lower())
        return posts
    else:
        posts = scrape_stocktwits(config['stocktwits'], limit)
        # 💾 Sauvegarde automatique
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
        
        source = st.radio("Source", ["Reddit", "StockTwits"], horizontal=True, key="dash_source")
        
        if source == "Reddit":
            method = st.radio("Méthode", ["HTTP", "Selenium"], horizontal=True, key="dash_method")
            max_limit = LIMITS["Reddit"][method]
        else:
            method = "Selenium"
            max_limit = LIMITS["StockTwits"]["Selenium"]
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
    
    with col2:
        if analyze:
            run_analysis(crypto, config, source, method, model, limit)
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


def run_analysis(crypto, config, source, method, model, limit):
    with st.spinner(f"Scraping {source}..."):
        posts = scrape_data(source, config, limit, method)
    
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


def page_compare():
    render_header()
    st.markdown("### Comparaison FinBERT vs CryptoBERT")
    
    col1, col2 = st.columns([1, 3])
    
    with col1:
        crypto = st.selectbox("Crypto", list(CRYPTO_LIST.keys()), key="cmp_crypto")
        config = CRYPTO_LIST[crypto]
        
        source = st.radio("Source", ["Reddit", "StockTwits"], key="cmp_source")
        
        if source == "Reddit":
            method = st.radio("Méthode", ["HTTP", "Selenium"], key="cmp_method")
            max_limit = LIMITS["Reddit"][method]
        else:
            method = "Selenium"
            max_limit = LIMITS["StockTwits"]["Selenium"]
        
        limit = st.slider("Posts", 20, max_limit, min(50, max_limit), key="cmp_limit")
        run = st.button("Comparer", use_container_width=True, key="cmp_run")
    
    with col2:
        if run:
            with st.spinner("Scraping..."):
                posts = scrape_data(source, config, limit, method)
            
            if not posts:
                st.error("Aucun post")
                return
            
            with st.spinner("Analyse..."):
                fin_tok, fin_mod, _ = get_model("FinBERT")
                cry_tok, cry_mod, _ = get_model("CryptoBERT")
                
                results = []
                progress = st.progress(0)
                
                for i, post in enumerate(posts):
                    text = clean_text(post["title"])
                    if not text:
                        continue
                    
                    fin = analyze_finbert(text, fin_tok, fin_mod)
                    cry = analyze_cryptobert(text, cry_tok, cry_mod)
                    
                    results.append({
                        "text": text[:50],
                        "human_label": post.get("human_label"),
                        "finbert_score": fin["score"],
                        "finbert_label": fin["label"],
                        "cryptobert_score": cry["score"],
                        "cryptobert_label": cry["label"]
                    })
                    progress.progress((i + 1) / len(posts))
            
            df = pd.DataFrame(results)
            
            cols = st.columns(2)
            with cols[0]:
                render_metric_card("FinBERT", f"{df['finbert_score'].mean():+.3f}")
            with cols[1]:
                render_metric_card("CryptoBERT", f"{df['cryptobert_score'].mean():+.3f}")
            
            labeled = df[df['human_label'].notna()]
            if len(labeled) > 0:
                fin_acc = (labeled['finbert_label'] == labeled['human_label']).mean() * 100
                cry_acc = (labeled['cryptobert_label'] == labeled['human_label']).mean() * 100
                
                st.markdown("### Accuracy vs labels humains")
                cols = st.columns(2)
                with cols[0]:
                    render_metric_card("FinBERT", f"{fin_acc:.1f}%")
                with cols[1]:
                    render_metric_card("CryptoBERT", f"{cry_acc:.1f}%")
                
                winner = "CryptoBERT" if cry_acc > fin_acc else "FinBERT"
                diff = abs(cry_acc - fin_acc)
                st.markdown(f"""
                <div class="success-box">
                    <strong>{winner} gagne!</strong> (+{diff:.1f}%)
                </div>
                """, unsafe_allow_html=True)
            
            fig = px.scatter(df, x='finbert_score', y='cryptobert_score', color_discrete_sequence=['#8b5cf6'])
            fig.add_hline(y=0, line_dash="dash", line_color="#64748b")
            fig.add_vline(x=0, line_dash="dash", line_color="#64748b")
            fig.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font=dict(color='white'),
                xaxis=dict(gridcolor='rgba(255,255,255,0.1)', title="FinBERT"),
                yaxis=dict(gridcolor='rgba(255,255,255,0.1)', title="CryptoBERT"),
                height=400
            )
            st.plotly_chart(fig, use_container_width=True)


def page_multi():
    render_header()
    st.markdown("### Analyse Multi-Crypto Comparative")
    
    col1, col2 = st.columns([1, 3])
    
    with col1:
        selected = st.multiselect("Cryptos", list(CRYPTO_LIST.keys()),
                                  default=["Bitcoin", "Ethereum", "Solana"], key="multi_crypto")
        
        source = st.radio("Source", ["Reddit", "StockTwits"], key="multi_source")
        
        if source == "Reddit":
            method = st.radio("Méthode", ["HTTP", "Selenium"], key="multi_method")
            max_limit = LIMITS["Reddit"][method]
        else:
            method = "Selenium"
            max_limit = LIMITS["StockTwits"]["Selenium"]
        
        model = st.radio("Modèle", ["FinBERT", "CryptoBERT"], key="multi_model")
        
        # Limite adaptée au nombre de cryptos (éviter les bans)
        nb_cryptos = len(selected) if selected else 1
        safe_limit = min(max_limit, max(20, 200 // nb_cryptos))  # Répartir pour éviter ban
        
        limit = st.slider("Posts/crypto", 20, max_limit, safe_limit, key="multi_limit")
        
        # Warning si risque de ban
        total_posts = limit * nb_cryptos
        st.markdown(f"""
        <div class="info-box">
            <strong>Total estimé:</strong> {total_posts} posts<br>
            <small>Limite {source}: {max_limit}/crypto</small>
        </div>
        """, unsafe_allow_html=True)
        
        if total_posts > 500:
            st.markdown("""
            <div class="warning-box">
                <strong>Attention</strong><br>
                <small>Beaucoup de posts = risque de ban. Réduire si erreur.</small>
            </div>
            """, unsafe_allow_html=True)
        
        run = st.button("Analyser", use_container_width=True, key="multi_run")
    
    with col2:
        if run and selected:
            tokenizer, mod, analyze_fn = get_model(model)
            
            all_results = []
            all_posts_data = {}  # Stocker tous les posts pour détails
            progress = st.progress(0)
            status = st.empty()
            
            for i, name in enumerate(selected):
                status.text(f"Scraping {name}...")
                config = CRYPTO_LIST[name]
                posts = scrape_data(source, config, limit, method)
                
                if posts:
                    scores = []
                    labels = {"Bullish": 0, "Bearish": 0, "Neutral": 0}
                    post_details = []
                    correct = 0
                    labeled_count = 0
                    
                    for post in posts:
                        text = clean_text(post["title"])
                        if text:
                            s = analyze_fn(text, tokenizer, mod)
                            scores.append(s["score"])
                            labels[s["label"]] += 1
                            
                            # Accuracy si StockTwits
                            if post.get("human_label"):
                                labeled_count += 1
                                if s["label"] == post["human_label"]:
                                    correct += 1
                            
                            post_details.append({
                                "text": text[:50],
                                "score": s["score"],
                                "label": s["label"],
                                "human_label": post.get("human_label")
                            })
                    
                    accuracy = round(correct / labeled_count * 100, 1) if labeled_count > 0 else None
                    
                    all_results.append({
                        "Crypto": name,
                        "Posts": len(scores),
                        "Sentiment": round(np.mean(scores), 4) if scores else 0,
                        "Std": round(np.std(scores), 4) if scores else 0,
                        "Bullish": labels["Bullish"],
                        "Bearish": labels["Bearish"],
                        "Neutral": labels["Neutral"],
                        "Bullish%": round(labels["Bullish"] / len(scores) * 100, 1) if scores else 0,
                        "Accuracy": accuracy
                    })
                    all_posts_data[name] = post_details
                
                progress.progress((i + 1) / len(selected))
            
            status.empty()
            
            if not all_results:
                st.error("Aucun résultat")
                return
            
            df = pd.DataFrame(all_results)
            
            # === METRIQUES GLOBALES ===
            st.markdown("### Vue d'ensemble")
            
            best_crypto = df.loc[df["Sentiment"].idxmax(), "Crypto"]
            worst_crypto = df.loc[df["Sentiment"].idxmin(), "Crypto"]
            avg_sentiment = df["Sentiment"].mean()
            
            cols = st.columns(4)
            with cols[0]:
                render_metric_card("Cryptos analysées", len(df))
            with cols[1]:
                render_metric_card("Sentiment moyen", f"{avg_sentiment:+.3f}")
            with cols[2]:
                render_metric_card("Plus haussier", best_crypto, f"{df.loc[df['Crypto']==best_crypto, 'Sentiment'].values[0]:+.3f}", "positive")
            with cols[3]:
                render_metric_card("Plus baissier", worst_crypto, f"{df.loc[df['Crypto']==worst_crypto, 'Sentiment'].values[0]:+.3f}", "negative")
            
            # === GRAPHIQUE COMPARATIF ===
            st.markdown("### Comparaison des sentiments")
            
            fig = go.Figure(data=[go.Bar(
                x=df["Crypto"],
                y=df["Sentiment"],
                marker=dict(
                    color=df["Sentiment"],
                    colorscale=[[0, '#f87171'], [0.5, '#64748b'], [1, '#4ade80']],
                    cmin=-0.5,
                    cmax=0.5
                ),
                text=[f"{s:+.3f}" for s in df["Sentiment"]],
                textposition='outside',
                textfont=dict(color='white')
            )])
            fig.add_hline(y=0, line_dash="dash", line_color="#64748b")
            fig.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font=dict(color='white'),
                xaxis=dict(gridcolor='rgba(255,255,255,0.1)'),
                yaxis=dict(gridcolor='rgba(255,255,255,0.1)', title="Sentiment Score"),
                height=350,
                margin=dict(t=30, b=30)
            )
            st.plotly_chart(fig, use_container_width=True)
            
            # === DISTRIBUTION PAR CRYPTO ===
            st.markdown("### Distribution Bullish/Bearish/Neutral")
            
            cols = st.columns(min(len(df), 3))
            for i, row in df.iterrows():
                with cols[i % 3]:
                    fig = go.Figure(data=[go.Pie(
                        labels=["Bullish", "Bearish", "Neutral"],
                        values=[row["Bullish"], row["Bearish"], row["Neutral"]],
                        hole=0.5,
                        marker=dict(colors=['#4ade80', '#f87171', '#64748b']),
                        textinfo='percent',
                        textfont=dict(size=11, color='white')
                    )])
                    fig.update_layout(
                        paper_bgcolor='rgba(0,0,0,0)',
                        plot_bgcolor='rgba(0,0,0,0)',
                        font=dict(color='white'),
                        showlegend=False,
                        title=dict(text=row["Crypto"], font=dict(size=14)),
                        margin=dict(t=40, b=20, l=20, r=20),
                        height=200
                    )
                    st.plotly_chart(fig, use_container_width=True)
            
            # === TABLEAU DETAILLE ===
            st.markdown("### Détails par crypto")
            
            display_df = df[["Crypto", "Posts", "Sentiment", "Std", "Bullish%", "Accuracy"]].copy()
            display_df.columns = ["Crypto", "Posts", "Sentiment", "Écart-type", "% Bullish", "Accuracy"]
            display_df["Accuracy"] = display_df["Accuracy"].apply(lambda x: f"{x}%" if x else "-")
            
            st.dataframe(display_df, use_container_width=True)
            
            # === DETAILS PAR CRYPTO (expandable) ===
            st.markdown("### Analyse détaillée par crypto")
            
            for name in selected:
                if name in all_posts_data:
                    with st.expander(f"{name} - {len(all_posts_data[name])} posts"):
                        crypto_df = pd.DataFrame(all_posts_data[name])
                        
                        # Stats
                        row = df[df["Crypto"] == name].iloc[0]
                        c1, c2, c3, c4 = st.columns(4)
                        c1.metric("Sentiment", f"{row['Sentiment']:+.3f}")
                        c2.metric("Bullish", f"{row['Bullish%']}%")
                        c3.metric("Bearish", f"{100 - row['Bullish%'] - (row['Neutral']/row['Posts']*100):.1f}%")
                        if row["Accuracy"]:
                            c4.metric("Accuracy", f"{row['Accuracy']}%")
                        
                        # Histogramme
                        fig = go.Figure(data=[go.Histogram(
                            x=crypto_df["score"],
                            nbinsx=20,
                            marker=dict(color='rgba(99, 102, 241, 0.7)')
                        )])
                        fig.add_vline(x=0, line_dash="dash", line_color="#64748b")
                        fig.update_layout(
                            paper_bgcolor='rgba(0,0,0,0)',
                            plot_bgcolor='rgba(0,0,0,0)',
                            font=dict(color='white'),
                            xaxis=dict(gridcolor='rgba(255,255,255,0.1)', title="Score"),
                            yaxis=dict(gridcolor='rgba(255,255,255,0.1)'),
                            height=200,
                            margin=dict(t=10, b=30)
                        )
                        st.plotly_chart(fig, use_container_width=True)
                        
                        # Table posts
                        st.dataframe(crypto_df, use_container_width=True, height=200)
            
            # === EXPORT ===
            st.markdown("---")
            col1, col2 = st.columns(2)
            with col1:
                st.download_button("Télécharger résumé CSV", df.to_csv(index=False), "multi_crypto_summary.csv", use_container_width=True)


def page_econometrie():
    render_header()
    st.markdown("### Analyse Économétrique")
    
    if not ECONO_OK:
        st.error("Module econometrics.py non disponible")
        return
    
    col1, col2 = st.columns([1, 3])
    
    with col1:
        # Mode selection
        mode = st.radio("Mode", ["Demo", "Données réelles"], key="eco_mode")
        
        if mode == "Demo":
            st.markdown("""
            <div class="info-box">
                <strong>Mode Demo</strong><br>
                <small>Données sentiment simulées sur 60 jours pour illustrer l'analyse</small>
            </div>
            """, unsafe_allow_html=True)
            crypto = st.selectbox("Crypto", list(CRYPTO_LIST.keys()), key="eco_crypto")
            config = CRYPTO_LIST[crypto]
        else:
            if 'results' not in st.session_state:
                st.markdown("""
                <div class="warning-box">
                    <strong>Aucune donnée</strong><br>
                    Lance d'abord une analyse sur le Dashboard
                </div>
                """, unsafe_allow_html=True)
                crypto = None
                config = None
            else:
                results = st.session_state['results']
                crypto = st.session_state.get('crypto', 'Bitcoin')
                config = st.session_state.get('config', CRYPTO_LIST['Bitcoin'])
                st.info(f"{len(results)} posts ({crypto})")
        
        days = st.slider("Jours historiques", 30, 90, 60)
        max_lag = st.slider("Lag max", 3, 10, 5)
        run = st.button("Analyser", use_container_width=True)
    
    with col2:
        if run:
            if mode == "Demo":
                with st.spinner("Analyse économétrique (demo)..."):
                    output = run_demo_analysis(config['id'], days, max_lag)
            else:
                if 'results' not in st.session_state:
                    st.error("Pas de données. Lance une analyse sur le Dashboard d'abord.")
                    return
                
                results = st.session_state['results']
                posts = [{"title": r.get("title", ""), "created_utc": r.get("created_utc")} for r in results]
                sent = [{"score": r.get("sentiment_score", 0), "label": r.get("sentiment_label", "Neutral")} for r in results]
                
                with st.spinner("Analyse économétrique..."):
                    output = run_full_analysis(posts, sent, config['id'], days, max_lag)
            
            if output["status"] == "error":
                st.error(output.get("error"))
                return
            
            # Badge mode demo
            if output.get("mode") == "demo":
                st.markdown("""
                <div style="background: rgba(139, 92, 246, 0.2); border: 1px solid #8b5cf6; padding: 10px; border-radius: 8px; margin-bottom: 16px; text-align: center;">
                    <strong style="color: #c4b5fd;">MODE DEMO</strong> - Données sentiment simulées
                </div>
                """, unsafe_allow_html=True)
            
            # Info données
            info = output.get("data_info", {})
            st.markdown(f"**Période:** {info.get('date_debut', 'N/A')} → {info.get('date_fin', 'N/A')} ({info.get('jours_merged', 0)} jours)")
            
            st.markdown("#### Tests de Stationnarité (ADF)")
            adf = output["adf_tests"]
            cols = st.columns(2)
            with cols[0]:
                s = adf.get("sentiment", {})
                status = "Stationnaire" if s.get("stationary") else "Non stationnaire"
                render_metric_card("Sentiment", status, f"p={s.get('pvalue', 'N/A')}")
            with cols[1]:
                r = adf.get("returns", {})
                status = "Stationnaire" if r.get("stationary") else "Non stationnaire"
                render_metric_card("Returns", status, f"p={r.get('pvalue', 'N/A')}")
            
            st.markdown("#### Causalité de Granger")
            granger = output.get("granger", {})
            if "error" not in granger:
                cols = st.columns(2)
                with cols[0]:
                    s2r = granger.get("sentiment_to_returns", {})
                    status = "Significatif" if s2r.get("significant") else "Non significatif"
                    render_metric_card("Sentiment → Prix", status, f"lag={s2r.get('best_lag', 'N/A')}")
                with cols[1]:
                    r2s = granger.get("returns_to_sentiment", {})
                    status = "Significatif" if r2s.get("significant") else "Non significatif"
                    render_metric_card("Prix → Sentiment", status, f"lag={r2s.get('best_lag', 'N/A')}")
            else:
                st.warning(f"Granger: {granger.get('error')}")
            
            # Cross-correlation
            cross = output.get("cross_corr", {})
            if cross.get("best_lag") is not None:
                st.markdown("#### Corrélation croisée")
                best_lag = cross.get("best_lag")
                best_corr = cross.get("best_correlation")
                if best_lag > 0:
                    interp = f"Sentiment précède les prix de {best_lag} jour(s)"
                elif best_lag < 0:
                    interp = f"Prix précèdent le sentiment de {-best_lag} jour(s)"
                else:
                    interp = "Relation contemporaine"
                render_metric_card("Meilleure corrélation", f"r = {best_corr}", interp)
            
            # Graphique sentiment vs returns
            if "merged_data" in output:
                merged = output["merged_data"]
                st.markdown("#### Évolution Sentiment vs Returns")
                
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=merged['date'], y=merged['sentiment_mean'],
                    name='Sentiment', line=dict(color='#8b5cf6', width=2)
                ))
                fig.add_trace(go.Scatter(
                    x=merged['date'], y=merged['log_return'] * 10,
                    name='Returns (x10)', line=dict(color='#4ade80', width=2)
                ))
                fig.update_layout(
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    font=dict(color='white'),
                    xaxis=dict(gridcolor='rgba(255,255,255,0.1)'),
                    yaxis=dict(gridcolor='rgba(255,255,255,0.1)'),
                    height=300,
                    margin=dict(t=20, b=40, l=40, r=20),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02)
                )
                st.plotly_chart(fig, use_container_width=True)
            
            st.markdown("#### Conclusion")
            conclusion_text = output.get("conclusion", "Analyse terminée").replace("\n", "<br>")
            st.markdown(f"""
            <div class="info-box">
                {conclusion_text}
            </div>
            """, unsafe_allow_html=True)


def page_methodo():
    render_header()
    st.markdown("### Méthodologie")
    
    tabs = st.tabs(["Sources", "Modèles", "Limites", "Références"])
    
    with tabs[0]:
        st.markdown("""
        | Source | Méthode | Max posts | Vitesse | Labels |
        |--------|---------|-----------|---------|--------|
        | Reddit | HTTP | 1000 | ~1-5s | Non |
        | Reddit | Selenium | 200 | ~10-30s | Non |
        | StockTwits | Selenium | 300 | ~10-30s | Oui (Bullish/Bearish) |
        
        **Note:** StockTwits utilise Cloudflare, seul Selenium fonctionne.
        """)
    
    with tabs[1]:
        st.markdown("""
        | Modèle | Entraîné sur | Labels |
        |--------|--------------|--------|
        | **FinBERT** | News financières | Positive/Negative/Neutral |
        | **CryptoBERT** | 3.2M posts crypto | Bullish/Bearish/Neutral |
        
        CryptoBERT: StockTwits (1.8M) + Telegram (664K) + Reddit (172K) + Twitter (496K)
        """)
    
    with tabs[2]:
        st.markdown("""
        **Pour éviter les bans:**
        - Reddit HTTP: max 1000 posts, 1 req/s
        - Reddit Selenium: max 200 posts
        - StockTwits: max 300 posts
        """)
    
    with tabs[3]:
        st.markdown("""
        - **FinBERT:** ProsusAI/finbert
        - **CryptoBERT:** ElKulako/cryptobert (IEEE Intelligent Systems 38(4), 2023)
        - Kraaijeveld & De Smedt (2020) - Predictive power of Twitter sentiment
        """)


# ============ PAGE DONNÉES STOCKÉES ============

def page_stored_data():
    render_header()
    st.markdown("### Données Stockées")
    
    # Récupérer les statistiques
    stats = get_stats()
    
    # Affichage des métriques
    col1, col2, col3 = st.columns(3)
    
    with col1:
        render_metric_card("Total Posts", f"{stats['total_posts']:,}")
    
    with col2:
        render_metric_card("Premier Scrape", stats['first_scrape'][:10] if stats['first_scrape'] else "N/A")
    
    with col3:
        render_metric_card("Dernier Scrape", stats['last_scrape'][:10] if stats['last_scrape'] else "N/A")
    
    st.markdown("---")
    
    # Répartition par source/méthode
    if stats['by_source_method']:
        st.markdown("#### Répartition par Source et Méthode")
        df_stats = pd.DataFrame(stats['by_source_method'])
        
        fig = px.bar(
            df_stats,
            x='source',
            y='count',
            color='method',
            barmode='group',
            title='Nombre de posts par source et méthode',
            color_discrete_sequence=['#818cf8', '#22d3ee']
        )
        fig.update_layout(
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font_color='#e0e7ff'
        )
        st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("---")
    
    # Filtres
    st.markdown("#### Consulter les Données")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        source_filter = st.selectbox("Source", ["Toutes", "reddit", "stocktwits"])
    with col2:
        method_filter = st.selectbox("Méthode", ["Toutes", "http", "selenium"])
    with col3:
        limit = st.number_input("Limite", min_value=10, max_value=1000, value=100)
    
    # Récupérer les données
    source = source_filter if source_filter != "Toutes" else None
    method = method_filter if method_filter != "Toutes" else None
    
    posts = get_all_posts(source=source, method=method, limit=limit)
    
    if posts:
        st.success(f"{len(posts)} posts trouvés")
        
        # Afficher en DataFrame
        df = pd.DataFrame(posts)
        st.dataframe(df, use_container_width=True)
        
        # Boutons d'export
        st.markdown("#### Exporter les Données")
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("Exporter en CSV"):
                csv_path = export_to_csv(source=source, method=method)
                st.success(f"Exporté vers: {csv_path}")
        
        with col2:
            if st.button("Exporter en JSON"):
                json_path = export_to_json(source=source, method=method)
                st.success(f"Exporté vers: {json_path}")
    else:
        st.warning("Aucune donnée trouvée avec ces filtres.")
    
    # Informations sur les fichiers
    st.markdown("---")
    st.markdown("#### Localisation des Fichiers")
    st.code(f"""
Base de données SQLite: {stats['db_path']}
Fichier JSONL: {stats['jsonl_path']}
Exports CSV/JSON: data/exports/
    """)


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
        
        page = st.radio(
            "Navigation",
            ["Dashboard", "Comparaison", "Multi-crypto", "Économétrie", "Données Stockées", "Méthodologie"],
            label_visibility="collapsed"
        )
    
    if "Dashboard" in page:
        page_dashboard()
    elif "Comparaison" in page:
        page_compare()
    elif "Multi" in page:
        page_multi()
    elif "Économétrie" in page:
        page_econometrie()
    elif "Données" in page:
        page_stored_data()
    else:
        page_methodo()


if __name__ == "__main__":
    main()
