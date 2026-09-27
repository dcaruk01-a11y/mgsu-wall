import time, asyncio, aiosqlite
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
    analytics.track_game("clicker")

    token = _token(authorization)
    user = await users.get_user_by_token(token) if token else None

    score = max(0, min(int(payload.score or 0), 10000))
    rank = (payload.rank or "")[:30]
    mode = (payload.mode or "solo").strip()

    # ═══ ЛИМИТ 1 ПАРТИЯ В ДЕНЬ — только для соло ═══
    if user and mode == "solo":
        plays = await _get_daily_plays(user["uid"])
        if plays >= 1:
            raise HTTPException(
                status_code=429,
                detail="Одна партия в день. Возвращайся завтра!"
            )

    if user:
        nick = user["display_name"]
        uid = user["uid"]
        streak_info = await users.apply_streak(uid)

        is_record = False
        for e in state.clicker_top:
            if e.get("uid") == uid and e["score"] >= score:
                break
        else:
            is_record = score > 0

        progress = await users.apply_score_and_coins(uid, score, "clicker", is_record)
        try:
            await top.save_score(uid, nick, "clicker", score)
        except Exception as e:
            print("top save error:", e)
    else:
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
