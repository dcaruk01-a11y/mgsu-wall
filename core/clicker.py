import time, asyncio
from fastapi import APIRouter
from pydantic import BaseModel
import core.state as state
import core.analytics as analytics

router = APIRouter()
clicker_lock = asyncio.Lock()


class ClickerScore(BaseModel):
    nick: str = ""
    score: int = 0
    rank: str = ""


@router.post("/clicker/score")
async def clicker_score(payload: ClickerScore):
    state.clicker_reset_if_needed()
    analytics.track_game("clicker")
    analytics.track_clicker_score(score)
    nick = state.sanitize_nick(payload.nick)
    score = max(0, min(int(payload.score or 0), 10000))
    rank = (payload.rank or "")[:30]
    entry = {"nick": nick, "score": score, "rank": rank, "ts": time.time()}
    async with clicker_lock:
        state.clicker_top.append(entry)
        state.clicker_top.sort(key=lambda x: x["score"], reverse=True)
        del state.clicker_top[state.CLICKER_MAX_TOP:]
        pos = next((i for i, e in enumerate(state.clicker_top) if e["ts"] == entry["ts"]), -1)
    return {
        "ok": True,
        "position": pos + 1 if pos >= 0 else None,
        "top": [{"nick": e["nick"], "score": e["score"], "rank": e["rank"]} for e in state.clicker_top],
    }


@router.get("/clicker/top")
async def clicker_top_get():
    state.clicker_reset_if_needed()
    return {"top": [{"nick": e["nick"], "score": e["score"], "rank": e["rank"]} for e in state.clicker_top]}
