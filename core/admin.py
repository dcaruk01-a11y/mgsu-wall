import io, time, secrets, asyncio
from datetime import datetime, timedelta
from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import FileResponse, Response
from openpyxl import Workbook
import psutil

from config import ADMIN_PASSWORD, MSK
import core.state as state
import core.analytics as analytics
import core.ip_tracking as ip_tracking
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
        elif v in ("open", "on"):
            state.schedule_config["force_override"] = True
        elif v in ("close", "off"):
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

    headers = [
        "Дата", "Заходы", "Уникальные", "Новые", "Вернувшиеся",
        "Стена", "Кликер", "Бродвей", "Кампус", "Грабли",
        "Ср. счёт кликера", "Ср. сессия (сек)",
    ]
    ws.append(headers)

    for cell in ws[1]:
        cell.font = cell.font.copy(bold=True)

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


# ============ IP И ЧАСЫ ============

@router.get("/admin/api/ips")
async def admin_ips(token: str = Header(default="", alias="authorization")):
    if not check_admin(token.replace("Bearer ", "").strip()):
        raise HTTPException(status_code=401, detail="Unauthorized")
    return {
        "ips": await ip_tracking.get_ip_summary(),
        "geo": await ip_tracking.get_geo_summary(),
    }


@router.post("/admin/api/ips/tag")
async def admin_ip_tag(payload: dict, token: str = Header(default="", alias="authorization")):
    if not check_admin(token.replace("Bearer ", "").strip()):
        raise HTTPException(status_code=401, detail="Unauthorized")
    subnet = str(payload.get("subnet", ""))
    tag = str(payload.get("tag", "unknown"))
    label = str(payload.get("label", ""))
    if not subnet:
        raise HTTPException(status_code=400, detail="subnet required")
    return await ip_tracking.set_ip_tag(subnet, tag, label)


@router.get("/admin/api/hours")
async def admin_hours(days: int = 1, token: str = Header(default="", alias="authorization")):
    if not check_admin(token.replace("Bearer ", "").strip()):
        raise HTTPException(status_code=401, detail="Unauthorized")
    days = max(1, min(days, 30))
    return {
        "hours": await ip_tracking.get_hourly_stats(days),
        "devices": await ip_tracking.get_device_stats(days),
    }


# ============ СВОДКА ПО ЗАДАНИЯМ ============

@router.get("/admin/api/tasks-summary")
async def admin_tasks_summary(token: str = Header(default="", alias="authorization")):
    if not check_admin(token.replace("Bearer ", "").strip()):
        raise HTTPException(status_code=401, detail="Unauthorized")

    import json as _json
    import aiosqlite
    from config import DB_PATH, today_str

    today = today_str()
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT tasks, progress, claimed FROM user_tasks WHERE day=?",
            (today,)
        )
        rows = await cur.fetchall()

    # Агрегат: для каждого типа задания — сколько юзеров взяли, сколько выполнили
    stats = {}
    total_users = len(rows)
    total_completed = 0

    for r in rows:
        try:
            tasks_list = _json.loads(r[0])
            progress = _json.loads(r[1])
            claimed = _json.loads(r[2])
        except Exception:
            continue
        for t in tasks_list:
            key = t["key"]
            if key not in stats:
                stats[key] = {"text": t["text"], "reward": t["reward"], "taken": 0, "done": 0}
            stats[key]["taken"] += 1
            if key in claimed:
                stats[key]["done"] += 1
                total_completed += 1

    result = []
    for key, s in stats.items():
        pct = round(s["done"] / s["taken"] * 100) if s["taken"] else 0
        result.append({
            "key": key,
            "text": s["text"],
            "reward": s["reward"],
            "taken": s["taken"],
            "done": s["done"],
            "pct": pct,
        })
    result.sort(key=lambda x: -x["done"])

    return {
        "day": today,
        "total_users": total_users,
        "total_completed": total_completed,
        "tasks": result,
    }


# ============ АКТИВ РАЗРАБОТЧИКОВ ============

@router.get("/admin/api/dev-credits")
async def admin_dev_credits_get(token: str = Header(default="", alias="authorization")):
    if not check_admin(token.replace("Bearer ", "").strip()):
        raise HTTPException(status_code=401, detail="Unauthorized")
    return state.dev_credits_config


@router.post("/admin/api/dev-credits")
async def admin_dev_credits_set(payload: dict, token: str = Header(default="", alias="authorization")):
    if not check_admin(token.replace("Bearer ", "").strip()):
        raise HTTPException(status_code=401, detail="Unauthorized")

    if "enabled" in payload:
        state.dev_credits_config["enabled"] = bool(payload["enabled"])
    if "title" in payload:
        state.dev_credits_config["title"] = str(payload["title"])[:80]
    if "subtitle" in payload:
        state.dev_credits_config["subtitle"] = str(payload["subtitle"])[:200]
    if "footer" in payload:
        state.dev_credits_config["footer"] = str(payload["footer"])[:300]
    if "cards" in payload and isinstance(payload["cards"], list):
        clean = []
        for c in payload["cards"][:12]:
            if not isinstance(c, dict):
                continue
            clean.append({
                "role": str(c.get("role", ""))[:40],
                "name": str(c.get("name", ""))[:60],
                "note": str(c.get("note", ""))[:80],
            })
        state.dev_credits_config["cards"] = clean

    await state.save_dev_credits()
    return {"ok": True, "config": state.dev_credits_config}
