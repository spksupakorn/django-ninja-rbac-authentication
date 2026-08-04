# Glossary — Django Ninja RBAC Backend

คำศัพท์ร่วมของทีม (ubiquitous language) สำหรับ Phase 1 ลิงก์กลับไปยัง ADR ที่ตัดสินเรื่องนั้น

## RBAC & Authorization

- <a id="rbac"></a>**RBAC** — Role-Based Access Control. ให้สิทธิ์ผ่าน role/permission ไม่ผูกกับตัว user ตรงๆ → ADR-0001
- <a id="role"></a>**Role** — กลุ่มของ permission ที่ตั้งชื่อ (เช่น `admin`, `staff`). user มีได้หลาย role → ADR-0001
- <a id="permission"></a>**Permission** — สิทธิ์ระดับ action แบบ `resource.action` (เช่น `user.create`). เป็นหน่วยที่โค้ดเช็คจริง → ADR-0001
- <a id="require-permission"></a>**@require_permission** — guard/decorator ที่ endpoint ตรวจว่า caller มี permission ที่ระบุ (อ่านจาก claim ใน access token) → ADR-0001/0002

## Tokens

- <a id="access-token"></a>**Access token** — JWT อายุสั้น (15 นาที) ใช้เข้าถึง API ผ่าน `Authorization: Bearer`. ฝัง `roles`+`perms` เป็น claim → ADR-0002
- <a id="refresh-token"></a>**Refresh token** — token อายุยาว (7 วัน) เก็บ hash ใน DB ใช้แลก access token ใหม่ → ADR-0002
- <a id="token-rotation"></a>**Token rotation** — ทุกครั้งที่ refresh จะ revoke ตัวเก่าและออกคู่ใหม่ → ADR-0002
- <a id="token-family"></a>**Token family** — chain ของ refresh token ที่สืบจาก login ครั้งเดียวกัน ใช้ทำ reuse-detection → ADR-0002
- <a id="reuse-detection"></a>**Reuse-detection** — ถ้า refresh ที่ถูก rotate/revoke ไปแล้วถูกใช้ซ้ำ = สัญญาณถูกขโมย → revoke ทั้ง family → ADR-0002
- <a id="jti"></a>**jti** — JWT ID, ตัวระบุ token ไม่ซ้ำ ใช้ทำ revoke/tracking → ADR-0002
- <a id="claim"></a>**Claim** — ข้อมูลใน payload ของ JWT (เช่น `sub`, `exp`, `roles`, `perms`)

## Architecture layers

- <a id="interface-layer"></a>**Interface layer** — Django Ninja routers + Pydantic schemas: รับ/ตรวจ input, auth guard, map error → HTTP. ไม่แตะ ORM → ADR-0003
- <a id="service-layer"></a>**Service layer** — business logic/use case. ไม่รู้จัก HTTP, ไม่เขียน ORM query เอง → ADR-0003
- <a id="repository"></a>**Repository** — ชั้นเดียวที่เขียน ORM query. ห่อ data access, คุม async ORM ที่จุดเดียว → ADR-0003/0005
- <a id="domain-error"></a>**Domain error** — exception เชิงธุรกิจที่ service ยิง (เช่น `InvalidCredentials`) แล้ว map เป็น HTTP status ที่ interface → ADR-0003

## Identity

- <a id="custom-user-model"></a>**Custom User model** — `accounts.User` ที่เรานิยามเอง ตั้ง `AUTH_USER_MODEL` ก่อน migrate แรก → ADR-0004
- <a id="username-field"></a>**USERNAME_FIELD** — field ที่ Django ใช้เป็น identity ตอน login; ที่นี่ = `email` → ADR-0004

## Runtime & Security

- <a id="asgi"></a>**ASGI** — interface async ของ Python web (แทน WSGI) รันด้วย uvicorn → ADR-0005
- <a id="async-orm"></a>**Async ORM** — Django query methods แบบ async (`aget`, `acreate`, `afirst`, ...) → ADR-0005
- <a id="sync-to-async"></a>**sync_to_async** — util (asgiref) ห่อโค้ด sync ให้เรียกใน async ได้; ใช้กับ password hashing → ADR-0005/0006
- <a id="pydantic-settings"></a>**pydantic-settings** — อ่าน/validate env vars แบบ typed, fail ตอน boot → ADR-0005
- <a id="uv"></a>**uv** — Python package/dependency manager (เร็ว, มี lockfile) → ADR-0005
- <a id="argon2"></a>**Argon2 (id)** — algorithm hashing password แบบ memory-hard ที่แนะนำ → ADR-0006
- <a id="throttling"></a>**Throttling** — จำกัดจำนวน request ต่อช่วงเวลา (เช่น login 5/นาที/IP), เกิน → 429 → ADR-0006
- <a id="user-enumeration"></a>**User enumeration** — การเดาว่ามี account อยู่จริงจาก error/timing ที่ต่างกัน; กันด้วย error กลางๆ + dummy hash → ADR-0006
- <a id="timing-attack"></a>**Timing attack** — อนุมานความลับจากเวลาที่ response ต่างกัน; กันด้วย constant-time compare / dummy verify → ADR-0006
