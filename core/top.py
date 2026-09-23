"""
Единая таблица результатов по всем играм.
Из неё строятся топы: день, неделя, всё время.
"""
import time, aiosqlite
from datetime import datetime
from config import DB_PATH, MSK, today_str


def week_str() -> str:
    iso = datetime.now(MSK).isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def week_label() -> str:
    now = datetime.now(MSK)
    iso = now.isocalendar()
    monday = now.fromordinal(now.toordinal() - now.weekday())
    sunday = monday.fromordinal(monday.toordinal() + 6)
    return f"{monday.strftime('%d.%m')} – {sunday.strftime('%d.%m')}"


async def db_init_top():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uid TEXT,
                nick TEXT,
                game TEXT,
                score INTEGER,
                day TEXT,
                week TEXT,
                ts REAL
            )
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_scores_day ON scores (day, score DESC)
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_scores_week ON scores (week, score DESC)
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_scores_uid ON scores (uid)
        """)
        await db.commit()


async def save_score(uid: str, nick: str, game: str, score: int):
    if not uid:
        return
    score = max(0, min(int(score), 100000))
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO scores (uid, nick, game, score, day, week, ts)
            VALUES (?,?,?,?,?,?,?)
        """, (uid, nick[:30], game[:20], score, today_str(), week_str(), time.time()))
        await db.commit()


async def top_day(limit: int = 10):
    """Топ за сегодня — по сумме очков за день, каждый uid один раз."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            SELECT uid, nick, SUM(score) as total, COUNT(*) as games
            FROM scores
            WHERE day = ?
            GROUP BY uid
            ORDER BY total DESC
            LIMIT ?
        """, (today_str(), limit))
        rows = await cur.fetchall()
    return [
        {"uid": r[0], "nick": r[1], "score": r[2], "games": r[3]}
        for r in rows
    ]


async def top_week(limit: int = 10):
    """Топ за неделю."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            SELECT uid, nick, SUM(score) as total, COUNT(*) as games
            FROM scores
            WHERE week = ?
            GROUP BY uid
            ORDER BY total DESC
            LIMIT ?
        """, (week_str(), limit))
        rows = await cur.fetchall()
    return [
        {"uid": r[0], "nick": r[1], "score": r[2], "games": r[3]}
        for r in rows
    ]


async def top_alltime(limit: int = 20):
    """Топ за всё время."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            SELECT uid, nick, SUM(score) as total, COUNT(*) as games
            FROM scores
            GROUP BY uid
            ORDER BY total DESC
            LIMIT ?
        """, (limit,))
        rows = await cur.fetchall()
    return [
        {"uid": r[0], "nick": r[1], "score": r[2], "games": r[3]}
        for r in rows
    ]


async def my_position(uid: str):
    """Возвращает позицию игрока в трёх топах."""
    if not uid:
        return {"day": None, "week": None, "all": None}

    today = today_str()
    wk = week_str()

    result = {"day": None, "week": None, "all": None}

    async with aiosqlite.connect(DB_PATH) as db:
        # день
        cur = await db.execute("""
            SELECT SUM(score) FROM scores WHERE day = ? AND uid = ?
        """, (today, uid))
        row = await cur.fetchone()
        my_day = row[0] or 0
        if my_day > 0:
            cur = await db.execute("""
                SELECT COUNT(*) + 1 FROM (
                    SELECT uid, SUM(score) s FROM scores WHERE day = ?
                    GROUP BY uid HAVING s > ?
                )
            """, (today, my_day))
            r2 = await cur.fetchone()
            result["day"] = {"pos": r2[0], "score": my_day}

        # неделя
        cur = await db.execute("""
            SELECT SUM(score) FROM scores WHERE week = ? AND uid = ?
        """, (wk, uid))
        row = await cur.fetchone()
        my_week = row[0] or 0
        if my_week > 0:
            cur = await db.execute("""
                SELECT COUNT(*) + 1 FROM (
                    SELECT uid, SUM(score) s FROM scores WHERE week = ?
                    GROUP BY uid HAVING s > ?
                )
            """, (wk, my_week))
            r2 = await cur.fetchone()
            result["week"] = {"pos": r2[0], "score": my_week}

        # всё время
        cur = await db.execute("""
            SELECT SUM(score) FROM scores WHERE uid = ?
        """, (uid,))
        row = await cur.fetchone()
        my_all = row[0] or 0
        if my_all > 0:
            cur = await db.execute("""
                SELECT COUNT(*) + 1 FROM (
                    SELECT uid, SUM(score) s FROM scores
                    GROUP BY uid HAVING s > ?
                )
            """, (my_all,))
            r2 = await cur.fetchone()
            result["all"] = {"pos": r2[0], "score": my_all}

    return result


async def archive_old_scores(days: int = 90):
    """Удаляет старые записи, чтобы таблица не разрасталась."""
    cutoff_ts = time.time() - days * 86400
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM scores WHERE ts < ?", (cutoff_ts,))
        await db.commit()
