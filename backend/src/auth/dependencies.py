"""Auth dependencies for protected routes.

STUB — this is a temporary placeholder for P2-SHR2 (file upload endpoint),
which needs *some* notion of "the current user" to attach uploads to.

Real implementation lands with P1-SRE4 (Sreehitha) — JWT cookie verification
per the stack agreed in docs/architecture.md (P0-SHI1): backend issues a JWT
on login, set as an httpOnly secure cookie, verified here on each request.

TODO(P1-SRE4): replace get_current_user_id() body with real cookie/JWT
verification. Once that lands, every route currently importing this stub
(documents.py, etc.) should keep working unchanged — only this function's
internals need to change, not its signature or return type.
"""
import uuid

_DEV_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def get_current_user_id() -> uuid.UUID:
    """Return the authenticated user's ID.

    STUB: always returns a fixed dev user ID. Replace with real JWT cookie
    verification in P1-SRE4 — raise HTTPException(401) if the cookie is
    missing/invalid instead of returning a hardcoded value.
    """
    return _DEV_USER_ID