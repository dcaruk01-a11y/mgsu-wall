"""
Защита от спама регистраций.
Максимум 3 регистрации с одного IP за 24 часа.
"""
import time, aiosqlite
from config import DB_PATH


MAX_REGISTRATIONS_PER_IP = 3
WINDOW_SECONDS = 86400  # 24 часа


async def db_init_registration_guard():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS registration_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ip TEXT,
                uid TEXT,
                ts REAL
            )
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_reg_attempts_ip_ts
            ON registration_attempts (ip, ts)
        """)
        await db.commit()


async def check_limit(ip: str):
    """
    Проверяет, не превышен ли лимит регистраций с IP.
    Возвращает (можно_ли, осталось_попыток).
    """
    if not ip or ip == "unknown":
        return (True, MAX_REGISTRATIONS_PER_IP)

    now = time.time()
    window_start = now - WINDOW_SECONDS

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            SELECT COUNT(*) FROM registration_attempts
            WHERE ip=? AND ts > ?
        """, (ip, window_start))
        count = (await cur.fetchone())[0]

    left = MAX_REGISTRATIONS_PER_IP - count
    if left <= 0:
        return (False, 0)
    return (True, left)


async def record_registration(ip: str, uid: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO registration_attempts (ip, uid, ts)
            VALUES (?,?,?)
        """, (ip or "unknown", uid or "", time.time()))
        await db.commit()


async def cleanup_old():
    cutoff = time.time() - 7 * 86400  # храним 7 дней
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM registration_attempts WHERE ts < ?", (cutoff,))
        await db.commit()
