"""Offline tests for the per-IP rate limiter, client-IP lookup, and how the app uses them."""
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ratelimit import RateLimiter, client_ip, limiter_from_env, retry_message  # noqa: E402


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def make(rules, **kw):
    clock = Clock()
    return RateLimiter(rules, clock=clock, **kw), clock


# --- RateLimiter ------------------------------------------------------------------

def test_allows_up_to_limit_then_blocks():
    lim, _ = make([(3, 60)])
    assert [lim.check("a")[0] for _ in range(4)] == [True, True, True, False]


def test_keys_are_independent():
    lim, _ = make([(1, 60)])
    assert lim.check("a")[0] is True
    assert lim.check("a")[0] is False
    assert lim.check("b")[0] is True


def test_window_expiry_unblocks():
    lim, clock = make([(2, 60)])
    lim.check("a"), lim.check("a")
    assert lim.check("a")[0] is False
    clock.advance(59)
    assert lim.check("a")[0] is False
    clock.advance(2)
    assert lim.check("a")[0] is True


def test_retry_after_is_time_until_oldest_hit_ages_out():
    lim, clock = make([(2, 60)])
    lim.check("a")            # t=0
    clock.advance(10)
    lim.check("a")            # t=10
    clock.advance(20)         # t=30
    allowed, retry = lim.check("a")
    assert not allowed
    assert retry == pytest.approx(30.0)   # first hit (t=0) leaves the window at t=60


def test_denied_attempts_do_not_extend_the_block():
    lim, clock = make([(1, 60)])
    lim.check("a")
    for _ in range(20):
        clock.advance(1)
        assert lim.check("a")[0] is False
    clock.advance(41)   # t=61 since the single recorded hit
    assert lim.check("a")[0] is True


def test_all_rules_must_pass_and_longest_wait_wins():
    lim, clock = make([(2, 60), (3, 3600)])
    for _ in range(2):
        assert lim.check("a")[0]
    assert lim.check("a")[0] is False            # minute rule
    clock.advance(61)
    assert lim.check("a")[0] is True             # 3rd hit this hour
    clock.advance(61)
    allowed, retry = lim.check("a")
    assert allowed is False                      # hour rule now binds (3 hits in last hour)
    assert retry > 3000


def test_old_hits_are_forgotten():
    lim, clock = make([(1, 60)])
    lim.check("a")
    clock.advance(120)
    assert lim.check("a")[0] is True
    assert len(lim._hits["a"]) == 1


def test_memory_is_bounded_by_pruning_expired_keys():
    lim, clock = make([(1, 60)], max_keys=50)
    for i in range(50):
        lim.check(f"ip{i}")
    clock.advance(120)
    for i in range(50, 60):
        lim.check(f"ip{i}")
    assert len(lim._hits) <= 20      # the 50 expired keys were dropped


def test_requires_a_rule():
    with pytest.raises(ValueError):
        RateLimiter([])


def test_limiter_from_env_defaults_and_overrides(monkeypatch):
    monkeypatch.delenv("RATE_LIMIT_PER_MINUTE", raising=False)
    monkeypatch.delenv("RATE_LIMIT_PER_HOUR", raising=False)
    assert limiter_from_env().rules == [(10, 60.0), (60, 3600.0)]
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "3")
    monkeypatch.setenv("RATE_LIMIT_PER_HOUR", "7")
    assert limiter_from_env().rules == [(3, 60.0), (7, 3600.0)]


@pytest.mark.parametrize("seconds,expected", [(0.2, "1 seconds"), (12.1, "13 seconds"), (200, "4 minutes")])
def test_retry_message_wording(seconds, expected):
    assert expected in retry_message(seconds)
    assert "555-0142" in retry_message(seconds)


# --- client_ip --------------------------------------------------------------------

def req(headers=None, host=None):
    return SimpleNamespace(headers=headers or {}, client=SimpleNamespace(host=host) if host else None)


