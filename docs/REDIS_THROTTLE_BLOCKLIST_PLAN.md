# Implementation Plan — Redis Throttle + Token Blocklist

อ้างอิง [ADR-0008](adr/0008-redis-throttle-and-blocklist.md) เรียงตาม dependency order + DoD ที่ verify ได้
วางบนโค้ดปัจจุบัน (async, `JWTAuth`, `LoginRateThrottle`, refresh store, audit)

---

## R1 — Redis infra + distributed throttle  → ADR-0008/0006
1. deps: `django-redis`, `redis` (redis-py async รวมอยู่ใน `redis`)
2. settings: `REDIS_URL` (pydantic-settings); `CACHES["default"]` = django-redis พร้อม
   **`OPTIONS={"IGNORE_EXCEPTIONS": True}`** (throttle fail-open) + `KEY_PREFIX`
3. `docker-compose.yml`: service `redis` (redis:7-alpine, healthcheck) + `web` depends_on healthy;
   `.env.example` เพิ่ม `REDIS_URL`
4. `apps/common/redis.py` — async redis client singleton (`redis.asyncio.from_url`, decode_responses)
- **DoD**: `docker compose up` มี redis; test ยืนยัน cache backend เป็น redis; throttle test เดิม
  (429) ยังผ่านผ่าน Redis; ปิด Redis → throttle ปล่อยผ่าน (fail-open) ไม่ error

## R2 — Blocklist store + service  → ADR-0008
5. `apps/authz/security/blocklist.py` — `BlocklistService` บน redis.asyncio:
   - `block_token(jti, ttl)` → `SET bl:jti:<jti> 1 EX <ttl>`
   - `revoke_user(user_id, at, ttl)` → `SET user_epoch:<uid> <ts> EX <ttl>`
   - `is_blocked(jti, user_id, issued_at) -> bool` → MGET 2 คีย์; blocked ถ้า jti มี **หรือ** iat < epoch
   - ทุก method **try/except → fail-open** (blocked=False / no-op) + `logger.warning(exc_info)`
- **DoD**: unit test (async) — block jti → is_blocked True; bump epoch → token iat<T blocked, iat≥T ผ่าน;
  **Redis ล่ม (inject error) → is_blocked False (fail-open) + log**

## R3 — JWTAuth blocklist check  → ADR-0008/0002
6. เพิ่ม `jti` เข้า JWT claim decode + `Principal` (field `jti`, `issued_at`)
7. `JWTAuth.authenticate` (async): หลัง decode → `await blocklist.is_blocked(jti, uid, iat)` →
   ถ้า blocked raise `InvalidToken` (401)
- **DoD**: integration test — blocked jti → 401; token iat<epoch → 401; ปกติ → 200;
  Redis down → 200 (fail-open); วัด/ยืนยัน 1 Redis round-trip ต่อ request

## R4 — Write points (revocation triggers)  → ADR-0008/0002
8. `logout` → endpoint เป็น authenticated (`auth=JWTAuth()`); block `principal.jti` (TTL=อายุคงเหลือ)
   + revoke refresh (เดิม); audit เดิม
9. `POST /v1/auth/logout-all` (ใหม่, authenticated) → `revoke_user(uid)` + revoke refresh families
   ของ user + audit `logout` (metadata scope=all)
10. **reuse-detection** ใน `AuthService.refresh` → `revoke_user(victim_uid)` (ฆ่า access ทุกใบ) +
    audit `token.reuse_detected` (เดิม)
11. **admin deactivate** (`update_user(is_active=False)`) → `revoke_user(uid)` → access ตายทันที
- **DoD**: e2e — login→logout→ใช้ access เดิม = 401; reuse refresh → access ของ family = 401;
  admin ban → access เดิม 401 ทันที; logout-all → ทุก session 401

## R5 — Tests, coverage, docs
12. coverage source += `apps.authz.security` มีอยู่แล้ว; เพิ่ม blocklist ให้ ≥ 90%
13. factory/fixtures: fake redis (fakeredis async) หรือ redis จริงใน CI (เพิ่ม service redis ใน `ci.yml`)
14. README (REDIS_URL, logout-all, fail-open note) + glossary; docker compose + CI เขียว
- **DoD**: `ruff`/`mypy`/`pytest --cov` เขียว; CI มี redis service; e2e blocklist ครบ

---

## ลำดับ dependency
```
R1 → R2 → R3 → R4 → R5
       (R3 ต้องมี jti ใน Principal ก่อน; R4 ต้องมี BlocklistService + JWTAuth check)
```

## จุดเสี่ยงที่ต้องเฝ้า
- **fail-open ต้อง log ให้เห็น** (warning + exc_info + metric) — ไม่งั้น Redis ล่มเงียบ = revoke ใช้ไม่ได้โดยไม่รู้
- **TTL ของ block jti** = อายุคงเหลือของ token (exp − now) ไม่ใช่ ACCESS_TTL เต็ม (กัน block นานเกิน)
- **async redis ใน test**: ใช้ fakeredis.aioredis หรือ redis service; อย่าให้ test ชน state (prefix/flush)
- **Redis round-trip ต่อ request**: วัด latency; pipeline 2 คีย์เป็น 1 call
- **clock skew** ระหว่าง app instances กระทบ epoch compare (iat vs ts) — ใช้ server time เดียว/NTP
- **throttle IGNORE_EXCEPTIONS**: ยืนยันว่า fail-open จริง (django-redis คืน None ตอน error)

## นอก scope (Phase ถัดไป)
password-change → revoke_user · sliding-window/token-bucket throttle · per-device session list UI ·
distributed lock · Redis cluster/sentinel HA · rate-limit ต่อ user (ไม่ใช่แค่ IP)
