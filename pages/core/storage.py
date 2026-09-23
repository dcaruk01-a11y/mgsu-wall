import os
import aiosqlite
import httpx
from PIL import Image, ImageDraw
from config import (
    DB_PATH, SNAPSHOT_DIR, CANVAS_W, CANVAS_H,
    TG_BOT_TOKEN, TG_CHAT_ID, today_str,
)


async def db_init():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS strokes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                day TEXT, x0 REAL, y0 REAL, x1 REAL, y1 REAL,
                color TEXT, width INTEGER, ts REAL
            )
        """)
        await db.commit()


async def save_stroke(s):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO strokes(day,x0,y0,x1,y1,color,width,ts) VALUES (?,?,?,?,?,?,?,?)",
            (today_str(), s["x0"], s["y0"], s["x1"], s["y1"], s["color"], s["width"], s["ts"])
        )
        await db.commit()
        return cur.lastrowid


async def delete_stroke(stroke_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM strokes WHERE id=?", (stroke_id,))
        await db.commit()


async def load_today_strokes():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT id,x0,y0,x1,y1,color,width,ts FROM strokes WHERE day=? ORDER BY id",
            (today_str(),)
        )
        rows = await cur.fetchall()
    return [dict(zip(["id","x0","y0","x1","y1","color","width","ts"], r)) for r in rows]


async def clear_today():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM strokes WHERE day=?", (today_str(),))
        await db.commit()


async def make_snapshot():
    img = Image.new("RGB", (CANVAS_W, CANVAS_H), (10, 10, 14))
    d = ImageDraw.Draw(img)
    for s in await load_today_strokes():
        d.line([s["x0"], s["y0"], s["x1"], s["y1"]], fill=s["color"], width=s["width"])
    path = os.path.join(SNAPSHOT_DIR, f"{today_str()}.png")
    img.save(path)
    return path


async def post_to_telegram(path):
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        print("Telegram не настроен")
        return
    caption = f"Стена МГСУ — {today_str()}"
    try:
        async with httpx.AsyncClient(timeout=60) as c:
            with open(path, "rb") as f:
                r = await c.post(
                    f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendPhoto",
                    data={"chat_id": TG_CHAT_ID, "caption": caption},
                    files={"photo": f},
                )
                print("Telegram:", r.status_code)
    except Exception as e:
        print("Ошибка Telegram:", e)
