from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
import core.users as users

router = APIRouter()


class RegisterPayload(BaseModel):
    name: str = ""
    pin: str = ""


class LoginPayload(BaseModel):
    uid: str = ""
    pin: str = ""


class UpdateNamePayload(BaseModel):
    display_name: str = ""


class UpdatePinPayload(BaseModel):
    old_pin: str = ""
    new_pin: str = ""


def _token(authorization: str) -> str:
    return authorization.replace("Bearer ", "").strip()


@router.post("/api/auth/register")
async def register(payload: RegisterPayload):
    r = await users.create_user(payload.name, payload.pin)
    if not r["ok"]:
        raise HTTPException(status_code=400, detail=r["error"])
    return r


@router.post("/api/auth/login")
async def login(payload: LoginPayload):
    r = await users.login(payload.uid, payload.pin)
    if not r["ok"]:
        raise HTTPException(status_code=401, detail=r["error"])
    return r


@router.post("/api/auth/logout")
async def logout(authorization: str = Header(default="")):
    await users.logout(_token(authorization))
    return {"ok": True}


@router.get("/api/auth/me")
async def me(authorization: str = Header(default="")):
    user = await users.get_user_by_token(_token(authorization))
    if not user:
        raise HTTPException(status_code=401, detail="Не авторизован")
    return {"ok": True, "user": user}


@router.post("/api/auth/update-name")
async def update_name(payload: UpdateNamePayload, authorization: str = Header(default="")):
    user = await users.get_user_by_token(_token(authorization))
    if not user:
        raise HTTPException(status_code=401, detail="Не авторизован")
    r = await users.update_display_name(user["uid"], payload.display_name)
    if not r["ok"]:
        raise HTTPException(status_code=400, detail=r["error"])
    return r


@router.post("/api/auth/update-pin")
async def update_pin(payload: UpdatePinPayload, authorization: str = Header(default="")):
    user = await users.get_user_by_token(_token(authorization))
    if not user:
        raise HTTPException(status_code=401, detail="Не авторизован")
    r = await users.update_pin(user["uid"], payload.old_pin, payload.new_pin)
    if not r["ok"]:
        raise HTTPException(status_code=400, detail=r["error"])
    return r
