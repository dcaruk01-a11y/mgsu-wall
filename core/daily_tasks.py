"""
Ежедневные задания. Генерируются раз в день для каждого игрока.
Прогресс обновляется при каждом завершении игры.
"""
import time, json, aiosqlite, random
from datetime import datetime
from config import DB_PATH, MSK, today_str


# Пул возможных заданий
TASK_POOL = [
    {
        "key": "clicker_200",
        "text": "Накликай 200 в Кликере",
        "game": "clicker",
        "target": 200,
        "reward": 150,
    },
    {
        "key": "clicker_350",
        "text": "Накликай 350 в Кликере",
        "game": "clicker",
        "target": 350,
        "reward": 250,
    },
    {
        "key": "broadway_400",
        "text": "Пройди 400 метров по Бродвею",
        "game": "broadway",
        "target": 400,
        "reward": 150,
    },
    {
        "key": "broadway_700",
        "text": "Пройди 700 метров по Бродвею",
        "game": "broadway",
        "target": 700,
        "reward": 250,
    },
    {
        "key": "campus_vote",
        "text": "Проголосуй в «Построй кампус»",
        "game": "campus",
        "target": 1,
        "reward": 100,
    },
    {
        "key": "grable_win",
        "text": "Выиграй в «Грабли» (открой все безопасные клетки)",
        "game": "grable",
        "target": 1,
        "extra_key": "win",
        "reward": 200,
    },
    {
        "key": "wall_50",
        "text": "Нарисуй 50 штрихов на Стене",
        "game": "wall",
        "target": 50,
        "reward": 100,
    },
    {
        "key": "any_two_games",
        "text": "Сыграй в 2 разные игры",
        "game": "any",
        "target": 2,
        "reward": 150,
    },
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


def _pick_tasks(uid: str, day: str):
    """Стабильный выбор 3 заданий для игрока на день."""
    seed = hash((uid, day)) & 0xffffffff
    rng = random.Random(seed)
    pool = TASK_POOL.copy()
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
            return {
                "tasks": json.loads(row[0]),
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
    """
    Вызывается после игры. Возвращает список выполненных заданий,
    за которые начислены монеты.
    """
    if not uid:
        return []

    state = await get_or_create_day(uid)
    tasks_list = state["tasks"]
    progress = state["progress"]
    claimed = state["claimed"]

    # для задания «2 разные игры» — считаем уникальные игры за сегодня
    games_today = None

    completed_now = []

    for t in tasks_list:
        key = t["key"]
        if key in claimed:
            continue

        cur_val = progress.get(key, 0)
        new_val = cur_val

        if t["game"] == game:
            if key == "clicker_200" or key == "clicker_350" or key == "broadway_400" or key == "broadway_700":
                # прогресс = максимум из партий
                new_val = max(cur_val, raw_score)
            elif key == "campus_vote":
                new_val = cur_val + 1
            elif key == "grable_win":
                if extra.get("win"):
                    new_val = 1
            elif key == "wall_50":
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
            # начисляем награду
            from core.users import add_coins
            await add_coins(uid, t["reward"], f"task-{key}")
            claimed.append(key)
            completed_now.append({"key": key, "text": t["text"], "reward": t["reward"]})

    # сохраняем
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE user_tasks SET progress=?, claimed=? WHERE uid=? AND day=?
        """, (json.dumps(progress), json.dumps(claimed), uid, today_str()))
        await db.commit()

    return completed_now
