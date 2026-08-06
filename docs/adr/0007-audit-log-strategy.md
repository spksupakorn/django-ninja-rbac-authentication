# ADR 0007 — Audit log strategy

- สถานะ: Accepted
- วันที่: 2026-08-06

## Context

ต้องบันทึกร่องรอย (audit trail) ของเหตุการณ์ด้านความปลอดภัยและการเปลี่ยนแปลงเชิงบริหาร
เพื่อสืบสวนเหตุ, ตรวจจับการใช้งานผิดปกติ (เช่น token theft) และรองรับ compliance
โดยไม่ทำให้ hot path ช้าหรือทำให้ action ล้มเหลวเพราะระบบ audit เอง

## Decision

**Scope — เก็บ security events + admin mutations** (ไม่เก็บ read/GET ปกติ)
- auth: `login.success`, `login.failure`, `logout`, `register`, `token.refreshed`,
  `token.reuse_detected` (สัญญาณ theft → ดู ADR-0002)
- admin mutation: `user.create`, `user.update`, `user.delete`, `role.assign`

**Emit — explicit ใน service layer** (ตาม ADR-0003)
- service เรียก `await self.audit.record(action, ...)` ตรงจุด domain event
- HTTP context (actor_id, actor_email, ip, user_agent, request_id) ห่อใน **`AuditContext`
  dataclass** ที่ **router สร้างจาก `request`+principal แล้วส่งเข้า service เป็น argument** →
  service ยังคง HTTP-agnostic (รับ data ไม่ใช่ `request`)

**Storage — ตาราง `AuditLog` ใน Postgres, append-only**
```
AuditLog(
  id, created_at,             # created_at indexed
  action,                     # จาก AuditAction catalog (enum, single source of truth)
  actor_id, actor_email,      # actor_id = int (ไม่ใช่ FK) + email snapshot
  target_type, target_id,     # เช่น ("user", "42")
  outcome,                    # "success" | "failure"
  ip, user_agent,             # user_agent ตัดความยาว
  metadata,                   # JSONB, ห้ามใส่ password/token
)
```
- **actor เก็บเป็น `actor_id` (int) ไม่ใช่ ForeignKey** เจตนา — ถ้า user ถูกลบ audit history
  ต้องอยู่ต่อ (FK+CASCADE จะลบประวัติทิ้ง); เก็บ `actor_email` เป็น snapshot กันข้อมูลหาย
- **insert-only**: repository เปิดเฉพาะ `create` + read query; ไม่มี update/delete
  (บังคับเชิง DB ด้วย trigger/role = Phase ถัดไป)
- index: `created_at`, `(actor_id, created_at)`, `(action, created_at)` สำหรับ query/สืบสวน

**Failure/async — awaited best-effort, ไม่ block action**
- `record()` ครอบ `try/except` → ถ้าเขียนพลาด **log warning แล้วคืนปกติ** (action ไม่ rollback)
- audit insert อยู่ **นอก transaction ของ action** — action ที่ commit แล้วจะไม่ถูก audit ลากล้ม
- phase นี้ยัง await ใน request path (เพิ่ม latency ~1 insert); ยัง**ไม่ใช่ queue offload**

**Read API — `GET /api/v1/admin/audit-logs`** ป้องกันด้วย `require_permission("audit.read")`
+ pagination + filter (actor_id, action, outcome, ช่วงเวลา); เพิ่ม permission `audit.read`
เข้า catalog ผ่าน **data migration ใหม่** (ตามกติกา freeze ใน ADR-0001)

## Consequences

- (+) มีร่องรอยเหตุการณ์สำคัญครบ ตรวจสอบได้ทั้งฝั่ง security และ admin
- (+) service ยัง testable/HTTP-agnostic (รับ `AuditContext`)
- (+) audit ล่ม/ช้าไม่ทำให้ login/assign ล้ม (best-effort)
- (+) audit history อยู่รอดแม้ลบ user (actor_id snapshot)
- (−) เพิ่ม latency ~1 insert ต่อ audited action (ยอมรับได้; offload = Phase ถัดไป)
- (−) volume โต → ต้องมี retention/partition (Phase ถัดไป)
- (−) best-effort = อาจมี audit หายเงียบถ้า DB ล่มพอดี (ยอมแลกกับ availability ของ action)

## Alternatives considered

- **Middleware auto ทุก request**: ได้ครบทุก endpoint แต่ขาด domain intent (แยก login.success/fail
  ยาก, ไม่มี target semantics) → ปฏิเสธ; explicit ใน service สื่อความหมายกว่า
- **Django signals/event bus**: decouple ดี แต่ debug ยาก + signal ไม่ async-friendly → ปฏิเสธ
- **Hash-chain tamper-evident**: แข็งด้าน compliance แต่ต้อง serialize write + ซับซ้อน →
  เลื่อน (append-only + DB-level insert-only เพียงพอ phase นี้)
- **Sync ใน transaction เดียวกับ action**: audit fail → action rollback = ระบบเปราะ → ปฏิเสธ
- **External sink (SIEM) ตั้งแต่แรก**: เพิ่ม infra → เลื่อน (เปิดทางส่งออกภายหลังได้)

## Related

[[audit-log]] · [[audit-context]] · [[audit-action]] · ADR-0001 (permission catalog freeze) ·
ADR-0002 (reuse_detected) · ADR-0003 (service layer)
