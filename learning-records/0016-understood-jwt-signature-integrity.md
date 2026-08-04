# Understood JWT signature integrity

The learner understands that modifying JWT payload claims such as `perms` invalidates the existing
signature. Without the server-held `JWT_SECRET`, a client cannot create a replacement HS256
signature that the server will verify.
