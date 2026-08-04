# ADR 0003 — Layered architecture: API / Service / Repository

- สถานะ: Accepted
- วันที่: 2026-08-04

## Context

ต้องการ "clean, maintain ง่าย" — แยก concern ให้ test ได้ แต่ไม่ over-engineer จน boilerplate ท่วมใน phase 1
เทียบ 3 แบบ: thin (router+service), layered (API/Service/Repository), full hexagonal

## Decision

ใช้ **Layered 4 ชั้น** แต่ละชั้นพึ่งชั้นล่างทางเดียว:

```
interfaces (Django Ninja routers + Pydantic schemas)   ← I/O, validation, auth guard
        ↓ เรียก
services (business logic / use cases)                   ← กติกา, transaction, orchestration
        ↓ เรียก
repositories (data access)                              ← ห่อ ORM query, คืน domain-ish object
        ↓ ใช้
models (Django ORM)                                     ← schema, persistence
```

กติกา:
- **router ไม่แตะ ORM ตรงๆ** — คุยผ่าน service เท่านั้น
- **service ไม่รู้จัก HTTP** (ไม่มี request/response) — รับ input ธรรมดา คืน result/raise domain error
- **repository เป็นที่เดียวที่เขียน ORM query** — service ไม่เขียน `.filter()` เอง
- domain error map เป็น HTTP status ที่ชั้น interface (exception handler กลาง)

โครงโฟลเดอร์ (per Django app เช่น `accounts`, `authnz`):
```
apps/<name>/
  api/            routers.py, schemas.py, dependencies.py
  services/       *.py
  repositories/   *.py
  models.py
  exceptions.py
```

## Consequences

- (+) business logic test ได้โดยไม่ต้องยิง HTTP (เรียก service ตรง)
- (+) เปลี่ยน persistence/ORM query ได้ที่ repository จุดเดียว
- (+) router บาง อ่านเป็น API contract ล้วน
- (−) boilerplate มากกว่า thin ~1 ชั้น (repository) — ยอมรับเพื่อ testability + ขอบเขตชัด
- (−) ต้องมีวินัยไม่ให้ ORM รั่วขึ้น service (บังคับผ่าน review/lint import)

## Alternatives considered

- **Thin (router+service, service ใช้ ORM เอง)**: เร็วกว่า แต่ business logic ผูก ORM, mock ยาก → ปฏิเสธ
- **Full hexagonal (domain แยกจาก framework, ports/adapters)**: maintain ระยะยาวดี แต่ boilerplate หนักเกินไปสำหรับ phase 1 auth → เลื่อน

## Related

[[service-layer]] · [[repository]] · [[interface-layer]] · [[domain-error]]
