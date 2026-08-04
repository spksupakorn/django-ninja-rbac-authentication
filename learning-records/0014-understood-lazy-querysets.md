# Understood lazy QuerySets

The learner understands that `filter()` constructs a lazy SQL query plan (including its WHERE
condition) without contacting the database, while an async evaluation method such as `afirst()`
executes the query and must be awaited.
