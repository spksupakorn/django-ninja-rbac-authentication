# Corrected the purpose of generic login errors

The learner initially focused on giving the API layer one error to map. The model was refined: a
shared `InvalidCredentials` error also intentionally hides whether an email exists, reducing user
enumeration risk while consistently mapping both failures to HTTP 401.
