"""Request-derived data supplied to audit use cases."""

from __future__ import annotations

from dataclasses import dataclass
from ipaddress import IPv4Address, IPv6Address, ip_address, ip_network
from typing import TYPE_CHECKING

from django.conf import settings
from django.http import HttpRequest

if TYPE_CHECKING:
    from apps.authz.api.auth import Principal


@dataclass(frozen=True)
class AuditContext:
    """HTTP details captured by a router without exposing a request to services."""

    actor_id: int | None = None
    actor_email: str | None = None
    ip: str | None = None
    user_agent: str | None = None
    request_id: str | None = None

    @classmethod
    def from_request(
        cls, request: HttpRequest, principal: Principal | None = None
    ) -> AuditContext:
        """Build a context snapshot from an HTTP request and authenticated principal."""
        return cls(
            actor_id=principal.user_id if principal is not None else None,
            actor_email=getattr(principal, "email", None),
            ip=_client_ip(request),
            user_agent=(request.headers.get("User-Agent") or None),
            request_id=(request.headers.get("X-Request-ID") or None),
        )


def _client_ip(request: HttpRequest) -> str | None:
    """Honor X-Forwarded-For only when the direct peer is a trusted proxy."""
    remote_addr = request.META.get("REMOTE_ADDR")
    if not remote_addr:
        return None
    try:
        remote_ip = ip_address(remote_addr)
    except ValueError:
        return remote_addr
    if not _is_trusted_proxy(remote_ip):
        return str(remote_ip)

    forwarded_for = request.headers.get("X-Forwarded-For")
    if not forwarded_for:
        return str(remote_ip)
    for candidate in reversed([item.strip() for item in forwarded_for.split(",")]):
        try:
            candidate_ip = ip_address(candidate)
        except ValueError:
            continue
        if not _is_trusted_proxy(candidate_ip):
            return str(candidate_ip)
    return str(remote_ip)


def _is_trusted_proxy(ip: IPv4Address | IPv6Address) -> bool:
    return any(ip in ip_network(cidr, strict=False) for cidr in settings.TRUSTED_PROXY_CIDRS)
