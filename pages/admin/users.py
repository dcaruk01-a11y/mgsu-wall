"""Управление пользователями."""
import time, aiosqlite
from fastapi import APIRouter, Header, HTTPException
from config import DB_PATH
from core.admin.common import check_admin

router = APIRouter()


@router.get("/admin/api/users")
async def admin_users_list(
    token: str = Header(default="", alias="authorization"),
    search: str = "",
    limit: int = 100,
):
    if not check_admin(token.replace("Bearer ", "").strip()):
        raise HTTPException(status_code=401, detail="Unauthorized")

    limit = max(10, min(limit, 500))
    search = (search or "").strip()

    async with aiosqlite.connect(DB_PATH) as db:
        if search:
            sql = """
                SELECT uid, display_name, created_at, last_seen, streak, best_streak,
                       coins, total_score, games_played, active_char
                FROM users
                WHERE LOWER(display_name) LIKE ? OR LOWER(uid) LIKE ?
                ORDER BY last_seen DESC
                LIMIT ?
            """
            q = "%" + search.lower() + "%"
            cur = await db.execute(sql, (q, q, limit))
        else:
            sql = """
                SELECT uid, display_name, created_at, last_seen, streak, best_streak,
                       coins, total_score, games_played, active_char
                FROM users
                ORDER BY last_seen DESC
                LIMIT ?
            """
            cur = await db.execute(sql, (limit,))
        rows = await cur.fetchall()

        # Общее число
        cur2 = await db.execute("SELECT COUNT(*) FROM users")
        total = (await cur2.fetchone())[0]

        # Активные за 24ч и 7 дней
        now = time.time()
        cur3 = await db.execute("SELECT COUNT(*) FROM users WHERE last_seen > ?", (now - 86400,))
        active_24h = (await cur3.fetchone())[0]
        cur4 = await db.execute("SELECT COUNT(*) FROM users WHERE last_seen > ?", (now - 7 * 86400,))
        active_7d = (await cur4.fetchone())[0]

    users = []
    for r in rows:
        users.append({
            "uid": r[0],
            "display_name": r[1],
            "created_at": r[2],
            "last_seen": r[3],
            "streak": r[4] or 0,
            "best_streak": r[5] or 0,
            "coins": r[6] or 0,
            "total_score": r[7] or 0,
            "games_played": r[8] or 0,
            "active_char": r[9] or "student",
        })

    return {
        "total": total,
        "active_24h": active_24h,
        "active_7d": active_7d,
        "users": users,
    }
