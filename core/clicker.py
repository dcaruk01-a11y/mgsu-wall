import time, asyncio
from fastapi import APIRouter, Header
from pydantic import BaseModel
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


def _token(authorization: str) -> str:
    return authorization.replace("Bearer ", "").strip()


@router.post("/clicker/score")
async def clicker_score(payload: ClickerScore, authorization: str = Header(default="")):
    state.clicker_reset_if_needed()
    analytics.track_game("clicker")

    token = _token(authorization)
    user = await users.get_user_by_token(token) if token else None

    score = max(0, min(int(payload.score or 0), 10000))
    rank = (payload.rank or "")[:30]

    if user:
        nick = user["display_name"]
        uid = user["uid"]
        streak_info = await users.apply_streak(uid)

        is_record = False
        for e in state.clicker_top:
            if e.get("uid") == uid and e["score"] >= score:
                is_record = False
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
