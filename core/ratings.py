from fastapi import APIRouter, Header
import core.top as top
import core.users as users

router = APIRouter()


def _token(authorization: str) -> str:
    return authorization.replace("Bearer ", "").strip()


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

    my = None
    if user:
        my = await top.my_position(user["uid"])
        my["uid"] = user["uid"]
        my["nick"] = user["display_name"]

    return {
        "day": day,
        "week": week,
        "alltime": alltime,
        "week_label": top.week_label(),
        "me": my,
    }
