from __future__ import annotations

import hmac
import os

from fastapi import Depends, HTTPException
from fastapi.security import HTTPBasic, HTTPBasicCredentials

security = HTTPBasic(auto_error=False)


def require_auth(credentials: HTTPBasicCredentials | None = Depends(security)) -> None:
    user = os.environ.get("CRONOS_BASIC_AUTH_USER")
    password = os.environ.get("CRONOS_BASIC_AUTH_PASSWORD")
    if not user or not password:
        return  # auth disabled — no env vars set
    if credentials is None:
        raise HTTPException(status_code=401, headers={"WWW-Authenticate": "Basic"})
    ok = hmac.compare_digest(credentials.username.encode(), user.encode()) and hmac.compare_digest(
        credentials.password.encode(), password.encode()
    )
    if not ok:
        raise HTTPException(status_code=401, headers={"WWW-Authenticate": "Basic"})
