# ADR 0006 — Argon2 + rate limiting ตอน login

- สถานะ: Accepted
- วันที่: 2026-08-04

## Context

Login เป็นเป้าของ brute-force / credential stuffing ต้องแข็งพอตั้งแต่ phase 1 โดยไม่พึ่ง infra เพิ่ม

## Decision

**Password hashing: Argon2id**
```python
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",  # fallback/verify legacy
    ...
]
```
- ติดตั้ง `argon2-cffi`
- **async note**: `check_password`/`make_password` เป็น CPU-bound → เรียกผ่าน
  `sync_to_async(..., thread_sensitive=False)` ในชั้น service ไม่ให้ block event loop (ดู ADR-0005)

**Rate limiting (throttle) ที่ login/refresh**
- ใช้ Django Ninja throttling: จำกัด **5 login/นาที/IP** และ throttle เพิ่มต่อ email
- ตอบ `429 Too Many Requests` เมื่อเกิน
- error message ตอน login ผิด **ต้องไม่บอกว่า email หรือ password ผิด** (กัน user enumeration) — คืน `401` กลางๆ

**เสริม (ทำเลยเพราะถูก)**
- login ผิด ทำ dummy hash verify เพื่อกัน timing attack แยก user มี/ไม่มี
- security headers + secure cookie flags ที่ prod (ADR-0005 prod.py)

## Consequences

- (+) กัน brute-force / credential stuffing ได้ระดับ app โดยไม่ต้องมี Redis ใน phase 1
- (+) Argon2id เป็น hashing ที่แนะนำปัจจุบัน (memory-hard)
- (−) throttle แบบ in-memory/DB ไม่ share ข้าม process — พอ scale หลาย instance ต้องย้าย backend เป็น Redis (Phase 2)
- (−) Argon2 กิน CPU/RAM ต่อ verify มากกว่า PBKDF2 — คุมด้วย threadpool + tune params

## Alternatives considered

- Argon2 อย่างเดียว ไม่ throttle: เสี่ยง brute-force → ปฏิเสธ
- PBKDF2 default + ไม่ throttle: อ่อนสุด → ปฏิเสธ
- Redis-backed throttle/lockout: ดีสุดตอน scale แต่เพิ่ม infra → เลื่อน Phase 2

## Related

[[argon2]] · [[throttling]] · [[user-enumeration]] · [[timing-attack]] · ADR-0002
