"""
Универсальный эндпоинт сохранения результата игры.
С дневными лимитами, бонусом ранга и очками для института.
"""
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
import aiosqlite
import time
from uuid import UUID
import core.users as users
import core.top as top
import core.analytics as analytics
import core.daily_tasks as tasks
from config import DB_PATH, today_str

router = APIRouter()


GAME_WEIGHTS = {
    "wall":        0.5,
    "clicker":     1.0,
    "broadway":    1.0,
    "campus":      50.0,
    "grable":      1.0,
    "tetris":      0.7,
    "2048":        0.4,
    "adventure":   1.0,
    "ventilation": 1.0,
}

GAME_LABELS = {
    "wall":        "Стена",
    "clicker":     "Кликер",
    "broadway":    "Бродвей",
    "campus":      "Построй кампус",
    "grable":      "Столовая МГСУ",
    "tetris":      "Тетрис",
    "2048":        "2048 Здания",
    "adventure":   "Лабиринт МГСУ",
    "ventilation": "Вентиляция МГСУ",
}


DAILY_MULTIPLIERS = [1.0, 1.0, 0.7, 0.7, 0.4, 0.4, 0.2]


def daily_multiplier(plays_today: int) -> float:
    if plays_today < len(DAILY_MULTIPLIERS):
        return DAILY_MULTIPLIERS[plays_today]
    return 0.2


class FinishPayload(BaseModel):
    game: str = ""
    raw_score: int = 0
    submission_id: str = ""
    extra: dict = {}


def _token(authorization: str) -> str:
    return authorization.replace("Bearer ", "").strip()


async def _get_daily_plays(uid: str, game: str) -> int:
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

    if game == "clicker":
        raise HTTPException(status_code=400, detail="Используй сохранение результата кликера")

    token = _token(authorization)
    user = await users.get_user_by_token(token) if token else None

    raw = max(0, min(int(payload.raw_score or 0), 100000))

    if not user:
        analytics.track_game(game)
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
    try:
        submission_id = str(UUID(payload.submission_id))
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail="Обнови страницу игры и повтори попытку")

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            SELECT game, raw_score, points FROM game_awards
            WHERE uid = ? AND submission_id = ?
        """, (uid, submission_id))
        previous = await cur.fetchone()
    if previous:
        if previous[0] != game or previous[1] != raw:
            raise HTTPException(status_code=409, detail="Идентификатор партии уже использован")
        users.invalidate_user_cache(uid)
        refreshed = await users.get_user_by_token(token)
        return {
            "ok": True, "duplicate": True, "logged_in": True,
            "game": game, "raw_score": raw, "points": previous[2],
            "progress": refreshed,
            "tasks_completed": [], "achievements_new": [],
        }

    # 1. Дневной множитель
    plays_today = await _get_daily_plays(uid, game)
    mult = daily_multiplier(plays_today)

    # 2. Очки
    points = int(raw * GAME_WEIGHTS[game] * mult)

    # 3. Бонус ранга
    rank_data = users.get_account_rank(
        user.get("total_score", 0),
        user.get("games_played", 0),
    )
    rank_bonus_pct = rank_data.get("bonus_pct", 0)

    # The insert and trigger update profile, rankings and institute together.
    coins = int(round(users.COINS_PER_GAME * mult))
    coins = int(round(coins * (1 + rank_bonus_pct / 100.0)))
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            INSERT OR IGNORE INTO game_awards
                (uid, submission_id, nick, game, raw_score, points, coins,
                 institute, day, week, ts)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            RETURNING submission_id
        """, (uid, submission_id, nick[:30], game, raw, points, coins,
              user.get("institute") or "", today_str(), top.week_str(), time.time()))
        inserted = await cur.fetchone()
        await db.commit()
    if not inserted:
        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute("""
                SELECT game, raw_score, points FROM game_awards
                WHERE uid = ? AND submission_id = ?
            """, (uid, submission_id))
            previous = await cur.fetchone()
        if not previous or previous[0] != game or previous[1] != raw:
            raise HTTPException(status_code=409, detail="Идентификатор партии уже использован")
        users.invalidate_user_cache(uid)
        refreshed = await users.get_user_by_token(token)
        return {
            "ok": True, "duplicate": True, "logged_in": True,
            "game": game, "raw_score": raw, "points": previous[2],
            "progress": refreshed,
            "tasks_completed": [], "achievements_new": [],
        }

    users.invalidate_user_cache(uid)
    analytics.track_game(game)
    streak_info = await users.apply_streak(uid)
    is_record = False

    # 9. Задания
    completed = []
    try:
        completed = await tasks.check_game_completion(uid, game, raw, payload.extra or {})
    except Exception as e:
        print("tasks error:", e)

        # ★ 9.5. Проверка достижений
    achievements_new = []
    try:
        updated_user_for_ach = await users.get_user_by_token(token)
        if updated_user_for_ach:
            from core.achievements import check_and_grant
            achievements_new = await check_and_grant(
                uid, updated_user_for_ach,
                {"game": game, "raw_score": raw, "win": (payload.extra or {}).get("win")}
            )
    except Exception as e:
        print("achievements error:", e)

    # 10. Streak-бонусы
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

    updated_user = await users.get_user_by_token(token)

    return {
        "ok": True,
        "logged_in": True,
        "game": game,
        "raw_score": raw,
        "points": points,
        "is_record": is_record,
        "daily_plays": plays_today + 1,
        "daily_multiplier": mult,
        "next_multiplier": daily_multiplier(plays_today + 1),
        "progress": {
            "coins": updated_user["coins"] if updated_user else 0,
            "total_score": updated_user["total_score"] if updated_user else 0,
            "games_played": updated_user["games_played"] if updated_user else 0,
            "streak": streak_info.get("streak", 0),
            "streak_changed": streak_info.get("changed", False),
            "rank_bonus_pct": rank_bonus_pct,
            "institute": (updated_user.get("institute") if updated_user else "") or "",
        },
                "streak_bonus": streak_bonus,
        "tasks_completed": completed,
        "achievements_new": [
            {"key": a["key"], "name": a["name"], "emoji": a["emoji"], "desc": a["desc"]}
            for a in achievements_new
        ],
    }


@router.get("/api/game/info")
async def game_info():
    return {
        "games": [
            {"key": k, "label": GAME_LABELS[k], "weight": GAME_WEIGHTS[k]}
            for k in GAME_WEIGHTS
        ]
    }
