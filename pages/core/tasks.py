import asyncio
from datetime import datetime, timedelta
from config import MSK
import core.state as state
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
                print("Готово!")
            else:
                print("Холст пустой — снимок не делаем")
            state.clicker_top = []
            state.clicker_day = ""
            print("Топ кликера сброшен")
        except Exception as e:
            print("Ошибка:", e)
