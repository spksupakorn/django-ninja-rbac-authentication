# ADR 0009 — Refresh token binding (device + IP)

- สถานะ: Accepted
- วันที่: 2026-08-08

## Context

Refresh token เป็น **bearer token อายุยาว (7d)** — ใครถือ raw token ก็ rotate ต่อได้ Phase 1
ป้องกันแค่ **reuse-detection**: จับได้ก็ต่อเมื่อ *ทั้งของจริงและของขโมยถูกใช้* (token ที่ revoked
แล้วถูกนำมา rotate → ฆ่าทั้ง family, ADR-0002). ถ้าผู้โจมตีขโมย refresh token แล้วใช้ *แทน*
เจ้าของ (เจ้าของยังไม่ rotate) จะไม่มีสัญญาณ reuse ให้จับเลย — attacker rotate เงียบ ๆ ได้เรื่อย ๆ

ต้องการ **สัญญาณเพิ่ม (defense-in-depth)**: ผูก refresh token กับบริบทของ client ที่ออก token
(device + IP) แล้วตรวจตอน rotate ถ้าบริบทเปลี่ยนผิดปกติ = น่าจะถูกขโมยไปใช้ที่อื่น

## Decision

**ผูกที่ระดับ family** — ทุก token ในสาย rotation เดียวกันแชร์ binding เดียว (replacement สืบทอด
binding จาก token ที่ถูก consume); binding มาจาก **request ตอน login** (สร้าง family):

```
device_hash = sha256(normalize(User-Agent))   # 64 hex, null = unbound (grandfathered)
issued_ip   = client IP ตอนออก family          # เก็บเพื่อ audit + soft-check
```

ทั้งสองค่าดึงจาก `AuditContext` ที่ router สร้างอยู่แล้ว (`ip`, `user_agent`) — **ไม่ต้อง plumb
request เพิ่มเข้า service** (ADR-0003 boundary คงเดิม)

**นโยบายตรวจตอน `refresh` (ตั้งค่าได้ผ่าน settings)**

| binding | default | ผลเมื่อไม่ตรง |
|---------|---------|---------------|
| **device** (`REFRESH_BIND_DEVICE`) | **strict = on** | mismatch → **revoke ทั้ง family** + `revoke_user` (ฆ่า access ทุกใบ) + audit `token.binding_mismatch` → 401 — ปฏิบัติเท่า **theft** |
| **IP** (`REFRESH_BIND_IP`) | **soft = off** | เปลี่ยน IP → audit `token.ip_changed` (metadata IP เก่า/ใหม่ mask) แต่ **ไม่ revoke** — rotate ต่อได้ |

- **device strict** เพราะ device ของ session ไม่ควรเปลี่ยนกลางคัน; mismatch = สัญญาณขโมยที่แรงพอ
  จะฆ่า family เท่า reuse-detection
- **IP soft** เพราะ IP เปลี่ยนตามปกติ (mobile roaming, NAT, Wi-Fi↔cellular) — hard-bind IP = logout
  ผู้ใช้จริงพร่ำเพรื่อ; เก็บเป็น audit signal ไว้ก่อน (เปิด strict ได้ถ้า deploy รู้ว่า IP นิ่ง)
- ตรวจ binding **ใน `_rotate` ใต้ row lock เดียวกับ reuse-detection** → atomic, race-safe
  (outcome ใหม่ `"binding_mismatch"`)

**Grandfathering** — token เก่าที่ `device_hash IS NULL` (ออกก่อน migration) → **ผ่าน** (unbound);
ค่อยผูกตอน rotate ครั้งถัดไป (replacement เก็บ device_hash ของ request ที่มา rotate) → ไม่เตะ
session ที่ล็อกอินอยู่ให้หลุด

## Consequences

- (+) ปิดช่อง **silent theft**: refresh token ที่ถูกขโมยไปใช้ต่าง device → จับได้ทันที rotate แรก
  โดยไม่ต้องรอ reuse
- (+) ใช้ `AuditContext` เดิม → ไม่แตะ contract ระหว่าง router/service; ผูกที่ family → 1 ค่า/สาย
- (+) IP soft = ได้ forensic trail (`token.ip_changed`) โดยไม่ทำ UX พัง
- (−) **User-Agent เปราะ**: browser/app อัปเดต → UA เปลี่ยน → device mismatch → ผู้ใช้จริงถูก
  logout ทั้ง family (ต้อง login ใหม่). ยอมรับได้เพราะ refresh อายุยาว + major UA change ไม่บ่อย;
  ปิดได้ด้วย `REFRESH_BIND_DEVICE=False`
- (−) device_hash จาก UA **spoof ได้** ถ้า attacker ก็ขโมย UA มาด้วย → เป็น defense-in-depth
  ไม่ใช่ auth factor แข็ง (จงใจ; ไม่ทดแทน reuse-detection/blocklist)
- (−) เพิ่ม 2 คอลัมน์ + migration; `_rotate` ตรรกะเพิ่มหนึ่ง branch

## Alternatives considered

- **hard-bind IP (strict)**: กันขโมยข้ามเครือข่ายดีสุด แต่ logout ผู้ใช้ mobile พร่ำเพรื่อ → ปฏิเสธ
  (default soft; เปิด strict ได้)
- **bind IP แบบ /24 หรือ ASN**: ทน roaming กว่า exact IP แต่ต้อง GeoIP/ASN lookup ต่อ refresh →
  เกินคุ้ม Phase นี้ → ปฏิเสธ (soft-log ก่อน)
- **strong device fingerprint (JS/TLS-JA3)**: แข็งกว่า UA มาก แต่ต้อง client cooperation/ข้อมูล
  เพิ่ม + privacy concern → ปฏิเสธ (เกิน scope backend-only)
- **binding เป็น token ผูกใน JWT/cookie (bound token, RFC 8705 mTLS / DPoP)**: มาตรฐานแข็งสุด แต่
  ต้องแก้ client + infra (cert/proof) → เลื่อน; ADR นี้เป็น server-side heuristic ที่ deploy ได้ทันที
- **mismatch → แค่ audit ไม่ revoke**: กระทบ UX น้อยสุด แต่ไม่ปิดช่อง theft จริง → ปฏิเสธสำหรับ device
  (แต่ **เลือกแนวนี้กับ IP**)

## Related

[[device-binding]] · [[refresh-token]] · [[rotation-family]] · [[reuse-detection]] ·
ADR-0002 (refresh rotation + reuse-detection) · ADR-0007 (audit) · ADR-0008 (blocklist/revoke_user)
