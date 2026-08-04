# Understood UserManager creation invariants

The learner understands that registration should create users through `UserManager.create_user()`
rather than direct model saves, so validation, email normalization, and password hashing happen
consistently at every user-creation entry point.
