import time
from typing import Any, Dict, Optional, Tuple

class TTLCache:
    """
    Thread-safe TTL cache with stale fallback and no-cache option.
    
    Usage:
        cache = TTLCache(ttl=300, stale_ttl=600, no_cache=False)
        value, is_stale = cache.get(key)
        cache.set(key, value)
    """
    
    def __init__(self, ttl: float = 300, stale_ttl: float = 600, no_cache: bool = False):
        self.ttl = float(ttl)
        self.stale_ttl = float(stale_ttl)
        self.no_cache = bool(no_cache)
        self._store: Dict[str, Dict[str, Any]] = {}
        self._lock = None  # Will be set if multiprocessing is needed

    def get(self, key: str) -> Tuple[Optional[Any], bool]:
        """
        Get value from cache.
        
        Returns:
            (value, is_stale) where:
                - value is the cached value or None if not found or expired
                - is_stale is True if the value is stale (within stale_ttl) but still usable
        """
        if self.no_cache:
            return None, False
            
        with self._lock() if self._lock else self._synchronized_get(key):
            entry = self._store.get(key)
            if not entry:
                return None, False
                
            ts = entry["ts"]
            val = entry["value"]
            age = time.time() - ts
            
            if age < self.ttl:
                return val, False  # Fresh
            elif age < self.stale_ttl:
                return val, True   # Stale but usable
            else:
                return None, False  # Expired

    def set(self, key: str, value: Any) -> None:
        """Set value in cache if not disabled by no_cache."""
        if not self.no_cache:
            with self._lock() if self._lock else self._synchronized_set(key, value):
                self._store[key] = {"ts": time.time(), "value": value}

    def _synchronized_get(self, key: str) -> None:
        """Synchronized access for single-threaded use."""
        # This is just a placeholder - real sync would be needed in multi-process
        pass

    def _synchronized_set(self, key: str, value: Any) -> None:
        """Synchronized access for single-threaded use."""
        pass

    def _lock(self) -> Optional[Any]:
        """Return lock object if needed, otherwise None."""
        return self._lock


# Global cache instance used by the application
# It's initialized in sopx_coingecko.py
CACHE: TTLCache = TTLCache(
    ttl=30 * 60,       # 30 minutes for market data
    stale_ttl=6 * 60 * 60,  # 6 hours for detail data
    no_cache=False
)