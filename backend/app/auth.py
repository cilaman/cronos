from __future__ import annotations

import hmac
import os

from fastapi import Depends, HTTPException
from fastapi.security import HTTPBasic, HTTPBasicCredentials

security = HTTPBasic(auto_error=False)


def require_auth(credentials: HTTPBasicCredentials | None = Depends(security)) -> None:
    # Explicit opt-out: must be the exact string "true" — any other value falls through.
    if os.environ.get("CRONOS_AUTH_DISABLED") == "true":
        return

    user = os.environ.get("CRONOS_BASIC_AUTH_USER")
    password = os.environ.get("CRONOS_BASIC_AUTH_PASSWORD")
    if not user or not password:
        # Credentials unconfigured and auth not explicitly disabled → misconfiguration.
        raise HTTPException(status_code=503, detail="Auth credentials not configured")
    if credentials is None:
        raise HTTPException(status_code=401, headers={"WWW-Authenticate": "Basic"})
    ok = hmac.compare_digest(credentials.username.encode(), user.encode()) and hmac.compare_digest(
        credentials.password.encode(), password.encode()
    )
    if not ok:
        raise HTTPException(status_code=401, headers={"WWW-Authenticate": "Basic"})
