"""
Достижения (ачивки). Выдаются автоматически по событиям.
"""
import time, aiosqlite
from config import DB_PATH


# ┌───────────────────────────────────────────────────────────┐
# │ Все ачивки проекта                                        │
# │ Тип определяет как проверяется (см. check_and_grant)      │
# └───────────────────────────────────────────────────────────┘
ACHIEVEMENTS = [
    # Игровые
    {"key":"first_game",     "name":"Первая игра",         "emoji":"🎮", "desc":"Сыграй первую партию",                    "type":"games",  "target":1},
    {"key":"games_10",       "name":"10 партий",           "emoji":"🎯", "desc":"Сыграй 10 партий",                        "type":"games",  "target":10},
    {"key":"games_100",      "name":"100 партий",          "emoji":"🔥", "desc":"Сыграй 100 партий",                       "type":"games",  "target":100},
    {"key":"score_1k",       "name":"Тысячник",            "emoji":"🏆", "desc":"Набери 1 000 очков всего",                "type":"score",  "target":1000},
    {"key":"score_10k",      "name":"Десятка",             "emoji":"💎", "desc":"Набери 10 000 очков всего",               "type":"score",  "target":10000},
    {"key":"score_100k",     "name":"Сотка",               "emoji":"👑", "desc":"Набери 100 000 очков всего",              "type":"score",  "target":100000},

    # Игровые — конкретные игры
    {"key":"clicker_500",    "name":"Кликер-мастер",       "emoji":"🎓", "desc":"500 очков в Кликере за партию",           "type":"game",   "game":"clicker",  "target":500},
    {"key":"broadway_1k",    "name":"Марафонец",           "emoji":"🏃", "desc":"1000 метров на Бродвее",                  "type":"game",   "game":"broadway", "target":1000},
    {"key":"tetris_2k",      "name":"Строитель",           "emoji":"🧱", "desc":"2000 очков в Тетрисе",                    "type":"game",   "game":"tetris",   "target":2000},
    {"key":"2048_2k",        "name":"Градостроитель",      "emoji":"🏙️", "desc":"2000 очков в 2048",                       "type":"game",   "game":"2048",     "target":2000},
    {"key":"grable_2k",      "name":"Столовая-мастер",     "emoji":"🍽️", "desc":"2000 очков в Столовой",                   "type":"game",   "game":"grable",   "target":2000},
    {"key":"adventure_win",  "name":"Кладоискатель",       "emoji":"🗺️", "desc":"Пройди Лабиринт МГСУ",                    "type":"game",   "game":"adventure","target":1, "extra":"win"},
    {"key":"ventilation_win","name":"Свежий воздух",       "emoji":"💨", "desc":"Пройди уровень в Вентиляции",             "type":"game",   "game":"ventilation","target":1},

    # Социальные
    {"key":"streak_3",       "name":"3 дня подряд",        "emoji":"📅", "desc":"Заходи 3 дня подряд",                     "type":"streak", "target":3},
    {"key":"streak_7",       "name":"Неделя подряд",       "emoji":"🗓️", "desc":"Заходи 7 дней подряд",                    "type":"streak", "target":7},
    {"key":"streak_30",      "name":"Месяц подряд",        "emoji":"📆", "desc":"Заходи 30 дней подряд",                   "type":"streak", "target":30},
    {"key":"in_institute",   "name":"В команде",           "emoji":"🏛️", "desc":"Выбери свой институт",                    "type":"manual"},

    # Магазин
    {"key":"chars_3",        "name":"Стиляга",             "emoji":"🎭", "desc":"Купи 3 персонажа",                        "type":"chars",  "target":3},
    {"key":"chars_legend",   "name":"Легенда",             "emoji":"👑", "desc":"Купи Легенду МГСУ",                       "type":"chars",  "target":7},

    # Ранг
    {"key":"rank_student",   "name":"Уже не первокурсник", "emoji":"📚", "desc":"Достигни ранга «Студент»",                "type":"rank",   "rank_key":"student"},
    {"key":"rank_expert",    "name":"Знаток",              "emoji":"✏️", "desc":"Достигни ранга «Знаток»",                 "type":"rank",   "rank_key":"expert"},
    {"key":"rank_headman",   "name":"Староста",            "emoji":"🏅", "desc":"Достигни ранга «Староста»",               "type":"rank",   "rank_key":"headman"},
    {"key":"rank_legend",    "name":"Легенда МГСУ",        "emoji":"👑", "desc":"Достигни максимального ранга",            "type":"rank",   "rank_key":"legend"},
]

