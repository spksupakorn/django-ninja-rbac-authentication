# Implementation Plan — Refresh Token Binding (device + IP)

อ้างอิง [ADR-0009](adr/0009-refresh-token-binding.md) เรียงตาม dependency order + DoD ที่ verify ได้
วางบนโค้ดปัจจุบัน (async, `RefreshToken` family + `arotate` row-lock, `AuditContext`, `revoke_user`)

---

## B1 — Model fields + settings flags  → ADR-0009
1. `RefreshToken` เพิ่ม 2 field: `device_hash = CharField(max_length=64, null=True, blank=True)`,
   `issued_ip = GenericIPAddressField(null=True, blank=True)` — **null = unbound (grandfathered)**
2. `makemigrations authz` + migrate (nullable → ไม่ต้อง backfill; token เก่าคง null)
3. settings (pydantic-settings): `REFRESH_BIND_DEVICE: bool = True` (strict),
   `REFRESH_BIND_IP: bool = False` (soft); `.env.example` เพิ่มทั้งสองพร้อม comment นโยบาย
4. `apps/authz/security/binding.py` — `device_hash(user_agent: str | None) -> str | None`:
   normalize (strip/lower) แล้ว `sha256`; `user_agent` ว่าง/None → คืน `None` (unbound)
- **DoD**: migrate ผ่านบน Postgres; `device_hash(None) is None`; UA เดิม → hash เดิม (stable);
  column ปรากฏใน `\d authz_refreshtoken`

## B2 — Repository: capture at issue + compare on rotate  → ADR-0009/0002
5. `RefreshTokenRepository.acreate` เพิ่ม param `device_hash`, `issued_ip` (เก็บลง row)
6. `arotate` / `_rotate` เพิ่ม param `presented_device_hash`, `presented_ip`:
   - **binding check ใน `_rotate` ใต้ row lock เดิม** (atomic กับ reuse-detection): ถ้า
     `settings.REFRESH_BIND_DEVICE` และ `stored.device_hash is not None` และ
     `stored.device_hash != presented_device_hash` → **revoke ทั้ง family** (เหมือน reuse) +
     คืน `RefreshRotationResult(outcome="binding_mismatch", refresh_token=stored)`
   - stored `device_hash IS NULL` (grandfathered) → **ข้าม check**, ผ่านไป rotate ปกติ
   - replacement **สืบทอด binding**: `device_hash = stored.device_hash or presented_device_hash`
     (ผูกครั้งแรกตอน grandfathered token ถูก rotate), `issued_ip = presented_ip`
   - เพิ่ม `"binding_mismatch"` เข้า `Literal` ของ `RefreshRotationResult.outcome`
- **DoD**: unit test (async, `transaction=True`) — device ตรง → `rotated`; device ต่าง →
  `binding_mismatch` + ทุก token ใน family `revoked_at` ถูกเซ็ต; grandfathered (null) → `rotated`
  + replacement ได้ device_hash ของผู้มา rotate; `REFRESH_BIND_DEVICE=False` → mismatch ผ่าน (`rotated`)

## B3 — AuthService binding logic + audit + exceptions  → ADR-0009/0002/0007
7. `apps/common/exceptions.py` — `RefreshTokenBindingMismatch` (map → 401 กลาง ๆ, ข้อความไม่ใบ้ว่า
   fail เพราะ binding เพื่อกัน probing) ที่ exception handler เดิม
8. `audit/actions.py` — `TOKEN_BINDING_MISMATCH = "token.binding_mismatch"`,
   `TOKEN_IP_CHANGED = "token.ip_changed"`
9. `AuthService._issue_token_pair` / `login`: ส่ง `device_hash(context.user_agent)` + `context.ip`
   เข้า `refresh_tokens.acreate` (login สร้าง family = ผูก binding ที่นี่)
10. `AuthService.refresh`: ส่ง `presented_device_hash = device_hash(context.user_agent)`,
    `presented_ip = context.ip` เข้า `arotate`; จัดการ outcome ใหม่:
    - `binding_mismatch` → `blocklist.revoke_user(uid, now, ttl=...)` (ฆ่า access ทุกใบ, เหมือน reuse) +
      audit `TOKEN_BINDING_MISMATCH` (outcome=`failure`, metadata `family_id`; **ไม่ใส่ UA/IP ดิบ**) →
      raise `RefreshTokenBindingMismatch`
    - **soft IP**: rotate สำเร็จแล้ว ถ้า `REFRESH_BIND_IP` (หรือ always-log) และ
      `stored.issued_ip != presented_ip` → audit `TOKEN_IP_CHANGED` (metadata IP เก่า/ใหม่ **mask**
      ผ่าน sanitizer เดิม) — **ไม่ revoke**
