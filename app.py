import asyncio, json, time, secrets, os
from datetime import datetime, timedelta
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import aiosqlite
import httpx
from PIL import Image, ImageDraw
import psutil

from config import (
    MSK, is_open, today_str,
    CANVAS_W, CANVAS_H, DB_PATH, SNAPSHOT_DIR,
    TG_BOT_TOKEN, TG_CHAT_ID, ADMIN_PASSWORD,
)
from feedback_bot import feedback_bot_loop

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/assets", StaticFiles(directory="assets"), name="assets")


# ============ СТАТИСТИКА (в памяти) ============
stats = {
    "visits_today": 0,
    "uniques_today": set(),
    "games_played": {"wall": 0, "clicker": 0, "snake": 0, "poll": 0, "click": 0},
    "started_at": time.time(),
    "day": today_str(),
}

def stats_reset_if_needed():
    today = today_str()
    if stats["day"] != today:
        stats["day"] = today
        stats["visits_today"] = 0
        stats["uniques_today"] = set()
        stats["games_played"] = {"wall": 0, "clicker": 0, "snake": 0, "poll": 0, "click": 0}

def track_visit(uid: str = ""):
    stats_reset_if_needed()
    stats["visits_today"] += 1
    if uid and len(uid) < 64:
        stats["uniques_today"].add(uid)

def track_game(name: str):
    stats_reset_if_needed()
    if name in stats["games_played"]:
        stats["games_played"][name] += 1


# ============ УПРАВЛЕНИЕ ИГРАМИ (в памяти) ============
games_config = {
    "wall":    {"enabled": True,  "title": "Стена"},
    "clicker": {"enabled": True,  "title": "Кликер"},
    "snake":   {"enabled": False, "title": "Змейка"},
    "poll":    {"enabled": False, "title": "Опрос дня"},
    "click":   {"enabled": False, "title": "Гонка кликов"},
}

theme_config = {"current": "classic"}


# ============ АДМИН-СЕССИИ ============
admin_tokens: dict = {}  # token -> expiry_ts
TOKEN_TTL = 60 * 60 * 24 * 7  # 7 дней

def check_admin(token: str) -> bool:
    if not token or not ADMIN_PASSWORD:
        return False
    exp = admin_tokens.get(token)
    if not exp or exp < time.time():
        admin_tokens.pop(token, None)
        return False
    return True

def require_admin(authorization: str = Header(default="")):
    token = authorization.replace("Bearer ", "").strip()
    if not check_admin(token):
        raise HTTPException(status_code=401, detail="Unauthorized")
    return token


# ============ БАЗА ДАННЫХ (штрихи стены) ============
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


# ============ КЛИКЕР: ТОП В ПАМЯТИ ============
clicker_top: list = []
clicker_day: str = ""
clicker_lock = asyncio.Lock()
CLICKER_MAX_TOP = 5

class ClickerScore(BaseModel):
    nick: str = ""
    score: int = 0
    rank: str = ""

def _clicker_reset_if_needed():
    global clicker_day, clicker_top
    today = today_str()
    if clicker_day != today:
        clicker_day = today
        clicker_top = []

def _sanitize_nick(nick: str) -> str:
    nick = (nick or "").strip()
    nick = "".join(c for c in nick if c.isalnum() or c in " _-")
    nick = nick[:20].strip()
    return nick or "Аноним"

@app.post("/clicker/score")
async def clicker_score(payload: ClickerScore):
    _clicker_reset_if_needed()
    track_game("clicker")
    nick = _sanitize_nick(payload.nick)
    score = max(0, min(int(payload.score or 0), 10000))
    rank = (payload.rank or "")[:30]
    entry = {"nick": nick, "score": score, "rank": rank, "ts": time.time()}
    async with clicker_lock:
        clicker_top.append(entry)
        clicker_top.sort(key=lambda x: x["score"], reverse=True)
        del clicker_top[CLICKER_MAX_TOP:]
        pos = next((i for i, e in enumerate(clicker_top) if e["ts"] == entry["ts"]), -1)
    return {
        "ok": True,
        "position": pos + 1 if pos >= 0 else None,
        "top": [{"nick": e["nick"], "score": e["score"], "rank": e["rank"]} for e in clicker_top],
    }

@app.get("/clicker/top")
async def clicker_top_get():
    _clicker_reset_if_needed()
    return {"top": [{"nick": e["nick"], "score": e["score"], "rank": e["rank"]} for e in clicker_top]}


# ============ WEBSOCKET ============
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
connection_strokes: dict = {}

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await hub.connect(ws)
    connection_strokes[ws] = []
    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except Exception:
                continue
            t = msg.get("type")
            if t == "stroke":
                if not is_open():
                    continue
                stroke = {
                    "x0": float(msg["x0"]), "y0": float(msg["y0"]),
                    "x1": float(msg["x1"]), "y1": float(msg["y1"]),
                    "color": str(msg.get("color", "#ffffff"))[:9],
                    "width": max(1, min(40, int(msg.get("width", 4)))),
                    "ts": time.time(),
                }
                new_id = await save_stroke(stroke)
                connection_strokes[ws].append(new_id)
                await hub.broadcast({"type": "stroke", "id": new_id, **stroke})
            elif t == "undo":
                ids = connection_strokes.get(ws, [])
                if not ids:
                    continue
                last_id = ids.pop()
                await delete_stroke(last_id)
                await hub.broadcast({"type": "remove", "id": last_id})
    except WebSocketDisconnect:
        connection_strokes.pop(ws, None)
        hub.disconnect(ws)
    except Exception:
        connection_strokes.pop(ws, None)
        hub.disconnect(ws)


# ============ СНИМОК / TELEGRAM ============
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

