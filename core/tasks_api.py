from fastapi import APIRouter, Header
import core.daily_tasks as tasks
import core.users as users

router = APIRouter()


def _token(authorization: str) -> str:
    return authorization.replace("Bearer ", "").strip()


def _task_out(t, progress, claimed):
    return {
        "key": t["key"],
        "text": t["text"],
        "game": t["game"],
        "target": t["target"],
        "reward": t["reward"],
        "progress": progress.get(t["key"], 0),
        "done": t["key"] in claimed,
    }


@router.get("/api/tasks")
async def get_tasks(authorization: str = Header(default="")):
    """Все задания на сегодня (для профиля)."""
    user = await users.get_user_by_token(_token(authorization))
    if not user:
        return {"ok": False, "logged_in": False, "tasks": []}

    state = await tasks.get_or_create_day(user["uid"])
    out = [_task_out(t, state["progress"], state["claimed"]) for t in state["tasks"]]
    return {"ok": True, "logged_in": True, "tasks": out}


@router.get("/api/tasks/game/{game_key}")
async def get_tasks_for_game(game_key: str, authorization: str = Header(default="")):
    """Задания по конкретной игре (для модалки на главной)."""
    user = await users.get_user_by_token(_token(authorization))
    if not user:
        return {"ok": True, "logged_in": False, "tasks": []}

    game_key = (game_key or "").strip()
    state = await tasks.get_or_create_day(user["uid"])
    out = []
    for t in state["tasks"]:
        if t["game"] == game_key:
            out.append(_task_out(t, state["progress"], state["claimed"]))
    return {"ok": True, "logged_in": True, "tasks": out}
