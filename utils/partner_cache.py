"""
utils/partner_cache.py
──────────────────────
সাধারণ TTL in-memory cache — Partner API ক্যাটালগ রেট লিমিট থেকে বাঁচাতে।

ব্যবহার:
    from utils.partner_cache import get_cache, set_cache, invalidate

    set_cache("partner:products:gemini", products, ttl=90)

    data = get_cache("partner:products:gemini")
    if not data:
        data = await papi.products(provider="gemini")
        set_cache("partner:products:gemini", data, ttl=90)

    invalidate("partner:products:")   # prefix-এ সব ক্লিয়ার
"""

import time
import threading
from typing import Any

# ─────────────────────────────────────────────────────
#  INTERNAL STORE
# ─────────────────────────────────────────────────────
# key → (expires_at_epoch, value)
_store: dict[str, tuple[float, Any]] = {}
_lock = threading.Lock()


# ─────────────────────────────────────────────────────
#  PUBLIC API
# ─────────────────────────────────────────────────────
def set_cache(key: str, value: Any, ttl: int = 90) -> None:
    """
    ক্যাশে মান রাখে।

    Args:
        key:   ইউনিক কী (যেমন "partner:products:gemini")
        value: যেকোনো অবজেক্ট (list, dict, etc.)
        ttl:   সেকেন্ডে কতক্ষণ বাঁচবে
    """
    if not key or ttl <= 0:
        return
    expires = time.time() + ttl
    with _lock:
        _store[key] = (expires, value)


def get_cache(key: str) -> Any | None:
    """
    ক্যাশ থেকে মান আনে। না থাকলে বা মেয়াদ শেষ হলে None।
    """
    if not key:
        return None
    with _lock:
        entry = _store.get(key)
        if not entry:
            return None
        expires, value = entry
        if time.time() > expires:
            _store.pop(key, None)
            return None
        return value


def invalidate(prefix: str = "") -> int:
    """
    prefix দিয়ে শুরু হওয়া সব কী মুছে দেয়।
    prefix="" হলে পুরো ক্যাশ খালি হয়।

    Returns: কতটি entry মুছল
    """
    with _lock:
        if not prefix:
            n = len(_store)
            _store.clear()
            return n
        keys = [k for k in _store if k.startswith(prefix)]
        for k in keys:
            _store.pop(k, None)
        return len(keys)


def clear() -> None:
    """পুরো ক্যাশ খালি করে।"""
    with _lock:
        _store.clear()


def stats() -> dict:
    """ডিবাগ/মনিটরিং-এর জন্য ক্যাশের অবস্থা।"""
    now = time.time()
    with _lock:
        total = len(_store)
        expired = sum(1 for exp, _ in _store.values() if exp <= now)
    return {
        "total_keys":   total,
        "expired_keys": expired,
        "active_keys":  total - expired,
    }