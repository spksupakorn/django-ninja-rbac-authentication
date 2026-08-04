# Separate management and HTTP server entry points

The learner initially treated `manage.py` as the HTTP request entry point. The distinction was
corrected: `manage.py` starts Django management commands, while Uvicorn imports
`config.asgi:application` to serve HTTP; both set `DJANGO_SETTINGS_MODULE` so they share settings.
