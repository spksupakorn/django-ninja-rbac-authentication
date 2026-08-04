# Django Ninja RBAC Project Resources

## Knowledge

- [Django: How Django processes a request](https://docs.djangoproject.com/en/5.2/topics/http/urls/)
  Official explanation of URL resolution and views. Use for: tracing a URL from Django's entry
  point to a response.
- [Django: Settings](https://docs.djangoproject.com/en/5.2/topics/settings/)
  Official guide to settings modules and `DJANGO_SETTINGS_MODULE`. Use for: understanding why
  `config/settings/` controls how the app boots.
- [Django: ASGI deployment](https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/)
  Official guide to the ASGI application callable. Use for: understanding `config/asgi.py` and
  Uvicorn.
- [Django: Applications](https://docs.djangoproject.com/en/5.2/ref/applications/)
  Official explanation of Django application configuration and the app registry. Use for:
  understanding `INSTALLED_APPS`, `AppConfig`, model discovery, and migrations.
- [Django: Customizing authentication](https://docs.djangoproject.com/en/5.2/topics/auth/customizing/)
  Official guide to custom user models, `AUTH_USER_MODEL`, and migration constraints. Use for:
  understanding M1 before the project creates its first application migration.
- [Django: Migrations](https://docs.djangoproject.com/en/5.2/topics/migrations/)
  Official migration workflow and concepts. Use for: understanding the difference between creating
  migration files and applying schema changes to PostgreSQL.
- [Django: Data migrations](https://docs.djangoproject.com/en/5.2/topics/migrations/#data-migrations)
  Official migration guidance for versioned initial data. Use for: understanding how M2 seeds the
  permission catalog and default roles consistently in every environment.
- [Django: Async support](https://docs.djangoproject.com/en/5.2/topics/async/)
  Official async view and ORM guidance. Use for: understanding async-safe query methods and why
  repositories contain the project’s database boundary.
- [Django: Password management](https://docs.djangoproject.com/en/5.2/topics/auth/passwords/)
  Official password hashing and verification guide. Use for: understanding `set_password`,
  `check_password`, configured hashers, and why raw passwords are never stored.
- [PyJWT usage guide](https://pyjwt.readthedocs.io/en/stable/usage.html)
  Official PyJWT documentation. Use for: creating and verifying HS256 JWTs safely.
- [Django Ninja: Authentication](https://django-ninja.dev/guides/authentication/)
  Official guide to Ninja authentication hooks. Use for: understanding the bearer-auth guard and
  how authenticated request context reaches protected endpoints.
- [Django Ninja: Schema](https://django-ninja.dev/guides/input/)
  Official guide to request validation and response schemas. Use for: defining safe, explicit API
  contracts for the auth and admin endpoints in M7.
- [Django: Testing overview](https://docs.djangoproject.com/en/5.2/topics/testing/overview/)
  Official guide to Django test databases and test execution. Use for: understanding integration
  tests and how schema migrations are exercised in M8.
- [pytest documentation](https://docs.pytest.org/)
  Official pytest documentation. Use for: test discovery, fixtures, and concise unit-test design.
- [RFC 7519 — JSON Web Token](https://www.rfc-editor.org/rfc/rfc7519)
  The JWT standard. Use for: the registered claims and token format underlying the project’s auth
  design.
- [Django: Many-to-many relationships](https://docs.djangoproject.com/en/5.2/topics/db/examples/many_to_many/)
  Official relationship examples. Use for: understanding the join tables that express RBAC links.
- [Project ADR 0001 — RBAC model](docs/adr/0001-rbac-role-permission-model.md)
  The project’s accepted design for Role, Permission, UserRole, and RolePermission. Use for:
  explaining authorization behavior in M2 and later auth flows.
- [Project ADR 0003 — Layered architecture](docs/adr/0003-layered-architecture.md)
  The project’s accepted API, service, repository, and model separation. Use for: understanding
  where HTTP concerns, business rules, and async ORM queries belong from M3 onward.
- [Project ADR 0002 — JWT strategy](docs/adr/0002-jwt-auth-strategy.md)
  The project’s accepted access/refresh-token, rotation, and reuse-detection design. Use for:
  understanding authentication flows in M4–M6.
- [Django Ninja: First steps](https://django-ninja.dev/tutorial/)
  Official Django Ninja tutorial. Use for: the `NinjaAPI` object, endpoint decorators, schemas,
  and generated API docs.
- [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
  Official guide to `BaseSettings`, environment variables, and dotenv files. Use for: explaining
  how this project validates configuration before Django finishes booting.
- [Project implementation plan](docs/IMPLEMENTATION_PLAN.md)
  The project’s primary source for scope and dependency order. Use for: placing each future
  milestone in the codebase.

## Wisdom (Communities)

- [Django Forum](https://forum.djangoproject.com/)
  Officially hosted, well-moderated community. Use for: framework questions after reducing a
  problem to a small reproducible example.
- [Django Discord](https://www.djangoproject.com/community/)
  Django community channels listed by the Django project. Use for: practical discussion and
  learning from other maintainers.
