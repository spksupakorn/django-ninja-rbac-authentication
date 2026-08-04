# Understood permission-set deduplication

The learner correctly explained that a permission set contains `reports.read` only once even when
multiple Roles grant it, because set membership removes duplicates. This supports later permission
guard reasoning.
