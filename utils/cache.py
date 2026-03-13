"""
Project HER v2.0 – Pipeline Cache
Caches scrape results and LLM analysis to avoid redundant API calls.
Uses a file-based cache in the temp directory with TTL expiry.
"""

from __future__ import annotations

import json
import logging
import hashlib
import os
import time
from pathlib import Path
from typing import Optional

import config

logger = logging.getLogger(__name__)

CACHE_DIR = config.TEMP_DIR / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Cache TTL in seconds (default: 1 hour)
CACHE_TTL = int(os.getenv("CACHE_TTL", "3600"))


def _cache_key(prefix: str, content: str) -> str:
    """Generate a cache key from prefix + content hash."""
    h = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{h}"


def _cache_path(key: str) -> Path:
    """Path to cache file."""
    return CACHE_DIR / f"{key}.json"


def get_cache(prefix: str, content: str) -> Optional[dict]:
    """
    Retrieve a cached result if it exists and hasn't expired.
    
    Args:
        prefix: Cache namespace (e.g. "scrape", "analysis")
        content: The content to hash for cache key
        
    Returns:
        Cached data dict or None if miss/expired.
    """
    key = _cache_key(prefix, content)
    path = _cache_path(key)
    
    if not path.exists():
        return None
    
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        created = data.get("_cached_at", 0)
        
        if time.time() - created > CACHE_TTL:
            logger.debug("Cache expired for %s", key)
            path.unlink(missing_ok=True)
            return None
        
        logger.info("Cache hit for %s (%s)", prefix, key[:12])
        return data.get("payload")
    except Exception as e:
        logger.debug("Cache read error for %s: %s", key, e)
        return None


def set_cache(prefix: str, content: str, payload: dict) -> None:
    """
    Store a result in the cache.
    
    Args:
        prefix: Cache namespace
        content: The content to hash for cache key
        payload: Data to cache (must be JSON-serializable)
    """
    key = _cache_key(prefix, content)
    path = _cache_path(key)
    
    try:
        data = {
            "_cached_at": time.time(),
            "_prefix": prefix,
            "_key": key,
            "payload": payload,
        }
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.debug("Cache set for %s (%s)", prefix, key[:12])
    except Exception as e:
        logger.debug("Cache write error for %s: %s", key, e)


def clear_cache(prefix: Optional[str] = None) -> int:
    """
    Clear cache files.
    
    Args:
        prefix: If given, only clear caches with this prefix. Otherwise clear all.
        
    Returns:
        Number of files removed.
    """
    count = 0
    for path in CACHE_DIR.glob("*.json"):
        if prefix and not path.stem.startswith(prefix):
            continue
        path.unlink(missing_ok=True)
        count += 1
    logger.info("Cleared %d cache entries%s", count, f" (prefix={prefix})" if prefix else "")
    return count


def cache_stats() -> dict:
    """Return cache statistics."""
    files = list(CACHE_DIR.glob("*.json"))
    total_size = sum(f.stat().st_size for f in files)
    
    by_prefix: dict[str, int] = {}
    for f in files:
        prefix = f.stem.rsplit("_", 1)[0] if "_" in f.stem else "unknown"
        by_prefix[prefix] = by_prefix.get(prefix, 0) + 1
    
    return {
        "total_entries": len(files),
        "total_size_kb": round(total_size / 1024, 1),
        "by_prefix": by_prefix,
    }
