from fastapi import APIRouter
from datetime import datetime
from config import MSK, is_open
import core.state as state
from core.storage import make_snapshot, post_to_telegram

router = APIRouter()


@router.get("/status")
async def status_endpoint():
    now = datetime.now(MSK)
    return {
        "open": is_open(),
        "opens_at": 8,
        "closes_at": 17,
        "current_hour_msk": now.hour,
    }


@router.post("/api/track")
async def api_track(payload: dict):
    uid = str(payload.get("uid", ""))[:64]
    state.track_visit(uid)
    return {"ok": True}


@router.get("/api/games")
async def api_games():
    return {
        "games": [
            {
                "key": k,
                "title": v["title"],
                "enabled": v["enabled"],
                "status": v.get("status", "available"),
                "url": v.get("url", ""),
            }
            for k, v in state.games_config.items()
        ],
        "theme": state.theme_config["current"],
    }


@router.get("/snapshot")
async def manual_snapshot():
    path = await make_snapshot()
    await post_to_telegram(path)
    return {"ok": True, "path": path}
