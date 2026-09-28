"""IP, часы, лента заходов, зоны."""
import json as _json
from fastapi import APIRouter, Header, HTTPException
import aiosqlite
from config import DB_PATH, today_str
import core.ip_tracking as ip_tracking
from core.admin.common import check_admin

router = APIRouter()


def _tok(token: str) -> str:
    return token.replace("Bearer ", "").strip()


# ═══════════════════════════════════════════════════════════
# ЖИВАЯ ЛЕНТА
# ═══════════════════════════════════════════════════════════
@router.get("/admin/api/feed")
async def admin_feed(days: int = 7, limit: int = 60,
                     token: str = Header(default="", alias="authorization")):
    if not check_admin(_tok(token)):
        raise HTTPException(status_code=401, detail="Unauthorized")
    feed = await ip_tracking.get_live_feed(limit=limit, days=days)
    return {"feed": feed}


# ═══════════════════════════════════════════════════════════
# ЗОНЫ IP
# ═══════════════════════════════════════════════════════════
@router.get("/admin/api/zones")
async def admin_zones(days: int = 7, sort: str = "visits",
                      token: str = Header(default="", alias="authorization")):
    if not check_admin(_tok(token)):
        raise HTTPException(status_code=401, detail="Unauthorized")
    zones = await ip_tracking.get_ip_zones(days=days, sort_by=sort)
    return {"zones": zones}


@router.post("/admin/api/zones/tag")
async def admin_zone_tag(payload: dict,
                         token: str = Header(default="", alias="authorization")):
    if not check_admin(_tok(token)):
        raise HTTPException(status_code=401, detail="Unauthorized")
    subnet = str(payload.get("subnet", ""))
    tag = str(payload.get("tag", "unknown"))
    label = str(payload.get("label", ""))
    if not subnet:
        raise HTTPException(status_code=400, detail="subnet required")
    return await ip_tracking.set_ip_tag(subnet, tag, label)


# ═══════════════════════════════════════════════════════════
# ЧАСЫ С УСТРОЙСТВАМИ
# ═══════════════════════════════════════════════════════════
@router.get("/admin/api/hours-full")
async def admin_hours_full(days: int = 7,
                           token: str = Header(default="", alias="authorization")):
    if not check_admin(_tok(token)):
        raise HTTPException(status_code=401, detail="Unauthorized")
    hours = await ip_tracking.get_hourly_full(days)
    summary = await ip_tracking.get_summary(days)
    return {"hours": hours, "summary": summary}


@router.get("/admin/api/hours")
async def admin_hours(days: int = 1, token: str = Header(default="", alias="authorization")):
    if not check_admin(_tok(token)):
        raise HTTPException(status_code=401, detail="Unauthorized")
    days = max(1, min(days, 30))
    return {
        "hours": await ip_tracking.get_hourly_stats(days),
        "devices": await ip_tracking.get_device_stats(days),
    }


# ═══════════════════════════════════════════════════════════
# ВОРОНКА
# ═══════════════════════════════════════════════════════════
@router.get("/admin/api/funnel")
async def admin_funnel(days: int = 7,
                       token: str = Header(default="", alias="authorization")):
    if not check_admin(_tok(token)):
        raise HTTPException(status_code=401, detail="Unauthorized")
    return await ip_tracking.get_funnel(days)


# ═══════════════════════════════════════════════════════════
# СВОДКА
# ═══════════════════════════════════════════════════════════
@router.get("/admin/api/summary")
async def admin_summary(days: int = 7,
                        token: str = Header(default="", alias="authorization")):
    if not check_admin(_tok(token)):
        raise HTTPException(status_code=401, detail="Unauthorized")
    return await ip_tracking.get_summary(days)


# ═══════════════════════════════════════════════════════════
# СТАРЫЕ ЭНДПОИНТЫ (совместимость)
# ═══════════════════════════════════════════════════════════
@router.get("/admin/api/ips")
async def admin_ips(token: str = Header(default="", alias="authorization")):
    if not check_admin(_tok(token)):
        raise HTTPException(status_code=401, detail="Unauthorized")
    return {
        "ips": await ip_tracking.get_ip_summary(),
        "geo": await ip_tracking.get_geo_summary(),
    }


@router.post("/admin/api/ips/tag")
async def admin_ip_tag(payload: dict, token: str = Header(default="", alias="authorization")):
    if not check_admin(_tok(token)):
        raise HTTPException(status_code=401, detail="Unauthorized")
    subnet = str(payload.get("subnet", ""))
    tag = str(payload.get("tag", "unknown"))
    label = str(payload.get("label", ""))
    if not subnet:
        raise HTTPException(status_code=400, detail="subnet required")
    return await ip_tracking.set_ip_tag(subnet, tag, label)


@router.get("/admin/api/tasks-summary")
async def admin_tasks_summary(token: str = Header(default="", alias="authorization")):
    if not check_admin(_tok(token)):
        raise HTTPException(status_code=401, detail="Unauthorized")

    today = today_str()
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT tasks, progress, claimed FROM user_tasks WHERE day=?",
            (today,)
        )
        rows = await cur.fetchall()

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
            "key": key, "text": s["text"], "reward": s["reward"],
            "taken": s["taken"], "done": s["done"], "pct": pct,
        })
    result.sort(key=lambda x: -x["done"])

    return {
        "day": today,
        "total_users": total_users,
        "total_completed": total_completed,
        "tasks": result,
    }
