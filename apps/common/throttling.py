"""Reusable throttles for public authentication endpoints."""

from __future__ import annotations

from django.conf import settings
from django.http import HttpRequest
from ninja.throttling import SimpleRateThrottle


class _IpRateThrottle(SimpleRateThrottle):
    """Rate-limit by client IP, using a per-subclass cache bucket (``scope``)."""

    scope = "ip"

    def __init__(self, rate: str | None = None) -> None:
        super().__init__(_normalize_rate(rate or settings.THROTTLE_LOGIN))

    def get_cache_key(self, request: HttpRequest) -> str | None:
        ident = self.get_ident(request)
        if ident is None:
            return None
        return self.cache_format % {"scope": self.scope, "ident": ident}


class LoginRateThrottle(_IpRateThrottle):
    """Shared IP bucket for login and refresh attempts."""

    scope = "login"


class RegisterRateThrottle(_IpRateThrottle):
    """Separate IP bucket for registration, to slow account enumeration."""

    scope = "register"


def _normalize_rate(rate: str) -> str:
    """Translate human-readable environment units to Ninja's short forms."""
    count, separator, period = rate.partition("/")
    if not count or not separator or not period:
        return rate
    units = {
        "second": "sec",
        "minute": "min",
        "hour": "hour",
        "day": "day",
    }
    return f"{count}/{units.get(period, period)}"
