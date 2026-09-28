from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel
import asyncio
import core.users as users
import core.ip_tracking as ip_tracking

router = APIRouter()


class RegisterPayload(BaseModel):
    name: str = ""
    pin: str = ""
    visitor_id: str = ""


class LoginPayload(BaseModel):
    uid: str = ""
    pin: str = ""
    visitor_id: str = ""


class UpdateNamePayload(BaseModel):
    display_name: str = ""


class UpdatePinPayload(BaseModel):
    old_pin: str = ""
    new_pin: str = ""


def _token(authorization: str) -> str:
    return authorization.replace("Bearer ", "").strip()


def _client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.post("/api/auth/register")
async def register(payload: RegisterPayload, request: Request):
    import core.registration_guard as reg_guard

    ip = _client_ip(request)
    visitor_id = (payload.visitor_id or "").strip()[:64]

    can_register, left = await reg_guard.check_limit(ip)
    if not can_register:
        raise HTTPException(
            status_code=429,
            detail="Слишком много регистраций с этого IP. Попробуй завтра."
        )

    await asyncio.sleep(2)

    r = await users.create_user(payload.name, payload.pin)
    if not r["ok"]:
        raise HTTPException(status_code=400, detail=r["error"])

    try:
        await reg_guard.record_registration(ip, r["uid"])
    except Exception as e:
        print("registration guard error:", e)

    # Линкуем visitor_id к uid
    if visitor_id:
        try:
            await ip_tracking.link_visitor_to_uid(visitor_id, r["uid"])
        except Exception as e:
            print("link visitor error:", e)

    # Пишем заход
    try:
        await ip_tracking.track_visit(
            ip=ip,
            user_agent=request.headers.get("user-agent", ""),
            uid=r["uid"],
            page="/auth",
            action="register",
            visitor_id=visitor_id,
        )
    except Exception as e:
        print("ip track error:", e)

    return r


@router.post("/api/auth/login")
async def login(payload: LoginPayload, request: Request):
    ip = _client_ip(request)
    visitor_id = (payload.visitor_id or "").strip()[:64]

    r = await users.login(payload.uid, payload.pin, ip=ip)
    if not r["ok"]:
        raise HTTPException(status_code=401, detail=r["error"])

    # Линкуем visitor_id к uid
    if visitor_id:
        try:
            await ip_tracking.link_visitor_to_uid(visitor_id, r["uid"])
        except Exception as e:
            print("link visitor error:", e)

    try:
        await ip_tracking.track_visit(
            ip=ip,
            user_agent=request.headers.get("user-agent", ""),
            uid=r["uid"],
            page="/auth",
            action="login",
            visitor_id=visitor_id,
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

    rank = users.get_account_rank(
        user.get("total_score", 0),
        user.get("games_played", 0),
    )

    return {"ok": True, "user": {**user, "rank": rank}}


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
    Публичный трекинг захода.
    Принимает JSON {page, visitor_id, source}.
    """
    page = ""
    visitor_id = ""
    source = ""
    try:
        body = await request.json()
        page = (body or {}).get("page", "")
        visitor_id = (body or {}).get("visitor_id", "")
        source = (body or {}).get("source", "")
    except Exception:
        pass

    try:
        await ip_tracking.track_visit(
            ip=_client_ip(request),
            user_agent=request.headers.get("user-agent", ""),
            uid="",
            page=page,
            action="visit",
            visitor_id=visitor_id,
            source=source,
        )
    except Exception as e:
        print("public visit error:", e)
    return {"ok": True}
