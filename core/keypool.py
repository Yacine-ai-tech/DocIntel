"""Rotating API-key pool for rate-limited LLM providers.

Keys are discovered from the process environment at runtime, so adding, removing or
rotating a key is an environment change and nothing in the code names a specific key.

Discovery for a provider ``P`` (upper-cased, for example ``GROQ``):

* ``P_API_KEY`` and any ``P_API_KEY_<suffix>`` variable, in a stable sorted order;
* ``P_API_KEYS`` as a comma- or whitespace-separated list.

An app can be pinned to a subset of the discovered keys with ``P_KEY_SLOTS`` (a
comma-separated list of 1-based positions in that stable order), which is how a small
set of keys is split across several deployments without hardcoding anything.

Selection is round-robin over keys that are not cooling down. A key that hit a rate
limit is parked for the provider's ``Retry-After`` (or a default) and skipped until
then. Keys are never logged; only their position is.
"""
from __future__ import annotations

import itertools
import os
import re
import threading
import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, TypeVar

T = TypeVar("T")

_DEFAULT_COOLDOWN_S = 30.0
_RATE_LIMIT_MARKERS = (
    "429", "rate limit", "rate_limit", "ratelimit", "quota", "resource_exhausted",
    "resource exhausted", "too many requests", "tokens per minute", "requests per minute",
)


@dataclass(frozen=True)
class KeyLease:
    provider: str
    index: int      # 0-based position within the pool, for logs and cooldown tracking
    key: str


class AllKeysExhausted(RuntimeError):
    """Every key in the pool failed with a rate-limit style error."""


def discover(provider: str, environ: Optional[Dict[str, str]] = None) -> List[str]:
    env = os.environ if environ is None else environ
    p = re.escape(provider.upper())
    pattern = re.compile(rf"^{p}_API_KEY(?:_[A-Za-z0-9]+)?$")
    names = sorted(n for n in env if pattern.match(n))
    # Plain ``P_API_KEY`` first, then numeric suffixes in numeric order, then the rest.
    def order(n: str):
        suffix = n[len(f"{provider.upper()}_API_KEY"):].lstrip("_")
        return (0, 0, "") if not suffix else ((1, int(suffix), "") if suffix.isdigit() else (2, 0, suffix))
    keys: List[str] = []
    for n in sorted(names, key=order):
        v = (env.get(n) or "").strip()
        if v and v not in keys:
            keys.append(v)
    for part in re.split(r"[,\s]+", (env.get(f"{provider.upper()}_API_KEYS") or "").strip()):
        if part and part not in keys:
            keys.append(part)
    slots = (env.get(f"{provider.upper()}_KEY_SLOTS") or "").strip()
    if slots:
        wanted = {int(s) for s in re.split(r"[,\s]+", slots) if s.isdigit()}
        picked = [k for i, k in enumerate(keys, start=1) if i in wanted]
        if picked:
            keys = picked
    return keys


def looks_rate_limited(exc: BaseException) -> bool:
    status = getattr(exc, "status_code", None) or getattr(getattr(exc, "response", None), "status_code", None)
    if status == 429:
        return True
    text = f"{type(exc).__name__} {exc}".lower()
    return any(m in text for m in _RATE_LIMIT_MARKERS)


def retry_after_seconds(exc: BaseException) -> float:
    headers = getattr(getattr(exc, "response", None), "headers", None) or {}
    try:
        raw = headers.get("retry-after") or headers.get("Retry-After")
        if raw:
            return max(1.0, min(float(raw), 300.0))
    except Exception:
        pass
    m = re.search(r"retry (?:in|after) ([0-9.]+)\s*s", str(exc), re.I)
    if m:
        return max(1.0, min(float(m.group(1)), 300.0))
    return _DEFAULT_COOLDOWN_S


