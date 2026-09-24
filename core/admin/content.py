"""Управление контентом: актив разработчиков."""
from fastapi import APIRouter, Header, HTTPException
import core.state as state
from core.admin.common import check_admin

router = APIRouter()


@router.get("/admin/api/dev-credits")
async def admin_dev_credits_get(token: str = Header(default="", alias="authorization")):
    if not check_admin(token.replace("Bearer ", "").strip()):
        raise HTTPException(status_code=401, detail="Unauthorized")
    return state.dev_credits_config


@router.post("/admin/api/dev-credits")
async def admin_dev_credits_set(payload: dict, token: str = Header(default="", alias="authorization")):
    if not check_admin(token.replace("Bearer ", "").strip()):
        raise HTTPException(status_code=401, detail="Unauthorized")

    if "enabled" in payload:
        state.dev_credits_config["enabled"] = bool(payload["enabled"])
    if "title" in payload:
        state.dev_credits_config["title"] = str(payload["title"])[:80]
    if "subtitle" in payload:
        state.dev_credits_config["subtitle"] = str(payload["subtitle"])[:200]
    if "footer" in payload:
        state.dev_credits_config["footer"] = str(payload["footer"])[:300]
    if "cards" in payload and isinstance(payload["cards"], list):
        clean = []
        for c in payload["cards"][:12]:
            if not isinstance(c, dict):
                continue
            clean.append({
                "role": str(c.get("role", ""))[:40],
                "name": str(c.get("name", ""))[:60],
                "note": str(c.get("note", ""))[:80],
            })
        state.dev_credits_config["cards"] = clean

    await state.save_dev_credits()
    return {"ok": True, "config": state.dev_credits_config}


# ============ КОНТЕНТ-ПЛАН ============

import core.content_plan as cplan
from datetime import datetime
from config import MSK


@router.get("/admin/api/content/plan")
async def admin_content_plan_get(week: str = "", token: str = Header(default="", alias="authorization")):
    if not check_admin(token.replace("Bearer ", "").strip()):
        raise HTTPException(status_code=401, detail="Unauthorized")
    wk = week or cplan.week_key()
    plan = await cplan.get_week_plan(wk)
    stats = await cplan.get_stats(wk)
    return {"week": wk, "plan": plan, "stats": stats, "slots": cplan.SLOTS, "schedule": {str(k): v for k, v in cplan.WEEK_SCHEDULE.items()}}


@router.post("/admin/api/content/slot")
async def admin_content_slot_set(payload: dict, token: str = Header(default="", alias="authorization")):
    if not check_admin(token.replace("Bearer ", "").strip()):
        raise HTTPException(status_code=401, detail="Unauthorized")
    week = str(payload.get("week", ""))
    day = str(payload.get("day", ""))
    slot = str(payload.get("slot", ""))
    text = str(payload.get("text", ""))
    if not (week and day and slot):
        raise HTTPException(status_code=400, detail="week, day, slot required")
    await cplan.save_slot(week, day, slot, text)
    return {"ok": True}


@router.post("/admin/api/content/skip")
async def admin_content_skip(payload: dict, token: str = Header(default="", alias="authorization")):
    if not check_admin(token.replace("Bearer ", "").strip()):
        raise HTTPException(status_code=401, detail="Unauthorized")
    day = str(payload.get("day", ""))
    slot = str(payload.get("slot", ""))
    if not (day and slot):
        raise HTTPException(status_code=400, detail="day, slot required")
    await cplan.mark_skipped(day, slot)
    return {"ok": True}


@router.get("/admin/api/content/prompt")
async def admin_content_prompt(day: str = "", slot: str = "", token: str = Header(default="", alias="authorization")):
    if not check_admin(token.replace("Bearer ", "").strip()):
        raise HTTPException(status_code=401, detail="Unauthorized")
    prompt = cplan.build_prompt(slot, day)
    return {"prompt": prompt}


@router.post("/admin/api/content/test-publish")
async def admin_content_test_publish(payload: dict, token: str = Header(default="", alias="authorization")):
    """Тестовая публикация поста в канал — для проверки настроек."""
    if not check_admin(token.replace("Bearer ", "").strip()):
        raise HTTPException(status_code=401, detail="Unauthorized")

    text = str(payload.get("text", "")).strip()
    if not text:
        raise HTTPException(status_code=400, detail="Текст пустой")

    from core.content_publisher import tg_send
    from config import TG_CHAT_ID

    if not TG_CHAT_ID:
        raise HTTPException(status_code=400, detail="TG_CHAT_ID не настроен")

    ok = await tg_send(TG_CHAT_ID, text)
    return {"ok": ok, "sent_to": TG_CHAT_ID}
