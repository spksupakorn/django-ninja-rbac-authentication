# Implementation Plan — Async ORM รอบด้าน (Hardening)

อ้างอิง [ADR-0005](adr/0005-async-runtime-and-tooling.md) (async runtime + ORM caveat) และ
[ADR-0003](adr/0003-layered-architecture.md) (repository = ที่เดียวที่แตะ ORM)
เรียงตาม dependency order แต่ละขั้นมี DoD ที่ verify ได้

โค้ด phase 1 เป็น async ORM ครบทุก repository อยู่แล้ว (ทุก DB access ผ่าน async methods,
multi-write ห่อ `transaction.atomic()` ใน `sync_to_async(thread_sensitive=True)`)
แผนนี้ **ไม่ใช่การ rewrite** แต่คือ pass ปิด caveat ที่ ADR-0005 บันทึกไว้ให้ครบรอบด้าน:
บังคับวินัย (enforcement), กัน lazy-load trap ที่ boundary, audit atomicity, และ connection lifecycle

---

## AO1 — Baseline audit & inventory  → ADR-0005/0003
1. รวบรวมทุก ORM touchpoint (`.objects`, `.save`, `.delete`, `.refresh_from_db`) — ยืนยันอยู่ใน
   `apps/**/repositories/` ทั้งหมด; ถ้ามีตัวที่รั่วออกนอก repo → ใส่ fix-list
2. รวบรวมทุก `sync_to_async` + ค่า `thread_sensitive` (คาดหวัง: password hashing = `False`,
   transaction wrapper = `True`) — ตารางกำกับเหตุผลแต่ละตัว
3. รวบรวมทุกจุดที่ `services`/`api` import `apps.*.models` หรือ `django.db.models` (baseline
   สำหรับ contract ใน AO4)
- **DoD**: ตาราง inventory commit ลงแผน; ยืนยัน "ORM = 0 นอก repository"; fix-list (ถ้ามี) ชัดเจน

### AO1 inventory (2026-08-08)

| Surface | ORM touchpoints | Result |
| --- | --- | --- |
| `apps/accounts/repositories/users.py` | user create/read/list/count/update/delete | Repository-only; returns `UserDTO` |
| `apps/authz/repositories/rbac.py` | user/role/permission and link create/read/list/count | Repository-only; returns DTOs/scalars |
| `apps/authz/repositories/refresh_tokens.py` | refresh token create/read/revoke/locked rotation | Repository-only; returns `RefreshTokenDTO` |
| `apps/audit/repositories.py` | audit create/read/list | Repository-only; returns `AuditLogDTO` |
| `apps/*/models.py` | model-manager internals | Model implementation, not an application-layer query |
| `apps/*/migrations/` | historical data migrations | Django migration allowlist |
| `apps/common/management/commands/bootstrap_admin.py` | bootstrap user/role writes | Management-command allowlist |

**Result:** application services and API modules have zero imports of `apps.*.models` or
`django.db.models`; no ORM touchpoint leaks outside the repository, migration, model, or
management-command allowlists. Fix-list: none.

| `sync_to_async` site | `thread_sensitive` | Reason |
| --- | --- | --- |
| `apps/authz/security/passwords.py::hash_password` | `False` | CPU-bound password hashing; no DB connection state |
| `apps/authz/security/passwords.py::verify_password` | `False` | CPU-bound password verification; no DB connection state |
| `apps/common/db.py::run_in_transaction` | `True` | synchronous `transaction.atomic()` and row locks must retain one DB thread/connection |
| `config/asgi.py::_database_is_ready` | `True` | startup DB connection check |
| test fixtures/tests | `True` or default | test-only connection cleanup and synchronous test setup |

## AO2 — Repository DTO boundary (กัน lazy-load trap)  → ADR-0003
*(blast radius ใหญ่สุด — ทำทีละ app, รักษาเทสต์เขียวทุก repo)*
4. นิยาม output DTO เป็น `@dataclass(frozen=True)` ต่อ read ของ repo:
   `UserDTO`, `RoleDTO`, `PermissionDTO`, `RefreshTokenDTO` (+ page/list DTO ตามจำเป็น)
   วางไว้ `apps/<app>/repositories/dtos.py` (หรือ `common/dtos.py` สำหรับตัวร่วม)
5. repository **คืน DTO / `.values()` / scalar เท่านั้น** — ห้ามคืน Django Model instance ข้าม
   boundary ออกไปให้ service/router เด็ดขาด (กันเผลอ `obj.relation.field` → `SynchronousOnlyOperation`)
