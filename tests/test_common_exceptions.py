import json

from django.test import RequestFactory

from apps.common.exceptions import (
    EmailAlreadyExists,
    InvalidCredentials,
    PermissionDenied,
    TokenReused,
)
from config.api import handle_domain_error


def test_domain_error_handler_returns_safe_error_response() -> None:
    response = handle_domain_error(RequestFactory().get("/api/test"), EmailAlreadyExists())

    assert response.status_code == 409
    assert json.loads(response.content) == {
        "success": False,
        "code": 409,
        "message": "Request could not be completed.",
        "data": None,
    }


def test_domain_errors_define_expected_http_mappings() -> None:
    assert InvalidCredentials.status_code == 401
    assert TokenReused.status_code == 401
    assert PermissionDenied.status_code == 403
