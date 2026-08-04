# Understood exact permission-code contracts

The learner understands that permission codes are exact identifiers shared by application logic and
database rows: `users.read` and `user.read` are distinct permissions. This motivates maintaining a
single catalog in `permissions.py`.
