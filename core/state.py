import time, json
from datetime import datetime
from config import today_str, MSK
import core.settings as settings


# ============ РАСПИСАНИЕ ============
schedule_config = {
    "open_hour": 8,
    "open_minute": 30,
    "close_hour": 17,
    "close_minute": 20,
    "force_override": None,
}


def is_open_now() -> bool:
    force = schedule_config.get("force_override")
    if force is True:
        return True
    if force is False:
        return False
    now = datetime.now(MSK)
    open_t = now.replace(hour=schedule_config["open_hour"], minute=schedule_config["open_minute"], second=0, microsecond=0)
    close_t = now.replace(hour=schedule_config["close_hour"], minute=schedule_config["close_minute"], second=0, microsecond=0)
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


# ============ ТЕМА ============
theme_config = {"current": "classic"}


# ============ АКТИВ РАЗРАБОТЧИКОВ ============
dev_credits_config = {
    "enabled": True,
    "title": "Актив разработчиков",
    "subtitle": "Проект «Игры МГСУ» делает команда студентов",
    "footer": "Хочешь в команду или есть идея? Напиши через кнопку «Обратная связь» на сайте.",
    "cards": [
        {"role": "Идея и продукт", "name": "Даниил Царук", "note": "автор проекта"},
        {"role": "Разработка", "name": "Команда МГСУ", "note": "Python · FastAPI · Turso"},
        {"role": "Дизайн и медиа", "name": "Студенческий актив", "note": "стикеры · афиши · фото"},
    ],
}


# ============ АДМИН-ТОКЕНЫ ============
admin_tokens: dict = {}
TOKEN_TTL = 60 * 60 * 24 * 7


# ============ КЛИКЕР ТОП ============
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


# ============ СОХРАНЕНИЕ В SQLITE ============

async def load_all_settings():
    theme = await settings.get_setting("theme")
    if theme and theme in ("classic", "retro", "notebook", "cyberpunk", "cozy"):
        theme_config["current"] = theme

    sch_raw = await settings.get_setting("schedule")
    if sch_raw:
        try:
            data = json.loads(sch_raw)
            for k in ("open_hour", "open_minute", "close_hour", "close_minute"):
                if k in data and isinstance(data[k], int):
                    schedule_config[k] = data[k]
            if "force_override" in data:
                schedule_config["force_override"] = data["force_override"]
        except Exception as e:
            print("load schedule error:", e)

    games_raw = await settings.get_setting("games_config")
    if games_raw:
        try:
            data = json.loads(games_raw)
            for k, v in data.items():
                if k not in games_config:
                    continue
                for f in ("enabled", "title", "status", "url"):
                    if f in v:
                        games_config[k][f] = v[f]
        except Exception as e:
            print("load games error:", e)

    dc_raw = await settings.get_setting("dev_credits")
    if dc_raw:
        try:
            data = json.loads(dc_raw)
            for k in ("enabled", "title", "subtitle", "footer"):
                if k in data:
                    dev_credits_config[k] = data[k]
            if "cards" in data and isinstance(data["cards"], list):
                dev_credits_config["cards"] = data["cards"]
        except Exception as e:
            print("load dev_credits error:", e)

    print("settings loaded from DB")


async def save_theme(theme: str):
    theme_config["current"] = theme
    await settings.set_setting("theme", theme)


async def save_schedule():
    await settings.set_setting("schedule", json.dumps(schedule_config))


async def save_games():
    await settings.set_setting("games_config", json.dumps(games_config))


async def save_dev_credits():
    await settings.set_setting("dev_credits", json.dumps(dev_credits_config))
