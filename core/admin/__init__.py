"""Собирает все роутеры админки в один."""
from fastapi import APIRouter

from core.admin import auth, stats, settings, analytics, content, users, system, users_manage
import core.content_plan

router = APIRouter()
router.include_router(auth.router)
router.include_router(stats.router)
router.include_router(settings.router)
router.include_router(analytics.router)
router.include_router(content.router)
router.include_router(users.router)
router.include_router(system.router)
router.include_router(users_manage.router)
