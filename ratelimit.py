"""Per-IP rate limiting for the chat app: a sliding-window limiter plus client-IP lookup.

The limiter is in-memory, which is correct for this deployment (one process) but means:
  * counts reset when the service restarts or wakes from sleep, and
  * it would NOT be shared across several instances (that would need a shared store).
"""
import ipaddress
import math
import os
import threading
import time
from collections import defaultdict, deque


class RateLimiter:
    """Sliding-window limiter. `rules` is a list of (max_hits, window_seconds); all must pass.

    Denied attempts are not recorded, so hammering the endpoint while blocked does not
    extend the block.
    """

    def __init__(self, rules, clock=time.monotonic, max_keys=10_000):
        if not rules:
            raise ValueError("at least one rule is required")
        self.rules = [(int(n), float(w)) for n, w in rules]
        self._clock = clock
        self._max_keys = max_keys
        self._hits = defaultdict(deque)
        self._lock = threading.Lock()
        self._longest = max(w for _, w in self.rules)

    def check(self, key: str):
        """Record a hit for `key` if allowed. Returns (allowed, retry_after_seconds)."""
        now = self._clock()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] >= self._longest:
                hits.popleft()

            retry_after = 0.0
            for limit, window in self.rules:
                recent = [t for t in hits if now - t < window]
                if len(recent) >= limit:
                    # Allowed again once the oldest hit in the blocking window ages out.
                    retry_after = max(retry_after, recent[len(recent) - limit] + window - now)
            if retry_after > 0:
                return False, retry_after

            hits.append(now)
            if len(self._hits) > self._max_keys:
                self._prune(now)
            return True, 0.0

    def _prune(self, now: float):
        """Drop keys with no hits inside the longest window (bounds memory use)."""
        for k in [k for k, d in self._hits.items() if not d or now - d[-1] >= self._longest]:
            del self._hits[k]


def retry_message(retry_after: float) -> str:
    seconds = max(1, math.ceil(retry_after))
    wait = f"{seconds} seconds" if seconds < 90 else f"{math.ceil(seconds / 60)} minutes"
    return (
        f"You're sending messages too quickly. Please wait about {wait} and try again. "
        "If it's urgent, call the shop at 555-0142."
    )


def _valid_ip(value):
    try:
        return str(ipaddress.ip_address((value or "").strip()))
    except ValueError:
        return None


def client_ip(request) -> str:
    """Best-effort real client IP, preferring headers a client cannot forge.

    On Render the app sits behind Cloudflare, which sets CF-Connecting-IP itself (a client's
    own value is overwritten). X-Forwarded-For is a weaker fallback: its leftmost entry is
    whatever the client sent, so only the proxy-appended entries are trustworthy; we use the
    last one. Locally (no proxy) the socket address is used. Returns "unknown" if nothing
    valid is found, so all such requests share one bucket rather than bypassing the limit.
    """
    if request is None:
        return "unknown"
    headers = {k.lower(): v for k, v in (getattr(request, "headers", None) or {}).items()}

    ip = _valid_ip(headers.get("cf-connecting-ip"))
    if ip:
        return ip
    forwarded = headers.get("x-forwarded-for", "")
    if forwarded:
        ip = _valid_ip(forwarded.split(",")[-1])
        if ip:
            return ip
    client = getattr(request, "client", None)
    ip = _valid_ip(getattr(client, "host", None))
    return ip or "unknown"


def limiter_from_env() -> RateLimiter:
    """Defaults: 10 messages per minute and 60 per hour per IP. Override with env vars."""
    per_minute = int(os.environ.get("RATE_LIMIT_PER_MINUTE", "10"))
    per_hour = int(os.environ.get("RATE_LIMIT_PER_HOUR", "60"))
    return RateLimiter([(per_minute, 60), (per_hour, 3600)])
