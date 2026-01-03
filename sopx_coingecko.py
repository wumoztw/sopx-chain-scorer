import time
import random
import requests

BASE = "https://api.coingecko.com/api/v3"

class SopxCoinGeckoClient:
    def __init__(self, delay_sec: float = 1.0, max_retries: int = 8):
        self.delay_sec = float(delay_sec)
        self.max_retries = int(max_retries)
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": "sopx-chain-scorer/1.1"})

    def _sleep_with_jitter(self, seconds: float):
        # small jitter helps when many runners hit the API at same time
        jitter = random.uniform(0.0, 0.4)
        time.sleep(max(0.0, seconds + jitter))

    def _get(self, path: str, params=None):
        url = f"{BASE}{path}"

        for attempt in range(1, self.max_retries + 1):
            r = self.s.get(url, params=params, timeout=30)

            # Success
            if r.status_code < 400:
                # baseline pacing
                self._sleep_with_jitter(self.delay_sec)
                return r.json()

            # Rate limited
            if r.status_code == 429:
                retry_after = r.headers.get("Retry-After")
                if retry_after:
                    try:
                        wait = float(retry_after)
                    except Exception:
                        wait = None
                else:
                    wait = None

                # exponential backoff (cap)
                backoff = min(60.0, (2 ** (attempt - 1)) * self.delay_sec)
                wait_time = wait if wait is not None else backoff

                # extra buffer
                wait_time = wait_time + 1.0

                print(f"[CoinGecko] 429 rate limited: {path} attempt {attempt}/{self.max_retries}. "
                      f"sleep {wait_time:.1f}s")
                self._sleep_with_jitter(wait_time)
                continue

            # Transient server errors
            if r.status_code in (500, 502, 503, 504):
                backoff = min(45.0, (2 ** (attempt - 1)) * self.delay_sec)
                print(f"[CoinGecko] {r.status_code} server error: {path} attempt {attempt}/{self.max_retries}. "
                      f"sleep {backoff:.1f}s")
                self._sleep_with_jitter(backoff)
                continue

            # Other errors: raise
            r.raise_for_status()

        # Retries exhausted
        raise requests.exceptions.HTTPError(
            f"CoinGecko request failed after {self.max_retries} retries: {url}"
        )

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