async def daily_loop():
    while True:
        now = datetime.now(MSK)
        target = now.replace(hour=17, minute=0, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        wait = (target - now).total_seconds()
        print(f"До снимка: {wait / 3600:.1f} ч")
        await asyncio.sleep(wait)
        try:
            strokes = await load_today_strokes()
            if strokes:
                print("Снимок дня...")
                path = await make_snapshot()
                await post_to_telegram(path)
                await clear_today()
                await hub.broadcast({"type": "reset"})
                print("Готово!")
            else:
                print("Холст пустой — снимок не делаем")
            global clicker_top, clicker_day
            clicker_top = []
            clicker_day = ""
            print("Топ кликера сброшен")
        except Exception as e:
            print("Ошибка:", e)

@app.on_event("startup")
async def on_startup():
    await db_init()
    asyncio.create_task(daily_loop())
    asyncio.create_task(feedback_bot_loop())


# ============ ПУБЛИЧНЫЕ СТРАНИЦЫ ============
@app.get("/")
async def index():
    track_game("wall")
    return FileResponse("pages/wall.html")

@app.get("/games")
async def games():
    track_visit()
    return FileResponse("pages/games.html")

@app.get("/kiosk")
async def kiosk():
    return FileResponse("pages/kiosk.html")

@app.get("/privacy")
async def privacy():
    return FileResponse("pages/privacy.html")

@app.get("/clicker")
async def clicker():
    return FileResponse("pages/clicker.html")


# ============ PUBLIC API ============
@app.get("/status")
async def status_endpoint():
    now = datetime.now(MSK)
    return {
        "open": is_open(),
        "opens_at": 8,
        "closes_at": 17,
        "current_hour_msk": now.hour,
    }

@app.post("/api/track")
async def api_track(payload: dict):
    uid = str(payload.get("uid", ""))[:64]
    track_visit(uid)
    return {"ok": True}

@app.get("/api/games")
async def api_games():
    return {
        "games": [{"key": k, "title": v["title"], "enabled": v["enabled"]} for k, v in games_config.items()],
        "theme": theme_config["current"],
    }

@app.get("/snapshot")
async def manual_snapshot():
    path = await make_snapshot()
    await post_to_telegram(path)
    return {"ok": True, "path": path}


# ============ АДМИНКА ============
@app.get("/admin")
async def admin_page():
    return FileResponse("pages/admin.html")

@app.get("/admin/api/check")
async def admin_check():
    return {
        "admin_password_set": bool(ADMIN_PASSWORD),
        "length": len(ADMIN_PASSWORD) if ADMIN_PASSWORD else 0,
    }

@app.post("/admin/api/login")
async def admin_login(payload: dict):
    pw = str(payload.get("password", ""))
    if not ADMIN_PASSWORD or pw != ADMIN_PASSWORD:
        await asyncio.sleep(1)  # против брутфорса
        return {"ok": False, "error": "Неверный пароль"}
    token = secrets.token_urlsafe(32)
    admin_tokens[token] = time.time() + TOKEN_TTL
    return {"ok": True, "token": token}

@app.post("/admin/api/logout")
async def admin_logout(authorization: str = Header(default="")):
    token = authorization.replace("Bearer ", "").strip()
    admin_tokens.pop(token, None)
    return {"ok": True}

def _mem_mb():
    try:
        return round(psutil.Process().memory_info().rss / 1024 / 1024, 1)
    except Exception:
        return None

def _cpu_pct():
    try:
        return round(psutil.cpu_percent(interval=0.1), 1)
    except Exception:
        return None

@app.get("/admin/api/stats")
async def admin_stats(token: str = Header(default="", alias="authorization")):
    if not check_admin(token.replace("Bearer ", "").strip()):
        raise HTTPException(status_code=401, detail="Unauthorized")
    stats_reset_if_needed()
    uptime_sec = int(time.time() - stats["started_at"])
    return {
        "online": len(hub.clients),
        "visits_today": stats["visits_today"],
        "uniques_today": len(stats["uniques_today"]),
        "games_played": stats["games_played"],
        "memory_mb": _mem_mb(),
        "cpu_pct": _cpu_pct(),
        "uptime_sec": uptime_sec,
        "clicker_top": [
            {"nick": e["nick"], "score": e["score"], "rank": e["rank"]}
            for e in clicker_top
        ],
    }

@app.get("/admin/api/games")
async def admin_games_get(token: str = Header(default="", alias="authorization")):
    if not check_admin(token.replace("Bearer ", "").strip()):
        raise HTTPException(status_code=401, detail="Unauthorized")
    return {
        "games": [{"key": k, "title": v["title"], "enabled": v["enabled"]} for k, v in games_config.items()],
        "theme": theme_config["current"],
    }

@app.post("/admin/api/games")
async def admin_games_set(payload: dict, token: str = Header(default="", alias="authorization")):
    if not check_admin(token.replace("Bearer ", "").strip()):
        raise HTTPException(status_code=401, detail="Unauthorized")
    key = str(payload.get("key", ""))
    enabled = bool(payload.get("enabled", False))
    if key in games_config:
        games_config[key]["enabled"] = enabled
    return {"ok": True, "games": [{"key": k, "title": v["title"], "enabled": v["enabled"]} for k, v in games_config.items()]}

@app.post("/admin/api/theme")
async def admin_theme_set(payload: dict, token: str = Header(default="", alias="authorization")):
    if not check_admin(token.replace("Bearer ", "").strip()):
        raise HTTPException(status_code=401, detail="Unauthorized")
    theme = str(payload.get("theme", "classic"))
    if theme in ("classic", "cyberpunk"):
        theme_config["current"] = theme
    return {"ok": True, "theme": theme_config["current"]}
