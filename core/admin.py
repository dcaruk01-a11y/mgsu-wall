import time, secrets, asyncio
from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import FileResponse
import psutil

from config import ADMIN_PASSWORD
import core.state as state
import core.analytics as analytics
from core.websocket import hub

router = APIRouter()


def check_admin(token: str) -> bool:
    if not token or not ADMIN_PASSWORD:
        return False
    exp = state.admin_tokens.get(token)
    if not exp or exp < time.time():
        state.admin_tokens.pop(token, None)
        return False
    return True


@router.get("/admin")
async def admin_page():
    return FileResponse("pages/admin/dashboard.html")


@router.get("/admin/login")
async def admin_login_page():
    return FileResponse("pages/admin/login.html")


@router.post("/admin/api/login")
async def admin_login(payload: dict):
    pw = str(payload.get("password", ""))
    if not ADMIN_PASSWORD or pw != ADMIN_PASSWORD:
        await asyncio.sleep(1)
        return {"ok": False, "error": "Неверный пароль"}
    token = secrets.token_urlsafe(32)
    state.admin_tokens[token] = time.time() + state.TOKEN_TTL
    return {"ok": True, "token": token}


@router.post("/admin/api/logout")
async def admin_logout(authorization: str = Header(default="")):
    token = authorization.replace("Bearer ", "").strip()
    state.admin_tokens.pop(token, None)
    return {"ok": True}


@router.get("/admin/api/check")
async def admin_check():
    return {
        "admin_password_set": bool(ADMIN_PASSWORD),
        "length": len(ADMIN_PASSWORD) if ADMIN_PASSWORD else 0,
    }


@router.get("/admin/api/stats")
async def admin_stats(token: str = Header(default="", alias="authorization")):
    if not check_admin(token.replace("Bearer ", "").strip()):
        raise HTTPException(status_code=401, detail="Unauthorized")
    analytics.cleanup_old()
    state.clicker_reset_if_needed()
    return {
        "health": analytics.project_health(),
        "metrics": analytics.all_metrics(),
        "uptime_sec": int(time.time() - state.started_at),
        "clicker_top": [
            {"nick": e["nick"], "score": e["score"], "rank": e["rank"]}
            for e in state.clicker_top
        ],
    }


@router.get("/admin/api/games")
async def admin_games_get(token: str = Header(default="", alias="authorization")):
    if not check_admin(token.replace("Bearer ", "").strip()):
        raise HTTPException(status_code=401, detail="Unauthorized")
    return {
        "games": [{"key": k, "title": v["title"], "enabled": v["enabled"], "status": v.get("status"), "url": v.get("url","")} for k, v in state.games_config.items()],
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
    return {
        "ok": True,
        "games": [{"key": k, "title": v["title"], "enabled": v["enabled"], "status": v.get("status"), "url": v.get("url","")} for k, v in state.games_config.items()],
    }


@router.post("/admin/api/theme")
async def admin_theme_set(payload: dict, token: str = Header(default="", alias="authorization")):
    if not check_admin(token.replace("Bearer ", "").strip()):
        raise HTTPException(status_code=401, detail="Unauthorized")
    theme = str(payload.get("theme", "classic"))
    if theme in ("classic", "retro", "notebook", "cyberpunk", "cozy"):
        state.theme_config["current"] = theme
    return {"ok": True, "theme": state.theme_config["current"]}
