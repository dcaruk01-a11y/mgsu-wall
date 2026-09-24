"""Общие функции для всех модулей админки."""
import time
from fastapi import Header, HTTPException

from config import ADMIN_PASSWORD
import core.state as state


def check_admin(token: str) -> bool:
    if not token or not ADMIN_PASSWORD:
        return False
    exp = state.admin_tokens.get(token)
    if not exp or exp < time.time():
        state.admin_tokens.pop(token, None)
        return False
    return True


def require_admin(authorization: str = Header(default="")) -> str:
    token = authorization.replace("Bearer ", "").strip()
    if not check_admin(token):
        raise HTTPException(status_code=401, detail="Unauthorized")
    return token
