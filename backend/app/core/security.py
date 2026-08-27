"""Shared-secret authentication for admin-only write endpoints."""

import secrets
from typing import Annotated

from fastapi import Header, HTTPException, status

from app.core.config import settings


async def require_admin_api_key(x_admin_api_key: Annotated[str | None, Header()] = None) -> None:
    """
    Require a valid admin API key on the ``X-Admin-Api-Key`` request header.

    Intended as a dependency (``Depends(require_admin_api_key)``) on every
    write endpoint that must be restricted to the site admin and the
    deployment's GitHub Action, so the public read endpoints stay open while
    nothing else can create or overwrite draw data. The comparison uses
    :func:`secrets.compare_digest` rather than ``==`` so it takes constant
    time regardless of where the strings first differ.

    :param x_admin_api_key: Value of the ``X-Admin-Api-Key`` request header.
    :return: None.
    :raises fastapi.HTTPException: 401 if the header is missing or does not
        match :attr:`app.core.config.settings.admin_api_key`.
    """
    expected = settings.admin_api_key.get_secret_value()

    if x_admin_api_key is None or not secrets.compare_digest(x_admin_api_key, expected):
        error_message = "Invalid or missing admin API key."
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=error_message)
