"""Auth routes — optional login. Anonymous users share the demo session;
logged-in users get isolated per-user data stores.
"""
from fastapi import APIRouter, Request, Response
from pydantic import BaseModel

from app.database.users import (
    AUTH_COOKIE,
    sign_username,
    unsign_cookie,
    verify_user,
)

router = APIRouter(prefix="/api/auth")


class LoginPayload(BaseModel):
    username: str
    password: str


def current_username(request: Request) -> str | None:
    """Extract the authenticated username from the signed cookie, if any."""
    raw = request.cookies.get(AUTH_COOKIE)
    if not raw:
        return None
    return unsign_cookie(raw)


@router.post("/login")
def login(payload: LoginPayload, response: Response):
    if not verify_user(payload.username, payload.password):
        response.status_code = 401
        return {"ok": False, "error": "invalid credentials"}
    response.set_cookie(
        key=AUTH_COOKIE,
        value=sign_username(payload.username),
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 24 * 30,
    )
    return {"ok": True, "username": payload.username}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(AUTH_COOKIE)
    return {"ok": True}


@router.get("/me")
def me(request: Request):
    username = current_username(request)
    return {"authenticated": username is not None, "username": username}
