"""Create an initial Django/API administrator safely and idempotently."""

from __future__ import annotations

import os
import sys
from argparse import ArgumentParser
from getpass import getpass
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import User
from apps.authz.models import Role, UserRole

_PASSWORD_ENVIRONMENT_VARIABLE = "BOOTSTRAP_ADMIN_PASSWORD"


class Command(BaseCommand):
    """Bootstrap one account for Django admin and the API RBAC admin role."""

    help = "Create or update an administrator and assign the authz admin role."

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("--email", required=True, help="Administrator email address.")

    def handle(self, *args: object, **options: Any) -> None:
        del args
        email = User.objects.normalize_email(str(options["email"]))
        with transaction.atomic():
            try:
                admin_role = Role.objects.get(name="admin")
            except Role.DoesNotExist as exc:
                msg = "The authz admin role does not exist. Run migrate first."
                raise CommandError(msg) from exc

            user = User.objects.filter(email=email).first()
            if user is None:
                user = User.objects.create_superuser(email=email, password=self._password())
                created = True
            else:
                created = False
                self._ensure_django_admin_flags(user)

            _, role_created = UserRole.objects.get_or_create(user=user, role=admin_role)

        action = "Created" if created else "Updated"
        role_action = "assigned" if role_created else "already assigned"
        self.stdout.write(
            self.style.SUCCESS(
                f"{action} administrator {user.email}; authz admin role {role_action}."
            )
        )

    def _password(self) -> str:
        """Read the bootstrap password without accepting it as a CLI argument."""
        password = os.environ.get(_PASSWORD_ENVIRONMENT_VARIABLE)
        if password:
            return password
        if sys.stdin.isatty():
            password = getpass("Administrator password: ")
            if password:
                return password
        raise CommandError(
            f"Set {_PASSWORD_ENVIRONMENT_VARIABLE} when creating a new administrator."
        )

    @staticmethod
    def _ensure_django_admin_flags(user: User) -> None:
        """Make an existing account eligible for Django's built-in admin site."""
        fields: list[str] = []
        for field_name in ("is_active", "is_staff", "is_superuser"):
            if not getattr(user, field_name):
                setattr(user, field_name, True)
                fields.append(field_name)
        if fields:
            user.save(update_fields=fields)
