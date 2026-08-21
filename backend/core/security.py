from __future__ import annotations

import logging
import secrets
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from core.settings import settings

logger = logging.getLogger(__name__)

bearer_scheme = HTTPBearer(auto_error=False)


async def verify_api_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> None:
    """Require `Authorization: Bearer <token>` matching API_AUTH_TOKEN when set.
    If API_AUTH_TOKEN is empty, requests are accepted unauthenticated for local/dev use.
    """
    if not settings.api_auth_token:
        return

    if credentials is None or not secrets.compare_digest(
        credentials.credentials, settings.api_auth_token
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
