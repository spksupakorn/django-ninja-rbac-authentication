# Implementation Plan — Phase 1 (RBAC Auth, JWT Bearer)

อ้างอิงการตัดสินใน [ADR](adr/README.md) เรียงตาม **dependency order** — ทำจากล่างขึ้นบน
แต่ละขั้นมี "เสร็จเมื่อ" (definition of done) ที่ verify ได้

---

## M0 — Project skeleton & tooling  → ADR-0005
1. `pyproject.toml` + `uv.lock` — deps: `django`, `django-ninja`, `psycopg[binary]`,
   `pyjwt`, `argon2-cffi`, `pydantic-settings`, `python-dotenv`; dev: `pytest`,
   `pytest-django`, `pytest-asyncio`, `ruff`, `mypy`, `factory-boy`
2. โครง repo
   ```
   config/          settings/{base,dev,prod}.py, asgi.py, urls.py, api.py (NinjaAPI root)
   apps/accounts/   User, UserManager, migrations
   apps/authz/      Role, Permission, RefreshToken, RBAC logic
   apps/common/     base repository, exceptions, pagination, throttling
   tests/
   docker/          Dockerfile
   docker-compose.yml, .env.example, manage.py
   ```
3. `config/settings/base.py` — `Settings(BaseSettings)` typed: `DATABASE_URL`,
   `JWT_SECRET`, `ACCESS_TTL=15m`, `REFRESH_TTL=7d`, `THROTTLE_LOGIN`; `AUTH_USER_MODEL`
   placeholder ยังไม่ตั้งจนกว่ามี model (M1)
4. `PASSWORD_HASHERS` = Argon2id first (ADR-0006)
5. `docker-compose.yml`: `web` (ASGI, uvicorn, build จาก uv) + `db` (Postgres 16, healthcheck),
   `web` depends_on db healthy; `.env.example`
- **DoD**: `docker compose up` ขึ้น, `GET /api/v1/health` = 200, `ruff`/`mypy` ผ่าน

## M1 — Custom User model  → ADR-0004  *(ต้องก่อน migrate แรก)*
6. `accounts.User(AbstractBaseUser, PermissionsMixin)` — email unique, `USERNAME_FIELD="email"`, ไม่มี username
7. `UserManager.create_user/create_superuser` ด้วย email
8. ตั้ง `AUTH_USER_MODEL="accounts.User"` → `makemigrations` + `migrate` ครั้งแรก
- **DoD**: `createsuperuser` ด้วย email ได้, migration แรกรันบน Postgres สำเร็จ

## M2 — RBAC domain (models + seed)  → ADR-0001
9. `authz` models: `Role`, `Permission(code="resource.action")`,
   `UserRole`, `RolePermission` (through tables + unique constraints + index)
10. `permissions.py` — enum/constants เป็น single source of truth ของ permission code
11. data migration: seed permission catalog + role เริ่มต้น
    (`admin` ได้ทุก perm, `user` = default role สิทธิ์ขั้นต่ำ); `DEFAULT_USER_ROLE="user"` ใน settings
- **DoD**: migrate + seed ผ่าน, query `user.permissions()` คืน set ของ code ถูกต้อง (unit test)

## M3 — Repository & Service scaffolding  → ADR-0003
12. `common/repositories.py` — base async repository (`aget_or_none`, `acreate`, ...)
13. `accounts/repositories.py`, `authz/repositories.py` — async ORM ที่นี่ที่เดียว
14. `common/exceptions.py` — domain errors (`InvalidCredentials`, `TokenReused`,
    `PermissionDenied`, `EmailAlreadyExists`) + exception handler กลางที่ NinjaAPI (map → HTTP)
- **DoD**: unit test repository (async) กับ test DB ผ่าน

## M4 — Password & JWT core  → ADR-0002/0006
15. `authz/security/passwords.py` — `hash_password`/`verify_password` ห่อ
    `sync_to_async(thread_sensitive=False)` + dummy verify กัน timing attack
