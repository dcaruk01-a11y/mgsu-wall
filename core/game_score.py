"""
Универсальный эндпоинт сохранения результата игры.
Все игры вызывают его: /api/game/finish
"""
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
import core.users as users
import core.top as top
import core.analytics as analytics
import core.tasks as tasks

router = APIRouter()


# Веса очков за единицу для каждой игры
GAME_WEIGHTS = {
    "wall":     0.5,    # за штрих
    "clicker":  1.0,    # за клик
    "broadway": 1.0,    # за метр
    "campus":   50.0,   # за голос
    "grable":   10.0,   # за клетку
}

GAME_LABELS = {
    "wall":     "Стена",
    "clicker":  "Кликер",
    "broadway": "Бродвей",
    "campus":   "Построй кампус",
    "grable":   "Грабли",
}


class FinishPayload(BaseModel):
    game: str = ""
    raw_score: int = 0       # «сырое» значение (клики, метры, штрихи)
    extra: dict = {}         # доп. данные (например, победа в граблях)


def _token(authorization: str) -> str:
    return authorization.replace("Bearer ", "").strip()


@router.post("/api/game/finish")
async def finish_game(payload: FinishPayload, authorization: str = Header(default="")):
    game = (payload.game or "").strip()
    if game not in GAME_WEIGHTS:
        raise HTTPException(status_code=400, detail="Unknown game")

    token = _token(authorization)
    user = await users.get_user_by_token(token) if token else None

    raw = max(0, min(int(payload.raw_score or 0), 100000))
    points = int(raw * GAME_WEIGHTS[game])

    # всегда пишем в аналитику
    analytics.track_game(game)

    if not user:
        return {
            "ok": True,
            "logged_in": False,
            "points": points,
            "raw_score": raw,
            "game": game,
        }

    uid = user["uid"]
    nick = user["display_name"]

    # 1. streak
    streak_info = await users.apply_streak(uid)

    # 2. проверка — не рекорд ли это (для кликера)
    is_record = False
    if game == "clicker":
        prev = 0
        # ищем лучший результат за сегодня у этого uid
        async with __import__("aiosqlite").connect(__import__("config").DB_PATH) as db:
            cur = await db.execute("""
                SELECT MAX(score) FROM scores WHERE uid = ? AND day = ?
            """, (uid, __import__("config").today_str()))
            row = await cur.fetchone()
            prev = row[0] or 0
        is_record = raw > prev

    # 3. начисляем очки и монеты
    progress = await users.apply_score_and_coins(uid, points, game, is_record)

    # 4. сохраняем в топы
    try:
        await top.save_score(uid, nick, game, points)
    except Exception as e:
        print("top save error:", e)

    # 5. ежедневные задания
    completed = []
    try:
        completed = await tasks.check_game_completion(uid, game, raw, payload.extra or {})
    except Exception as e:
        print("tasks error:", e)

    # 6. награда за streak-вехи
    streak_bonus = 0
    if streak_info.get("ok") and streak_info.get("changed"):
        s = streak_info.get("streak", 0)
        if s == 3:
            streak_bonus = 100
        elif s == 7:
            streak_bonus = 500
        elif s == 14:
            streak_bonus = 1500
        elif s == 30:
            streak_bonus = 5000
        if streak_bonus:
            await users.add_coins(uid, streak_bonus, f"streak-{s}")

    # берём обновлённый профиль
    updated_user = await users.get_user_by_token(token)

    return {
        "ok": True,
        "logged_in": True,
        "game": game,
        "raw_score": raw,
        "points": points,
        "is_record": is_record,
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
