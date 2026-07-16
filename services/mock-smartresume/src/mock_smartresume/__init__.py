"""Mock SmartResume — a deterministic, stateless stand-in for the SmartResume
CredentialConnect API.

Implements only the two endpoints the SmartResume Adapter calls
(``POST /api/v1/token`` and ``POST /api/v1/credentials``) plus a health check,
in the same request/response shapes as the real API. Credentials validation is
deliberately permissive; the redirect URL is derived deterministically from the
request so demo runs and test assertions are reproducible. This is NOT
SmartResume — no resume is created and nothing is persisted. See
docs/3_design/mock-smartresume.md."""
