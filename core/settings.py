"""
Хранилище настроек в SQLite/Turso.
Переживает засыпание сервера (но не деплой).
"""
import time, aiosqlite
from config import DB_PATH


async def db_init_settings():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at REAL
            )
        """)
        await db.commit()


async def get_setting(key: str, default=None):
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute("SELECT value FROM settings WHERE key=?", (key,))
            row = await cur.fetchone()
        if row:
            return row[0]
    except Exception as e:
        print("get_setting error:", e)
    return default


async def set_setting(key: str, value: str):
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                INSERT OR REPLACE INTO settings (key, value, updated_at)
                VALUES (?, ?, ?)
            """, (key, value, time.time()))
            await db.commit()
        return True
    except Exception as e:
        print("set_setting error:", e)
        return False
