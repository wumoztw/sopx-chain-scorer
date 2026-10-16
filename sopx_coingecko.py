import time
import random
import requests
import threading
from collections import deque

BASE = "https://api.coingecko.com/api/v3"

class RateLimiter:
    """Token bucket rate limiter to respect CoinGecko's API rate limits."""
    
    def __init__(self, max_requests_per_second: float = 1.0, burst: int = 1):
        self.max_requests_per_second = max_requests_per_second  # sustained rate (requests/sec)
        self.burst = burst  # max burst size
        self.tokens = float(burst)  # current tokens
        self.last_refill = time.time()
        self.lock = threading.Lock()
    
    def _acquire(self):
        """Acquire a token, waiting if necessary."""
        with self.lock:
            now = time.time()
            # Refill tokens based on elapsed time
            elapsed = now - self.last_refill
            self.tokens = min(self.burst, self.tokens + elapsed * self.max_requests_per_second)
            self.last_refill = now
            
            if self.tokens >= 1.0:
                self.tokens -= 1.0
                return
            else:
                # Calculate wait time needed
                wait = (1.0 - self.tokens) / self.max_requests_per_second
                time.sleep(wait)
                # The wait replenishes exactly one token, which this request consumes.
                self.tokens = 0.0
                self.last_refill = time.time()

    def __enter__(self):
        self._acquire()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


class SopxCoinGeckoClient:
    def __init__(self, delay_sec: float = 1.0, max_retries: int = 8, rate_limit_rps: float = None):
        self.delay_sec = float(delay_sec)
        self.max_retries = int(max_retries)
        # If rate_limit_rps not set, derive from delay_sec for equivalent pacing
        if rate_limit_rps is None:
            rate_limit_rps = 1.0 / delay_sec  # sustained rate equivalent to original delay
        self.rate_limit_rps = rate_limit_rps  # requests per second (sustained rate)
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": "sopx-chain-scorer/1.1"})
        # Rate limiter: sustain at rate_limit_rps, with burst for initial parallelism
        # burst = 2 so a couple of requests can start in parallel before pacing kicks in
        burst = max(2, int(delay_sec / (1.0 / rate_limit_rps)))
        self.rate_limiter = RateLimiter(max_requests_per_second=rate_limit_rps, burst=burst)

    def _sleep_with_jitter(self, seconds: float):
        # small jitter helps when many runners hit the API at same time
        jitter = random.uniform(0.0, 0.4)
        time.sleep(max(0.0, seconds + jitter))

    def _get(self, path: str, params=None):
        url = f"{BASE}{path}"

        for attempt in range(1, self.max_retries + 1):
            # Acquire rate limit token before making the request
            with self.rate_limiter:
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
