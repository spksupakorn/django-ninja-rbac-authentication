"""Wait for the configured Django database before starting a server."""

from __future__ import annotations

from argparse import ArgumentParser
from time import monotonic, sleep
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import connections
from django.db.utils import OperationalError


class Command(BaseCommand):
    """Block startup until the default database accepts a connection."""

    help = "Wait until the configured default database accepts connections."

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--timeout",
            type=float,
            default=60.0,
            help="Maximum seconds to wait before exiting with an error (default: 60).",
        )
        parser.add_argument(
            "--interval",
            type=float,
            default=1.0,
            help="Seconds between connection attempts (default: 1).",
        )

    def handle(self, *args: object, **options: Any) -> None:
        del args
        timeout = float(options["timeout"])
        interval = float(options["interval"])
        if timeout < 0:
            raise CommandError("--timeout must be zero or greater")
        if interval <= 0:
            raise CommandError("--interval must be greater than zero")

        deadline = monotonic() + timeout
        while True:
            connection = connections["default"]
            try:
                connection.ensure_connection()
            except OperationalError as exc:
                if monotonic() >= deadline:
                    raise CommandError("Database did not become available before timeout.") from exc
                self.stdout.write("Waiting for database connection...")
                sleep(interval)
            else:
                connection.close()
                self.stdout.write(self.style.SUCCESS("Database connection is ready."))
                return
