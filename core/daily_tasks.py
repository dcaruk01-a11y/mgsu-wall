"""
Ежедневные задания. Генерируются раз в день для каждого игрока.
Задания — только для ВКЛЮЧЁННЫХ игр (учитываем state.games_config).
"""
import time, json, aiosqlite, random
from datetime import datetime
from config import DB_PATH, MSK, today_str


TASK_POOL = [
    {"key": "clicker_200",    "text": "Накликай 200 в Кликере",           "game": "clicker",   "target": 200, "reward": 150},
    {"key": "clicker_350",    "text": "Накликай 350 в Кликере",           "game": "clicker",   "target": 350, "reward": 250},
    {"key": "broadway_400",   "text": "Пройди 400 метров по Бродвею",     "game": "broadway",  "target": 400, "reward": 150},
    {"key": "broadway_700",   "text": "Пройди 700 метров по Бродвею",     "game": "broadway",  "target": 700, "reward": 250},
    {"key": "campus_vote",    "text": "Проголосуй в «Построй кампус»",    "game": "campus",    "target": 1,   "reward": 100},
        {"key": "grable_500",     "text": "Набери 500 очков в Столовой",      "game": "grable",    "target": 500, "reward": 200},
    {"key": "grable_1500",    "text": "Набери 1500 очков в Столовой",     "game": "grable",    "target": 1500,"reward": 300},
    {"key": "wall_50",        "text": "Нарисуй 50 штрихов на Стене",      "game": "wall",      "target": 50,  "reward": 100},
    {"key": "tetris_500",     "text": "Набери 500 очков в Тетрисе",       "game": "tetris",    "target": 500, "reward": 150},
    {"key": "tetris_1500",    "text": "Набери 1500 очков в Тетрисе",      "game": "tetris",    "target": 1500,"reward": 250},
    {"key": "2048_500",       "text": "Набери 500 очков в 2048",          "game": "2048",      "target": 500, "reward": 150},
    {"key": "adventure_win",  "text": "Пройди Лабиринт МГСУ",             "game": "adventure", "target": 1,   "extra_key": "win", "reward": 250},
    {"key": "ventilation_1",  "text": "Пройди уровень в Вентиляции",      "game": "ventilation","target": 1,  "reward": 200},
    {"key": "any_two_games",  "text": "Сыграй в 2 разные игры",           "game": "any",       "target": 2,   "reward": 150},
]


async def db_init_tasks():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_tasks (
                uid TEXT,
                day TEXT,
                tasks TEXT,
                progress TEXT,
                claimed TEXT,
                PRIMARY KEY (uid, day)
            )
        """)
        await db.commit()


def _get_available_task_pool():
    """
    Возвращает только задания для ВКЛЮЧЁННЫХ игр.
    Импорт state делаем внутри функции, чтобы избежать циклических импортов.
    """
    try:
        import core.state as state
        enabled_games = {k for k, v in state.games_config.items() if v.get("enabled")}
    except Exception:
        # Fallback — если не получилось, возвращаем весь пул
        return list(TASK_POOL)

    available = []
    for t in TASK_POOL:
        game = t.get("game")
        if game == "any":
            # Задание «2 разные игры» — только если есть хотя бы 2 включённые
            if len(enabled_games) >= 2:
                available.append(t)
        elif game in enabled_games:
            available.append(t)
    return available


def _pick_tasks(uid: str, day: str):
    """Стабильный выбор 3 заданий для игрока на день — только из доступных игр."""
    seed = hash((uid, day)) & 0xffffffff
    rng = random.Random(seed)
    pool = _get_available_task_pool()
    rng.shuffle(pool)
    picked = pool[:3]
    return picked


async def get_or_create_day(uid: str):
    day = today_str()
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT tasks, progress, claimed FROM user_tasks WHERE uid=? AND day=?",
            (uid, day)
        )
        row = await cur.fetchone()

        if row:
            tasks_list = json.loads(row[0])
            # Фильтруем задания — если игра выключена, не показываем
            try:
                import core.state as state
                filtered = []
                for t in tasks_list:
                    game = t.get("game")
                    if game == "any":
                        filtered.append(t)
                    elif state.games_config.get(game, {}).get("enabled"):
                        filtered.append(t)
                tasks_list = filtered
            except Exception:
                pass

            return {
                "tasks": tasks_list,
                "progress": json.loads(row[1]),
                "claimed": json.loads(row[2]),
            }

        # создаём
        picked = _pick_tasks(uid, day)
        tasks_list = [{"key": t["key"], "text": t["text"], "game": t["game"],
                       "target": t["target"], "reward": t["reward"],
                       "extra_key": t.get("extra_key")} for t in picked]
        progress = {t["key"]: 0 for t in picked}
        claimed = []

        await db.execute("""
            INSERT INTO user_tasks (uid, day, tasks, progress, claimed)
            VALUES (?,?,?,?,?)
        """, (uid, day, json.dumps(tasks_list), json.dumps(progress), json.dumps(claimed)))
        await db.commit()

        return {"tasks": tasks_list, "progress": progress, "claimed": claimed}


async def check_game_completion(uid: str, game: str, raw_score: int, extra: dict) -> list:
    """Вызывается после игры. Возвращает список выполненных заданий."""
    if not uid:
        return []

    state = await get_or_create_day(uid)
    tasks_list = state["tasks"]
    progress = state["progress"]
    claimed = state["claimed"]

    games_today = None
    completed_now = []

    for t in tasks_list:
        key = t["key"]
        if key in claimed:
            continue

        cur_val = progress.get(key, 0)
        new_val = cur_val

        if t["game"] == game:
            if key in ("clicker_200", "clicker_350", "broadway_400", "broadway_700",
                       "tetris_500", "tetris_1500", "2048_500"):
                new_val = max(cur_val, raw_score)
            elif key == "campus_vote":
                new_val = cur_val + 1
            elif key in ("grable_win", "adventure_win"):
                if extra.get("win"):
                    new_val = 1
            elif key in ("wall_50", "ventilation_1"):
                new_val = max(cur_val, raw_score)
        elif t["game"] == "any" and key == "any_two_games":
            if games_today is None:
                async with aiosqlite.connect(DB_PATH) as db:
                    c = await db.execute("""
                        SELECT COUNT(DISTINCT game) FROM scores
                        WHERE uid = ? AND day = ?
                    """, (uid, today_str()))
                    r = await c.fetchone()
                    games_today = r[0] if r else 0
            new_val = max(cur_val, games_today)

        progress[key] = new_val

        if new_val >= t["target"]:
            from core.users import add_coins
            await add_coins(uid, t["reward"], f"task-{key}")
            claimed.append(key)
            completed_now.append({"key": key, "text": t["text"], "reward": t["reward"]})

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE user_tasks SET progress=?, claimed=? WHERE uid=? AND day=?
        """, (json.dumps(progress), json.dumps(claimed), uid, today_str()))
        await db.commit()

    return completed_now
