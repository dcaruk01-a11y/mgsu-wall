from fastapi import APIRouter, Header
import aiosqlite
import core.top as top
import core.users as users
from config import DB_PATH

router = APIRouter()


def _token(authorization: str) -> str:
    return authorization.replace("Bearer ", "").strip()


async def _attach_institutes(items: list) -> list:
    """Добавляет поле institute_short каждому игроку."""
    if not items:
        return items

    uids = [it.get("uid") for it in items if it.get("uid")]
    if not uids:
        return items

    placeholders = ",".join("?" for _ in uids)
    mapping = {}
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute(
                f"SELECT uid, COALESCE(institute, '') FROM users WHERE uid IN ({placeholders})",
                uids
            )
            rows = await cur.fetchall()
            mapping = {r[0]: r[1] for r in rows}
    except Exception as e:
        print("attach institutes error:", e)

    try:
        from core.institutes import get_short
    except Exception:
        get_short = lambda k: "—"

    for it in items:
        inst_key = mapping.get(it.get("uid"), "")
        it["institute"] = inst_key
        it["institute_short"] = get_short(inst_key) if inst_key else ""

    return items


@router.get("/ratings")
async def ratings_page():
    from fastapi.responses import FileResponse
    return FileResponse("pages/ratings.html")


@router.get("/api/ratings")
async def api_ratings(authorization: str = Header(default="")):
    user = await users.get_user_by_token(_token(authorization))

    day = await top.top_day(10)
    week = await top.top_week(10)
    alltime = await top.top_alltime(20)

    # ★ Добавляем институт каждому игроку в топах
    day = await _attach_institutes(day)
    week = await _attach_institutes(week)
    alltime = await _attach_institutes(alltime)

    my = None
    if user:
        my = await top.my_position(user["uid"])
        my["uid"] = user["uid"]
        my["nick"] = user["display_name"]
        my["coins"] = user.get("coins", 0)

    return {
        "day": day,
        "week": week,
        "alltime": alltime,
        "week_label": top.week_label(),
        "me": my,
    }
