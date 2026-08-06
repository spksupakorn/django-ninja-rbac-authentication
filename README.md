# Django Ninja RBAC Authentication

Backend สำหรับ JWT authentication และ role-based access control (RBAC) บน Django Ninja/ASGI

## สิ่งที่ต้องมี

- Docker Desktop พร้อม Docker Compose v2 สำหรับการรันแบบ container
- [uv](https://docs.astral.sh/uv/) สำหรับ tooling บนเครื่อง
- Python **3.12.13** เมื่อรันบนเครื่อง (ช่วงเวอร์ชันถูกบังคับใน `pyproject.toml`)

## เริ่มต้นด้วย Docker

1. สร้าง environment file และเปลี่ยน secret ทั้งสองค่าเป็นค่าสุ่มคนละค่า ความยาวอย่างน้อย 32 ตัวอักษร

   ```sh
   cp .env.example .env
   ```

2. Build และเริ่ม PostgreSQL กับ API

   ```sh
   docker compose up --build -d
   ```

3. รัน migration แบบ manual (รวม RBAC catalog/role seed)

   ```sh
   docker compose exec web python manage.py migrate
   ```

4. Bootstrap administrator สำหรับ Django Admin และ API RBAC

   ```sh
   read -s BOOTSTRAP_ADMIN_PASSWORD
   export BOOTSTRAP_ADMIN_PASSWORD
   docker compose exec -e BOOTSTRAP_ADMIN_PASSWORD web \
     python manage.py bootstrap_admin --email admin@example.com
   unset BOOTSTRAP_ADMIN_PASSWORD
   ```

   คำสั่งนี้สร้างหรืออัปเดต account ให้เป็น Django superuser และ assign `authz` role `admin`.
   รันซ้ำได้โดยไม่ reset password ของ account เดิม

5. ตรวจ health

   ```sh
   curl http://localhost:8000/api/v1/health
   ```

   ผลลัพธ์คือ `{"status":"ok"}` และ OpenAPI อยู่ที่ [http://localhost:8000/api/docs](http://localhost:8000/api/docs)

   > การ migrate เป็นขั้นตอน manual ทั้ง local Compose และ production เพื่อให้ควบคุมจังหวะเปลี่ยน schema ได้

คำสั่งที่ใช้บ่อย:

```sh
docker compose logs -f web
docker compose exec web python manage.py bootstrap_admin --email admin@example.com
docker compose exec web python manage.py check
docker compose down
```

`docker compose down -v` ลบ PostgreSQL volume อย่างถาวร ใช้เฉพาะเมื่อต้องการ reset ข้อมูล development

## API หลัก

| Method | Path | หน้าที่ |
| --- | --- | --- |
| POST | `/api/v1/auth/register` | สมัคร user และ assign role เริ่มต้น |
| POST | `/api/v1/auth/login` | รับ access/refresh token |
| POST | `/api/v1/auth/refresh` | rotate refresh token |
| POST | `/api/v1/auth/logout` | revoke refresh token ปัจจุบัน |
| GET | `/api/v1/auth/me` | ดู claims จาก access token |
| CRUD | `/api/v1/admin/users` | จัดการ user (ต้องมี permission) |
| POST | `/api/v1/admin/users/{id}/roles` | assign role (ต้องมี `role.assign`) |
| GET | `/api/v1/admin/roles`, `/api/v1/admin/permissions` | ดู RBAC catalog (ต้องมี permission) |

ส่ง access token ด้วย `Authorization: Bearer <access-token>` ทุก endpoint ที่ป้องกันไว้
การแก้ role/permission จะมีผลกับ access token ที่ออกใหม่; token เดิมอาจคง claims ได้นานสูงสุดตาม `ACCESS_TTL`

role `admin` ที่ seed จาก migration ได้ permission catalog ทั้งหมด ส่วน role เริ่มต้น `user`
ไม่มี collection-level admin permission โดยตั้งใจ จึงเข้าถึง `/api/v1/admin/*` ไม่ได้จนกว่าจะได้รับสิทธิ์เพิ่ม

## รันบนเครื่องและทดสอบ

ติดตั้ง dependency development:

```sh
uv sync --frozen --group dev
```

สร้าง `.env` ให้ `DATABASE_URL` ชี้ PostgreSQL ที่เข้าถึงได้ (เมื่อรันบน host ใช้ `localhost` แทน `db`) แล้วรัน:

```sh
uv run python manage.py migrate
uv run uvicorn config.asgi:application --reload --host 127.0.0.1 --port 8000
uv run ruff check .
uv run mypy
uv run pytest --cov --cov-report=term-missing
```

test suite ใช้ PostgreSQL จริง และ CI บังคับ lint, type check และ service coverage อย่างน้อย 90%.
Factory สำหรับ test อยู่ที่ `tests/factories.py`; ใช้สร้าง model fixture ที่ reusable ใน test แบบ synchronous
ทั้ง Gunicorn และ Uvicorn ตรวจ connection ที่ ASGI lifespan; server จะไม่เริ่มเมื่อ PostgreSQL ไม่พร้อม

## Environment configuration

| Variable | ความหมาย | ค่า default |
| --- | --- | --- |
| `DATABASE_URL` | PostgreSQL connection URL | ต้องกำหนด |
| `DJANGO_SECRET_KEY` | Django signing secret; ต้องแยกจาก JWT secret | ต้องกำหนด |
| `JWT_SECRET` | HS256 JWT signing secret; ต้องแยกจาก Django secret | ต้องกำหนด |
| `ACCESS_TTL` | อายุ access token (`15m`, `1h`, `7d`) | `15m` |
| `REFRESH_TTL` | อายุ refresh token | `7d` |
| `DEFAULT_USER_ROLE` | role ที่ assign ระหว่าง register/create user | `user` |
| `THROTTLE_LOGIN` | rate limit ต่อ IP ของ login/refresh | `5/minute` |
| `ALLOWED_HOSTS` | domain/IP production คั่นด้วย comma | ต้องกำหนดใน production |
| `DJANGO_SETTINGS_MODULE` | settings module ที่ใช้ boot | `config.settings.dev` |

`config.settings.prod` บังคับ `DEBUG=False`, `ALLOWED_HOSTS`, HTTPS redirect, secure cookies,
HSTS, `nosniff` และ referrer policy. กำหนด TLS ที่ reverse proxy/load balancer ให้เสร็จก่อนเปิดใช้ production settings.

## RBAC seed และการเปลี่ยน catalog

Permission catalog ถูก freeze ใน data migration เพื่อให้ migration reproducible. เมื่อเพิ่ม permission
ให้เพิ่ม migration ใหม่เพื่อ seed/grant permission นั้น ไม่ควรแก้ migration เก่า. รายละเอียดการตัดสินใจอยู่ใน [docs/adr](docs/adr/README.md).
