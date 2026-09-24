"""
Защита от перебора PIN.
3 неудачных попытки за 10 минут → блок на 15 минут.
Учёт по uid и по IP.
"""
import time, aiosqlite
from config import DB_PATH


# Настройки
MAX_FAILURES = 3           # сколько неудач
WINDOW_SECONDS = 600       # окно наблюдения (10 минут)
BLOCK_SECONDS = 900        # блокировка (15 минут)


async def db_init_login_guard():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS login_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uid TEXT,
                ip TEXT,
                ts REAL,
                success INTEGER
            )
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_login_attempts_uid_ts
            ON login_attempts (uid, ts)
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_login_attempts_ip_ts
            ON login_attempts (ip, ts)
        """)
        await db.commit()


async def record_attempt(uid: str, ip: str, success: bool):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO login_attempts (uid, ip, ts, success)
            VALUES (?,?,?,?)
        """, (uid or "", ip or "", time.time(), 1 if success else 0))
        await db.commit()


async def check_blocked(uid: str, ip: str):
    """
    Возвращает (заблокирован: bool, сколько_секунд_осталось: int).
    Проверяет и по uid, и по IP.
    """
    now = time.time()
    window_start = now - WINDOW_SECONDS

    async with aiosqlite.connect(DB_PATH) as db:
        # По uid
        if uid:
            cur = await db.execute("""
                SELECT ts, success FROM login_attempts
                WHERE uid=? AND ts > ?
                ORDER BY ts DESC
            """, (uid, window_start))
            rows = await cur.fetchall()

            result = _analyze(rows, now)
            if result[0]:
                return result

        # По IP
        if ip and ip != "unknown":
            cur = await db.execute("""
                SELECT ts, success FROM login_attempts
                WHERE ip=? AND ts > ?
                ORDER BY ts DESC
            """, (ip, window_start))
            rows = await cur.fetchall()

            result = _analyze(rows, now)
            if result[0]:
                return result

    return (False, 0)


def _analyze(rows, now):
    """Анализирует список попыток: возвращает (заблокирован, секунд осталось)."""
    if not rows:
        return (False, 0)

    failures = []
    for ts, success in rows:
        if success:
            # Успешный вход — сбрасываем неудачи
            return (False, 0)
        failures.append(ts)

    if len(failures) < MAX_FAILURES:
        return (False, 0)

    # Если >= MAX_FAILURES неудач — считаем, когда была последняя
    last_failure = max(failures)
    block_until = last_failure + BLOCK_SECONDS
    if now >= block_until:
        return (False, 0)

    return (True, int(block_until - now))


async def cleanup_old():
    """Удаляет записи старше 1 дня."""
    cutoff = time.time() - 86400
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM login_attempts WHERE ts < ?", (cutoff,))
        await db.commit()
