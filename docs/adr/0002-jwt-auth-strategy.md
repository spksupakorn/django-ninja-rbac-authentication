# ADR 0002 — JWT auth strategy: Access + Refresh (rotation + reuse-detection)

- สถานะ: Accepted
- วันที่: 2026-08-04

## Context

JWT เป็น stateless — จุดที่คนพลาดคือ "การเพิกถอน" (logout/ban) และ token theft
ต้องเลือก: อายุ token, signing algorithm, ที่มาของสิทธิ์ตอนเช็ค, และกลไก revoke

## Decision

**คู่ token**
- **Access token**: JWT อายุสั้น **15 นาที**, stateless, ส่งแบบ `Authorization: Bearer <token>`
- **Refresh token**: อายุยาว **7 วัน**, opaque/JWT ที่ **เก็บ hash ใน DB** (`RefreshToken` table)

**Signing** — **HS256 (symmetric)** ด้วย `SECRET_KEY` แยกจาก Django secret
- เหมาะกับ monolith เดี่ยว; เปลี่ยนเป็น RS256 ภายหลังได้เมื่อแตกเป็นหลาย service (Phase 2+)

**สิทธิ์ตอนเช็ค** — **ฝัง `roles` + `perms` เป็น claim ใน access token**
- ไม่ query DB ต่อ request → เร็ว
- ราคาที่จ่าย: การเปลี่ยนสิทธิ์ (admin แก้ role) มีผลจริงหลัง token หมดอายุ (**≤ 15 นาที**) หรือเมื่อ refresh
- ยอมรับ trade-off นี้ (ดู ADR-0001 admin CRUD)

**Rotation + reuse-detection**
- ทุกครั้งที่เรียก `/auth/refresh`: revoke refresh เดิม แล้วออก access+refresh คู่ใหม่
- refresh token มี **family id** (chain). ถ้า refresh ที่ถูก rotate/revoke ไปแล้วถูกใช้ซ้ำ →
  ถือว่า **token ถูกขโมย** → revoke **ทั้ง family** และบังคับ login ใหม่
- **logout** = ลบ/revoke refresh token ปัจจุบันออกจาก DB

## Consequences

- (+) revoke ได้จริงผ่าน refresh store; access หลุดก็เสียหายจำกัดที่ ≤15 นาที
- (+) reuse-detection จับ token theft ได้ตั้งแต่เนิ่น
- (+) hot path (เช็คสิทธิ์) ไม่แตะ DB
- (−) สิทธิ์ที่ฝังใน access ไม่ "สด" ทันที (delay ≤15 นาที)
- (−) ต้องมีตาราง refresh token + logic rotation/family (ซับซ้อนกว่า access อย่างเดียว)
- (−) HS256 ใช้ secret ร่วม — ทุกฝ่ายที่ verify ต้องถือ secret (ยอมรับได้ใน monolith)

## Risks & mitigations

- **Argon2 + async**: การ verify/hash password เป็น CPU-bound ต้องรันผ่าน threadpool
  (`sync_to_async(thread_sensitive=False)`) ไม่งั้น block event loop — ดู ADR-0005/0006

## Alternatives considered

- Access token อย่างเดียว: revoke ไม่ได้, UX แย่ → ปฏิเสธ
- Blocklist (jti) ทุก request: revoke ได้แต่แตะ store ทุก request → เลือก DB-refresh store แทน
- Lookup สิทธิ์จาก DB ทุก request: สิทธิ์สดกว่า แต่เพิ่ม query hot path → เลื่อน (ใส่ cache ได้ภายหลัง)
- RS256: ดีตอนหลาย service, setup ซับกว่า → เลื่อน Phase 2

## Related

[[access-token]] · [[refresh-token]] · [[token-rotation]] · [[reuse-detection]] · [[token-family]] · [[jti]]
