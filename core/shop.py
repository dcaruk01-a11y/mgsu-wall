"""
Магазин персонажей. Все покупки списывают монеты с аккаунта.
"""
import json, aiosqlite
from fastapi import APIRouter, Header, HTTPException
from config import DB_PATH
import core.users as users

router = APIRouter()


CATALOG = [
    {"key": "student", "name": "Студент",       "emoji": "🎓", "price": 0,     "desc": "Обычный студент МГСУ. Начало пути."},
    {"key": "sso",     "name": "ССОшник",        "emoji": "👷", "price": 800,   "desc": "Стройотрядовская куртка и боевой дух."},
    {"key": "prorab",  "name": "Прораб",         "emoji": "📋", "price": 2500,  "desc": "Уже управляет стройкой."},
    {"key": "builder", "name": "Строитель",      "emoji": "🏗️", "price": 6000,  "desc": "Руки в деле, каска на месте."},
    {"key": "prof",    "name": "Преподаватель",  "emoji": "🧑‍🏫", "price": 12000, "desc": "Ставит зачёты и раздаёт мудрость."},
    {"key": "dean",    "name": "Декан",          "emoji": "🧑‍💼", "price": 25000, "desc": "Костюм, папка, полномочия."},
    {"key": "legend",  "name": "Легенда МГСУ",   "emoji": "👑", "price": 60000, "desc": "Ты в истории университета."},
]


def _token(authorization: str) -> str:
    return authorization.replace("Bearer ", "").strip()


def get_catalog_item(key: str):
    for c in CATALOG:
        if c["key"] == key:
            return c
    return None


@router.get("/api/shop/catalog")
async def shop_catalog(authorization: str = Header(default="")):
    user = await users.get_user_by_token(_token(authorization))
    owned = user.get("owned_chars", ["student"]) if user else []
    active = user.get("active_char", "student") if user else None
    coins = user.get("coins", 0) if user else 0

    items = []
    for c in CATALOG:
        items.append({
            **c,
            "owned": c["key"] in owned or c["key"] == "student",
            "active": c["key"] == active,
            "can_afford": coins >= c["price"],
        })

    return {"ok": True, "logged_in": bool(user), "coins": coins, "items": items}


@router.post("/api/shop/buy")
async def shop_buy(payload: dict, authorization: str = Header(default="")):
    user = await users.get_user_by_token(_token(authorization))
    if not user:
        raise HTTPException(status_code=401, detail="Не авторизован")

    key = str(payload.get("key", ""))
    item = get_catalog_item(key)
    if not item:
        raise HTTPException(status_code=400, detail="Такого персонажа нет")
    if key == "student":
        raise HTTPException(status_code=400, detail="Студент и так твой")
    # The balance and inventory must be checked in the same statement that
    # debits the account. The user object above may be cached or out of date.
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            UPDATE users
            SET coins = coins - ?,
                owned_chars = json_insert(
                    COALESCE(owned_chars, '["student"]'), '$[#]', ?
                ),
                active_char = ?
            WHERE uid = ? AND coins >= ?
              AND NOT EXISTS (
                  SELECT 1 FROM json_each(COALESCE(owned_chars, '["student"]'))
                  WHERE value = ?
              )
            RETURNING coins, owned_chars
        """, (item["price"], key, key, user["uid"], item["price"], key))
        bought = await cur.fetchone()
        await db.commit()

        if not bought:
            cur = await db.execute("SELECT coins, owned_chars FROM users WHERE uid = ?", (user["uid"],))
            current = await cur.fetchone()
            if not current:
                raise HTTPException(status_code=401, detail="Не авторизован")
            if key in json.loads(current[1] or '["student"]'):
                raise HTTPException(status_code=400, detail="Уже куплен")
            if current[0] < item["price"]:
                raise HTTPException(status_code=400, detail=f"Не хватает {item['price'] - current[0]} монет")
            raise HTTPException(status_code=409, detail="Не удалось завершить покупку, попробуйте ещё раз")

    users.invalidate_user_cache(user["uid"])
    return {"ok": True, "coins": bought[0], "active_char": key, "owned": json.loads(bought[1])}


@router.post("/api/shop/equip")
async def shop_equip(payload: dict, authorization: str = Header(default="")):
    user = await users.get_user_by_token(_token(authorization))
    if not user:
        raise HTTPException(status_code=401, detail="Не авторизован")

    key = str(payload.get("key", ""))
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            UPDATE users SET active_char = ?
            WHERE uid = ? AND EXISTS (
                SELECT 1 FROM json_each(COALESCE(owned_chars, '["student"]'))
                WHERE value = ?
            )
            RETURNING active_char
        """, (key, user["uid"], key))
        equipped = await cur.fetchone()
        await db.commit()

    if not equipped:
        raise HTTPException(status_code=400, detail="Персонаж не куплен")

    users.invalidate_user_cache(user["uid"])
    return {"ok": True, "active_char": key}