6. query ที่ต้องใช้ relation → ใช้ `select_related`/`prefetch_related` **ภายใน repo** แล้ว flatten
   ลงฟิลด์ DTO (ไม่มี lazy access หลุดออก, กัน N+1 พร้อมกัน)
7. service/router รับ-ส่ง DTO อย่างเดียว; ปรับ type hints ของ service/repo ให้เป็น DTO
8. **schema boundary**: Ninja `ModelSchema` import model + lazy-load ได้ → เปลี่ยน schema out ที่
   อิง model ให้เป็น `Schema` ธรรมดา (`from_attributes`) map จาก DTO แทน
- **DoD**: signature ของ repo คืน DTO; ไม่มี `Model` type ใน signature ของ service/router ใดๆ
  (grep/mypy ยืนยัน); เทสต์เดิมเขียว

### AO2 implementation (2026-08-08)

Repository reads and writes now detach ORM objects immediately into frozen `UserDTO`, `RoleDTO`,
`PermissionDTO`, `RefreshTokenDTO`, and `AuditLogDTO` (plus link DTOs). Services and routers use
those DTOs exclusively. Output schemas are plain Ninja `Schema` classes and routers map DTO fields
explicitly, so `ModelSchema` cannot trigger relation access outside the repository boundary.

`UserDTO` deliberately excludes the password hash. The login path uses the narrower
`CredentialsDTO` from `UserRepository.aget_credentials()` instead; it carries the canonical email
needed to write the successful-login audit event without a second user query.

## AO3 — Guardrail Layer 1: pytest AST scan (primary)  → ADR-0003
9. `tests/architecture/test_orm_boundary.py` — เดิน AST ทุกไฟล์ใน `apps/` แล้ว **fail** ถ้าพบการ
   เรียก `.objects` / `.save()` / `.delete()` / `.refresh_from_db()` นอก `apps/**/repositories/`
   (allowlist: repositories, migrations, management commands)
10. ยืนยันด้วย negative test: ปลูก `.objects.` ปลอมใน service ชั่วคราว → test ต้องแดง
- **DoD**: test ผ่านบน tree ปัจจุบัน; การปลูก ORM นอก repo ทำให้ test แดงจริง

### AO3 implementation (2026-08-09)

`tests/architecture/test_orm_boundary.py` AST-scans all application modules and rejects `.objects`,
`.save()`, `.delete()`, and `.refresh_from_db()` outside repository, migration, management-command,
or model-definition allowlists. Its negative test proves a service-level `User.objects` access fails.

## AO4 — Guardrail Layer 2: import contract (secondary)  → ADR-0003
*(ขนานกับ AO3 ได้หลัง AO2)*
11. เพิ่ม `import-linter` (dev dep) + config (`pyproject.toml` / `.importlinter`)
12. forbidden contract: `apps.*.services` และ `apps.*.api` **ห้าม import** `apps.*.models`
    และ `django.db.models` (repository + dto layer = ชั้นที่แตะ model ได้เท่านั้น)
13. รัน `lint-imports` ใน CI (ต่อจาก ruff/mypy)
- **DoD**: `lint-imports` เขียว; contract อยู่ใน CI; violation ทำให้ CI แดง

### AO4 implementation (2026-08-09)

`import-linter` forbids every service and API package from importing application Django models;
the AST architecture test also checks the specific external `django.db.models` import because
import-linter cannot target external-package submodules. `lint-imports` is part of CI.

## AO5 — Transaction atomicity audit  → ADR-0005/0002
14. ตาราง audit ทุก multi-write flow: `register` (atomic ✓), `refresh._rotate`
    (atomic + `select_for_update` ✓); ยืนยัน single-write/idempotent (`assign_role`,
    `update_user`, `logout`) ไม่ต้อง atomic (+ note blocklist = Redis ไม่เข้า DB txn)
15. สกัด idiom เป็น helper `apps/common/db.py::run_in_transaction(fn, /, **kwargs)` =
    `sync_to_async(thread_sensitive=True)` ครอบ `transaction.atomic()`; refactor
    `_create_user_with_role` / `_rotate` มาใช้ helper เดียวกัน
16. document กติกา `thread_sensitive`: hashing/CPU-bound = `False`, ORM-transaction = `True`
    (ต้อง share connection เดียวกันทั้ง transaction); ระบุชัด **async ไม่มี native atomic**
- **DoD**: ตาราง audit ในแผน; helper ถูกใช้จริง; test พิสูจน์ rollback (register ที่ assign role
  ล้มกลางคัน → user ไม่ถูก persist)

### AO5 implementation (2026-08-09)

