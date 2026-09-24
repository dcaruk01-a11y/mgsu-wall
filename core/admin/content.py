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
