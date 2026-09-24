"""Системная информация: память, CPU, uptime, размер БД."""
import os, time, aiosqlite
from fastapi import APIRouter, Header, HTTPException
from config import DB_PATH
import core.state as state
from core.websocket import hub
from core.admin.common import check_admin

router = APIRouter()


@router.get("/admin/api/system")
async def admin_system(token: str = Header(default="", alias="authorization")):
    if not check_admin(token.replace("Bearer ", "").strip()):
        raise HTTPException(status_code=401, detail="Unauthorized")

    mem_mb = None
    cpu_pct = None
    try:
        import psutil
        p = psutil.Process()
        mem_mb = round(p.memory_info().rss / 1024 / 1024, 1)
        cpu_pct = round(psutil.cpu_percent(interval=0.1), 1)
    except Exception:
        pass

    # Размер БД (если файл есть — в Turso мы его не имеем, но попробуем)
    db_size_kb = None
    try:
        if os.path.exists(DB_PATH):
            db_size_kb = round(os.path.getsize(DB_PATH) / 1024, 1)
    except Exception:
        pass

    # Количество записей в основных таблицах
    counts = {}
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            for table in ("users", "sessions", "scores", "visits", "daily_stats", "user_tasks", "strokes", "settings", "ip_tags"):
                try:
                    cur = await db.execute(f"SELECT COUNT(*) FROM {table}")
                    counts[table] = (await cur.fetchone())[0]
                except Exception:
                    counts[table] = None
    except Exception as e:
        print("system counts error:", e)

    uptime_sec = int(time.time() - state.started_at)

    return {
        "memory_mb": mem_mb,
        "cpu_pct": cpu_pct,
        "db_size_kb": db_size_kb,
        "uptime_sec": uptime_sec,
        "online": len(hub.clients),
        "tables": counts,
        "theme": state.theme_config["current"],
        "games_enabled": sum(1 for v in state.games_config.values() if v.get("enabled")),
        "games_total": len(state.games_config),
    }
