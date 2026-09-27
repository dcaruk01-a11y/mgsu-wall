"""
Дуэльный режим кликера. Два игрока кликают одновременно.
Комнаты в памяти, живут 15 минут. С кешем юзеров — чтобы не душить Turso.
"""
import time, secrets
from fastapi import APIRouter, Header, HTTPException, Body
import core.users as users

router = APIRouter()

rooms = {}
ROOM_TTL = 15 * 60
WAITING_TTL = 120

# ═══ КЕШ ЮЗЕРОВ ═══
# Чтобы не обращаться к Turso на каждый poll
_user_cache = {}       # token -> {"uid":..., "nick":..., "ts":...}
_USER_CACHE_TTL = 60   # 60 секунд

async def get_cached_user(token: str):
    if not token:
        return None
    now = time.time()
    cached = _user_cache.get(token)
    if cached and now - cached["ts"] < _USER_CACHE_TTL:
        return {"uid": cached["uid"], "display_name": cached["nick"]}
    user = await users.get_user_by_token(token)
    if user:
        _user_cache[token] = {"uid": user["uid"], "nick": user["display_name"], "ts": now}
        # Иногда чистим кеш
        if len(_user_cache) > 500:
            cutoff = now - _USER_CACHE_TTL
            for k in list(_user_cache.keys()):
                if _user_cache[k]["ts"] < cutoff:
                    del _user_cache[k]
    return user


def cleanup():
    now = time.time()
    for code in list(rooms.keys()):
        room = rooms[code]
        if (not room.get("guest")
            and room["status"] == "waiting"
            and now - room["created_at"] > WAITING_TTL):
            del rooms[code]
            continue
        if now - room["created_at"] > ROOM_TTL:
            del rooms[code]


def gen_code():
    alphabet = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
    for _ in range(50):
        code = "".join(secrets.choice(alphabet) for _ in range(4))
        if code not in rooms:
            return code
    return "AAAA"


def _token(authorization: str) -> str:
    return authorization.replace("Bearer ", "").strip()


def _pub_room(room):
    return {
        "code": room["code"],
        "host": {"nick": room["host"]["nick"], "score": room["host"]["score"]},
        "guest": {"nick": room["guest"]["nick"], "score": room["guest"]["score"]} if room["guest"] else None,
        "status": room["status"],
        "start_at": room["start_at"],
        "is_public": room.get("is_public", False),
    }


@router.post("/api/duel/create")
async def duel_create(payload: dict = Body(default={}), authorization: str = Header(default="")):
    cleanup()
    user = await get_cached_user(_token(authorization))
    if not user:
        raise HTTPException(status_code=401, detail="Войди в аккаунт")

    is_public = bool(payload.get("is_public", False))
    code = gen_code()
    rooms[code] = {
        "code": code,
        "host": {"uid": user["uid"], "nick": user["display_name"], "score": None},
        "guest": None,
        "status": "waiting",
        "created_at": time.time(),
        "start_at": None,
        "is_public": is_public,
    }
    return {"ok": True, "code": code, "role": "host"}


@router.get("/api/duel/list")
async def duel_list():
    cleanup()
    now = time.time()
    open_rooms = []
    for code, room in rooms.items():
        if not room.get("is_public"): continue
        if room["status"] != "waiting": continue
        if room["guest"]: continue
        open_rooms.append({
            "code": code,
            "host_nick": room["host"]["nick"],
            "created_at": room["created_at"],
        })
    open_rooms.sort(key=lambda r: r["created_at"], reverse=True)
    return {"ok": True, "rooms": open_rooms[:12]}


@router.post("/api/duel/join")
async def duel_join(payload: dict = Body(...), authorization: str = Header(default="")):
    cleanup()
    user = await get_cached_user(_token(authorization))
    if not user:
        raise HTTPException(status_code=401, detail="Войди в аккаунт")

    code = str(payload.get("code", "")).strip().upper()
    room = rooms.get(code)
    if not room: raise HTTPException(status_code=404, detail="Комната не найдена")
    if room["host"]["uid"] == user["uid"]: raise HTTPException(status_code=400, detail="Ты уже в этой комнате")
    if room["guest"] and room["guest"]["uid"] != user["uid"]: raise HTTPException(status_code=400, detail="Комната занята")
    if room["status"] != "waiting" and not room["guest"]: raise HTTPException(status_code=400, detail="Игра началась")

    room["guest"] = {"uid": user["uid"], "nick": user["display_name"], "score": None}
    room["status"] = "ready"
    return {"ok": True, "code": code, "role": "guest"}


