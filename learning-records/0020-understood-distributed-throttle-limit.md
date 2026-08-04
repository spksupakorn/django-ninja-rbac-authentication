# Understood the distributed throttle limitation

The learner understands that each web instance has separate in-memory counters, so a rate limit is
not global after horizontal scaling. A shared backend such as Redis is required for consistent
cross-instance throttling in a later phase.
