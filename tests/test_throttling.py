from django.core.cache import cache
from django.http import HttpRequest
from django.test import RequestFactory
from ninja import NinjaAPI
from ninja.testing import TestClient

from apps.common.throttling import LoginRateThrottle


def test_login_rate_throttle_limits_requests_by_ip() -> None:
    cache.clear()
    throttle = LoginRateThrottle(rate="2/minute")
    request = RequestFactory().post("/api/v1/auth/login", REMOTE_ADDR="203.0.113.1")

    assert throttle.allow_request(request)
    assert throttle.allow_request(request)
    assert not throttle.allow_request(request)


def test_throttled_route_returns_429_after_rate_limit() -> None:
    cache.clear()
    api = NinjaAPI(urls_namespace="throttle-test")

    @api.post("/login", throttle=LoginRateThrottle(rate="2/minute"))
    def login(request: HttpRequest) -> dict[str, bool]:
        del request
        return {"ok": True}

    client = TestClient(api)
    assert client.post("/login").status_code == 200
    assert client.post("/login").status_code == 200
    assert client.post("/login").status_code == 429
