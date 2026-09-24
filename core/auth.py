from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel
import asyncio
import core.users as users
import core.ip_tracking as ip_tracking

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


def _client_ip(request: Request) -> str:
    # За прокси Render реальный IP в X-Forwarded-For
    xff = request.headers.get("x-forwarded-for", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.post("/api/auth/register")
async def register(payload: RegisterPayload, request: Request):
    import core.registration_guard as reg_guard

    ip = _client_ip(request)

    # Проверка лимита
    can_register, left = await reg_guard.check_limit(ip)
    if not can_register:
        raise HTTPException(
            status_code=429,
            detail="Слишком много регистраций с этого IP. Попробуй завтра."
        )

    # Антибот-пауза (2 секунды)
    await asyncio.sleep(2)

    r = await users.create_user(payload.name, payload.pin)
    if not r["ok"]:
        raise HTTPException(status_code=400, detail=r["error"])

    # Записываем успешную регистрацию
    try:
        await reg_guard.record_registration(ip, r["uid"])
    except Exception as e:
        print("registration guard error:", e)

    try:
        await ip_tracking.track_visit(
            ip=ip,
            user_agent=request.headers.get("user-agent", ""),
            uid=r["uid"],
        )
    except Exception as e:
        print("ip track error:", e)

    return r


@router.post("/api/auth/login")
async def login(payload: LoginPayload, request: Request):
    r = await users.login(payload.uid, payload.pin, ip=_client_ip(request))
    if not r["ok"]:
        raise HTTPException(status_code=401, detail=r["error"])
    try:
        await ip_tracking.track_visit(
            ip=_client_ip(request),
            user_agent=request.headers.get("user-agent", ""),
            uid=r["uid"],
        )
    except Exception as e:
        print("ip track error:", e)
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


@router.post("/api/visit")
async def public_visit(request: Request):
    """
    Публичный трекинг захода на сайт (без авторизации).
    Собирает IP и час, чтобы понимать, откуда и когда заходят.
    """
    try:
        await ip_tracking.track_visit(
            ip=_client_ip(request),
            user_agent=request.headers.get("user-agent", ""),
            uid="",
        )
    except Exception as e:
        print("public visit error:", e)
    return {"ok": True}