ACHIEVEMENTS_MAP = {a["key"]: a for a in ACHIEVEMENTS}


async def db_init_achievements():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_achievements (
                uid TEXT,
                ach_key TEXT,
                unlocked_at REAL,
                PRIMARY KEY (uid, ach_key)
            )
        """)
        await db.commit()


async def get_user_achievements(uid: str) -> dict:
    """Возвращает {key: timestamp} для игрока."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT ach_key, unlocked_at FROM user_achievements WHERE uid=?",
            (uid,)
        )
        rows = await cur.fetchall()
    return {r[0]: r[1] for r in rows}


async def grant_achievement(uid: str, ach_key: str) -> bool:
    """Выдать ачивку. Возвращает True если только что выдали."""
    if ach_key not in ACHIEVEMENTS_MAP:
        return False

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT 1 FROM user_achievements WHERE uid=? AND ach_key=?",
            (uid, ach_key)
        )
        if await cur.fetchone():
            return False

        await db.execute(
            "INSERT INTO user_achievements (uid, ach_key, unlocked_at) VALUES (?,?,?)",
            (uid, ach_key, time.time())
        )
        await db.commit()
    return True


async def check_and_grant(uid: str, user: dict, extra: dict = None) -> list:
    """
    Проверяет все ачивки и выдаёт новые.
    extra = {"game": "clicker", "raw_score": 500, "win": True}
    Возвращает список только что выданных ачивок.
    """
    if not uid or not user:
        return []

    extra = extra or {}
    granted = []

    # Текущие данные игрока
    total_score = user.get("total_score", 0) or 0
    games_played = user.get("games_played", 0) or 0
    streak = user.get("streak", 0) or 0
    owned_chars = user.get("owned_chars", ["student"]) or ["student"]
    institute = user.get("institute", "") or ""

    # Ранг
    rank_info = {}
    try:
        import core.users as users_mod
        rank_info = users_mod.get_account_rank(total_score, games_played)
        rank_key = rank_info.get("key", "freshman")
    except Exception:
        rank_key = "freshman"

    # Ранги для сравнения
    RANK_ORDER = ["freshman", "student", "expert", "activist", "headman", "commander", "legend"]
    try:
        rank_idx = RANK_ORDER.index(rank_key)
    except ValueError:
        rank_idx = 0

    for ach in ACHIEVEMENTS:
        key = ach["key"]
        atype = ach["type"]

        should_grant = False

        # Игры (количество)
        if atype == "games":
            if games_played >= ach["target"]:
                should_grant = True

        # Общий счёт
        elif atype == "score":
            if total_score >= ach["target"]:
                should_grant = True

        # Streak
        elif atype == "streak":
            if streak >= ach["target"]:
                should_grant = True

        # Персонажи
        elif atype == "chars":
            if len(owned_chars) >= ach["target"]:
                should_grant = True

        # Ранг
        elif atype == "rank":
            target_rank = ach.get("rank_key", "")
            try:
                target_idx = RANK_ORDER.index(target_rank)
                if rank_idx >= target_idx:
                    should_grant = True
            except ValueError:
                pass

        # В институте
        elif atype == "manual":
            if key == "in_institute" and institute:
                should_grant = True

        # Конкретная игра
        elif atype == "game":
            game = extra.get("game", "")
            if game == ach.get("game"):
                if ach.get("extra") == "win":
                    if extra.get("win"):
                        should_grant = True
                else:
                    raw = int(extra.get("raw_score", 0) or 0)
                    if raw >= ach["target"]:
                        should_grant = True

        if should_grant:
            was_new = await grant_achievement(uid, key)
            if was_new:
                granted.append(ach)

    return granted
