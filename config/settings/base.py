"""Shared, validated Django settings."""

from __future__ import annotations

import re
from datetime import timedelta
from ipaddress import ip_network
from pathlib import Path
from typing import Final

import dj_database_url
from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR: Final = Path(__file__).resolve().parents[2]
_TTL_PATTERN: Final = re.compile(r"^(?P<value>[1-9][0-9]*)\s*(?P<unit>[mhd])$")


def parse_ttl(value: str) -> timedelta:
    """Convert a positive duration such as ``15m`` or ``7d`` to a timedelta."""
    match = _TTL_PATTERN.fullmatch(value.strip())
    if not match:
        msg = "TTL must be a positive duration using m, h, or d, e.g. 15m, 1h, or 7d"
        raise ValueError(msg)

    amount = int(match["value"])
    unit = match["unit"]
    keyword = {"m": "minutes", "h": "hours", "d": "days"}[unit]
    return timedelta(**{keyword: amount})


class Settings(BaseSettings):
    """Environment-backed configuration validated while Django boots."""

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env", extra="ignore", enable_decoding=False
    )

    database_url: str = Field(validation_alias="DATABASE_URL", min_length=1)
    django_secret_key: SecretStr = Field(
        validation_alias="DJANGO_SECRET_KEY", min_length=32
    )
    jwt_secret: SecretStr = Field(validation_alias="JWT_SECRET", min_length=32)
    access_ttl: timedelta = Field(
        default_factory=lambda: parse_ttl("15m"), validation_alias="ACCESS_TTL"
    )
    refresh_ttl: timedelta = Field(
        default_factory=lambda: parse_ttl("7d"), validation_alias="REFRESH_TTL"
    )
    refresh_bind_device: bool = Field(default=True, validation_alias="REFRESH_BIND_DEVICE")
    refresh_bind_ip: bool = Field(default=False, validation_alias="REFRESH_BIND_IP")
    default_user_role: str = Field(default="user", validation_alias="DEFAULT_USER_ROLE")
    throttle_login: str = Field(default="5/minute", validation_alias="THROTTLE_LOGIN")
    redis_url: str = Field(default="redis://redis:6379/0", validation_alias="REDIS_URL")
    allowed_hosts: list[str] = Field(default_factory=list, validation_alias="ALLOWED_HOSTS")
    trusted_proxy_cidrs: list[str] = Field(
        default_factory=list, validation_alias="TRUSTED_PROXY_CIDRS"
    )

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        try:
            database_config = dj_database_url.parse(value)
        except ValueError as exc:
            msg = "DATABASE_URL must be a valid PostgreSQL URL"
            raise ValueError(msg) from exc
        if (
            database_config.get("ENGINE") != "django.db.backends.postgresql"
            or not database_config.get("HOST")
            or not database_config.get("NAME")
        ):
            msg = "DATABASE_URL must be a PostgreSQL URL, e.g. postgresql://user:pass@host:5432/db"
            raise ValueError(msg)
        return value

    @field_validator("access_ttl", "refresh_ttl", mode="before")
    @classmethod
    def validate_ttl(cls, value: str | timedelta) -> timedelta:
        if isinstance(value, timedelta):
            return value
        return parse_ttl(value)

    @field_validator("allowed_hosts", mode="before")
    @classmethod
    def parse_allowed_hosts(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, list):
            return value
        return [host.strip() for host in value.split(",") if host.strip()]

    @field_validator("trusted_proxy_cidrs", mode="before")
    @classmethod
    def validate_trusted_proxy_cidrs(cls, value: str | list[str]) -> list[str]:
        cidrs = value if isinstance(value, list) else [item.strip() for item in value.split(",")]
        valid_cidrs = [cidr for cidr in cidrs if cidr]
        try:
            for cidr in valid_cidrs:
                ip_network(cidr, strict=False)
        except ValueError as exc:
            msg = "TRUSTED_PROXY_CIDRS must contain valid IPv4 or IPv6 CIDRs"
            raise ValueError(msg) from exc
        return valid_cidrs

    @model_validator(mode="after")
    def validate_distinct_secrets(self) -> Settings:
        if self.django_secret_key.get_secret_value() == self.jwt_secret.get_secret_value():
            msg = "DJANGO_SECRET_KEY and JWT_SECRET must be different values"
            raise ValueError(msg)
        return self


settings = Settings()  # type: ignore[call-arg]

SECRET_KEY = settings.django_secret_key.get_secret_value()
DEBUG = False
ALLOWED_HOSTS: list[str] = []
ROOT_URLCONF = "config.urls"
ASGI_APPLICATION = "config.asgi.application"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "accounts.User"
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "apps.accounts",
    "apps.authz",
    "apps.audit",
    "apps.common",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": [
            "django.template.context_processors.request",
            "django.contrib.auth.context_processors.auth",
            "django.contrib.messages.context_processors.messages",
        ]},
    },
]

DATABASES = {"default": dj_database_url.parse(settings.database_url, conn_max_age=0)}

# Used by Django Ninja's SimpleRateThrottle.  Redis failures intentionally degrade to
# an allowed request so a cache outage does not turn into an authentication outage.
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": settings.redis_url,
        "OPTIONS": {"IGNORE_EXCEPTIONS": True},
        "KEY_PREFIX": "rbac_auth",
    }
}

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
    "django.contrib.auth.hashers.ScryptPasswordHasher",
]

STATIC_URL = "static/"

# JWT-related values stay typed and are exposed for later auth layers.
JWT_SECRET = settings.jwt_secret
ACCESS_TTL = settings.access_ttl
REFRESH_TTL = settings.refresh_ttl
REFRESH_BIND_DEVICE = settings.refresh_bind_device
REFRESH_BIND_IP = settings.refresh_bind_ip
DEFAULT_USER_ROLE = settings.default_user_role
TRUSTED_PROXY_CIDRS = settings.trusted_proxy_cidrs
THROTTLE_LOGIN = settings.throttle_login
REDIS_URL = settings.redis_url
ACCESS_TOKEN_LIFETIME = settings.access_ttl
REFRESH_TOKEN_LIFETIME = settings.refresh_ttl
