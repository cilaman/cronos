from __future__ import annotations

import hmac
import os

import bcrypt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBasic, HTTPBasicCredentials

security = HTTPBasic(auto_error=False)


def require_auth(
    request: Request,
    credentials: HTTPBasicCredentials | None = Depends(security),
) -> None:
    # Explicit opt-out: must be the exact string "true" — any other value falls through.
    if os.environ.get("CRONOS_AUTH_DISABLED") == "true":
        return

    # Internal service token: agents inside the container bypass bcrypt by
    # sending Authorization: Bearer <CRONOS_INTERNAL_TOKEN>. Fail-closed: if
    # CRONOS_INTERNAL_TOKEN is unset or empty, this bypass path is disabled.
    internal_token = os.environ.get("CRONOS_INTERNAL_TOKEN")
    if internal_token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            provided = auth_header[len("Bearer "):]
            if hmac.compare_digest(provided.encode(), internal_token.encode()):
                return
            # Token presented but wrong — fail immediately; do not fall through
            # to the bcrypt check.
            raise HTTPException(status_code=401)

    user = os.environ.get("CRONOS_BASIC_AUTH_USER")
    pw_hash = os.environ.get("CRONOS_BASIC_AUTH_HASH")
    password = os.environ.get("CRONOS_BASIC_AUTH_PASSWORD")
    # A username plus EITHER a bcrypt hash (preferred — keeps the plaintext
    # password out of the environment) OR a plaintext password must be set.
    # CRONOS_BASIC_AUTH_HASH can reuse the exact value of Caddy's BASIC_AUTH_HASH
    # so there is a single secret and no plaintext anywhere. When both are set,
    # the hash wins.
    if not user or not (pw_hash or password):
        # Credentials unconfigured and auth not explicitly disabled → misconfiguration.
        raise HTTPException(status_code=503, detail="Auth credentials not configured")
    if credentials is None:
        raise HTTPException(status_code=401, headers={"WWW-Authenticate": "Basic"})

    # Compute both factors without short-circuiting on the username so the
    # username does not become a timing oracle.
    user_ok = hmac.compare_digest(credentials.username.encode(), user.encode())
    if pw_hash:
        # bcrypt.checkpw is constant-time and truncates the password at 72 bytes
        # (matching Caddy's bcrypt). A malformed/garbage hash → non-match (401),
        # not a 500.
        try:
            pw_ok = bcrypt.checkpw(credentials.password.encode(), pw_hash.encode())
        except ValueError:
            pw_ok = False
    else:
        pw_ok = hmac.compare_digest(credentials.password.encode(), password.encode())
    if not (user_ok and pw_ok):
        raise HTTPException(status_code=401, headers={"WWW-Authenticate": "Basic"})
