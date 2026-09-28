from fastapi import APIRouter, Header, HTTPException
from datetime import datetime
from config import MSK, TG_FEEDBACK_BOT_TOKEN, TG_ADMIN_ID
import httpx, time, aiosqlite
from config import DB_PATH
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
# ИНСТИТУТЫ
# ═══════════════════════════════════════════════════════════

@router.get("/api/institutes")
async def api_institutes():
    from core.institutes import INSTITUTES, get_institutes_rating
    rating = await get_institutes_rating()
    return {"ok": True, "institutes": INSTITUTES, "rating": rating}


@router.get("/api/institutes/top")
async def api_institutes_top():
    from core.institutes import get_institutes_rating
    rating = await get_institutes_rating(3)
    return {"ok": True, "top": rating}


@router.get("/api/institutes/my")
async def api_my_institute(authorization: str = Header(default="")):
    import core.users as users
    from core.institutes import get_player_institute_info

    token = (authorization or "").replace("Bearer ", "").strip()
    user = await users.get_user_by_token(token) if token else None
    if not user:
        raise HTTPException(status_code=401, detail="Не авторизован")

    inst_key = user.get("institute") or ""
    if not inst_key:
        return {"ok": True, "has_institute": False}

    info = await get_player_institute_info(user["uid"], inst_key)
    return {"ok": True, "has_institute": True, "info": info}


@router.get("/api/institutes/players")
async def api_institute_players_q(key: str = "", limit: int = 20):
    from core.institutes import INSTITUTE_MAP, get_institute_players
    if key not in INSTITUTE_MAP:
        raise HTTPException(status_code=404, detail="Институт не найден")
    limit = max(5, min(limit, 50))
    players = await get_institute_players(key, limit)
    return {"ok": True, "players": players}


@router.get("/api/institutes/{key}/players")
async def api_institute_players(key: str):
    from core.institutes import INSTITUTE_MAP, get_institute_players
    if key not in INSTITUTE_MAP:
        raise HTTPException(status_code=404, detail="Институт не найден")
    players = await get_institute_players(key, 20)
    return {"ok": True, "players": players}


@router.post("/api/institutes/set")
async def api_institutes_set(payload: dict, authorization: str = Header(default="")):
    import core.users as users
    from core.institutes import get_institute

    token = (authorization or "").replace("Bearer ", "").strip()
    user = await users.get_user_by_token(token) if token else None
    if not user:
        raise HTTPException(status_code=401, detail="Не авторизован")

    key = str(payload.get("institute", "")).strip()
    inst = get_institute(key)
    if not inst:
        raise HTTPException(status_code=400, detail="Неизвестный институт")

    r = await users.set_institute(user["uid"], key)
    if not r["ok"]:
        raise HTTPException(status_code=400, detail=r.get("error", "Ошибка"))

    return {"ok": True, "institute": key, "was_change": r.get("was_change", False)}


# ═══════════════════════════════════════════════════════════
# ДОСТИЖЕНИЯ
# ═══════════════════════════════════════════════════════════

@router.get("/api/achievements")
async def api_achievements(authorization: str = Header(default="")):
    from core.achievements import ACHIEVEMENTS, get_user_achievements
    import core.users as users

    token = (authorization or "").replace("Bearer ", "").strip()
    user = await users.get_user_by_token(token) if token else None

    if not user:
        return {
            "ok": True,
            "logged_in": False,
            "achievements": [
                {**a, "unlocked": False, "unlocked_at": None}
                for a in ACHIEVEMENTS
            ],
            "total": len(ACHIEVEMENTS),
            "unlocked": 0,
        }

    unlocked_map = await get_user_achievements(user["uid"])

    result = []
    for a in ACHIEVEMENTS:
        result.append({
            **a,
            "unlocked": a["key"] in unlocked_map,
            "unlocked_at": unlocked_map.get(a["key"]),
        })

    return {
        "ok": True,
        "logged_in": True,
        "achievements": result,
        "total": len(ACHIEVEMENTS),
        "unlocked": len(unlocked_map),
    }


@router.post("/api/achievements/check")
async def api_achievements_check(authorization: str = Header(default="")):
    from core.achievements import check_and_grant
    import core.users as users

    token = (authorization or "").replace("Bearer ", "").strip()
    user = await users.get_user_by_token(token) if token else None
    if not user:
        raise HTTPException(status_code=401, detail="Не авторизован")

    granted = await check_and_grant(user["uid"], user)

    return {
        "ok": True,
        "granted": [
            {"key": a["key"], "name": a["name"], "emoji": a["emoji"]}
            for a in granted
        ],
    }


