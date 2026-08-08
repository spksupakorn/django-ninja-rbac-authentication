# ADR 0008 — Redis-backed throttle + token blocklist

- สถานะ: Accepted
- วันที่: 2026-08-06

## Context

สองข้อจำกัดที่ค้างจาก Phase 1:
1. **Throttle เป็น in-memory** (LocMemCache) → ไม่ share ข้าม process/instance; พอ scale หลาย
   worker/pod แต่ละตัวนับ rate แยกกัน → เพดานจริงบานเกินตั้งใจ
2. **Access token เป็น stateless JWT (≤15m)** → revoke ก่อนหมดอายุไม่ได้ (ADR-0002 ยอมรับ exposure
   ≤15m). กรณี logout, ban, หรือ token theft (reuse-detection) access token ที่หลุด/ของเหยื่อ
   ยังใช้ได้จนหมดอายุ

## Decision

**Redis client**
- **throttle** → ตั้ง `CACHES["default"]` เป็น **django-redis** → ninja `SimpleRateThrottle` ใช้
  Django cache อยู่แล้ว จึงกลายเป็น distributed ทันที (โค้ด throttle ไม่ต้องแก้)
- **blocklist** → **redis.asyncio** (redis-py async) เรียกใน `JWTAuth` โดยตรง (async native, ไม่ block loop)
- อ่าน `REDIS_URL` จาก settings (pydantic-settings); เพิ่ม service `redis` ใน docker-compose

**Blocklist schema — per-jti + per-user epoch**
```
bl:jti:<jti>        = "1"   TTL = ACCESS_TTL   # block access token ใบเดียว
user_epoch:<uid>    = <ts>  TTL = ACCESS_TTL   # invalidate ทุก token ที่ iat < ts
```
- เพิ่ม **`jti` เข้า `Principal`** (มีใน claim อยู่แล้ว) เพื่อเช็ค + block
- ตรวจใน `JWTAuth.authenticate` **ทุก authenticated request**: blocked ถ้า `bl:jti:<jti>` มีอยู่
  **หรือ** `token.iat < user_epoch:<uid>` → คืน 401 (`InvalidToken`)
- อ่าน 2 คีย์ใน round-trip เดียว (MGET/pipeline)
- **TTL = ACCESS_TTL** ทุกคีย์ — พอ token ที่เกี่ยวข้องหมดอายุ entry ก็ไม่จำเป็นอีก → auto-expire

**Write points (ใครเขียน blocklist)**
- `logout` → block `jti` ปัจจุบัน (endpoint ต้อง authenticated เพื่อได้ jti) + revoke refresh (เดิม)
- `logout-all` (endpoint ใหม่) → bump `user_epoch:<uid>` = now
- **reuse-detection (token theft)** → bump `user_epoch` ของเหยื่อ → ฆ่า access token ทุกใบทันที
- **admin deactivate/ban** (`is_active=False`) → bump `user_epoch` → access token ตายทันที (ไม่รอ 15m)
- (Phase ถัดไป) password change → bump `user_epoch`

**Failure mode — fail-open ทั้งคู่ (availability มาก่อน)**
- Redis error → throttle ปล่อยผ่าน (django-redis `IGNORE_EXCEPTIONS=True`), blocklist ปล่อยผ่าน
  (try/except → allow) + **log alert** ทุกครั้ง
- fail-open blocklist **degrade กลับไปที่ baseline ADR-0002 พอดี** (exposure ≤ ACCESS_TTL) —
  ไม่ใช่รูใหม่; refresh-token store ใน DB ยังเป็น authoritative revocation ของ refresh ตามเดิม

## Consequences

- (+) throttle บังคับ rate จริงระดับ cluster
- (+) revoke access token ได้ทันที (logout/ban/theft) — ปิดช่อง ≤15m ของ reuse-detection
- (+) TTL = ACCESS_TTL ทำให้ blocklist ไม่โตไม่จบ
- (−) **เพิ่ม Redis GET 1 ครั้ง/authenticated request** — ย้อน trade-off ADR-0002 (ที่ตั้งใจไม่แตะ
  store ต่อ request); ยอมรับเพราะ Redis ~ms และได้ instant-revoke
- (−) เพิ่ม infra dependency (Redis) — dev ต้องมี redis ใน compose
- (−) fail-open = ตอน Redis ล่ม revoked token กลับมาใช้ได้ (แต่ degrade เท่า baseline เดิม) →
  ต้อง monitor/alert Redis ให้ดี
- (−) `Principal` ต้องพก `jti`; endpoint logout ต้อง authenticated

## Alternatives considered

- **blocklist fail-closed**: กัน revoked token หลุดตอน Redis ล่ม แต่ Redis กลายเป็น SPOF ของ auth
  ทั้งระบบ → ปฏิเสธ (เลือก availability)
- **per-jti อย่างเดียว**: logout ได้ แต่ ban/logout-all/theft ต้องรู้ jti ทุกใบ → ไม่ practical → ปฏิเสธ
- **per-user epoch อย่างเดียว**: logout อุปกรณ์เดียวทำไม่ได้ (ต้อง revoke ทั้ง user) → เพิ่ม per-jti ด้วย
- **redis.asyncio ทั้งคู่ (custom throttle)**: unified async แต่ต้องเขียน throttle เอง ทิ้ง ninja
  SimpleRateThrottle → ปฏิเสธ (django-redis drop-in คุ้มกว่า)
- **เช็ค blocklist เฉพาะ sensitive endpoints**: latency ต่ำกว่า แต่ revoked token ยังเข้า endpoint
  อื่นได้ → ปฏิเสธ (instant-revoke ต้องครบ)

## Related

[[blocklist]] · [[user-epoch]] · [[fail-open]] · [[jti]] · ADR-0002 (stateless access + refresh
store) · ADR-0006 (throttle)
