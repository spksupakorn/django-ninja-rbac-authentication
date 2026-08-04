# ADR 0001 — RBAC model: Role → Permission

- สถานะ: Accepted
- วันที่: 2026-08-04

## Context

ต้องการควบคุมสิทธิ์การเข้าถึง API แบบยืดหยุ่น รองรับการเพิ่ม role ใหม่โดยไม่ต้องแก้โค้ด
มีสามทางเลือกหลัก: role อย่างเดียว (เช็ค role ที่ endpoint), role→permission (role เป็นถุงของ permission ย่อย), หรือเพิ่ม object-level permission

## Decision

ใช้โมเดล **Role → Permission**:

- `User` มีได้หลาย `Role` (many-to-many ผ่าน `UserRole`)
- `Role` มีได้หลาย `Permission` (many-to-many ผ่าน `RolePermission`)
- `Permission` ใช้ naming แบบ `resource.action` (เช่น `user.create`, `user.read`, `role.assign`)
- โค้ด **เช็คที่ระดับ permission ไม่ใช่ role**: `@require_permission("user.create")`
  - endpoint ผูกกับ capability ไม่ใช่ชื่อ role → เพิ่ม/แก้ role ได้โดยไม่แตะโค้ด

Permission เป็น **catalog ที่นิยามในโค้ด** (enum/constants) และ seed ลง DB ผ่าน migration/data-migration
เพื่อให้ permission string มี single source of truth และ refactor ได้ปลอดภัย

**Default role ตอน register**: user ใหม่ถูก assign role `user` **อัตโนมัติ** (role นี้ seed ไว้ตั้งแต่ต้น)
- `user` = สิทธิ์ขั้นต่ำของ authenticated user (จัดการ resource ของตัวเอง — ขยาย perm ทีหลังได้)
- role `admin` (ได้ทุก perm) assign ให้เฉพาะโดย admin ผ่าน admin CRUD ไม่ได้อัตโนมัติ
- ชื่อ default role เก็บเป็น setting (`DEFAULT_USER_ROLE="user"`) ไม่ hardcode ในหลายที่

## Consequences

- (+) เพิ่ม role / ปรับสิทธิ์ได้ที่ข้อมูล ไม่ต้อง deploy
- (+) endpoint อ่านง่าย สื่อ intent (`order.refund` ชัดกว่า `role == "manager"`)
- (+) schema เป็นมาตรฐาน ต่อยอด object-level ได้ภายหลังโดยไม่รื้อ
- (−) schema ซับซ้อนกว่า role อย่างเดียว 2 ตาราง join
- (−) ต้องมี seed/migration ดูแล permission catalog ให้ตรงกับโค้ด

## Alternatives considered

- **Role อย่างเดียว**: ง่ายสุด แต่พอ business ซับซ้อนต้องแก้โค้ดทุกครั้งที่เพิ่มเงื่อนไข → ปฏิเสธ
- **Role + Permission + object-level**: ทรงพลังสุด แต่ over-engineer สำหรับ phase 1 → เลื่อน (เปิดทางไว้แล้ว)

## Related

[[permission]] · [[role]] · [[rbac]] · ADR-0002 (perms ฝังใน access token)