# ═══════════════════════════════════════════════════════════
# РАМКИ
# ═══════════════════════════════════════════════════════════

@router.get("/api/frames/catalog")
async def api_frames_catalog(authorization: str = Header(default="")):
    from core.frames import FRAMES, get_user_frames
    import core.users as users

    token = (authorization or "").replace("Bearer ", "").strip()
    user = await users.get_user_by_token(token) if token else None

    if not user:
        return {
            "ok": True,
            "logged_in": False,
            "coins": 0,
            "active_frame": "",
            "items": [
                {**f, "owned": False, "active": False, "can_afford": False}
                for f in FRAMES
            ],
        }

    owned_list = await get_user_frames(user["uid"])
    owned_keys = {f["key"] for f in owned_list}
    active = user.get("active_frame", "") or ""
    coins = user.get("coins", 0) or 0

    items = []
    for f in FRAMES:
        items.append({
            **f,
            "owned": f["key"] in owned_keys,
            "active": f["key"] == active,
            "can_afford": coins >= f["price"],
        })

    return {
        "ok": True,
        "logged_in": True,
        "coins": coins,
        "active_frame": active,
        "items": items,
    }


@router.post("/api/frames/buy")
async def api_frames_buy(payload: dict, authorization: str = Header(default="")):
    from core.frames import buy_frame
    import core.users as users

    token = (authorization or "").replace("Bearer ", "").strip()
    user = await users.get_user_by_token(token) if token else None
    if not user:
        raise HTTPException(status_code=401, detail="Не авторизован")

    key = str(payload.get("key", "")).strip()
    r = await buy_frame(user["uid"], key, user.get("coins", 0))
    if not r["ok"]:
        raise HTTPException(status_code=400, detail=r.get("error", "Ошибка"))
    return r


@router.post("/api/frames/equip")
async def api_frames_equip(payload: dict, authorization: str = Header(default="")):
    from core.frames import equip_frame
    import core.users as users

    token = (authorization or "").replace("Bearer ", "").strip()
    user = await users.get_user_by_token(token) if token else None
    if not user:
        raise HTTPException(status_code=401, detail="Не авторизован")

    key = str(payload.get("key", "")).strip()
    r = await equip_frame(user["uid"], key)
    if not r["ok"]:
        raise HTTPException(status_code=400, detail=r.get("error", "Ошибка"))
    return r


# ═══════════════════════════════════════════════════════════
# FEEDBACK
# ═══════════════════════════════════════════════════════════

@router.get("/api/feedback/check")
async def api_feedback_check(authorization: str = Header(default="")):
    token = (authorization or "").replace("Bearer ", "").strip()
    if not token:
        return {"ok": True, "pending": False}
    try:
        import core.users as users
        user = await users.get_user_by_token(token)
        if not user:
            return {"ok": True, "pending": False}

        uid = user["uid"]
        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute("""
                SELECT COALESCE(feedback_request_at, 0), COALESCE(feedback_seen_at, 0)
                FROM users WHERE uid=?
            """, (uid,))
            row = await cur.fetchone()

        if not row:
            return {"ok": True, "pending": False}

        req_at, seen_at = row[0] or 0, row[1] or 0
        pending = req_at > 0 and seen_at < req_at
        return {"ok": True, "pending": pending, "requested_at": req_at}
    except Exception as e:
        print("feedback check error:", e)
        return {"ok": True, "pending": False}


@router.post("/api/feedback/seen")
async def api_feedback_seen(authorization: str = Header(default="")):
    token = (authorization or "").replace("Bearer ", "").strip()
    if not token:
        return {"ok": False}
    try:
        import core.users as users
        user = await users.get_user_by_token(token)
        if not user:
            return {"ok": False}
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "UPDATE users SET feedback_seen_at=? WHERE uid=?",
                (time.time(), user["uid"])
            )
            await db.commit()
        return {"ok": True}
    except Exception as e:
        print("feedback seen error:", e)
        return {"ok": False}


@router.post("/api/feedback/app")
async def api_feedback_app(payload: dict, authorization: str = Header(default="")):
    stars = max(0, min(int(payload.get("stars", 0) or 0), 5))
    text = str(payload.get("text", ""))[:1000].strip()
    page = str(payload.get("page", ""))[:100]
    ua = str(payload.get("ua", ""))[:200]

    if stars <= 0:
        return {"ok": False, "error": "Нужна оценка"}

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

    if uid:
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute("""
                    UPDATE users SET feedback_request_at=0, feedback_seen_at=? WHERE uid=?
                """, (time.time(), uid))
                await db.commit()
        except Exception:
            pass

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
