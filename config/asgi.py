"""ASGI entry point for the project."""

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

from django.core.asgi import get_asgi_application

application = get_asgi_application()