@router.get("/api/duel/status")
async def duel_status(code: str, authorization: str = Header(default="")):
    cleanup()
    code = code.strip().upper()
    room = rooms.get(code)
    if not room: raise HTTPException(status_code=404, detail="Комната закрыта")

    user = await get_cached_user(_token(authorization))
    if not user: raise HTTPException(status_code=401, detail="Не авторизован")

    role = None
    if room["host"]["uid"] == user["uid"]: role = "host"
    elif room["guest"] and room["guest"]["uid"] == user["uid"]: role = "guest"
    if role is None: raise HTTPException(status_code=403, detail="Ты не участник")

    return {"ok": True, "room": _pub_room(room), "role": role}


@router.post("/api/duel/progress")
async def duel_progress(payload: dict = Body(...), authorization: str = Header(default="")):
    # Здесь НЕ проверяем юзера через Turso — используем кеш
    code = str(payload.get("code", "")).strip().upper()
    score = max(0, min(int(payload.get("score", 0)), 100000))
    room = rooms.get(code)
    if not room:
        raise HTTPException(status_code=404, detail="Комната закрыта")

    user = await get_cached_user(_token(authorization))
    if not user: raise HTTPException(status_code=401, detail="Не авторизован")

    if room["host"]["uid"] == user["uid"]:
        room["host"]["score"] = score
    elif room["guest"] and room["guest"]["uid"] == user["uid"]:
        room["guest"]["score"] = score
    else:
        raise HTTPException(status_code=403, detail="Ты не участник")

    return {"ok": True}


@router.post("/api/duel/start")
async def duel_start(payload: dict = Body(...), authorization: str = Header(default="")):
    user = await get_cached_user(_token(authorization))
    if not user: raise HTTPException(status_code=401, detail="Не авторизован")

    code = str(payload.get("code", "")).strip().upper()
    room = rooms.get(code)
    if not room: raise HTTPException(status_code=404, detail="Комната закрыта")
    if room["host"]["uid"] != user["uid"]: raise HTTPException(status_code=403, detail="Только хост может начать")
    if not room["guest"]: raise HTTPException(status_code=400, detail="Ждём соперника")

    room["host"]["score"] = None
    room["guest"]["score"] = None
    room["status"] = "playing"
    room["start_at"] = time.time() + 3.5
    return {"ok": True}


@router.post("/api/duel/submit")
async def duel_submit(payload: dict = Body(...), authorization: str = Header(default="")):
    user = await get_cached_user(_token(authorization))
    if not user: raise HTTPException(status_code=401, detail="Не авторизован")

    code = str(payload.get("code", "")).strip().upper()
    score = max(0, min(int(payload.get("score", 0)), 100000))
    room = rooms.get(code)
    if not room: raise HTTPException(status_code=404, detail="Комната закрыта")

    if room["host"]["uid"] == user["uid"]:
        room["host"]["score"] = score
    elif room["guest"] and room["guest"]["uid"] == user["uid"]:
        room["guest"]["score"] = score
    else:
        raise HTTPException(status_code=403, detail="Ты не участник")

    if (room["host"]["score"] is not None
        and room["guest"]
        and room["guest"]["score"] is not None):
        room["status"] = "finished"

    return {"ok": True, "room": _pub_room(room)}


@router.post("/api/duel/leave")
async def duel_leave(payload: dict = Body(...), authorization: str = Header(default="")):
    user = await get_cached_user(_token(authorization))
    if not user: raise HTTPException(status_code=401, detail="Не авторизован")

    code = str(payload.get("code", "")).strip().upper()
    room = rooms.get(code)
    if not room: return {"ok": True}

    if room["host"]["uid"] == user["uid"]:
        del rooms[code]
    elif room["guest"] and room["guest"]["uid"] == user["uid"]:
        room["guest"] = None
        room["status"] = "waiting"

    return {"ok": True}
