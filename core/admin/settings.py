"""Управление играми, расписанием и темами."""
from fastapi import APIRouter, Header, HTTPException
import core.state as state
from core.admin.common import check_admin

router = APIRouter()


@router.get("/admin/api/games")
async def admin_games_get(token: str = Header(default="", alias="authorization")):
    if not check_admin(token.replace("Bearer ", "").strip()):
        raise HTTPException(status_code=401, detail="Unauthorized")
    return {
        "games": [{"key": k, "title": v["title"], "enabled": v["enabled"], "status": v.get("status"), "url": v.get("url", "")} for k, v in state.games_config.items()],
        "theme": state.theme_config["current"],
    }


@router.post("/admin/api/games")
async def admin_games_set(payload: dict, token: str = Header(default="", alias="authorization")):
    if not check_admin(token.replace("Bearer ", "").strip()):
        raise HTTPException(status_code=401, detail="Unauthorized")
    key = str(payload.get("key", ""))
    if key in state.games_config:
        if "enabled" in payload:
            state.games_config[key]["enabled"] = bool(payload["enabled"])
        if "title" in payload:
            state.games_config[key]["title"] = str(payload["title"])[:40]
        if "status" in payload and payload["status"] in ("available", "soon"):
            state.games_config[key]["status"] = payload["status"]
        if "url" in payload:
            state.games_config[key]["url"] = str(payload["url"])[:200]
    await state.save_games()
    return {
        "ok": True,
        "games": [{"key": k, "title": v["title"], "enabled": v["enabled"], "status": v.get("status"), "url": v.get("url", "")} for k, v in state.games_config.items()],
    }


@router.get("/admin/api/schedule")
async def admin_schedule_get(token: str = Header(default="", alias="authorization")):
    if not check_admin(token.replace("Bearer ", "").strip()):
        raise HTTPException(status_code=401, detail="Unauthorized")
    return {"schedule": state.schedule_str(), "is_open_now": state.is_open_now()}


@router.post("/admin/api/schedule")
async def admin_schedule_set(payload: dict, token: str = Header(default="", alias="authorization")):
    if not check_admin(token.replace("Bearer ", "").strip()):
        raise HTTPException(status_code=401, detail="Unauthorized")

    if "open_hour" in payload:
        try:
            h = int(payload["open_hour"])
            if 0 <= h <= 23: state.schedule_config["open_hour"] = h
        except Exception: pass
    if "open_minute" in payload:
        try:
            m = int(payload["open_minute"])
            if 0 <= m <= 59: state.schedule_config["open_minute"] = m
        except Exception: pass
    if "close_hour" in payload:
        try:
            h = int(payload["close_hour"])
            if 0 <= h <= 23: state.schedule_config["close_hour"] = h
        except Exception: pass
    if "close_minute" in payload:
        try:
            m = int(payload["close_minute"])
            if 0 <= m <= 59: state.schedule_config["close_minute"] = m
        except Exception: pass

    if "force_override" in payload:
        v = payload["force_override"]
        if v is None: state.schedule_config["force_override"] = None
        elif isinstance(v, bool): state.schedule_config["force_override"] = v
        elif v in ("open", "on"): state.schedule_config["force_override"] = True
        elif v in ("close", "off"): state.schedule_config["force_override"] = False
        elif v == "auto": state.schedule_config["force_override"] = None

    await state.save_schedule()
    return {"ok": True, "schedule": state.schedule_str(), "is_open_now": state.is_open_now()}


@router.post("/admin/api/theme")
async def admin_theme_set(payload: dict, token: str = Header(default="", alias="authorization")):
    if not check_admin(token.replace("Bearer ", "").strip()):
        raise HTTPException(status_code=401, detail="Unauthorized")
    theme = str(payload.get("theme", "classic"))
    if theme in ("classic", "retro", "notebook", "cyberpunk", "cozy"):
        await state.save_theme(theme)
    return {"ok": True, "theme": state.theme_config["current"]}
