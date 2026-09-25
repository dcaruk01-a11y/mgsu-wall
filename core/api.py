from fastapi import APIRouter
from datetime import datetime
from config import MSK
import core.state as state
import core.analytics as analytics
from core.storage import make_snapshot, post_to_telegram

router = APIRouter()


@router.get("/status")
async def status_endpoint():
    now = datetime.now(MSK)
    sch = state.schedule_str()
    return {
        "open": state.is_open_now(),
        "opens_at": f"{sch['open_hour']:02d}:{sch['open_minute']:02d}",
        "closes_at": f"{sch['close_hour']:02d}:{sch['close_minute']:02d}",
        "open_hour": sch["open_hour"],
        "open_minute": sch["open_minute"],
        "close_hour": sch["close_hour"],
        "close_minute": sch["close_minute"],
        "force_override": sch["force_override"],
        "current_time_msk": now.strftime("%H:%M"),
    }


@router.post("/api/track")
async def api_track(payload: dict):
    uid = str(payload.get("uid", ""))[:64]
    analytics.track_visit(uid)
    return {"ok": True}


@router.post("/api/session")
async def api_session(payload: dict):
    try:
        dur = float(payload.get("duration", 0))
    except Exception:
        dur = 0
    analytics.track_session(dur)
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


@router.get("/api/dev-credits")
async def api_dev_credits():
    dc = state.dev_credits_config
    if not dc.get("enabled", True):
        return {"enabled": False}
    return {
        "enabled": True,
        "title": dc.get("title", ""),
        "subtitle": dc.get("subtitle", ""),
        "footer": dc.get("footer", ""),
        "cards": dc.get("cards", []),
    }


@router.get("/api/top-day")
async def api_top_day():
    """Топ-3 за сегодня — для блока на главной."""
    try:
        from core.top import top_day
        top = await top_day(3)
    except Exception as e:
        print("top-day error:", e)
        top = []
    return {"top": top}


@router.get("/snapshot")
async def manual_snapshot():
    path = await make_snapshot()
    await post_to_telegram(path)
    return {"ok": True, "path": path}
