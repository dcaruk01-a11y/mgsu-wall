import io
from datetime import datetime, timedelta
from openpyxl import Workbook
import time, secrets, asyncio
from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import FileResponse, Response
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

@router.get("/admin/api/schedule")
async def admin_schedule_get(token: str = Header(default="", alias="authorization")):
    if not check_admin(token.replace("Bearer ", "").strip()):
        raise HTTPException(status_code=401, detail="Unauthorized")
    return {
        "schedule": state.schedule_str(),
        "is_open_now": state.is_open_now(),
    }


@router.post("/admin/api/schedule")
async def admin_schedule_set(payload: dict, token: str = Header(default="", alias="authorization")):
    if not check_admin(token.replace("Bearer ", "").strip()):
        raise HTTPException(status_code=401, detail="Unauthorized")

    if "open_hour" in payload:
        try:
            h = int(payload["open_hour"])
            if 0 <= h <= 23:
                state.schedule_config["open_hour"] = h
        except Exception:
            pass
    if "open_minute" in payload:
        try:
            m = int(payload["open_minute"])
            if 0 <= m <= 59:
                state.schedule_config["open_minute"] = m
        except Exception:
            pass
    if "close_hour" in payload:
        try:
            h = int(payload["close_hour"])
            if 0 <= h <= 23:
                state.schedule_config["close_hour"] = h
        except Exception:
            pass
    if "close_minute" in payload:
        try:
            m = int(payload["close_minute"])
            if 0 <= m <= 59:
                state.schedule_config["close_minute"] = m
        except Exception:
            pass

    if "force_override" in payload:
        v = payload["force_override"]
        if v is None:
            state.schedule_config["force_override"] = None
        elif isinstance(v, bool):
            state.schedule_config["force_override"] = v
        elif v in ("open", "on", True):
            state.schedule_config["force_override"] = True
        elif v in ("close", "off", False):
            state.schedule_config["force_override"] = False
        elif v == "auto":
            state.schedule_config["force_override"] = None

    return {
        "ok": True,
        "schedule": state.schedule_str(),
        "is_open_now": state.is_open_now(),
    }


@router.post("/admin/api/theme")
async def admin_theme_set(payload: dict, token: str = Header(default="", alias="authorization")):
    if not check_admin(token.replace("Bearer ", "").strip()):
        raise HTTPException(status_code=401, detail="Unauthorized")
    theme = str(payload.get("theme", "classic"))
    if theme in ("classic", "retro", "notebook", "cyberpunk", "cozy"):
        state.theme_config["current"] = theme
    return {"ok": True, "theme": state.theme_config["current"]}


# ============ ЭКСПОРТ В EXCEL ============

@router.get("/admin/api/export")
async def admin_export(period: str = "7", token: str = Header(default="", alias="authorization")):
    if not check_admin(token.replace("Bearer ", "").strip()):
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        days = int(period)
    except Exception:
        days = 7
    days = max(1, min(days, 90))

    cutoff = (datetime.now(MSK) - timedelta(days=days)).strftime("%Y-%m-%d")

    wb = Workbook()
    ws = wb.active
    ws.title = "Статистика"

    # Заголовки
    headers = [
        "Дата", "Заходы", "Уникальные", "Новые", "Вернувшиеся",
        "Стена", "Кликер", "Бродвей", "Кампус", "Грабли",
        "Ср. счёт кликера", "Ср. сессия (сек)",
    ]
    ws.append(headers)

    # Жирная строка заголовков
    for cell in ws[1]:
        cell.font = cell.font.copy(bold=True)

    # Данные
    for d in sorted(analytics.history.keys()):
        if d < cutoff:
            continue
        day = analytics.history[d]
        avg_score = round(sum(day["clicker_scores"]) / len(day["clicker_scores"])) if day["clicker_scores"] else 0
        avg_sess = round(sum(day["sessions"]) / len(day["sessions"])) if day["sessions"] else 0
        g = day["games"]
        ws.append([
            d,
            day["visits"],
            analytics.uniq_count(day),
            day["new"],
            day["returning"],
            g.get("wall", 0), g.get("clicker", 0), g.get("broadway", 0),
            g.get("campus", 0), g.get("grable", 0),
            avg_score,
            avg_sess,
        ])

    # Ширина колонок
    widths = [12, 10, 12, 10, 12, 8, 10, 10, 10, 8, 16, 16]
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[chr(64 + i)].width = w

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    filename = f"mgsu-stats-{days}d.xlsx"
    return Response(
        content=buf.read(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