- **DoD**: unit test service — login แล้ว refresh ด้วย UA เดิม → ok; UA ต่าง → `revoke_user` ถูกเรียก
  + audit `token.binding_mismatch` + raise; IP เปลี่ยน (UA เดิม) → rotate ผ่าน + audit `token.ip_changed`
  ไม่ revoke

## B4 — Endpoint behavior + edge cases  → ADR-0009/0003
11. `/v1/auth/refresh` router — **ไม่ต้องแก้ contract**: `AuditContext.from_request` มี `ip`+`user_agent`
    อยู่แล้ว; ยืนยัน context ถูกส่งเข้า `refresh` ครบ (เดิมส่งอยู่แล้ว)
12. edge: **missing User-Agent** ตอน refresh (`presented_device_hash is None`) ขณะ stored ผูกไว้ →
    ตัดสินเป็น mismatch (strict) — ป้องกัน attacker ลบ UA เพื่อ bypass; ครอบใน test
13. ตรวจ `me`/response schema ไม่รั่ว binding (device_hash/ip เป็น server-side เท่านั้น — **ห้าม**
    คืนออก API)
- **DoD**: e2e — login (UA=A) → refresh (UA=A) 200 → refresh (UA=B) 401 + session ตาย (access เดิม
  ใช้ไม่ได้ผ่าน blocklist); refresh ที่ไม่มี header User-Agent ขณะ family ผูกไว้ → 401

## B5 — Tests, coverage, docs
14. coverage: `apps.authz.security` มีอยู่แล้ว → เพิ่ม `binding.py` ให้ ≥ 90%; เพิ่มเคส grandfather/
    toggle-off ใน rotate tests
15. factory: `RefreshTokenFactory` รองรับ `device_hash`/`issued_ip` (default null = grandfather)
16. README (นโยบาย binding + 2 env flag + caveat UA-update logout) + glossary
    (`device-binding`, `rotation-family`); ยืนยัน `docker compose` + CI เขียว
- **DoD**: `ruff`/`mypy`/`pytest --cov` เขียว; e2e binding ครบ; docs ตรงโค้ด + ADR-0009

---

## ลำดับ dependency
```
B1 → B2 → B3 → B4 → B5
       (B2 ต้องมี field + device_hash helper ก่อน; B3 ต้องมี outcome "binding_mismatch" + exception)
```

## จุดเสี่ยงที่ต้องเฝ้า
- **UA-update = logout**: browser/app อัปเดต → device mismatch → ผู้ใช้จริงหลุดทั้ง family; สื่อสารใน
  README + มี `REFRESH_BIND_DEVICE=False` เป็นวาล์วปิด (ADR-0009 accepted trade-off)
- **grandfathering**: token เก่า `device_hash IS NULL` **ต้องผ่าน** ไม่งั้น deploy = logout ทุกคนทันที;
  ผูก binding ตอน rotate แรกเท่านั้น
- **atomic กับ reuse-detection**: binding check ต้องอยู่ **ใน `_rotate` ใต้ row lock เดียวกัน** —
  อย่าเช็คใน service ก่อน rotate (race: reuse/rotate แทรกได้)
- **missing UA bypass**: `presented_device_hash is None` ขณะ stored ผูกไว้ = mismatch (strict) ไม่ใช่ skip
- **PII ใน audit**: UA/IP ดิบห้ามลง metadata ตรง ๆ — IP ผ่าน sanitizer/mask; binding_mismatch ใส่แค่
  family_id (ADR-0007 กติกา)
- **แยกจาก reuse-detection**: binding_mismatch เป็นสาเหตุคนละตัวกับ token.reuse_detected — action/
  exception แยก เพื่อ forensic แยกแยะได้ (แต่ผลลัพธ์ revoke_user เท่ากัน)

## นอก scope (Phase ถัดไป)
IP binding แบบ /24·ASN (GeoIP) · strong device fingerprint (JA3/TLS) · bound token มาตรฐาน
(DPoP / RFC 8705 mTLS) · per-device session list + selective revoke UI · step-up re-auth ตอน IP เปลี่ยน ·
เตือนผู้ใช้ทางอีเมลเมื่อ device/IP ใหม่
