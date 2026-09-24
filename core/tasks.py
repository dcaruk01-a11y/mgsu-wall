import asyncio
from datetime import datetime, timedelta
from config import MSK
import core.analytics as analytics
import core.top as top
from core.storage import load_today_strokes, make_snapshot, post_to_telegram, clear_today
from core.websocket import hub


async def daily_loop():
    while True:
        now = datetime.now(MSK)
        target = now.replace(hour=17, minute=0, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        wait = (target - now).total_seconds()
        print(f"До снимка: {wait / 3600:.1f} ч")
        await asyncio.sleep(wait)
        try:
            strokes = await load_today_strokes()
            if strokes:
                print("Снимок дня...")
                path = await make_snapshot()
                await post_to_telegram(path)
                await clear_today()
                await hub.broadcast({"type": "reset"})
                await analytics.archive_day()
                print("Готово!")
            else:
                print("Холст пустой — снимок не делаем")
            state.clicker_top = []
            state.clicker_day = ""
            print("Топ кликера сброшен")

                        try:
                from core.login_guard import cleanup_old as lg_cleanup
                await lg_cleanup()
                print("login_attempts очищены")
            except Exception as e:
                print("login_guard cleanup error:", e)

            try:
                await top.archive_old_scores(90)
                print("Старые результаты очищены (90+ дней)")
            except Exception as e:
                print("archive scores error:", e)
            analytics.cleanup_old()
            print("Старая статистика очищена")
        except Exception as e:
            print("Ошибка:", e)
