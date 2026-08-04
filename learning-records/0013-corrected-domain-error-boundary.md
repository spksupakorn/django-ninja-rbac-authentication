# Corrected the domain-error boundary

The learner initially focused on exceptions stopping later execution. The model was refined: a
service raises `PermissionDenied` primarily to express a business outcome without coupling to HTTP;
the API layer owns translation to a 403 response, while the exception also stops the normal flow.
