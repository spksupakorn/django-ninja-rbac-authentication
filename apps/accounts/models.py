"""Account domain models."""

from __future__ import annotations

from typing import Any

from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.db.models.functions import Lower


class UserManager(BaseUserManager):
    """Create users whose unique identity is their email address."""

    def normalize_email(self, email: str) -> str:
        """Normalize an email identity to its case-insensitive canonical form."""
        return super().normalize_email(email).lower()

    def create_user(
        self, email: str, password: str | None = None, **extra_fields: Any
    ) -> User:
        """Create and save a regular user."""
        if not email:
            raise ValueError("The email address must be set")

        user = self.model(email=self.normalize_email(email), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(
        self, email: str, password: str | None = None, **extra_fields: Any
    ) -> User:
        """Create and save an administrator with the required Django flags."""
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """Application user identified by email rather than a username."""

    email = models.EmailField(unique=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    class Meta:
        constraints = [
            models.UniqueConstraint(Lower("email"), name="accounts_user_email_ci_unique"),
        ]

    def __str__(self) -> str:
        return self.email
