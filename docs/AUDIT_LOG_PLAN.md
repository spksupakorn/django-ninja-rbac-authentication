# Implementation Plan — Audit Log

อ้างอิง [ADR-0007](adr/0007-audit-log-strategy.md) เรียงตาม dependency order แต่ละขั้นมี DoD ที่ verify ได้
วางบนโค้ด phase 1 (service layer, `BuildResponse` envelope, `require_permission`, การ์ด async)

---

## A1 — Audit app + model + action catalog  → ADR-0007
1. app ใหม่ `apps/audit/` (`AppConfig`, register ใน `INSTALLED_APPS`)
2. `audit/actions.py` — `AuditAction(StrEnum)`: `login.success/failure`, `logout`, `register`,
   `token.refreshed`, `token.reuse_detected`, `user.create/update/delete`, `role.assign`
   (single source of truth เหมือน `PermissionCode`)
3. `audit/models.py` — `AuditLog` (fields ตาม ADR-0007): `actor_id` เป็น `BigIntegerField(null)`
   **ไม่ใช่ FK**, `metadata=JSONField(default=dict)`, index `created_at` / `(actor_id, created_at)`
   / `(action, created_at)`
4. `makemigrations audit` + migrate
- **DoD**: migrate ผ่านบน Postgres, สร้าง AuditLog row ได้จาก shell, index ปรากฏใน `pg_indexes`

## A2 — Repository (append-only) + AuditService + AuditContext  → ADR-0007/0003
5. `audit/context.py` — `AuditContext` dataclass (`actor_id`, `actor_email`, `ip`,
   `user_agent`, `request_id`) + helper `from_request(request, principal|None)`
6. `audit/repositories.py` — `AuditRepository`: **`acreate(...)` + read query เท่านั้น**
   (ไม่มี update/delete = append-only ที่ระดับ repo)
7. `audit/services.py` — `AuditService.record(action, *, context, target_type=None,
   target_id=None, outcome="success", metadata=None)` → **try/except ครอบ, fail → `logger.warning`,
   ไม่ raise** (best-effort); ยืนยัน metadata ไม่รับ password/token (สร้าง sanitizer)
- **DoD**: unit test (async, `transaction=True`) — record สำเร็จ + **repo โยน exception แล้ว record
  ไม่ raise** (best-effort พิสูจน์)

## A3 — ผูกเข้า AuthService  → ADR-0002/0007
8. เพิ่ม `context: AuditContext` param ให้ `login/register/logout/refresh`
9. emit: `login.success`/`login.failure` (failure actor อาจ null, เก็บ email ที่ลอง),
   `register`, `logout`, `token.refreshed`, และ **`token.reuse_detected`** ตอน reuse-detection ยิง
   (ADR-0002) — metadata ใส่ family_id ได้ (ไม่ใส่ raw token)
10. routers `/v1/auth/*` สร้าง `AuditContext.from_request(...)` ส่งเข้า service
- **DoD**: integration test — login สำเร็จ/ผิด → มี AuditLog row ถูก action+outcome;
  reuse token → มี `token.reuse_detected`

## A4 — ผูกเข้า AdminService  → ADR-0007
11. เพิ่ม `context` param ให้ `create_user/update_user/delete_user/assign_role`
12. emit `user.create/update/delete` (target=("user", id)), `role.assign`
    (metadata: role_id/role_name)
13. routers `/v1/admin/*` ส่ง context
- **DoD**: integration test — admin CRUD/assign → AuditLog row ครบ actor(admin)+target ถูก

## A5 — Read API (admin query)  → ADR-0001/0007
14. เพิ่ม permission `audit.read` เข้า `PermissionCode` + **data migration ใหม่** grant ให้ role
    `admin` (ห้ามแก้ migration เก่า — กติกา freeze ADR-0001)
15. `GET /api/v1/admin/audit-logs` — `@require_permission("audit.read")`, async, `BuildResponse`
    envelope, pagination (offset/limit) + filter (`actor_id`, `action`, `outcome`, `from`/`to`)
16. schemas `AuditLogOut` / `AuditLogsPageOut`
- **DoD**: e2e — admin (มี `audit.read`) → 200 + รายการ; user ไม่มีสิทธิ์ → 403;
  filter by action ได้ผลถูก

## A6 — Tests, coverage, docs
17. เพิ่ม `apps.audit.services` เข้า `[tool.coverage.run] source`; รักษา coverage ≥ 90%
18. factory สำหรับ AuditLog; ยืนยัน sanitizer กัน password/token หลุดลง metadata (test)
19. อัปเดต README (ส่วน audit + `audit.read`), glossary; ยืนยัน `docker compose` + CI เขียว
- **DoD**: `ruff`/`mypy`/`pytest --cov` เขียว, e2e audit ครบ, docs ตรงโค้ด

---

## ลำดับ dependency
```
A1 → A2 → A3 → A4 → A5 → A6
        (A3/A4 ขนานกันได้หลัง A2; A5 ต้องรอ permission catalog + read path)
```

## จุดเสี่ยงที่ต้องเฝ้า
- **async DB test**: `django_db(transaction=True)` + self-provision seed (ดู memory/M3 lesson)
- **best-effort ต้องไม่กลืน bug จริง**: log ให้เห็น (warning + exc_info) ไม่ใช่ except เงียบ
- **PII/secret**: metadata ต้องผ่าน sanitizer เสมอ — ห้าม password/token/refresh เข้า audit
- **actor_id ไม่ใช่ FK**: อย่าเผลอ join กับ users แบบ CASCADE; query read ใช้ id + email snapshot
- **latency**: await insert ใน hot path — วัด; ถ้าหนักค่อย offload (queue) Phase ถัดไป

## นอก scope (Audit Phase ถัดไป)
hash-chain tamper-evidence · DB-level insert-only (trigger/role) · retention/partition + pruning ·
queue/async offload (Celery/Redis) · export ไป SIEM · audit ฝั่ง read (sensitive GET)
