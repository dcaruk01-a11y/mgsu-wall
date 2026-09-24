"""
Бот-публикатор контент-плана.
Работает в фоне, каждые 60 секунд проверяет расписание.
"""
import asyncio, time, httpx
from datetime import datetime
from config import MSK, TG_BOT_TOKEN, TG_CHAT_ID, TG_ADMIN_ID, today_str
import core.content_plan as cplan
import core.state as state


API = f"https://api.telegram.org/bot{TG_BOT_TOKEN}" if TG_BOT_TOKEN else ""


async def tg_send(chat_id, text, parse_mode="HTML"):
    if not API or not chat_id:
        return False
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.post(f"{API}/sendMessage", json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": parse_mode,
                "disable_web_page_preview": True,
            })
            return r.status_code == 200
    except Exception as e:
        print("content_publisher send error:", e)
        return False


# ============ ГЕНЕРАЦИЯ АВТО-ПОСТОВ ============

def _fmt_time(ts):
    if not ts:
        return '—'
    d = datetime.fromtimestamp(ts, MSK)
    return d.strftime('%d.%m в %H:%M')


async def build_stats_post():
    """📊 Статистика дня."""
    import core.analytics as analytics
    today = today_str()
    day = analytics.history.get(today, {})
    visits = day.get("visits", 0)
    uniques = analytics.uniq_count(day) if hasattr(analytics, 'uniq_count') else 0
    games = day.get("games", {})
    total_games = sum(games.values())

    if visits == 0:
        return None  # ничего не публикуем, если сегодня пусто

    lines = [
        "📊 <b>Статистика дня</b>",
        "",
        f"👥 Заходов: <b>{visits}</b>",
        f"🆔 Уникальных: <b>{uniques}</b>",
        f"🎮 Партий: <b>{total_games}</b>",
    ]
    if games:
        top = sorted(games.items(), key=lambda x: -x[1])[:3]
        top = [(k, v) for k, v in top if v > 0]
        if top:
            lines.append("")
            lines.append("<b>По играм:</b>")
            for k, v in top:
                lines.append(f"• {k}: {v}")

    lines.append("")
    lines.append("🔗 mgsu-wall.onrender.com/glavnaya")
    return "\n".join(lines)


async def build_wall_post():
    """🖼 Снимок стены дня."""
    import os
    from config import SNAPSHOT_DIR
    today = today_str()
    path = os.path.join(SNAPSHOT_DIR, f"{today}.png")
    if not os.path.exists(path):
        return None
    return {"photo": path, "caption": f"🖼 Стена дня — {today}"}


async def build_rating_post():
    """🏆 Рейтинг дня — топ-3 по очкам."""
    from core.top import top_day
    top = await top_day(3)
    if not top:
        return None

    lines = ["🏆 <b>Рейтинг дня</b>", ""]
    medals = ["🥇", "🥈", "🥉"]
    for i, t in enumerate(top):
        medal = medals[i] if i < 3 else "•"
        nick = t.get("nick") or "Аноним"
        score = t.get("score", 0)
        lines.append(f"{medal} <b>{nick}</b> — {score} очков")

    lines.append("")
    lines.append("🔗 mgsu.ru/ratings — полный рейтинг")
    return "\n".join(lines)


# ============ ПУБЛИКАЦИЯ ============

async def tg_send_photo(chat_id, path, caption=""):
    if not API or not chat_id:
        return False
    try:
        async with httpx.AsyncClient(timeout=60) as c:
            with open(path, "rb") as f:
                r = await c.post(
                    f"{API}/sendPhoto",
                    data={"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"},
                    files={"photo": f},
                )
                return r.status_code == 200
    except Exception as e:
        print("send_photo error:", e)
        return False


async def publish_slot(item):
    """Публикует один слот в канал."""
    slot = item["slot"]
    day = item["day"]
    label = item["label"]

    # === АВТО-слоты ===
    if slot == "stats":
        text = await build_stats_post()
        if text:
            ok = await tg_send(TG_CHAT_ID, text)
            await cplan.mark_published(day, slot)
            return ok
        else:
            await cplan.mark_skipped(day, slot)
            return False

    if slot == "wall":
        data = await build_wall_post()
        if data:
            ok = await tg_send_photo(TG_CHAT_ID, data["photo"], data["caption"])
            await cplan.mark_published(day, slot)
            return ok
        else:
            await cplan.mark_skipped(day, slot)
            return False

    if slot == "rating":
        text = await build_rating_post()
        if text:
            ok = await tg_send(TG_CHAT_ID, text)
            await cplan.mark_published(day, slot)
            return ok
        else:
            await cplan.mark_skipped(day, slot)
            return False

    # === РУЧНЫЕ слоты ===
    text = (item.get("text") or "").strip()
    if not text:
        # Нет текста — сообщаем админу, но в канал не публикуем
        await tg_send(TG_ADMIN_ID, f"⚠️ Слот «{label}» на {day} пуст. Пост не опубликован.")
        await cplan.mark_skipped(day, slot)
        return False

    ok = await tg_send(TG_CHAT_ID, text)
    if ok:
        await cplan.mark_published(day, slot)
    return ok


# ============ ЧЕК-ЛИСТ ============

async def send_morning_checklist():
    """В 9:30 присылает админу чек-лист по дню."""
    stats = await cplan.get_stats()
    now = datetime.now(MSK)
    day_name = now.strftime("%d.%m")

    text = (
        f"📅 <b>Чек-лист на {day_name}</b>\n\n"
        f"Заполнено: <b>{stats['filled']}</b>\n"
        f"Опубликовано: <b>{stats['published']}</b>\n"
        f"Пропущено: <b>{stats['skipped']}</b>\n"
        f"Пусто: <b>{stats['empty']}</b>\n\n"
        f"🔗 mgsu-wall.onrender.com/admin/content"
    )
    await tg_send(TG_ADMIN_ID, text)


# ============ ГЛАВНЫЙ ЦИКЛ ============

_last_checklist_day = ""


async def content_publisher_loop():
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        print("Content publisher: TG не настроен, выход")
        return

    print("Content publisher started")
    last_check_minute = ""

    while True:
        try:
            now = datetime.now(MSK)
            minute_key = now.strftime("%Y-%m-%d %H:%M")

            # Раз в минуту — проверяем слоты
            if minute_key != last_check_minute:
                last_check_minute = minute_key

                # Публикация слотов
                pending = await cplan.get_pending_for_now()
                for item in pending:
                    try:
                        ok = await publish_slot(item)
                        status = "✓" if ok else "✗"
                        print(f"content publish {status}: {item['day']} {item['slot']}")
                    except Exception as e:
                        print("publish_slot error:", e)

                # Чек-лист в 09:30
                global _last_checklist_day
                today = today_str()
                if now.hour == 9 and now.minute == 30 and _last_checklist_day != today:
                    _last_checklist_day = today
                    try:
                        await send_morning_checklist()
                        print("morning checklist sent")
                    except Exception as e:
                        print("checklist error:", e)

        except Exception as e:
            print("content_publisher loop error:", e)

        await asyncio.sleep(30)
