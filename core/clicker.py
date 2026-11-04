import time, asyncio, aiosqlite
from uuid import UUID
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
from config import DB_PATH, today_str
import core.state as state
import core.analytics as analytics
import core.users as users
import core.top as top

router = APIRouter()
clicker_lock = asyncio.Lock()


class ClickerScore(BaseModel):
    nick: str = ""
    score: int = 0
    rank: str = ""
    mode: str = "solo"   # "solo" | "duel"
    submission_id: str = ""


def _token(authorization: str) -> str:
    return authorization.replace("Bearer ", "").strip()


async def _get_daily_plays(uid: str) -> int:
    """Сколько раз играл в кликер сегодня."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            SELECT COUNT(*) FROM scores WHERE uid=? AND game='clicker' AND day=?
        """, (uid, today_str()))
        row = await cur.fetchone()
        return row[0] if row else 0


@router.get("/clicker/can-play")
async def clicker_can_play(authorization: str = Header(default="")):
    """Можно ли играть в кликер сегодня (одну партию в день)."""
    token = _token(authorization)
    user = await users.get_user_by_token(token) if token else None
    if not user:
        # Гость — без лимита
        return {"ok": True, "can_play": True, "plays_today": 0, "is_guest": True}
    uid = user["uid"]
    plays = await _get_daily_plays(uid)
    return {
        "ok": True,
        "can_play": plays == 0,
        "plays_today": plays,
        "is_guest": False,
    }


@router.post("/clicker/score")
async def clicker_score(payload: ClickerScore, authorization: str = Header(default="")):
    state.clicker_reset_if_needed()

    token = _token(authorization)
    user = await users.get_user_by_token(token) if token else None

    score = max(0, min(int(payload.score or 0), 10000))
    rank = (payload.rank or "")[:30]
    mode = (payload.mode or "solo").strip()
    if mode not in ("solo", "duel"):
        raise HTTPException(status_code=400, detail="Неизвестный режим игры")

    # ═══ ЛИМИТ 1 ПАРТИЯ В ДЕНЬ — только для соло ═══
    if user:
        nick = user["display_name"]
        uid = user["uid"]
        try:
            submission_id = str(UUID(payload.submission_id))
        except (ValueError, AttributeError):
            raise HTTPException(status_code=400, detail="Обнови страницу игры и повтори попытку")

        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute("""
                SELECT game, raw_score FROM game_awards WHERE uid=? AND submission_id=?
            """, (uid, submission_id))
            previous = await cur.fetchone()
        if previous and (previous[0] != "clicker" or previous[1] != score):
            raise HTTPException(status_code=409, detail="Идентификатор партии уже использован")

        is_record = False
        for e in state.clicker_top:
            if e.get("uid") == uid and e["score"] >= score:
                break
        else:
            is_record = score > 0

        duplicate = bool(previous)
        if not duplicate:
            coins = users.COINS_PER_GAME + (users.COINS_PER_RECORD if is_record else 0)
            day = today_str()
            async with aiosqlite.connect(DB_PATH) as db:
                cur = await db.execute("""
                    INSERT OR IGNORE INTO game_awards
                        (uid, submission_id, nick, game, raw_score, points, coins,
                         institute, day, week, ts)
                    SELECT ?, ?, ?, 'clicker', ?, ?, ?, '', ?, ?, ?
                    WHERE ? != 'solo' OR NOT EXISTS (
                        SELECT 1 FROM scores WHERE uid=? AND game='clicker' AND day=?
                    )
                    RETURNING submission_id
                """, (uid, submission_id, nick[:30], score, score, coins,
                      day, top.week_str(), time.time(), mode, uid, day))
                inserted = await cur.fetchone()
                await db.commit()
            if not inserted:
                async with aiosqlite.connect(DB_PATH) as db:
                    cur = await db.execute("""
                        SELECT game, raw_score FROM game_awards WHERE uid=? AND submission_id=?
                    """, (uid, submission_id))
                    previous = await cur.fetchone()
                if previous:
                    if previous[0] != "clicker" or previous[1] != score:
                        raise HTTPException(status_code=409, detail="Идентификатор партии уже использован")
                    duplicate = True
                else:
                    raise HTTPException(status_code=429, detail="Одна партия в день. Возвращайся завтра!")
        users.invalidate_user_cache(uid)
        streak_info = await users.apply_streak(uid) if not duplicate else {"ok": False}
        refreshed = await users.get_user_by_token(token)
        progress = {"ok": True, **refreshed, "coins_added": 0 if duplicate else coins}
        if not duplicate:
            analytics.track_game("clicker")
    else:
        analytics.track_game("clicker")
        nick = state.sanitize_nick(payload.nick)
        uid = ""
        streak_info = {"ok": False}
        progress = {"ok": False}

    entry = {
        "nick": nick,
        "uid": uid,
        "score": score,
        "rank": rank,
        "ts": time.time(),
    }

    async with clicker_lock:
        if user and duplicate:
            return {
                "ok": True, "duplicate": True, "logged_in": True,
                "top": state.clicker_top, "position": None,
                "streak": progress.get("streak"), "streak_changed": False,
                "progress": progress,
            }
        if uid:
            state.clicker_top = [e for e in state.clicker_top if e.get("uid") != uid]
        state.clicker_top.append(entry)
        state.clicker_top.sort(key=lambda x: x["score"], reverse=True)
        del state.clicker_top[state.CLICKER_MAX_TOP:]
        pos = next((i for i, e in enumerate(state.clicker_top) if e["ts"] == entry["ts"]), -1)

    return {
        "ok": True,
        "position": pos + 1 if pos >= 0 else None,
        "top": [
            {
                "nick": e["nick"],
                "score": e["score"],
                "rank": e["rank"],
                "uid": e.get("uid", ""),
            }
            for e in state.clicker_top
        ],
        "streak": streak_info.get("streak") if streak_info.get("ok") else None,
        "streak_changed": streak_info.get("changed") if streak_info.get("ok") else False,
        "progress": progress if progress.get("ok") else None,
        "logged_in": bool(user),
    }


@router.get("/clicker/top")
async def clicker_top_get():
    state.clicker_reset_if_needed()
    return {
        "top": [
            {
                "nick": e["nick"],
                "score": e["score"],
                "rank": e["rank"],
                "uid": e.get("uid", ""),
            }
            for e in state.clicker_top
        ]
    }
