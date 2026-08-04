# Architecture Decision Records (ADR)

บันทึกการตัดสินใจเชิงสถาปัตยกรรมของโปรเจกต์ Django Ninja RBAC Backend
รูปแบบ: [MADR](https://adr.github.io/madr/) แบบย่อ — Context → Decision → Consequences → Alternatives

## Phase 1 — RBAC Authentication (JWT Bearer)

| ADR | หัวข้อ | สถานะ |
|-----|--------|-------|
| [0001](0001-rbac-role-permission-model.md) | RBAC model: Role → Permission | Accepted |
| [0002](0002-jwt-auth-strategy.md) | JWT auth: Access + Refresh (rotation + reuse-detection) | Accepted |
| [0003](0003-layered-architecture.md) | Layered architecture: API / Service / Repository | Accepted |
| [0004](0004-custom-user-email-login.md) | Custom User model, email เป็น identity | Accepted |
| [0005](0005-async-runtime-and-tooling.md) | Async Django Ninja + uv + Docker Compose + pydantic-settings | Accepted |
| [0006](0006-login-security-hardening.md) | Argon2 + rate limiting ตอน login | Accepted |

## Phase 1 Scope

**อยู่ใน scope**
- Register / Login / Logout (revoke refresh)
- Refresh token endpoint (rotation)
- Admin CRUD: จัดการ user + assign role/permission

**เลื่อนไป Phase 2**
- Email verification
- Password reset
- (พิจารณา) RS256, object-level permission, async ORM ทั้งระบบ, Redis-backed throttle/blocklist
