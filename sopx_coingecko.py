import hashlib
import json
import logging
import os
import random
import tempfile
import threading
import time
from pathlib import Path
from urllib.parse import urlsplit

import requests

BASE = "https://api.coingecko.com/api/v3"
logger = logging.getLogger(__name__)


def _default_cache_dir():
    cache_home = os.environ.get("XDG_CACHE_HOME")
    return Path(cache_home) / "sopx-chain-scorer" if cache_home else Path.home() / ".cache" / "sopx-chain-scorer"

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
    def __init__(
        self,
        delay_sec: float = 1.0,
        max_retries: int = 8,
        rate_limit_rps: float = None,
        cache_enabled: bool = True,
        cache_dir=None,
        market_cache_ttl: float = 30 * 60,
        detail_cache_ttl: float = 6 * 60 * 60,
    ):
        self.delay_sec = float(delay_sec)
        self.max_retries = int(max_retries)
        if market_cache_ttl < 0 or detail_cache_ttl < 0:
            raise ValueError("cache TTLs must be non-negative")
        self.cache_enabled = bool(cache_enabled)
        self.cache_dir = Path(cache_dir) if cache_dir is not None else _default_cache_dir()
        self.market_cache_ttl = float(market_cache_ttl)
        self.detail_cache_ttl = float(detail_cache_ttl)
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

    def _cache_path(self, path: str, params):
        key = json.dumps({"path": path, "params": params or {}}, sort_keys=True, separators=(",", ":"))
        return self.cache_dir / f"{hashlib.sha256(key.encode('utf-8')).hexdigest()}.json"

    def _read_cache(self, cache_path, ttl):
        try:
            record = json.loads(cache_path.read_text(encoding="utf-8"))
            fetched_at = float(record["fetched_at"])
            data = record["data"]
        except (OSError, ValueError, TypeError, KeyError):
            return None, False, False
        return data, time.time() - fetched_at < ttl, True

    def _write_cache(self, cache_path, data):
        temporary_path = None
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=self.cache_dir, delete=False
            ) as cache_file:
                temporary_path = Path(cache_file.name)
                json.dump({"fetched_at": time.time(), "data": data}, cache_file)
            os.replace(temporary_path, cache_path)
        except (OSError, TypeError, ValueError) as exc:
            logger.warning("could not write CoinGecko cache %s: %s", cache_path, exc)
            if temporary_path is not None:
                try:
                    temporary_path.unlink(missing_ok=True)
                except OSError:
                    pass

    def _get(self, path: str, params=None):
        url = f"{BASE}{path}"
        params = params or {}
        cache_path = None
        stale_data = None
        has_stale_data = False
        if self.cache_enabled:
            cache_path = self._cache_path(path, params)
            ttl = self.market_cache_ttl if urlsplit(url).path.endswith("/coins/markets") else self.detail_cache_ttl
            stale_data, is_fresh, has_stale_data = self._read_cache(cache_path, ttl)
            if is_fresh:
                return stale_data

        last_error = None
        for attempt in range(1, self.max_retries + 1):
            # Acquire rate limit token before making the request
            try:
                with self.rate_limiter:
                    r = self.s.get(url, params=params, timeout=30)
            except requests.exceptions.RequestException as exc:
                last_error = exc
                if attempt < self.max_retries:
                    backoff = min(45.0, (2 ** (attempt - 1)) * self.delay_sec)
                    logger.warning(
                        "CoinGecko request error: %s attempt %s/%s; sleep %.1fs",
                        path, attempt, self.max_retries, backoff,
                    )
                    self._sleep_with_jitter(backoff)
                continue

            # Success
            if r.status_code < 400:
                data = r.json()
                # baseline pacing
                self._sleep_with_jitter(self.delay_sec)
                if cache_path is not None:
                    self._write_cache(cache_path, data)
                return data

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
                last_error = requests.exceptions.HTTPError(
                    f"CoinGecko returned HTTP 429 for {url}"
                )
                continue

            # Transient server errors
            if r.status_code in (500, 502, 503, 504):
                backoff = min(45.0, (2 ** (attempt - 1)) * self.delay_sec)
                print(f"[CoinGecko] {r.status_code} server error: {path} attempt {attempt}/{self.max_retries}. "
                      f"sleep {backoff:.1f}s")
                self._sleep_with_jitter(backoff)
                last_error = requests.exceptions.HTTPError(
                    f"CoinGecko returned HTTP {r.status_code} for {url}"
                )
                continue

            # Other errors: raise
            r.raise_for_status()

        if has_stale_data:
            logger.warning("using stale CoinGecko cache for %s after request failure: %s", path, last_error)
            return stale_data
        if last_error is not None:
            raise last_error
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