16. `authz/security/jwt.py` — encode/decode HS256, claims `sub/exp/iat/jti/roles/perms`,
    ตรวจ exp/signature, error → domain error
- **DoD**: unit test round-trip encode/decode, token หมดอายุ/แก้ไข = reject; verify ไม่ block loop

## M5 — Auth service (use cases)  → ADR-0002
17. `RefreshToken` model: `token_hash`, `family_id`, `parent_id`, `expires_at`,
    `revoked_at`, `user` (+ index)
18. `AuthService`:
    - `register(email, password)` → สร้าง user + assign `DEFAULT_USER_ROLE` อัตโนมัติ
    - `login(email, password)` → verify → ออก access + refresh (สร้าง family ใหม่)
    - `refresh(raw_refresh)` → validate; **ถ้าใช้ token ที่ revoked แล้ว → revoke ทั้ง family (reuse-detection)**;
      ไม่งั้น rotate: revoke ตัวเดิม + ออกคู่ใหม่ใน family เดิม
    - `logout(raw_refresh)` → revoke token ปัจจุบัน
- **DoD**: unit test ครบ rotation happy path + reuse-detection revoke ทั้ง family

## M6 — Ninja auth guard & permission enforcement  → ADR-0001/0002
19. `authz/api/auth.py` — `JWTAuth(HttpBearer)` async: decode access, แนบ principal
    (user_id, roles, perms) เข้า `request.auth`
20. `require_permission(code)` — dependency/decorator เช็คจาก `request.auth.perms` → 403 ถ้าไม่มี
21. throttling ที่ login/refresh (5/min/IP) → 429 (ADR-0006)
- **DoD**: integration test — no token=401, token ไม่มี perm=403, throttle เกิน=429

## M7 — Endpoints (routers + schemas)  → ADR-0003
22. `POST /v1/auth/register` · `POST /v1/auth/login` · `POST /v1/auth/refresh` ·
    `POST /v1/auth/logout` · `GET /v1/auth/me`
23. Admin (require_permission): `users` CRUD, `POST /v1/admin/users/{id}/roles`,
    `GET /v1/admin/roles`, `GET /v1/admin/permissions` + pagination
24. Pydantic schemas in/out; login ผิดคืน 401 กลางๆ (กัน enumeration)
- **DoD**: OpenAPI docs (`/api/docs`) ครบ, e2e flow register→login→เรียก admin ด้วยสิทธิ์ถูก/ผิด ผ่าน

## M8 — Tests, CI, hardening
25. pytest: unit (service/jwt/passwords) + integration (endpoints ผ่าน async test client)
26. factory-boy fixtures; coverage เป้าหมาย service ≥ 90%
27. prod.py: secure cookies/headers, DEBUG=False, ALLOWED_HOSTS
28. README: วิธีรัน, .env, คำสั่ง compose/migrate/seed/test
- **DoD**: `pytest` เขียว, CI (lint+type+test) ผ่าน, README ครบ

---

## ลำดับ dependency
```
M0 → M1 → M2 → M3 → M4 → M5 → M6 → M7 → M8
        (M1 = ประตูทางเดียว: ตั้ง AUTH_USER_MODEL ก่อน migrate แรก)
```

## จุดเสี่ยงที่ต้องเฝ้า (จาก ADR)
- **async + ORM**: ทุก DB access ต้องผ่าน repository ที่ใช้ async methods เท่านั้น (ADR-0005)
- **Argon2 block loop**: verify/hash ต้องผ่าน `sync_to_async(thread_sensitive=False)` (ADR-0006)
- **สิทธิ์ใน token ไม่สดทันที**: ยอมรับ delay ≤15m; admin CRUD ต้องสื่อสารข้อนี้ (ADR-0002)
- **throttle in-memory ไม่ share ข้าม instance**: ย้าย Redis เมื่อ scale (Phase 2)

## นอก scope Phase 1 (Phase 2 backlog)
email verification · password reset · RS256 · object-level perms · Redis throttle/blocklist ·
async ORM รอบด้าน · audit log · refresh token binding (device/ip)
