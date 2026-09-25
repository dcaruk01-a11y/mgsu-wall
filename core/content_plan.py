"""
Контент-план на неделю.
Хранит тексты постов и публикует их по расписанию.
"""
import json, time, aiosqlite
from datetime import datetime, timedelta
from config import DB_PATH, MSK, today_str


# Расписание слотов (МСК)
SLOTS = [
    {"key":"morning",  "hour":9,  "minute":0,  "label":"🌅 Игра дня"},
    {"key":"stats",    "hour":17, "minute":5,  "label":"📊 Статистика дня", "auto":True},
    {"key":"wall",     "hour":17, "minute":10, "label":"🖼 Стена дня", "auto":True},
    {"key":"extra",    "hour":18, "minute":0,  "label":"💡 Доп. пост"},
    {"key":"rating",   "hour":20, "minute":0,  "label":"🏆 Рейтинг дня", "auto":True},
    {"key":"author",   "hour":21, "minute":0,  "label":"📖 Пост автора"},
]

# Какие слоты в какие дни недели
WEEK_SCHEDULE = {
    # 0=Пн, 6=Вс
    0: ["morning","stats","wall","rating","author"],
    1: ["morning","stats","wall","extra","rating"],
    2: ["morning","stats","wall","rating"],
    3: ["morning","stats","wall","extra","rating"],
    4: ["morning","stats","wall","rating"],
    5: ["morning","stats","wall","extra","rating"],
    6: ["morning","stats","wall","rating"],
}


def week_key(dt=None):
    """Ключ недели вида 2026-W39."""
    dt = dt or datetime.now(MSK)
    iso = dt.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def week_dates(week_str):
    """Возвращает 7 дат (Пн-Вс) для недели."""
    year, wk = week_str.split("-W")
    year, wk = int(year), int(wk)
    monday = datetime.fromisocalendar(year, wk, 1)
    return [(monday + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]


async def db_init_content():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS content_plan (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                week TEXT,
                day TEXT,
                slot TEXT,
                text TEXT,
                status TEXT DEFAULT 'pending',
                published_at REAL,
                created_at REAL
            )
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_content_day_slot
            ON content_plan (day, slot)
        """)
        await db.commit()


async def get_week_plan(week_str):
    """Возвращает план недели: {day: {slot: {text, status, published_at}}}."""
    dates = week_dates(week_str)
    result = {}
    for d in dates:
        result[d] = {}
        for slot in SLOTS:
            result[d][slot["key"]] = {"text":"", "status":"empty", "published_at":None}

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            SELECT day, slot, text, status, published_at
            FROM content_plan WHERE week=?
        """, (week_str,))
        rows = await cur.fetchall()

    for r in rows:
        day, slot, text, status, published_at = r
        if day in result and slot in result[day]:
            result[day][slot] = {
                "text": text or "",
                "status": status or "pending",
                "published_at": published_at,
            }
    return result


async def save_slot(week_str, day, slot, text):
    """Сохраняет или обновляет текст одного слота."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            SELECT id, status FROM content_plan WHERE week=? AND day=? AND slot=?
        """, (week_str, day, slot))
        row = await cur.fetchone()

        if row:
            # Обновляем только если ещё не опубликовано
            if row[1] != "published":
                await db.execute(
                    "UPDATE content_plan SET text=?, status='pending' WHERE id=?",
                    (text, row[0])
                )
        else:
            await db.execute("""
                INSERT INTO content_plan (week, day, slot, text, status, created_at)
                VALUES (?,?,?,?,?,?)
            """, (week_str, day, slot, text, "pending", time.time()))
        await db.commit()


async def mark_published(day, slot):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE content_plan SET status='published', published_at=?
            WHERE day=? AND slot=?
        """, (time.time(), day, slot))
        await db.commit()


async def mark_skipped(day, slot):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE content_plan SET status='skipped'
            WHERE day=? AND slot=?
        """, (day, slot))
        await db.commit()


