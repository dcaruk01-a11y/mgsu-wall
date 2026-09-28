"""Страницы админки, вход/выход, пометка админа."""
import time, secrets, asyncio
from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import FileResponse

from config import ADMIN_PASSWORD
import core.state as state
import core.ip_tracking as ip_tracking

router = APIRouter()


@router.get("/admin")
async def admin_page():
    return FileResponse("pages/admin/dashboard.html")


@router.get("/admin/login")
async def admin_login_page():
    return FileResponse("pages/admin/login.html")


@router.get("/admin/users")
async def admin_users_page():
    return FileResponse("pages/admin/users.html")


@router.get("/admin/player/{uid}")
async def admin_player_page(uid: str):
    return FileResponse("pages/admin/user.html")


@router.get("/admin/games")
async def admin_games_page():
    return FileResponse("pages/admin/games.html")


@router.get("/admin/schedule")
async def admin_schedule_page():
    return FileResponse("pages/admin/schedule.html")


@router.get("/admin/analytics")
async def admin_analytics_page():
    return FileResponse("pages/admin/analytics.html")


@router.get("/admin/design")
async def admin_design_page():
    return FileResponse("pages/admin/design.html")


@router.get("/admin/team")
async def admin_team_page():
    return FileResponse("pages/admin/team.html")


@router.get("/admin/links")
async def admin_links_page():
    return FileResponse("pages/admin/links.html")


@router.get("/admin/logs")
async def admin_logs_page():
    return FileResponse("pages/admin/logs.html")


@router.get("/admin/content")
async def admin_content_page():
    return FileResponse("pages/admin/content.html")


@router.get("/admin/system")
async def admin_system_page():
    return FileResponse("pages/admin/system.html")


@router.get("/admin/todo")
async def admin_todo_page():
    return FileResponse("pages/admin/todo.html")


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


@router.post("/admin/api/mark-admin")
async def admin_mark(visitor_id: str = "", authorization: str = Header(default="")):
    """
    Помечает visitor_id как админский.
    Вызывается после успешного логина в админку.
    Все заходы этого браузера исключаются из статистики.
    """
    token = authorization.replace("Bearer ", "").strip()
    if not token or token not in state.admin_tokens:
        raise HTTPException(status_code=401, detail="Unauthorized")
    exp = state.admin_tokens.get(token)
    if not exp or exp < time.time():
        raise HTTPException(status_code=401, detail="Token expired")

    visitor_id = (visitor_id or "").strip()[:64]
    if visitor_id:
        try:
            await ip_tracking.mark_admin_visitor(visitor_id)
        except Exception as e:
            print("mark_admin error:", e)
            raise HTTPException(status_code=500, detail="Ошибка пометки")

    return {"ok": True, "visitor_id": visitor_id}
