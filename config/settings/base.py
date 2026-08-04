"""Shared, validated Django settings."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import Final
from urllib.parse import urlparse

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR: Final = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Environment-backed configuration validated while Django boots."""

    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")

    database_url: str = Field(validation_alias="DATABASE_URL", min_length=1)
    jwt_secret: SecretStr = Field(validation_alias="JWT_SECRET", min_length=32)
    access_ttl: str = Field(default="15m", validation_alias="ACCESS_TTL")
    refresh_ttl: str = Field(default="7d", validation_alias="REFRESH_TTL")
    throttle_login: str = Field(default="5/minute", validation_alias="THROTTLE_LOGIN")

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        parsed = urlparse(value)
        if (
            parsed.scheme not in {"postgres", "postgresql"}
            or not parsed.hostname
            or not parsed.path
        ):
            msg = "DATABASE_URL must be a PostgreSQL URL, e.g. postgresql://user:pass@host:5432/db"
            raise ValueError(msg)
        return value


settings = Settings()  # type: ignore[call-arg]
_database_url = urlparse(settings.database_url)

SECRET_KEY = settings.jwt_secret.get_secret_value()
DEBUG = False
ALLOWED_HOSTS: list[str] = []
ROOT_URLCONF = "config.urls"
ASGI_APPLICATION = "config.asgi.application"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
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

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": _database_url.path.lstrip("/"),
        "USER": _database_url.username,
        "PASSWORD": _database_url.password,
        "HOST": _database_url.hostname,
        "PORT": _database_url.port or 5432,
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
THROTTLE_LOGIN = settings.throttle_login
ACCESS_TOKEN_LIFETIME = timedelta(minutes=15)
REFRESH_TOKEN_LIFETIME = timedelta(days=7)