async def get_pending_for_now():
    """
    Возвращает посты, которые надо опубликовать прямо сейчас.
    Проверяет день, час, минуту ± 2 минуты.
    """
    now = datetime.now(MSK)
    day = now.strftime("%Y-%m-%d")
    weekday = now.weekday()

    slots_today = WEEK_SCHEDULE.get(weekday, [])
    result = []

    async with aiosqlite.connect(DB_PATH) as db:
        for slot_key in slots_today:
            slot_def = next((s for s in SLOTS if s["key"] == slot_key), None)
            if not slot_def:
                continue

            target = now.replace(hour=slot_def["hour"], minute=slot_def["minute"], second=0, microsecond=0)
            diff = abs((now - target).total_seconds())
            if diff > 120:
                continue

            cur = await db.execute("""
                SELECT id, text, status FROM content_plan
                WHERE day=? AND slot=?
            """, (day, slot_key))
            row = await cur.fetchone()

            if not row:
                result.append({
                    "day": day, "slot": slot_key,
                    "label": slot_def["label"],
                    "auto": slot_def.get("auto", False),
                    "text": "", "status": "empty"
                })
                continue

            if row[2] == "pending":
                result.append({
                    "day": day, "slot": slot_key,
                    "label": slot_def["label"],
                    "auto": slot_def.get("auto", False),
                    "text": row[1] or "",
                    "status": "pending"
                })

    return result


async def get_stats(week_str=None):
    """Статистика: сколько слотов заполнено, опубликовано, пропущено."""
    week_str = week_str or week_key()
    dates = week_dates(week_str)

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            SELECT day, slot, status FROM content_plan WHERE week=?
        """, (week_str,))
        rows = await cur.fetchall()

    filled = 0
    published = 0
    skipped = 0
    total_planned = 0

    for r in rows:
        day, slot, status = r
        if status == "published":
            published += 1
        elif status == "skipped":
            skipped += 1
        elif status == "pending":
            filled += 1

    # Всего слотов на неделю
    for wd in range(7):
        total_planned += len(WEEK_SCHEDULE.get(wd, []))

    return {
        "week": week_str,
        "total_planned": total_planned,
        "filled": filled,
        "published": published,
        "skipped": skipped,
        "empty": total_planned - filled - published - skipped,
    }


# ============ ШАБЛОНЫ ПРОМПТОВ ============

GAMES_BY_WEEKDAY = {
    0: {"title":"Экран", "hint":"арт-объект, ты рисуешь с телефона — штрихи летят на большой экран"},
    1: {"title":"Стена",  "hint":"рисуй пальцем, смотри как линии появляются в реальном времени"},
    2: {"title":"Кликер", "hint":"30 секунд, максимум кликов, 7 рангов от Студента до Легенды"},
    3: {"title":"Бродвей","hint":"пробеги по коридору, собирай кофе и конспекты"},
    4: {"title":"Тетрис", "hint":"складывай дома и башни МГСУ, полные линии сгорают"},
    5: {"title":"Грабли", "hint":"открой безопасные клетки, не наступи на грабли"},
    6: {"title":"Построй кампус", "hint":"голосуй за улучшения МГСУ"},
}


def build_prompt(slot_key, day_str):
    """Возвращает готовый промпт для DeepSeek."""
    try:
        dt = datetime.strptime(day_str, "%Y-%m-%d")
        wd = dt.weekday()
    except Exception:
        wd = 0

    game = GAMES_BY_WEEKDAY.get(wd, {"title":"Игра", "hint":""})

    prompts = {
        "morning": (
            f"Напиши дружелюбный пост для Telegram-канала студенческих игр НИУ МГСУ.\n"
            f"Сегодня играем в «{game['title']}». Что это: {game['hint']}.\n\n"
            f"Расскажи кратко (2-3 предложения) что это за игра и почему стоит поиграть.\n"
            f"Тон: дружелюбный, молодёжный, с эмодзи. Длина: 4-5 строк. Не пиши «уважаемые студенты», пиши «ты»."
        ),
        "extra": (
            f"Напиши пост для канала игр МГСУ на тему: мем про студентов-строителей.\n"
            f"Тема на сегодня: [ТВОЯ ТЕМА — впиши].\n"
            f"2-3 строки юмора без пошлости, с эмодзи."
        ),
        "author": (
            f"Напиши авторский пост от первого лица для канала игр МГСУ.\n"
            f"Тема: [ТВОЯ ТЕМА — например, «Зачем этот проект»].\n"
            f"Тезисы: [ВПИШИ ТЕЗИСЫ].\n"
            f"Стиль: искренне, 5-7 строк, с эмодзи."
        ),
    }
    return prompts.get(slot_key, "")
