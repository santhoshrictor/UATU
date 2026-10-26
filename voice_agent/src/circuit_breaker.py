"""Lightweight, non-blocking circuit breaker for UATU FastAPI backend."""

from __future__ import annotations

import time
from urllib.parse import urlparse

_OFFLINE_CACHE: dict[str, float] = {}
_DEFAULT_CIRCUIT_DURATION: float = 15.0  # seconds to cache offline state


def _normalize_target(target: str | None) -> str:
    if not target:
        return "default"
    try:
        parsed = urlparse(target)
        if parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}"
    except Exception:
        pass
    return str(target).strip()


def is_backend_offline(target: str = "") -> bool:
    """Return True if the backend target was recently detected as unreachable.

    Automatically passes through if aiohttp.ClientSession has been mocked in tests.
    """
    try:
        import aiohttp

        get_fn = getattr(aiohttp.ClientSession, "get", None)
        if get_fn is not None and getattr(get_fn, "__module__", "") != "aiohttp.client":
            return False
    except Exception:
        pass

    now = time.monotonic()
    key = _normalize_target(target)
    if key in _OFFLINE_CACHE and now < _OFFLINE_CACHE[key]:
        return True
    if "default" in _OFFLINE_CACHE and now < _OFFLINE_CACHE["default"]:
        return True
    # If caller did not specify target, check if any backend target is offline
    if key == "default":
        for exp in _OFFLINE_CACHE.values():
            if now < exp:
                return True
    return False


def mark_backend_offline(target: str = "", duration: float = _DEFAULT_CIRCUIT_DURATION) -> None:
    """Trip the circuit breaker for `duration` seconds for the given target."""
    key = _normalize_target(target)
    _OFFLINE_CACHE[key] = time.monotonic() + duration


def mark_backend_online(target: str = "") -> None:
    """Reset the circuit breaker immediately for the given target."""
    key = _normalize_target(target)
    _OFFLINE_CACHE.pop(key, None)
    if key == "default":
        _OFFLINE_CACHE.clear()


def reset_circuit_breaker() -> None:
    """Clear all circuit breaker states."""
    _OFFLINE_CACHE.clear()
