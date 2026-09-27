"""
Дуэльный режим кликера. Игрок сам придумывает код комнаты.
Комнаты в памяти, живут 15 минут.
"""
import time, secrets, re
from fastapi import APIRouter, Header, HTTPException, Body
import core.users as users

router = APIRouter()

rooms = {}
ROOM_TTL = 15 * 60
WAITING_TTL = 180    # пустая комната живёт 3 мин

# Кеш юзеров — чтобы не душить Turso
_user_cache = {}
_USER_CACHE_TTL = 60


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


def normalize_code(raw: str) -> str:
    """Убирает всё лишнее, оставляет 4 символа A-Z0-9."""
    if not raw:
        return ""
    code = re.sub(r'[^A-Za-z0-9]', '', str(raw)).upper()
    return code[:4]


def _token(authorization: str) -> str:
    return authorization.replace("Bearer ", "").strip()


def _pub_room(room):
    return {
        "code": room["code"],
        "host": {"nick": room["host"]["nick"], "score": room["host"]["score"]},
        "guest": {"nick": room["guest"]["nick"], "score": room["guest"]["score"]} if room["guest"] else None,
        "status": room["status"],
        "start_at": room["start_at"],
    }


@router.post("/api/duel/create")
async def duel_create(payload: dict = Body(default={}), authorization: str = Header(default="")):
    """
    Создать комнату. Игрок сам вводит код (4 символа A-Z0-9).
    Если код не задан — сгенерируем случайный.
    """
    cleanup()
    user = await get_cached_user(_token(authorization))
    if not user:
        raise HTTPException(status_code=401, detail="Войди в аккаунт")

    raw_code = payload.get("code", "")
    code = normalize_code(raw_code)

    # Если игрок ничего не ввёл — генерируем
    if not code:
        alphabet = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
        for _ in range(50):
            candidate = "".join(secrets.choice(alphabet) for _ in range(4))
            if candidate not in rooms:
                code = candidate
                break

    if len(code) != 4:
        raise HTTPException(status_code=400, detail="Код — ровно 4 символа (A-Z, 0-9)")

    if code in rooms:
        raise HTTPException(status_code=400, detail="Такой код уже занят — придумай другой")

    rooms[code] = {
        "code": code,
        "host": {"uid": user["uid"], "nick": user["display_name"], "score": None},
        "guest": None,
        "status": "waiting",
        "created_at": time.time(),
        "start_at": None,
    }
    return {"ok": True, "code": code, "role": "host"}


@router.post("/api/duel/check-code")
async def duel_check_code(payload: dict = Body(...)):
    """Проверить свободен ли код."""
    code = normalize_code(payload.get("code", ""))
    if len(code) != 4:
        return {"ok": False, "reason": "Код должен быть 4 символа"}
    if code in rooms:
        return {"ok": False, "reason": "Код уже занят"}
    return {"ok": True, "code": code}


@router.post("/api/duel/join")
async def duel_join(payload: dict = Body(...), authorization: str = Header(default="")):
    cleanup()
    user = await get_cached_user(_token(authorization))
    if not user:
        raise HTTPException(status_code=401, detail="Войди в аккаунт")

    code = normalize_code(payload.get("code", ""))
    if len(code) != 4:
        raise HTTPException(status_code=400, detail="Код — 4 символа")

    room = rooms.get(code)
    if not room:
        raise HTTPException(status_code=404, detail="Комната не найдена — проверь код")
    if room["host"]["uid"] == user["uid"]:
        raise HTTPException(status_code=400, detail="Ты уже в этой комнате")
    if room["guest"] and room["guest"]["uid"] != user["uid"]:
        raise HTTPException(status_code=400, detail="Комната занята")
    if room["status"] != "waiting" and not room["guest"]:
        raise HTTPException(status_code=400, detail="Игра уже началась")

    room["guest"] = {"uid": user["uid"], "nick": user["display_name"], "score": None}
    room["status"] = "ready"
    return {"ok": True, "code": code, "role": "guest"}


@router.get("/api/duel/status")
async def duel_status(code: str, authorization: str = Header(default="")):
    cleanup()
    code = normalize_code(code)
    room = rooms.get(code)
    if not room:
        raise HTTPException(status_code=404, detail="Комната закрыта")

    user = await get_cached_user(_token(authorization))
    if not user:
        raise HTTPException(status_code=401, detail="Не авторизован")

    role = None
    if room["host"]["uid"] == user["uid"]:
        role = "host"
    elif room["guest"] and room["guest"]["uid"] == user["uid"]:
        role = "guest"
    if role is None:
        raise HTTPException(status_code=403, detail="Ты не участник")

    return {"ok": True, "room": _pub_room(room), "role": role}


@router.post("/api/duel/progress")
async def duel_progress(payload: dict = Body(...), authorization: str = Header(default="")):
    code = normalize_code(payload.get("code", ""))
    score = max(0, min(int(payload.get("score", 0)), 100000))
    room = rooms.get(code)
    if not room:
        raise HTTPException(status_code=404, detail="Комната закрыта")

    user = await get_cached_user(_token(authorization))
    if not user:
        raise HTTPException(status_code=401, detail="Не авторизован")

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
    if not user:
        raise HTTPException(status_code=401, detail="Не авторизован")

    code = normalize_code(payload.get("code", ""))
    room = rooms.get(code)
    if not room:
        raise HTTPException(status_code=404, detail="Комната закрыта")
    if room["host"]["uid"] != user["uid"]:
        raise HTTPException(status_code=403, detail="Только хост может начать")
    if not room["guest"]:
        raise HTTPException(status_code=400, detail="Ждём соперника")

    room["host"]["score"] = None
    room["guest"]["score"] = None
    room["status"] = "playing"
    room["start_at"] = time.time() + 3.5
    return {"ok": True}


@router.post("/api/duel/submit")
async def duel_submit(payload: dict = Body(...), authorization: str = Header(default="")):
    user = await get_cached_user(_token(authorization))
    if not user:
        raise HTTPException(status_code=401, detail="Не авторизован")

    code = normalize_code(payload.get("code", ""))
    score = max(0, min(int(payload.get("score", 0)), 100000))
    room = rooms.get(code)
    if not room:
        raise HTTPException(status_code=404, detail="Комната закрыта")

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
    if not user:
        raise HTTPException(status_code=401, detail="Не авторизован")

    code = normalize_code(payload.get("code", ""))
    room = rooms.get(code)
    if not room:
        return {"ok": True}

    if room["host"]["uid"] == user["uid"]:
        del rooms[code]
    elif room["guest"] and room["guest"]["uid"] == user["uid"]:
        room["guest"] = None
        room["status"] = "waiting"

    return {"ok": True}
