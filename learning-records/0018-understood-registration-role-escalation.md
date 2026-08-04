# Understood registration privilege-escalation risk

The learner understands that accepting a client-supplied role during registration would allow an
attacker to self-assign `admin`. The server must own role-assignment policy and apply
`DEFAULT_USER_ROLE` for new registrations.
