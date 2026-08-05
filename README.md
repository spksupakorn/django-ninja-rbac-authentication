# Django Ninja RBAC Authentication

Backend สำหรับ JWT authentication และ role-based access control (RBAC) ที่สร้างด้วย
Django Ninja และ ASGI runtime

## สิ่งที่ต้องมี

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) พร้อม Docker Compose v2
- [uv](https://docs.astral.sh/uv/) (เมื่อต้องการรัน tooling หรือแอปบนเครื่อง)
- Python 3.12 ขึ้นไป (uv จะจัดการ Python ที่ต้องใช้ให้ได้)

## เริ่มต้นสำหรับ local development

1. สร้างไฟล์ environment จาก template แล้วเปลี่ยน `DJANGO_SECRET_KEY` และ `JWT_SECRET`
   เป็นค่าสุ่มคนละค่า โดยแต่ละค่าต้องยาวอย่างน้อย 32 ตัวอักษร

   ```sh
   cp .env.example .env
   ```

2. Build และเริ่มทั้ง web service กับ PostgreSQL ในเบื้องหลัง

   ```sh
   docker compose up --build -d
   ```

   Compose จะรอให้ PostgreSQL พร้อมใช้งานก่อนจึงเริ่ม web service

3. ตรวจสถานะและเรียก health endpoint

   ```sh
   docker compose ps
   curl http://localhost:8000/api/health
   ```

   ควรได้ผลลัพธ์:

   ```json
   {"status": "ok"}
   ```

4. เปิด API documentation ที่ [http://localhost:8000/api/docs](http://localhost:8000/api/docs)

> Health endpoint ใช้ URL ไม่มี trailing slash: `/api/health`

## คำสั่งใช้งานประจำวัน

ดู log ของ service:

```sh
docker compose logs -f web
docker compose logs -f db
```

รัน Django management command ภายใน container:

```sh
docker compose exec web uv run --no-sync python manage.py check
docker compose exec web uv run --no-sync python manage.py migrate
```

ปิด service โดยเก็บข้อมูล PostgreSQL ไว้:

```sh
docker compose down
```

เมื่อต้องการล้าง database สำหรับ development แล้วเริ่มใหม่:

```sh
docker compose down -v
docker compose up --build -d
```

คำสั่ง `down -v` จะลบข้อมูลใน database volume อย่างถาวร

## รัน tooling บนเครื่อง

ติดตั้ง dependency กลุ่ม development หนึ่งครั้ง:

```sh
uv sync --group dev
```

จากนั้นใช้คำสั่งเหล่านี้:

```sh
uv run ruff check .
uv run mypy
uv run pytest
```
- uv 
## รัน app บนเครื่องโดยไม่ใช้ Docker

ติดตั้งและเริ่ม PostgreSQL บนเครื่องก่อน (M1 เป็นต้นไป app จะเชื่อมต่อ database จริง)
จากนั้นสร้าง `.env` และตั้ง URL ให้ชี้ไปที่ host ของเครื่อง:

```dotenv
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/rbac_auth
```

เริ่ม ASGI development server พร้อม auto-reload:

```sh
uv run uvicorn config.asgi:application --reload --host 127.0.0.1 --port 8000
```

เข้าใช้งานได้ที่ [http://127.0.0.1:8000/api/docs](http://127.0.0.1:8000/api/docs)
และตรวจ liveness ได้ด้วย `curl http://127.0.0.1:8000/api/health`

การทดสอบหรือคำสั่ง Django อ่านค่า config จาก `.env` ด้วย ดังนั้นให้สร้างไฟล์นี้ก่อนเสมอ
ค่า default ใน `.env.example` ใช้ hostname `db` ซึ่งมีไว้สำหรับ web container ใน Docker Compose;
ให้เปลี่ยนเป็น `localhost` เมื่อรัน service บน host

## Environment configuration

| Variable | ความหมาย | ค่า default |
| --- | --- | --- |
| `DATABASE_URL` | PostgreSQL connection URL | ต้องกำหนด |
| `DJANGO_SECRET_KEY` | Django signing secret, แยกจาก JWT และอย่างน้อย 32 ตัวอักษร | ต้องกำหนด |
| `JWT_SECRET` | JWT signing secret, แยกจาก Django secret และอย่างน้อย 32 ตัวอักษร | ต้องกำหนด |
| `ACCESS_TTL` | อายุ access token | `15m` |
| `REFRESH_TTL` | อายุ refresh token | `7d` |
| `DEFAULT_USER_ROLE` | role ที่ assign ให้ user ใหม่ | `user` |
| `THROTTLE_LOGIN` | ขีดจำกัด login per IP | `5/minute` |
| `ALLOWED_HOSTS` | โดเมน/IP ที่อนุญาตบน production (คั่นด้วย comma) | ต้องกำหนดบน production |
| `DJANGO_SETTINGS_MODULE` | settings module ที่ใช้ boot | `config.settings.dev` |

`config.settings.prod` เปิด secure-cookie, HSTS และ HTTPS redirect สำหรับ production;
ห้ามนำค่า secret ตัวอย่างไปใช้งานจริง

## โครงสร้างโดยย่อ

```text
config/             Django settings, ASGI, URL routing และ Ninja API root
apps/accounts/      custom user domain (จะเริ่มใน M1)
apps/authz/         role, permission และ JWT domain
apps/common/        shared primitives
docker/             Dockerfile สำหรับ ASGI service
tests/              automated tests
```