class KeyPool:
    def __init__(self, provider: str, keys: List[str]) -> None:
        self.provider = provider.lower()
        self._keys = list(keys)
        self._cool_until = [0.0] * len(self._keys)
        self._cursor = itertools.count()
        self._lock = threading.Lock()

    @classmethod
    def from_env(cls, provider: str) -> "KeyPool":
        return cls(provider, discover(provider))

    def __len__(self) -> int:
        return len(self._keys)

    def acquire(self) -> Optional[KeyLease]:
        if not self._keys:
            return None
        now = time.monotonic()
        with self._lock:
            n = len(self._keys)
            start = next(self._cursor)
            for step in range(n):
                i = (start + step) % n
                if self._cool_until[i] <= now:
                    return KeyLease(self.provider, i, self._keys[i])
            # Everything is cooling: hand out the key that frees up first.
            i = min(range(n), key=lambda j: self._cool_until[j])
            return KeyLease(self.provider, i, self._keys[i])

    def cool_down(self, lease: KeyLease, seconds: float) -> None:
        with self._lock:
            self._cool_until[lease.index] = max(self._cool_until[lease.index], time.monotonic() + seconds)

    def available(self) -> int:
        now = time.monotonic()
        with self._lock:
            return sum(1 for t in self._cool_until if t <= now)

    def call(self, fn: Callable[[str], T], attempts: Optional[int] = None) -> T:
        """Run ``fn(api_key)``, moving to the next key when one is rate limited."""
        if not self._keys:
            raise AllKeysExhausted(f"no API keys configured for provider '{self.provider}'")
        tries = attempts or len(self._keys)
        last: Optional[BaseException] = None
        for _ in range(tries):
            lease = self.acquire()
            assert lease is not None
            try:
                return fn(lease.key)
            except Exception as exc:  # noqa: BLE001 - classified below, re-raised if not a rate limit
                if not looks_rate_limited(exc):
                    raise
                last = exc
                self.cool_down(lease, retry_after_seconds(exc))
        raise AllKeysExhausted(
            f"all {len(self._keys)} '{self.provider}' keys are rate limited"
        ) from last


_POOLS: Dict[str, KeyPool] = {}
_POOLS_LOCK = threading.Lock()


def pool(provider: str) -> KeyPool:
    """Process-wide pool for a provider, built lazily from the current environment."""
    p = provider.lower()
    with _POOLS_LOCK:
        if p not in _POOLS:
            _POOLS[p] = KeyPool.from_env(p)
        return _POOLS[p]


def reset() -> None:
    """Forget cached pools (tests, or after the environment changed)."""
    with _POOLS_LOCK:
        _POOLS.clear()


# ── Model-string helpers (litellm "<provider>/<model>" convention) ──────────────
_MODEL_PREFIX_TO_PROVIDER = {"groq": "groq", "gemini": "gemini"}


def provider_for_model(model: str) -> Optional[str]:
    """Pooled provider for a litellm-style model string, or None if not pooled."""
    prefix = (model or "").split("/", 1)[0].lower()
    return _MODEL_PREFIX_TO_PROVIDER.get(prefix)


def lease_for_model(model: str) -> Optional[KeyLease]:
    """Lease the next usable key for the model's provider (None when none configured)."""
    provider = provider_for_model(model)
    if not provider:
        return None
    return pool(provider).acquire()


def note_failure(lease: Optional[KeyLease], exc: BaseException) -> bool:
    """Park the leased key if ``exc`` is a rate limit. Returns True when it was."""
    if lease is None or not looks_rate_limited(exc):
        return False
    pool(lease.provider).cool_down(lease, retry_after_seconds(exc))
    return True


def other_key_available(provider: Optional[str]) -> bool:
    """True when at least one key of this provider is not cooling down."""
    return bool(provider) and pool(provider).available() > 0


async def acompletion_pooled(acompletion_fn, model: str, **kwargs):
    """Await ``acompletion_fn(model=..., **kwargs)`` with a leased provider key.

    A key that fails with a rate limit is parked before the error propagates, so the
    caller's own retry loop picks another key on its next attempt.
    """
    lease = lease_for_model(model)
    if lease is not None and "api_key" not in kwargs:
        kwargs["api_key"] = lease.key
    try:
        return await acompletion_fn(model=model, **kwargs)
    except Exception as exc:
        note_failure(lease, exc)
        raise
