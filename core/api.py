from fastapi import APIRouter, Header
from datetime import datetime
from config import MSK, TG_FEEDBACK_BOT_TOKEN, TG_ADMIN_ID
import httpx
import core.state as state
import core.analytics as analytics
from core.storage import make_snapshot, post_to_telegram

router = APIRouter()


@router.get("/status")
async def status_endpoint():
    now = datetime.now(MSK)
    sch = state.schedule_str()
    return {
        "open": state.is_open_now(),
        "opens_at": f"{sch['open_hour']:02d}:{sch['open_minute']:02d}",
        "closes_at": f"{sch['close_hour']:02d}:{sch['close_minute']:02d}",
        "open_hour": sch["open_hour"],
        "open_minute": sch["open_minute"],
        "close_hour": sch["close_hour"],
        "close_minute": sch["close_minute"],
        "force_override": sch["force_override"],
        "current_time_msk": now.strftime("%H:%M"),
    }


@router.post("/api/track")
async def api_track(payload: dict):
    uid = str(payload.get("uid", ""))[:64]
    analytics.track_visit(uid)
    return {"ok": True}


@router.post("/api/session")
async def api_session(payload: dict):
    try:
        dur = float(payload.get("duration", 0))
    except Exception:
        dur = 0
    analytics.track_session(dur)
    return {"ok": True}


@router.get("/api/games")
async def api_games():
    return {
        "games": [
            {
                "key": k,
                "title": v["title"],
                "enabled": v["enabled"],
                "status": v.get("status", "available"),
                "url": v.get("url", ""),
            }
            for k, v in state.games_config.items()
        ],
        "theme": state.theme_config["current"],
    }


@router.get("/api/dev-credits")
async def api_dev_credits():
    dc = state.dev_credits_config
    if not dc.get("enabled", True):
        return {"enabled": False}
    return {
        "enabled": True,
        "title": dc.get("title", ""),
        "subtitle": dc.get("subtitle", ""),
        "footer": dc.get("footer", ""),
        "cards": dc.get("cards", []),
    }


@router.get("/api/top-day")
async def api_top_day():
    """Топ-3 за сегодня — для блока на главной."""
    try:
        from core.top import top_day
        top = await top_day(3)
    except Exception as e:
        print("top-day error:", e)
        top = []
    return {"top": top}


@router.get("/snapshot")
async def manual_snapshot():
    path = await make_snapshot()
    await post_to_telegram(path)
    return {"ok": True, "path": path}


# ═══════════════════════════════════════════════════════════
# FEEDBACK — обратная связь от игроков
# ═══════════════════════════════════════════════════════════
@router.post("/api/feedback/app")
async def api_feedback_app(payload: dict, authorization: str = Header(default="")):
    """Приём обратной связи из попапа. Отправляет админу в Telegram."""
    stars = max(0, min(int(payload.get("stars", 0) or 0), 5))
    text = str(payload.get("text", ""))[:1000].strip()
    page = str(payload.get("page", ""))[:100]
    ua = str(payload.get("ua", ""))[:200]

    if stars <= 0:
        return {"ok": False, "error": "Нужна оценка"}

    # Определяем игрока
    uid = ""
    nick = "Гость"
    token = (authorization or "").replace("Bearer ", "").strip()
    if token:
        try:
            import core.users as users
            user = await users.get_user_by_token(token)
            if user:
                uid = user["uid"]
                nick = user["display_name"]
        except Exception:
            pass

    # Отправляем в ТГ
    if TG_FEEDBACK_BOT_TOKEN and TG_ADMIN_ID:
        stars_str = "⭐" * stars + "☆" * (5 - stars)
        msg = (
            f"💌 <b>Обратная связь из приложения</b>\n\n"
            f"<b>Оценка:</b> {stars_str} ({stars}/5)\n"
            f"<b>Игрок:</b> {nick}"
        )
        if uid:
            msg += f" (<code>{uid}</code>)"
        if page:
            msg += f"\n<b>Страница:</b> <code>{page}</code>"
        if text:
            safe = text.replace("<", "&lt;").replace(">", "&gt;")
            msg += f"\n\n<b>Текст:</b>\n{safe}"
        else:
            msg += f"\n\n<i>Без комментария</i>"

        try:
            api_url = f"https://api.telegram.org/bot{TG_FEEDBACK_BOT_TOKEN}/sendMessage"
            async with httpx.AsyncClient(timeout=10) as c:
                await c.post(api_url, json={
                    "chat_id": TG_ADMIN_ID,
                    "text": msg,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                })
        except Exception as e:
            print("feedback app send error:", e)

    return {"ok": True}
