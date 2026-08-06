from unittest.mock import MagicMock, patch

import pytest
from django.core.management.base import CommandError
from django.db.utils import OperationalError

from apps.common.management.commands.wait_for_db import Command


def test_wait_for_db_closes_connection_after_it_is_ready() -> None:
    connection = MagicMock()

    with patch(
        "apps.common.management.commands.wait_for_db.connections", {"default": connection}
    ):
        Command().handle(timeout=0, interval=1)

    connection.ensure_connection.assert_called_once_with()
    connection.close.assert_called_once_with()


def test_wait_for_db_fails_after_timeout() -> None:
    connection = MagicMock()
    connection.ensure_connection.side_effect = OperationalError("database unavailable")

    with (
        patch(
            "apps.common.management.commands.wait_for_db.connections", {"default": connection}
        ),
        pytest.raises(CommandError, match="did not become available"),
    ):
        Command().handle(timeout=0, interval=1)
