"""
Дуэльный режим кликера. Два игрока кликают одновременно.
Комнаты хранятся в памяти, живут 15 минут.
"""
import time, secrets
from fastapi import APIRouter, Header, HTTPException
import core.users as users

router = APIRouter()

# code -> room
rooms = {}
ROOM_TTL = 15 * 60  # 15 минут


def cleanup():
    """Удаляет старые комнаты."""
    now = time.time()
    for code in list(rooms.keys()):
        if now - rooms[code]["created_at"] > ROOM_TTL:
            del rooms[code]


def gen_code():
    """4-символьный код без похожих букв/цифр (нет O/0, I/1)."""
    alphabet = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
    while True:
        code = "".join(secrets.choice(alphabet) for _ in range(4))
        if code not in rooms:
            return code


def _token(authorization: str) -> str:
    return authorization.replace("Bearer ", "").strip()


def _pub_room(room):
    """Публичное представление комнаты для клиента."""
    return {
        "code": room["code"],
        "host": {
            "nick": room["host"]["nick"],
            "score": room["host"]["score"],
        },
        "guest": {
            "nick": room["guest"]["nick"],
            "score": room["guest"]["score"],
        } if room["guest"] else None,
        "status": room["status"],
        "start_at": room["start_at"],
    }


@router.post("/api/duel/create")
async def duel_create(authorization: str = Header(default="")):
    cleanup()
    token = _token(authorization)
    user = await users.get_user_by_token(token) if token else None
    if not user:
        raise HTTPException(status_code=401, detail="Войди в аккаунт, чтобы играть в дуэли")

    code = gen_code()
    rooms[code] = {
        "code": code,
        "host": {"uid": user["uid"], "nick": user["display_name"], "score": None},
        "guest": None,
        "status": "waiting",
        "created_at": time.time(),
        "start_at": None,
    }
    return {"ok": True, "code": code, "role": "host"}


@router.post("/api/duel/join")
async def duel_join(payload: dict, authorization: str = Header(default="")):
    cleanup()
    token = _token(authorization)
    user = await users.get_user_by_token(token) if token else None
    if not user:
        raise HTTPException(status_code=401, detail="Войди в аккаунт, чтобы играть в дуэли")

    code = str(payload.get("code", "")).strip().upper()
    room = rooms.get(code)
    if not room:
        raise HTTPException(status_code=404, detail="Комната не найдена")
    if room["host"]["uid"] == user["uid"]:
        raise HTTPException(status_code=400, detail="Ты уже в этой комнате — как хост")
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
    code = code.strip().upper()
    room = rooms.get(code)
    if not room:
        raise HTTPException(status_code=404, detail="Комната не найдена")

    token = _token(authorization)
    user = await users.get_user_by_token(token) if token else None
    if not user:
        raise HTTPException(status_code=401, detail="Не авторизован")

    # Определяем роль
    role = None
    if room["host"]["uid"] == user["uid"]:
        role = "host"
    elif room["guest"] and room["guest"]["uid"] == user["uid"]:
        role = "guest"

    return {"ok": True, "room": _pub_room(room), "role": role}


@router.post("/api/duel/start")
async def duel_start(payload: dict, authorization: str = Header(default="")):
    token = _token(authorization)
    user = await users.get_user_by_token(token) if token else None
    if not user:
        raise HTTPException(status_code=401, detail="Не авторизован")

    code = str(payload.get("code", "")).strip().upper()
    room = rooms.get(code)
    if not room:
        raise HTTPException(status_code=404, detail="Комната не найдена")
    if room["host"]["uid"] != user["uid"]:
        raise HTTPException(status_code=403, detail="Только хост может начать")
    if not room["guest"]:
        raise HTTPException(status_code=400, detail="Ждём соперника")

    room["status"] = "playing"
    room["start_at"] = time.time() + 3.5   # 3.5 сек на отсчёт
    return {"ok": True}


@router.post("/api/duel/submit")
async def duel_submit(payload: dict, authorization: str = Header(default="")):
    token = _token(authorization)
    user = await users.get_user_by_token(token) if token else None
    if not user:
        raise HTTPException(status_code=401, detail="Не авторизован")

    code = str(payload.get("code", "")).strip().upper()
    score = max(0, min(int(payload.get("score", 0)), 100000))
    room = rooms.get(code)
    if not room:
        raise HTTPException(status_code=404, detail="Комната не найдена")

    if room["host"]["uid"] == user["uid"]:
        room["host"]["score"] = score
    elif room["guest"] and room["guest"]["uid"] == user["uid"]:
        room["guest"]["score"] = score
    else:
        raise HTTPException(status_code=403, detail="Ты не участник")

    # Оба сдали?
    if (room["host"]["score"] is not None
        and room["guest"]
        and room["guest"]["score"] is not None):
        room["status"] = "finished"

    return {"ok": True, "room": _pub_room(room)}
