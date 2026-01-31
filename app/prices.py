"""Prix crypto via CoinGecko"""

import requests
from datetime import datetime


class CryptoPrices:
    
    BASE_URL = "https://api.coingecko.com/api/v3"
    
    CRYPTO_IDS = {
        "btc": "bitcoin", "bitcoin": "bitcoin",
        "eth": "ethereum", "ethereum": "ethereum",
        "sol": "solana", "solana": "solana",
        "ada": "cardano", "cardano": "cardano",
        "doge": "dogecoin", "dogecoin": "dogecoin",
        "xrp": "ripple", "ripple": "ripple",
        "dot": "polkadot", "polkadot": "polkadot",
        "link": "chainlink", "chainlink": "chainlink",
        "ltc": "litecoin", "litecoin": "litecoin",
        "avax": "avalanche-2", "avalanche": "avalanche-2",
        "matic": "matic-network", "polygon": "matic-network",
    }

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json"
        })

    def _get_id(self, crypto: str) -> str:
        return self.CRYPTO_IDS.get(crypto.lower(), crypto.lower())

    def get_price(self, crypto: str) -> dict:
        coin_id = self._get_id(crypto)

        url = f"{self.BASE_URL}/simple/price"
        params = {
            "ids": coin_id,
            "vs_currencies": "usd",
            "include_24hr_change": "true",
            "include_market_cap": "true"
        }

        try:
            resp = self.session.get(url, params=params, timeout=10)
            data = resp.json()

            if coin_id not in data:
                return None

            d = data[coin_id]
            return {
                "crypto": crypto,
                "price": d.get("usd"),
                "change_24h": round(d.get("usd_24h_change", 0), 2),
                "market_cap": d.get("usd_market_cap")
            }
        except:
            return None

    def get_multiple_prices(self, cryptos: list[str]) -> dict:
        ids = [self._get_id(c) for c in cryptos]

        url = f"{self.BASE_URL}/simple/price"
        params = {
            "ids": ",".join(ids),
            "vs_currencies": "usd",
            "include_24hr_change": "true"
        }

        try:
            resp = self.session.get(url, params=params, timeout=10)
            data = resp.json()

            result = {}
            for crypto, coin_id in zip(cryptos, ids):
                if coin_id in data:
                    result[crypto] = {
                        "price": data[coin_id].get("usd"),
                        "change_24h": round(data[coin_id].get("usd_24h_change", 0), 2)
                    }
            return result
        except:
            return {}

    def get_historical(self, crypto: str, days: int = 30) -> list[dict]:
        coin_id = self._get_id(crypto)

        url = f"{self.BASE_URL}/coins/{coin_id}/market_chart"
        params = {"vs_currency": "usd", "days": days, "interval": "daily"}

        try:
            resp = self.session.get(url, params=params, timeout=10)
            data = resp.json()

            result = []
            for ts, price in data.get("prices", []):
                result.append({
                    "date": datetime.fromtimestamp(ts/1000).strftime("%Y-%m-%d"),
                    "price": round(price, 2)
                })
            return result
        except:
            return []


# Fonction standalone pour import facile
def get_historical_prices(crypto: str, days: int = 30) -> list[dict]:
    """Wrapper pour utilisation directe"""
    client = CryptoPrices()
    return client.get_historical(crypto, days)


if __name__ == "__main__":
    prices = CryptoPrices()
    btc = prices.get_price("bitcoin")
    if btc:
        print(f"Bitcoin: ${btc['price']:,.0f} ({btc['change_24h']:+.2f}%)")