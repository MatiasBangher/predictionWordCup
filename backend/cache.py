import time
from typing import Any, Dict, Optional

class SimpleCache:
    """
    A simple in-memory cache with Time-To-Live (TTL) support.
    Replaces Redis for a zero-dependency setup while providing aggressive caching.
    """
    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}

    def set(self, key: str, value: Any, ttl_seconds: int = 300):
        expire_at = time.time() + ttl_seconds
        self._cache[key] = {"value": value, "expire_at": expire_at}

    def get(self, key: str) -> Optional[Any]:
        if key in self._cache:
            item = self._cache[key]
            if time.time() < item["expire_at"]:
                return item["value"]
            else:
                del self._cache[key] # Clean up expired item
        return None

# Singleton instance for the application
cache = SimpleCache()
