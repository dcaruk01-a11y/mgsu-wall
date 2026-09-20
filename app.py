import asyncio, json, time
from datetime import datetime, timedelta
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import aiosqlite
import httpx
from PIL import Image, ImageDraw

from config import (
    MSK, is_open, today_str,
    CANVAS_W, CANVAS_H, DB_PATH, SNAPSHOT_DIR,
    TG_BOT_TOKEN, TG_CHAT_ID,
)
from feedback_bot import feedback_bot_loop
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/assets", StaticFiles(directory="assets"), name="assets")

# ============ БАЗА ДАННЫХ ============
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
        await db.execute(
            "INSERT INTO strokes(day,x0,y0,x1,y1,color,width,ts) VALUES (?,?,?,?,?,?,?,?)",
            (today_str(), s["x0"], s["y0"], s["x1"], s["y1"], s["color"], s["width"], s["ts"])
        )
        await db.commit()

async def load_today_strokes():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT x0,y0,x1,y1,color,width,ts FROM strokes WHERE day=? ORDER BY id",
            (today_str(),)
        )
        rows = await cur.fetchall()
    return [dict(zip(["x0","y0","x1","y1","color","width","ts"], r)) for r in rows]

async def clear_today():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM strokes WHERE day=?", (today_str(),))
        await db.commit()

# ============ WEBSOCKET ХАБ ============
class Hub:
    def __init__(self):
        self.clients = set()
    async def connect(self, ws):
        await ws.accept()
        self.clients.add(ws)
        for s in await load_today_strokes():
            await ws.send_text(json.dumps({"type": "stroke", **s}))
    def disconnect(self, ws):
        self.clients.discard(ws)
    async def broadcast(self, msg):
        data = json.dumps(msg)
        dead = []
        for c in list(self.clients):
            try:
                await c.send_text(data)
            except Exception:
                dead.append(c)
        for d in dead:
            self.disconnect(d)

hub = Hub()

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await hub.connect(ws)
    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except Exception:
                continue
            if msg.get("type") != "stroke":
                continue
            if not is_open():
                continue
            stroke = {
                "x0": float(msg["x0"]), "y0": float(msg["y0"]),
                "x1": float(msg["x1"]), "y1": float(msg["y1"]),
                "color": str(msg.get("color", "#ffffff"))[:9],
                "width": max(1, min(40, int(msg.get("width", 4)))),
                "ts": time.time(),
            }
            await save_stroke(stroke)
            await hub.broadcast({"type": "stroke", **stroke})
    except WebSocketDisconnect:
        hub.disconnect(ws)
    except Exception:
        hub.disconnect(ws)

# ============ СНИМОК И TELEGRAM ============
async def make_snapshot():
    img = Image.new("RGB", (CANVAS_W, CANVAS_H), (10, 10, 14))
    d = ImageDraw.Draw(img)
    for s in await load_today_strokes():
        d.line([s["x0"], s["y0"], s["x1"], s["y1"]],
               fill=s["color"], width=s["width"])
    import os
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

# ============ ЕЖЕДНЕВНЫЙ ЦИКЛ ============
async def daily_loop():
    while True:
        now = datetime.now(MSK)
        target = now.replace(hour=17, minute=0, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        wait = (target - now).total_seconds()
        print(f"До снимка: {wait/3600:.1f} ч")
        await asyncio.sleep(wait)
        try:
            strokes = await load_today_strokes()
            if not strokes:
                print("Холст пустой — снимок не делаем")
                continue
            print("Снимок дня...")
            path = await make_snapshot()
            await post_to_telegram(path)
            await clear_today()
            await hub.broadcast({"type": "reset"})
            print("Готово!")
        except Exception as e:
            print("Ошибка:", e)

@app.on_event("startup")
async def on_startup():
    await db_init()
    asyncio.create_task(daily_loop())
    asyncio.create_task(feedback_bot_loop())    

# ============ СТРАНИЦЫ (HTML-файлы) ============
@app.get("/")
async def index():
    return FileResponse("pages/wall.html")

@app.get("/games")
async def games():
    return FileResponse("pages/games.html")

@app.get("/kiosk")
@app.get("/privacy")
async def privacy():
    return FileResponse("pages/privacy.html")

async def kiosk():
    return FileResponse("pages/kiosk.html")

# ============ API ============
@app.get("/status")
async def status_endpoint():
    now = datetime.now(MSK)
    return {
        "open": is_open(),
        "opens_at": 8,
        "closes_at": 17,
        "current_hour_msk": now.hour,
    }

@app.get("/snapshot")
async def manual_snapshot():
    path = await make_snapshot()
    await post_to_telegram(path)
    return {"ok": True, "path": path}
