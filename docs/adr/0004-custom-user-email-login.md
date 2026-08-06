# ADR 0004 — Custom User model, email เป็น identity

- สถานะ: Accepted
- วันที่: 2026-08-04

## Context

การเปลี่ยน `AUTH_USER_MODEL` หลัง migrate ครั้งแรกใน Django เจ็บมาก (ต้อง reset migration/DB)
จึงต้องตัดสินตั้งแต่ก่อนรัน migration แรก — นี่คือ **ประตูทางเดียว**

## Decision

สร้าง **Custom User model** ตั้งแต่ต้น (`accounts.User`), ใช้ **email เป็น login identity**:

```python
class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    # ไม่มี field username
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []
    objects = UserManager()   # custom manager: create_user / create_superuser ด้วย email
```

- ตั้ง `AUTH_USER_MODEL = "accounts.User"` ใน settings ก่อน migrate แรก
- email identity เป็น **case-insensitive**: normalize เป็น lowercase ทั้งค่า และ database
  บังคับ unique ด้วย `Lower("email")`
- ใช้ `AbstractBaseUser` + `PermissionsMixin` (ได้ password/last_login + hook เข้ากับ Django auth)
- RBAC role/permission ของเราเป็น **ตารางแยกของเราเอง** (ADR-0001) ไม่ใช้ Django Group/Permission
  built-in เพื่อคุม schema/naming เอง (Django perms ยังใช้กับ admin ได้ตามปกติ)

## Consequences

- (+) identity เป็น email ตรงกับ UX สมัยใหม่ ไม่มี username ซ้ำซ้อน
- (+) ควบคุม user schema ได้เต็มที่ ต่อ field ได้อิสระ
- (+) เลี่ยงหายนะ migration ในอนาคต (ตัดสินก่อน migrate แรก)
- (−) ต้องเขียน custom `UserManager` + form/admin เอง
- (−) ผูกกับ Django auth เล็กน้อย (ไม่ใช่ domain-pure) — ยอมรับเพื่อความเรียบง่าย

## Alternatives considered

- ใช้ Django `User` มาตรฐาน: ติด username-based, เปลี่ยนทีหลังยาก → ปฏิเสธ
- Custom User + login ด้วย username: ไม่ตรง requirement (ต้องการ email) → ปฏิเสธ

## Related

[[custom-user-model]] · [[username-field]] · ADR-0001
