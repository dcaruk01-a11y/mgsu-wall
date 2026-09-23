import time
from config import today_str

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


games_config = {
    "wall":     {"enabled": True, "title": "Стена",         "url": "/games/wall",     "status": "available"},
    "clicker":  {"enabled": True, "title": "Кликер",        "url": "/games/clicker",  "status": "available"},
    "broadway": {"enabled": True, "title": "Бродвей",       "url": "",                "status": "soon"},
    "campus":   {"enabled": True, "title": "Построй кампус","url": "",                "status": "soon"},
    "grable":   {"enabled": True, "title": "Грабли",        "url": "",                "status": "soon"},
    "snake":    {"enabled": False, "title": "Змейка",       "url": "",                "status": "soon"},
    "poll":     {"enabled": False, "title": "Опрос дня",    "url": "",                "status": "soon"},
    "click":    {"enabled": False, "title": "Гонка кликов", "url": "",                "status": "soon"},
}

theme_config = {"current": "classic"}

admin_tokens: dict = {}
TOKEN_TTL = 60 * 60 * 24 * 7

clicker_top: list = []
clicker_day: str = ""
CLICKER_MAX_TOP = 5

def clicker_reset_if_needed():
    global clicker_day, clicker_top
    today = today_str()
    if clicker_day != today:
        clicker_day = today
        clicker_top = []

def sanitize_nick(nick: str) -> str:
    nick = (nick or "").strip()
    nick = "".join(c for c in nick if c.isalnum() or c in " _-")
    nick = nick[:20].strip()
    return nick or "Аноним"
