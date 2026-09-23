import asyncio
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from core.storage import db_init
from core.analytics import db_init_stats, load_history
from core.tasks import daily_loop
from core.websocket import router as ws_router
from core.api import router as api_router
from core.clicker import router as clicker_router
from core.admin import router as admin_router
from core.pages import router as pages_router
from core.themes import router as themes_router
from core.auth import router as auth_router
from core.users import db_init_users
from core.ip_tracking import db_init_ip
from core.top import db_init_top
from core.tasks import db_init_tasks
from core.game_score import router as game_score_router
from core.tasks_api import router as tasks_api_router
from core.ratings import router as ratings_router
from feedback_bot import feedback_bot_loop

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/assets", StaticFiles(directory="assets"), name="assets")

app.include_router(pages_router)
app.include_router(themes_router)
app.include_router(auth_router)
app.include_router(ratings_router)
app.include_router(game_score_router)
app.include_router(tasks_api_router)
app.include_router(api_router)
app.include_router(clicker_router)
app.include_router(admin_router)
app.include_router(ws_router)


@app.on_event("startup")
async def on_startup():
    await db_init()
    await db_init_stats()
    await db_init_users()
    await db_init_ip()
    await db_init_top()
    await db_init_tasks()
    await load_history()
