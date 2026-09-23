import time
from datetime import datetime, timedelta
from datetime import timezone
from config import today_str, MSK


# ============ РАСПИСАНИЕ ДОСТУПА ============
schedule_config = {
    "open_hour": 8,
    "open_minute": 30,
    "close_hour": 17,
    "close_minute": 20,
    "force_override": None,  # None = по расписанию, True = всегда открыто, False = всегда закрыто
}


def is_open_now() -> bool:
    """Проверяет, доступны ли игры сейчас."""
    force = schedule_config.get("force_override")
    if force is True:
        return True
    if force is False:
        return False

    now = datetime.now(MSK)
    open_t = now.replace(
        hour=schedule_config["open_hour"],
        minute=schedule_config["open_minute"],
        second=0, microsecond=0,
    )
    close_t = now.replace(
        hour=schedule_config["close_hour"],
        minute=schedule_config["close_minute"],
        second=0, microsecond=0,
    )
    return open_t <= now < close_t


def schedule_str() -> dict:
    return {
        "open_hour": schedule_config["open_hour"],
        "open_minute": schedule_config["open_minute"],
        "close_hour": schedule_config["close_hour"],
        "close_minute": schedule_config["close_minute"],
        "force_override": schedule_config.get("force_override"),
    }


# ============ ИГРЫ ============
games_config = {
    "wall":     {"enabled": True,  "title": "Стена",          "url": "/games/wall",     "status": "available"},
    "clicker":  {"enabled": True,  "title": "Кликер",         "url": "/games/clicker",  "status": "available"},
    "broadway": {"enabled": True,  "title": "Бродвей",        "url": "/games/broadway", "status": "available"},
    "campus":   {"enabled": True,  "title": "Построй кампус", "url": "/games/campus",   "status": "available"},
    "grable":   {"enabled": True,  "title": "Грабли",         "url": "/games/grable",   "status": "available"},
    "snake":    {"enabled": False, "title": "Змейка",         "url": "",                "status": "soon"},
    "poll":     {"enabled": False, "title": "Опрос дня",      "url": "",                "status": "soon"},
    "click":    {"enabled": False, "title": "Гонка кликов",   "url": "",                "status": "soon"},
}

theme_config = {"current": "classic"}

admin_tokens: dict = {}
TOKEN_TTL = 60 * 60 * 24 * 7

clicker_top: list = []
clicker_day: str = ""
CLICKER_MAX_TOP = 5
started_at = time.time()


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