| Flow | Classification | Atomicity decision |
| --- | --- | --- |
| `register` / `acreate_user_with_role` | multi-write: user + `UserRole` | `run_in_transaction()` ✓; FK failure rollback test proves no orphan user |
| `refresh._rotate` | multi-write: revoke + replacement token | `run_in_transaction()` + `select_for_update()` ✓ |
| `assign_role`, `update_user`, `logout` | single-write or idempotent | no DB transaction required |
| blocklist writes | Redis, outside the database | intentionally not included in DB transaction |

`apps.common.db.run_in_transaction()` is the only transaction bridge used by repository flows. It
wraps synchronous `transaction.atomic()` in `sync_to_async(thread_sensitive=True)`: ORM
transactions must retain their DB thread/connection; CPU-bound password hashing remains
`thread_sensitive=False`. Django does not provide native async `transaction.atomic()`.

## AO6 — Connection lifecycle ใน ASGI  → ADR-0005
17. คง `CONN_MAX_AGE=0` ใน ASGI (Django ไม่แนะนำ persistent connections สำหรับ async); ยืนยันว่า
    per-request `close_old_connections` ของ Django ครอบ thread-sensitive executor ที่รัน ORM
18. concurrency test: ยิง endpoint ที่แตะ DB พร้อมกัน N ครั้ง (เช่น refresh/login) แล้ว assert
    ไม่มี `InterfaceError` / "connection already closed"
- **DoD**: settings ตั้งครบ; concurrency test เขียวไม่มี connection error

### AO6 implementation (2026-08-09)

The default database connection has `CONN_MAX_AGE=0` and persistent-connection health checks are
disabled. Django recommends this for ASGI; deploy an external connection pool when reuse is needed.
Django's ASGI request lifecycle runs `close_old_connections`, and the transaction helper uses its
thread-sensitive executor for ORM work. A concurrent ASGI login test verifies multiple requests
complete without connection lifecycle errors.

## AO7 — Docs, CI, coverage
19. wire AST test (AO3) + `lint-imports` (AO4) เข้า CI pipeline; ยืนยัน `docker compose` + CI เขียว
20. README: เพิ่มหัวข้อ "async ORM discipline" (repo-only ORM, DTO boundary, atomic idiom,
    thread_sensitive rule); เพิ่ม addendum link ในส่วน "Related" ของ ADR-0005 ชี้มาแผนนี้
21. รักษา coverage ≥ 90% (เพิ่ม dto/helper เข้า `[tool.coverage.run] source` ถ้าจำเป็น)
- **DoD**: `ruff`/`mypy`/`pytest --cov`/`lint-imports` เขียว, README ตรงโค้ด, DoD ทุกขั้นถูกเช็ค

### AO7 implementation (2026-08-09)

CI runs `ruff`, `mypy`, `lint-imports`, and the full coverage-enforced pytest suite. README now
documents the async ORM discipline and ADR-0005 links back to this hardening plan.

---

## ลำดับ dependency
```
AO1 → AO2 → (AO3 ∥ AO4) → AO5 → AO6 → AO7
        (AO2 เป็นฐาน: DTO boundary ต้องมาก่อน contract ที่ห้าม import model ใน service/api)
```

## จุดเสี่ยงที่ต้องเฝ้า
- **DTO refactor กว้าง**: AO2 แตะทุก repo + service + schema → ทำทีละ app, รันเทสต์เขียวทุกก้าว
  อย่า big-bang
- **async ไม่มี native atomic**: ห้ามพยายาม `async with transaction.atomic()` — ต้องผ่าน
  `sync_to_async(thread_sensitive=True)` เท่านั้น
- **ModelSchema lazy-load**: Ninja `ModelSchema` ดึง relation แบบ lazy ได้ → ต้องเปลี่ยนเป็น
  `Schema` map จาก DTO (แก้ที่ AO2 ก่อน contract AO4 จะ enforce ได้)
- **thread_sensitive=True serialize DB work**: เป็น trade-off ที่ยอมรับ (ต้อง share connection) —
  อย่าเผลอสลับ transaction wrapper เป็น `False`
- **async DB test**: guardrail/rollback test ต้อง `django_db(transaction=True)` (+ seed เองถ้าจำเป็น)
  ตามบทเรียน M3
- **import-linter false positive**: schemas/serializers ที่ยังอิง model ต้องเคลียร์ใน AO2 ก่อน
  ไม่งั้น contract AO4 จะแดง

## นอก scope (Phase ถัดไป)
native async transaction (รอ Django support) · query offload ไป queue/Celery ·
read replica / DB router · raw-SQL / query-count budget ใน production · caching layer หน้า repository
