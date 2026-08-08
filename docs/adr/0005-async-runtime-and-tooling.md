# ADR 0005 — Async Django Ninja + uv + Docker Compose + pydantic-settings

- สถานะ: Accepted
- วันที่: 2026-08-04

## Context

ต้องเลือก runtime model (async/sync), เครื่องมือ dependency, ขอบเขต container, และการจัดการ config
ให้ robust/scalable และ dev ตั้งได้ง่าย

## Decision

**Async endpoints** — Django Ninja `async def`
- ORM: ใช้ **async query methods** (`aget`, `acreate`, `afirst`, `aupdate`, `async for`) ในชั้น repository
- โค้ด sync ที่เลี่ยงไม่ได้ (เช่น password hashing) ครอบด้วย `sync_to_async(..., thread_sensitive=False)`
- รันด้วย ASGI server (**uvicorn/gunicorn+uvicorn worker**)

**Dependency: uv** — `pyproject.toml` + `uv.lock` (reproducible, ติดตั้งเร็ว)

**Docker Compose** ครอบทั้ง stack สำหรับ dev:
```
services:
  web:  Django (ASGI) — build จาก Dockerfile ที่ใช้ uv
  db:   Postgres 16
volumes: pgdata
```
- ต่อ Postgres ผ่าน env `DATABASE_URL`; `web` รอ `db` healthy ก่อนรัน

**Config: pydantic-settings + split settings**
```
config/settings/
  base.py    ← อ่านค่าจาก Settings(BaseSettings) แบบ typed + validated
  dev.py     ← DEBUG, relax
  prod.py    ← strict, secure cookies/headers
```
- ค่าenv ผิด/ขาด → fail ตอน boot ไม่ใช่ runtime
- `DJANGO_SETTINGS_MODULE` เลือก dev/prod

## Consequences

- (+) concurrency สูงสำหรับ workload I/O-bound (auth เรียก DB เยอะ)
- (+) uv.lock ทำให้ build/CI reproducible
- (+) dev ยก stack ทั้งชุดด้วย `docker compose up` คำสั่งเดียว
- (+) config typed — จับ misconfig ได้เร็ว
- (−) **async + Django ORM มี caveat**: ลืมใช้ async method → `SynchronousOnlyOperation` หรือ block loop
  → บังคับผ่าน repository layer (ADR-0003) เป็นที่เดียวที่แตะ ORM จึงคุม async ได้จุดเดียว
- (−) บาง lib ยัง sync-only → ต้องห่อ `sync_to_async` (password hashing, throttle บางตัว)
- (−) ASGI + async ดีบั๊ก stack trace ยากกว่า sync เล็กน้อย

## Alternatives considered

- Sync + gunicorn workers: ecosystem พร้อมกว่า, ง่ายกว่า — แต่เลือก async เพื่อ concurrency/แนวทาง scale
- poetry / requirements.txt: ใช้ได้ แต่ uv เร็วและ lock แน่นกว่า → ปฏิเสธ
- postgres-only ใน compose: env dev/prod ต่างกัน → เลือกยกทั้ง stack เพื่อ parity

## Related

[[asgi]] · [[async-orm]] · [[sync-to-async]] · [[pydantic-settings]] · [[uv]] · [Async ORM hardening plan](../ASYNC_ORM_PLAN.md)
