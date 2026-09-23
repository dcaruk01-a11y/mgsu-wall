from fastapi import APIRouter, Header
import core.daily_tasks as tasks
import core.users as users

router = APIRouter()


def _token(authorization: str) -> str:
    return authorization.replace("Bearer ", "").strip()


@router.get("/api/tasks")
async def get_tasks(authorization: str = Header(default="")):
    user = await users.get_user_by_token(_token(authorization))
    if not user:
        return {"ok": False, "logged_in": False, "tasks": []}

    state = await tasks.get_or_create_day(user["uid"])
    # дополняем прогрессом
    out = []
    for t in state["tasks"]:
        key = t["key"]
        out.append({
            "key": key,
            "text": t["text"],
            "game": t["game"],
            "target": t["target"],
            "reward": t["reward"],
            "progress": state["progress"].get(key, 0),
            "done": key in state["claimed"],
        })
    return {"ok": True, "logged_in": True, "tasks": out}
