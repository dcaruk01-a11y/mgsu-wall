"""
Универсальный эндпоинт сохранения результата игры.
Все игры вызывают его: /api/game/finish
С дневными лимитами: чем больше партий в игру за день — тем меньше награда.
"""
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
import aiosqlite
import core.users as users
import core.top as top
import core.analytics as analytics
import core.tasks as tasks
from config import DB_PATH, today_str

router = APIRouter()


# Веса очков за единицу для каждой игры
GAME_WEIGHTS = {
    "wall":      0.5,
    "clicker":   1.0,
    "broadway":  1.0,
    "campus":    50.0,
    "grable":    10.0,
    "tetris":    0.7,
    "2048":      0.4,
    "adventure": 1.0,
}

GAME_LABELS = {
    "wall":      "Стена",
    "clicker":   "Кликер",
    "broadway":  "Бродвей",
    "campus":    "Построй кампус",
    "grable":    "Грабли",
    "tetris":    "Тетрис",
    "2048":      "2048 Здания",
    "adventure": "Лабиринт МГСУ",
}


# ── ДНЕВНЫЕ МНОЖИТЕЛИ ──
# индекс = сколько партий в эту игру уже сыграно сегодня
# 1-2 партии: полная награда
# 3-4: 70%
# 5-6: 40%
# 7+: 20%
DAILY_MULTIPLIERS = [1.0, 1.0, 0.7, 0.7, 0.4, 0.4, 0.2]


def daily_multiplier(plays_today: int) -> float:
    if plays_today < len(DAILY_MULTIPLIERS):
        return DAILY_MULTIPLIERS[plays_today]
    return 0.2


class FinishPayload(BaseModel):
    game: str = ""
    raw_score: int = 0
    extra: dict = {}


def _token(authorization: str) -> str:
    return authorization.replace("Bearer ", "").strip()


async def _get_daily_plays(uid: str, game: str) -> int:
    """Сколько партий в эту игру сыграно сегодня."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            SELECT COUNT(*) FROM scores WHERE uid=? AND game=? AND day=?
        """, (uid, game, today_str()))
        row = await cur.fetchone()
        return row[0] if row else 0


@router.post("/api/game/finish")
async def finish_game(payload: FinishPayload, authorization: str = Header(default="")):
    game = (payload.game or "").strip()
    if game not in GAME_WEIGHTS:
        raise HTTPException(status_code=400, detail="Unknown game")

    token = _token(authorization)
    user = await users.get_user_by_token(token) if token else None

    raw = max(0, min(int(payload.raw_score or 0), 100000))

    # всегда пишем в аналитику
    analytics.track_game(game)

    if not user:
        points = int(raw * GAME_WEIGHTS[game])
        return {
            "ok": True,
            "logged_in": False,
            "points": points,
            "raw_score": raw,
            "game": game,
            "daily_plays": 1,
            "daily_multiplier": 1.0,
        }

    uid = user["uid"]
    nick = user["display_name"]

    # 1. Считаем, сколько партий в эту игру за сегодня
    plays_today = await _get_daily_plays(uid, game)
    mult = daily_multiplier(plays_today)

    # 2. Итоговые очки (с учётом дневного множителя)
    points = int(raw * GAME_WEIGHTS[game] * mult)

    # 3. Streak
    streak_info = await users.apply_streak(uid)

    # 4. Рекорд (для кликера — лучший за день)
    is_record = False
    if game == "clicker":
        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute("""
                SELECT MAX(score) FROM scores WHERE uid=? AND day=?
            """, (uid, today_str()))
            row = await cur.fetchone()
            prev = row[0] or 0
        is_record = raw > prev

    # 5. Начисляем очки и монеты
    progress = await users.apply_score_and_coins(uid, points, game, is_record, daily_mult=mult)

    # 6. Сохраняем в топы (сырые очки, чтобы рейтинг был честным)
    try:
        await top.save_score(uid, nick, game, points)
    except Exception as e:
        print("top save error:", e)

    # 7. Ежедневные задания (считаются от raw — сырое значение)
    completed = []
    try:
        completed = await tasks.check_game_completion(uid, game, raw, payload.extra or {})
    except Exception as e:
        print("tasks error:", e)

    # 8. Streak-бонусы
    streak_bonus = 0
    if streak_info.get("ok") and streak_info.get("changed"):
        s = streak_info.get("streak", 0)
        if s == 3:    streak_bonus = 100
        elif s == 7:  streak_bonus = 500
        elif s == 14: streak_bonus = 1500
        elif s == 30: streak_bonus = 5000
        if streak_bonus:
            await users.add_coins(uid, streak_bonus, f"streak-{s}")

    # Берём обновлённый профиль
    updated_user = await users.get_user_by_token(token)

    return {
        "ok": True,
        "logged_in": True,
        "game": game,
        "raw_score": raw,
        "points": points,
        "is_record": is_record,
        "daily_plays": plays_today + 1,       # +1 — текущая только что сыграна
        "daily_multiplier": mult,             # текущий множитель
        "next_multiplier": daily_multiplier(plays_today + 1),  # что будет на следующей партии
        "progress": {
            "coins": updated_user["coins"] if updated_user else 0,
            "total_score": updated_user["total_score"] if updated_user else 0,
            "games_played": updated_user["games_played"] if updated_user else 0,
            "streak": streak_info.get("streak", 0),
            "streak_changed": streak_info.get("changed", False),
        },
        "streak_bonus": streak_bonus,
        "tasks_completed": completed,
    }


@router.get("/api/game/info")
async def game_info():
    """Какие игры есть и за что сколько очков."""
    return {
        "games": [
            {"key": k, "label": GAME_LABELS[k], "weight": GAME_WEIGHTS[k]}
            for k in GAME_WEIGHTS
        ]
    }