def test_prefers_cloudflare_header_over_everything():
    r = req({"CF-Connecting-IP": "203.0.113.9", "X-Forwarded-For": "1.1.1.1, 2.2.2.2"}, host="10.0.0.1")
    assert client_ip(r) == "203.0.113.9"


def test_forged_leftmost_forwarded_for_entry_is_ignored():
    # A client can send its own X-Forwarded-For; proxies append. Only the last entry is trusted.
    r = req({"x-forwarded-for": "6.6.6.6, 198.51.100.7"}, host="10.0.0.1")
    assert client_ip(r) == "198.51.100.7"


def test_invalid_header_values_fall_through():
    r = req({"cf-connecting-ip": "not-an-ip", "x-forwarded-for": "also bad"}, host="192.0.2.5")
    assert client_ip(r) == "192.0.2.5"


def test_socket_address_used_when_no_proxy_headers():
    assert client_ip(req(host="127.0.0.1")) == "127.0.0.1"


def test_ipv6_is_normalized():
    assert client_ip(req({"cf-connecting-ip": "2001:DB8:0:0:0:0:0:1"})) == "2001:db8::1"


def test_unknown_when_nothing_valid():
    assert client_ip(None) == "unknown"
    assert client_ip(req()) == "unknown"


# --- app integration --------------------------------------------------------------

@pytest.fixture
def app_module(monkeypatch):
    import app

    clock = Clock()
    monkeypatch.setattr(app, "limiter", RateLimiter([(2, 60)], clock=clock))
    calls = []
    monkeypatch.setattr(app, "respond", lambda m, h, t: calls.append(m) or f"echo:{m}")
    return app, calls, clock


def test_chat_blocks_without_calling_the_model_and_keeps_the_text(app_module):
    app, calls, _ = app_module
    r = req(host="127.0.0.1")
    box, hist = app.chat("one", [], "t", r)
    box, hist = app.chat("two", hist, "t", r)
    assert calls == ["one", "two"] and box == ""

    box, hist = app.chat("three", hist, "t", r)
    assert calls == ["one", "two"]                   # model NOT called
    assert box == "three"                            # text kept so it can be resent
    assert hist[-1]["role"] == "assistant"
    assert "too quickly" in hist[-1]["content"]
    assert sum(1 for m in hist if m["role"] == "user") == 2   # blocked message didn't use the chat cap


def test_chat_limits_each_ip_separately(app_module):
    app, calls, _ = app_module
    a, b = req(host="10.0.0.1"), req(host="10.0.0.2")
    for _ in range(2):
        app.chat("x", [], "t", a)
    assert app.chat("y", [], "t", a)[0] == "y"       # a is blocked
    assert app.chat("y", [], "t", b)[0] == ""        # b is fine


def test_chat_recovers_after_the_window(app_module):
    app, calls, clock = app_module
    r = req(host="127.0.0.1")
    for _ in range(2):
        app.chat("x", [], "t", r)
    assert app.chat("y", [], "t", r)[0] == "y"
    clock.advance(61)
    assert app.chat("y", [], "t", r)[0] == ""


def test_empty_messages_do_not_count(app_module):
    app, calls, _ = app_module
    r = req(host="127.0.0.1")
    for _ in range(10):
        assert app.chat("   ", [], "t", r) == ("", [])
    assert app.chat("real", [], "t", r)[0] == ""
    assert calls == ["real"]


def test_spoofed_forwarded_for_cannot_dodge_the_limit(app_module):
    app, calls, _ = app_module
    # Same real IP (Cloudflare header) but a different forged X-Forwarded-For each time.
    for i in range(2):
        app.chat("x", [], "t", req({"cf-connecting-ip": "203.0.113.9", "x-forwarded-for": f"9.9.9.{i}"}))
    blocked = app.chat("y", [], "t", req({"cf-connecting-ip": "203.0.113.9", "x-forwarded-for": "8.8.8.8"}))
    assert blocked[0] == "y"
