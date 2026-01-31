"""
Econometrie - Tests statistiques
Projet MoSEF 2024-2025
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import requests

from statsmodels.tsa.stattools import adfuller, grangercausalitytests
from statsmodels.tsa.api import VAR


def generate_demo_sentiment(crypto_id="bitcoin", days=60):
    """
    Genere des donnees de sentiment simulees pour la demo
    Simule une correlation realiste avec les prix
    """
    np.random.seed(42)
    
    # Recuperer les vrais prix
    prices_df = get_historical_prices(crypto_id, days)
    if prices_df.empty:
        return pd.DataFrame()
    
    prices_df = prices_df.sort_values('date')
    prices_df['log_return'] = np.log(prices_df['price'] / prices_df['price'].shift(1))
    prices_df = prices_df.dropna()
    
    # Generer sentiment correle aux returns (avec du bruit)
    n = len(prices_df)
    noise = np.random.normal(0, 0.15, n)
    
    # Sentiment = 0.3 * returns_precedents + 0.2 * returns_actuels + bruit
    returns = prices_df['log_return'].values
    sentiment = np.zeros(n)
    
    for i in range(n):
        base = 0.0
        if i > 0:
            base += 0.3 * returns[i-1] * 10  # Retard de 1 jour
        base += 0.2 * returns[i] * 10  # Contemporain
        sentiment[i] = np.clip(base + noise[i], -1, 1)
    
    # Creer DataFrame sentiment
    sentiment_df = pd.DataFrame({
        'date': prices_df['date'].values,
        'sentiment_mean': sentiment,
        'sentiment_std': np.abs(np.random.normal(0.1, 0.05, n)),
        'post_count': np.random.randint(10, 100, n)
    })
    
    return sentiment_df


def get_historical_prices(crypto_id, days=60):
    """
    Recupere les prix historiques depuis CoinGecko
    """
    url = f"https://api.coingecko.com/api/v3/coins/{crypto_id}/market_chart"
    params = {"vs_currency": "usd", "days": days, "interval": "daily"}

    try:
        resp = requests.get(url, params=params, timeout=15)
        data = resp.json()

        prices = []
        for ts, price in data.get("prices", []):
            dt = datetime.fromtimestamp(ts / 1000)
            prices.append({"date": dt.strftime("%Y-%m-%d"), "price": price})

        df = pd.DataFrame(prices)
        df['date'] = pd.to_datetime(df['date'])
        df = df.drop_duplicates(subset='date', keep='last')
        return df

    except Exception as e:
        print(f"Erreur prix: {e}")
        return pd.DataFrame()


def prepare_sentiment_data(posts, results):
    """
    Agrege les sentiments par jour
    """
    data = []

    for i, post in enumerate(posts):
        if i >= len(results):
            break

        ts = post.get("created_utc")
        if ts:
            try:
                if isinstance(ts, (int, float)):
                    dt = datetime.fromtimestamp(ts)
                else:
                    dt = datetime.fromisoformat(str(ts).replace("Z", ""))

                data.append({
                    "date": dt.strftime("%Y-%m-%d"),
                    "score": results[i]["score"]
                })
            except:
                continue

    if not data:
        return pd.DataFrame()

    df = pd.DataFrame(data)
    df['date'] = pd.to_datetime(df['date'])

    daily = df.groupby('date').agg(
        sentiment_mean=('score', 'mean'),
        sentiment_std=('score', 'std'),
        post_count=('score', 'count')
    ).reset_index()

    daily['sentiment_std'] = daily['sentiment_std'].fillna(0)

    return daily


def calculate_returns(prices_df):
    """
    Calcule les log returns
    """
    df = prices_df.copy()
    df = df.sort_values('date')
    df['log_return'] = np.log(df['price'] / df['price'].shift(1))
    df = df.dropna()
    return df


def merge_data(sentiment_df, prices_df):
    """
    Fusionne sentiment et prix
    """
    if sentiment_df.empty or prices_df.empty:
        return pd.DataFrame()

    prices_df = calculate_returns(prices_df)
    merged = pd.merge(sentiment_df, prices_df, on='date', how='inner')
    merged = merged.sort_values('date')

    return merged


def test_adf(series, name="serie"):
    """
    Test ADF - stationnarite
    """
    if len(series) < 10:
        return {"name": name, "error": "pas assez de donnees"}

    try:
        result = adfuller(series.dropna(), autolag='AIC')

        return {
            "name": name,
            "statistic": round(result[0], 4),
            "pvalue": round(result[1], 4),
            "lags": result[2],
            "stationary": result[1] < 0.05
        }
    except Exception as e:
        return {"name": name, "error": str(e)}


def test_granger(data, max_lag=5):
    """
    Test de Granger
    """
    results = {
        "sentiment_to_returns": {"significant": False, "pvalues": {}, "best_lag": None},
        "returns_to_sentiment": {"significant": False, "pvalues": {}, "best_lag": None}
    }

    if len(data) < max_lag + 5:
        return {"error": "pas assez de donnees"}

    df = data[['sentiment_mean', 'log_return']].dropna()

    if len(df) < max_lag + 5:
        return {"error": "pas assez de donnees apres nettoyage"}

    # sentiment -> returns
    try:
        test1 = grangercausalitytests(df[['log_return', 'sentiment_mean']], maxlag=max_lag, verbose=False)

        for lag in range(1, max_lag + 1):
            pval = test1[lag][0]['ssr_ftest'][1]
            results["sentiment_to_returns"]["pvalues"][lag] = round(pval, 4)

            if pval < 0.05:
                results["sentiment_to_returns"]["significant"] = True
                if results["sentiment_to_returns"]["best_lag"] is None:
                    results["sentiment_to_returns"]["best_lag"] = lag
    except Exception as e:
        results["sentiment_to_returns"]["error"] = str(e)

    # returns -> sentiment
    try:
        test2 = grangercausalitytests(df[['sentiment_mean', 'log_return']], maxlag=max_lag, verbose=False)

        for lag in range(1, max_lag + 1):
            pval = test2[lag][0]['ssr_ftest'][1]
            results["returns_to_sentiment"]["pvalues"][lag] = round(pval, 4)

            if pval < 0.05:
                results["returns_to_sentiment"]["significant"] = True
                if results["returns_to_sentiment"]["best_lag"] is None:
                    results["returns_to_sentiment"]["best_lag"] = lag
    except Exception as e:
        results["returns_to_sentiment"]["error"] = str(e)

    return results


def fit_var(data, max_lag=10):
    """
    Modele VAR
    """
    df = data[['sentiment_mean', 'log_return']].dropna()

    if len(df) < max_lag + 5:
        return {"error": "pas assez de donnees"}

    try:
        model = VAR(df)
        lag_order = model.select_order(maxlags=max_lag)
        optimal_lag = lag_order.aic
        fitted = model.fit(optimal_lag)

        return {
            "optimal_lag": optimal_lag,
            "aic": round(fitted.aic, 4),
            "bic": round(fitted.bic, 4)
        }
    except Exception as e:
        return {"error": str(e)}


def cross_correlation(sentiment, returns, max_lag=10):
    """
    Correlation croisee
    """
    correlations = {}

    sent = sentiment.values
    ret = returns.values

    for lag in range(-max_lag, max_lag + 1):
        try:
            if lag < 0:
                corr = np.corrcoef(ret[:lag], sent[-lag:])[0, 1]
            elif lag > 0:
                corr = np.corrcoef(sent[:-lag], ret[lag:])[0, 1]
            else:
                corr = np.corrcoef(sent, ret)[0, 1]

            if not np.isnan(corr):
                correlations[lag] = round(corr, 4)
        except:
            continue

    if correlations:
        best_lag = max(correlations, key=lambda x: abs(correlations[x]))
        best_corr = correlations[best_lag]
    else:
        best_lag, best_corr = None, None

    return {
        "correlations": correlations,
        "best_lag": best_lag,
        "best_correlation": best_corr
    }


def run_full_analysis(posts, results, crypto_id, days=60, max_lag=5):
    """
    Lance tous les tests
    """
    output = {
        "status": "ok",
        "data_info": {},
        "adf_tests": {},
        "granger": {},
        "var": {},
        "cross_corr": {},
        "conclusion": ""
    }

    # prepare donnees
    sentiment_df = prepare_sentiment_data(posts, results)
    if sentiment_df.empty:
        output["status"] = "error"
        output["error"] = "pas de donnees sentiment"
        return output

    prices_df = get_historical_prices(crypto_id, days)
    if prices_df.empty:
        output["status"] = "error"
        output["error"] = "pas de donnees prix"
        return output

    merged = merge_data(sentiment_df, prices_df)
    if merged.empty or len(merged) < 10:
        output["status"] = "error"
        output["error"] = f"pas assez de donnees ({len(merged)} jours)"
        return output

    output["data_info"] = {
        "jours_sentiment": len(sentiment_df),
        "jours_prix": len(prices_df),
        "jours_merged": len(merged),
        "date_debut": str(merged['date'].min().date()),
        "date_fin": str(merged['date'].max().date())
    }

    # tests
    output["adf_tests"]["sentiment"] = test_adf(merged['sentiment_mean'], "sentiment")
    output["adf_tests"]["returns"] = test_adf(merged['log_return'], "returns")
    output["granger"] = test_granger(merged, max_lag)
    output["var"] = fit_var(merged, max_lag * 2)
    output["cross_corr"] = cross_correlation(merged['sentiment_mean'], merged['log_return'], max_lag)

    # conclusion
    output["conclusion"] = generate_conclusion(output)
    output["merged_data"] = merged

    return output


def run_demo_analysis(crypto_id="bitcoin", days=60, max_lag=5):
    """
    Lance l'analyse avec des donnees simulees (mode demo)
    """
    output = {
        "status": "ok",
        "mode": "demo",
        "data_info": {},
        "adf_tests": {},
        "granger": {},
        "var": {},
        "cross_corr": {},
        "conclusion": ""
    }
    
    # Donnees simulees
    sentiment_df = generate_demo_sentiment(crypto_id, days)
    if sentiment_df.empty:
        output["status"] = "error"
        output["error"] = "impossible de generer les donnees demo"
        return output
    
    prices_df = get_historical_prices(crypto_id, days)
    if prices_df.empty:
        output["status"] = "error"
        output["error"] = "pas de donnees prix"
        return output
    
    merged = merge_data(sentiment_df, prices_df)
    if merged.empty or len(merged) < 10:
        output["status"] = "error"
        output["error"] = f"pas assez de donnees ({len(merged)} jours)"
        return output
    
    output["data_info"] = {
        "jours_sentiment": len(sentiment_df),
        "jours_prix": len(prices_df),
        "jours_merged": len(merged),
        "date_debut": str(merged['date'].min().date()),
        "date_fin": str(merged['date'].max().date())
    }
    
    # Tests
    output["adf_tests"]["sentiment"] = test_adf(merged['sentiment_mean'], "sentiment")
    output["adf_tests"]["returns"] = test_adf(merged['log_return'], "returns")
    output["granger"] = test_granger(merged, max_lag)
    output["var"] = fit_var(merged, max_lag * 2)
    output["cross_corr"] = cross_correlation(merged['sentiment_mean'], merged['log_return'], max_lag)
    
    # Conclusion
    output["conclusion"] = generate_conclusion(output)
    output["merged_data"] = merged
    
    return output


def generate_conclusion(results):
    """
    Conclusion en francais
    """
    lines = []

    # ADF
    adf_sent = results.get("adf_tests", {}).get("sentiment", {})
    adf_ret = results.get("adf_tests", {}).get("returns", {})

    if adf_sent.get("stationary"):
        lines.append("- Sentiment: stationnaire")
    else:
        lines.append("- Sentiment: NON stationnaire")

    if adf_ret.get("stationary"):
        lines.append("- Returns: stationnaires")
    else:
        lines.append("- Returns: NON stationnaires")

    # Granger
    granger = results.get("granger", {})
    s2r = granger.get("sentiment_to_returns", {})
    r2s = granger.get("returns_to_sentiment", {})

    if s2r.get("significant"):
        lines.append(f"- Sentiment CAUSE returns (lag={s2r.get('best_lag')})")
    else:
        lines.append("- Sentiment ne cause PAS returns")

    if r2s.get("significant"):
        lines.append(f"- Returns CAUSENT sentiment (lag={r2s.get('best_lag')})")
    else:
        lines.append("- Returns ne causent PAS sentiment")

    # Cross-corr
    cross = results.get("cross_corr", {})
    best_lag = cross.get("best_lag")
    best_corr = cross.get("best_correlation")

    if best_lag is not None:
        if best_lag > 0:
            lines.append(f"- Correlation max: sentiment precede de {best_lag}j (r={best_corr})")
        elif best_lag < 0:
            lines.append(f"- Correlation max: returns precedent de {-best_lag}j (r={best_corr})")
        else:
            lines.append(f"- Correlation max: contemporaine (r={best_corr})")

    # Finale
    lines.append("")
    if s2r.get("significant"):
        lines.append("CONCLUSION: Pouvoir predictif du sentiment detecte!")
    else:
        lines.append("CONCLUSION: Pas de relation significative.")

    return "\n".join(lines)