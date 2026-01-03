import time
import requests

BASE = "https://api.coingecko.com/api/v3"

class SopxCoinGeckoClient:
    def __init__(self, delay_sec: float = 1.0):
        self.delay_sec = delay_sec
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": "sopx-chain-scorer/1.0"})

    def _get(self, path: str, params=None):
        url = f"{BASE}{path}"
        r = self.s.get(url, params=params, timeout=30)
        if r.status_code == 429:
            time.sleep(self.delay_sec * 3)
            r = self.s.get(url, params=params, timeout=30)
        r.raise_for_status()
        time.sleep(self.delay_sec)
        return r.json()

    def top_markets(self, vs_currency="usd", per_page=100, page=1):
        return self._get("/coins/markets", params={
            "vs_currency": vs_currency,
            "order": "market_cap_desc",
            "per_page": per_page,
            "page": page,
            "sparkline": "false",
            "price_change_percentage": "7d",
        })

    def coin_detail(self, coin_id: str):
        return self._get(f"/coins/{coin_id}", params={
            "localization": "false",
            "tickers": "false",
            "market_data": "true",
            "community_data": "true",
            "developer_data": "true",
            "sparkline": "false",
        })
