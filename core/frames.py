"""
Рамки для аватарки. Покупаются за монеты, применяются к профилю.
"""
import time, json, aiosqlite
from config import DB_PATH


FRAMES = [
    {"key":"frame_blue",     "name":"Синяя рамка",     "emoji":"🔵", "price":500,    "color":"#3b82f6"},
    {"key":"frame_green",    "name":"Зелёная рамка",   "emoji":"🟢", "price":1000,   "color":"#22c55e"},
    {"key":"frame_purple",   "name":"Фиолетовая рамка","emoji":"🟣", "price":1500,   "color":"#a855f7"},
    {"key":"frame_gold",     "name":"Золотая рамка",   "emoji":"🟡", "price":3000,   "color":"#eab308"},
    {"key":"frame_red",      "name":"Красная рамка",   "emoji":"🔴", "price":5000,   "color":"#ef4444"},
    {"key":"frame_rainbow",  "name":"Радужная рамка",  "emoji":"🌈", "price":15000,  "color":"rainbow"},
]

FRAMES_MAP = {f["key"]: f for f in FRAMES}


def get_frame(key: str):
    return FRAMES_MAP.get(key)


def get_frame_color(key: str) -> str:
    f = FRAMES_MAP.get(key)
    return f["color"] if f else ""


async def db_init_frames():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_frames (
                uid TEXT,
                frame_key TEXT,
                bought_at REAL,
                PRIMARY KEY (uid, frame_key)
            )
        """)
        try:
            cur = await db.execute("PRAGMA table_info(users)")
            existing = {row[1] for row in await cur.fetchall()}
            if "active_frame" not in existing:
                await db.execute("ALTER TABLE users ADD COLUMN active_frame TEXT DEFAULT ''")
        except Exception:
            pass
        await db.commit()


async def get_user_frames(uid: str) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT frame_key, bought_at FROM user_frames WHERE uid=?",
            (uid,)
        )
        rows = await cur.fetchall()
    return [{"key": r[0], "bought_at": r[1]} for r in rows]


async def buy_frame(uid: str, frame_key: str, coins_available: int) -> dict:
    frame = get_frame(frame_key)
    if not frame:
        return {"ok": False, "error": "Такой рамки нет"}

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT 1 FROM user_frames WHERE uid=? AND frame_key=?",
            (uid, frame_key)
        )
        if await cur.fetchone():
            return {"ok": False, "error": "Уже куплена"}

        if coins_available < frame["price"]:
            return {"ok": False, "error": "Недостаточно монет"}

        await db.execute(
            "UPDATE users SET coins = coins - ? WHERE uid = ?",
            (frame["price"], uid)
        )
        await db.execute(
            "INSERT INTO user_frames (uid, frame_key, bought_at) VALUES (?,?,?)",
            (uid, frame_key, time.time())
        )
        await db.execute(
            "UPDATE users SET active_frame = ? WHERE uid = ?",
            (frame_key, uid)
        )
        await db.commit()

    return {"ok": True, "frame": frame_key, "active": frame_key}


async def equip_frame(uid: str, frame_key: str) -> dict:
    if frame_key == "":
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE users SET active_frame='' WHERE uid=?", (uid,))
            await db.commit()
        return {"ok": True, "active": ""}

    frame = get_frame(frame_key)
    if not frame:
        return {"ok": False, "error": "Такой рамки нет"}

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT 1 FROM user_frames WHERE uid=? AND frame_key=?",
            (uid, frame_key)
        )
        if not await cur.fetchone():
            return {"ok": False, "error": "Рамка не куплена"}

        await db.execute("UPDATE users SET active_frame=? WHERE uid=?", (frame_key, uid))
        await db.commit()

    return {"ok": True, "active": frame_key}
