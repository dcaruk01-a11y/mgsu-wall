"""
Магазин персонажей. Все покупки списывают монеты с аккаунта.
Каталог в памяти — легко расширить.
"""
import json, aiosqlite
from fastapi import APIRouter, Header, HTTPException
from config import DB_PATH
import core.users as users

router = APIRouter()


CATALOG = [
    {"key": "student", "name": "Студент",       "emoji": "🎓", "price": 0,     "desc": "Обычный студент МГСУ. Начало пути."},
    {"key": "sso",     "name": "ССОшник",        "emoji": "👷", "price": 500,   "desc": "Стройотрядовская куртка и боевой дух."},
    {"key": "prorab",  "name": "Прораб",         "emoji": "📋", "price": 1500,  "desc": "Уже управляет стройкой."},
    {"key": "builder", "name": "Строитель",      "emoji": "🏗️", "price": 3000,  "desc": "Руки в деле, каска на месте."},
    {"key": "prof",    "name": "Преподаватель",  "emoji": "🧑‍🏫", "price": 5000,  "desc": "Ставит зачёты и раздаёт мудрость."},
    {"key": "dean",    "name": "Декан",          "emoji": "🧑‍💼", "price": 10000, "desc": "Костюм, папка, полномочия."},
    {"key": "legend",  "name": "Легенда МГСУ",   "emoji": "👑", "price": 20000, "desc": "Ты в истории университета."},
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
    if key in user.get("owned_chars", []):
        raise HTTPException(status_code=400, detail="Уже куплен")
    if user["coins"] < item["price"]:
        raise HTTPException(status_code=400, detail="Недостаточно монет")

    new_owned = list(user.get("owned_chars", ["student"]))
    new_owned.append(key)

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE users
            SET coins = coins - ?,
                owned_chars = ?,
                active_char = ?
            WHERE uid = ?
        """, (item["price"], json.dumps(new_owned), key, user["uid"]))
        await db.commit()

    return {"ok": True, "coins": user["coins"] - item["price"], "active_char": key, "owned": new_owned}


@router.post("/api/shop/equip")
async def shop_equip(payload: dict, authorization: str = Header(default="")):
    user = await users.get_user_by_token(_token(authorization))
    if not user:
        raise HTTPException(status_code=401, detail="Не авторизован")

    key = str(payload.get("key", ""))
    if key not in user.get("owned_chars", []):
        raise HTTPException(status_code=400, detail="Персонаж не куплен")

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET active_char = ? WHERE uid = ?", (key, user["uid"]))
        await db.commit()

    return {"ok": True, "active_char": key}
