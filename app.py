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
from feedback_bot import feedback_bot_loop

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/assets", StaticFiles(directory="assets"), name="assets")

app.include_router(pages_router)
app.include_router(themes_router)
app.include_router(api_router)
app.include_router(clicker_router)
app.include_router(admin_router)
app.include_router(ws_router)


@app.on_event("startup")
async def on_startup():
    await db_init()
    await db_init_stats()
    await load_history()
    asyncio.create_task(daily_loop())
    asyncio.create_task(feedback_bot_loop())
