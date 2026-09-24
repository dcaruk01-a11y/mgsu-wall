import time, hashlib, secrets, json, aiosqlite
from datetime import datetime, timedelta
from config import DB_PATH, MSK, today_str


COINS_PER_GAME = 20
COINS_PER_VISIT = 5
COINS_PER_RECORD = 200
SESSION_TTL = 30 * 24 * 3600  # 30 дней

def _hash_pin(pin: str, uid: str) -> str:
    return hashlib.sha256((pin + "|" + uid + "|mgsu-salt-2026").encode()).hexdigest()


def generate_uid() -> str:
    alphabet = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
    code = "".join(secrets.choice(alphabet) for _ in range(5))
    return "MGSU-" + code


async def db_init_users():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                uid TEXT PRIMARY KEY,
                pin_hash TEXT NOT NULL,
                display_name TEXT NOT NULL,
                created_at REAL,
                last_seen REAL,
                streak INTEGER DEFAULT 0,
                best_streak INTEGER DEFAULT 0,
                coins INTEGER DEFAULT 0,
                total_score INTEGER DEFAULT 0,
                games_played INTEGER DEFAULT 0,
                last_day_played TEXT DEFAULT '',
                owned_chars TEXT DEFAULT '["student"]',
                active_char TEXT DEFAULT 'student',
                char_colors TEXT DEFAULT '{}'
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                uid TEXT NOT NULL,
                created_at REAL,
                last_used REAL
            )
        """)
        # миграции для старых баз
               # Миграции: проверяем существование колонок через PRAGMA
        try:
            cur = await db.execute("PRAGMA table_info(users)")
            existing = {row[1] for row in await cur.fetchall()}
        except Exception:
            existing = set()

        migrations = [
            ("owned_chars", "ALTER TABLE users ADD COLUMN owned_chars TEXT DEFAULT '[\"student\"]'"),
            ("active_char", "ALTER TABLE users ADD COLUMN active_char TEXT DEFAULT 'student'"),
            ("char_colors", "ALTER TABLE users ADD COLUMN char_colors TEXT DEFAULT '{}'"),
        ]
        for col, ddl in migrations:
            if col not in existing:
                try:
                    await db.execute(ddl)
                except Exception:
                    pass
        await db.commit()


async def create_user(display_name: str, pin: str) -> dict:
    display_name = (display_name or "").strip()[:20]
    if not display_name:
        return {"ok": False, "error": "Введи имя"}
    if not (pin.isdigit() and len(pin) == 4):
        return {"ok": False, "error": "PIN — 4 цифры"}

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT uid FROM users WHERE LOWER(display_name)=LOWER(?)",
            (display_name,)
        )
        if await cur.fetchone():
            return {"ok": False, "error": "Такое имя уже занято"}

    uid = None
    for _ in range(10):
        candidate = generate_uid()
        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute("SELECT 1 FROM users WHERE uid=?", (candidate,))
            if not await cur.fetchone():
                uid = candidate
                break
    if not uid:
        return {"ok": False, "error": "Не удалось создать ID, попробуй ещё раз"}

    pin_h = _hash_pin(pin, uid)
    now = time.time()

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO users (uid, pin_hash, display_name, created_at, last_seen, last_day_played)
            VALUES (?,?,?,?,?,?)
        """, (uid, pin_h, display_name, now, now, today_str()))
        await db.commit()

    token = secrets.token_urlsafe(32)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO sessions (token, uid, created_at, last_used) VALUES (?,?,?,?)",
            (token, uid, now, now)
        )
        await db.commit()

    return {"ok": True, "uid": uid, "token": token, "display_name": display_name}


async def login(uid: str, pin: str, ip: str = "") -> dict:
    import core.login_guard as guard

    uid = (uid or "").strip().upper()
    if not uid.startswith("MGSU-"):
        uid = "MGSU-" + uid
    if not (pin.isdigit() and len(pin) == 4):
        return {"ok": False, "error": "PIN — 4 цифры"}

    # Проверка блокировки
    blocked, wait_sec = await guard.check_blocked(uid, ip)
    if blocked:
        mins = (wait_sec + 59) // 60
        return {"ok": False, "error": f"Слишком много попыток. Подожди {mins} мин."}

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT uid, pin_hash, display_name FROM users WHERE uid=?", (uid,)
        )
        row = await cur.fetchone()

    if not row:
        await guard.record_attempt(uid, ip, False)
        return {"ok": False, "error": "ID не найден"}

    real_uid, pin_h, name = row
    if _hash_pin(pin, real_uid) != pin_h:
        await guard.record_attempt(uid, ip, False)
        return {"ok": False, "error": "Неверный PIN"}

    # Успех — записываем и сбрасываем счётчик
    await guard.record_attempt(uid, ip, True)

    token = secrets.token_urlsafe(32)
    now = time.time()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO sessions (token, uid, created_at, last_used) VALUES (?,?,?,?)",
            (token, real_uid, now, now)
        )
        await db.execute("UPDATE users SET last_seen=? WHERE uid=?", (now, real_uid))
        await db.commit()

    return {"ok": True, "uid": real_uid, "token": token, "display_name": name}

async def get_user_by_token(token: str):
    if not token:
        return None
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT uid, created_at FROM sessions WHERE token=?", (token,)
        )
        row = await cur.fetchone()
        if not row:
            return None
        uid, created_at = row

        # Проверка срока жизни токена
        if created_at and (time.time() - created_at) > SESSION_TTL:
            await db.execute("DELETE FROM sessions WHERE token=?", (token,))
            await db.commit()
            return None

        await db.execute("UPDATE sessions SET last_used=? WHERE token=?", (time.time(), token))
        cur = await db.execute("""
            SELECT uid, display_name, created_at, last_seen,
                   streak, best_streak, coins, total_score, games_played,
                   COALESCE(owned_chars, '["student"]'),
                   COALESCE(active_char, 'student')
            FROM users WHERE uid=?
        """, (uid,))
        urow = await cur.fetchone()
        await db.commit()

    if not urow:
        return None

    try:
        owned = json.loads(urow[9] or '["student"]')
    except Exception:
        owned = ["student"]

    return {
        "uid": urow[0],
        "display_name": urow[1],
        "created_at": urow[2],
        "last_seen": urow[3],
        "streak": urow[4] or 0,
        "best_streak": urow[5] or 0,
        "coins": urow[6] or 0,
        "total_score": urow[7] or 0,
        "games_played": urow[8] or 0,
        "owned_chars": owned,
        "active_char": urow[10] or "student",
    }


async def logout(token: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM sessions WHERE token=?", (token,))
        await db.commit()


async def update_display_name(uid: str, new_name: str) -> dict:
    new_name = (new_name or "").strip()[:20]
    if not new_name:
        return {"ok": False, "error": "Имя не может быть пустым"}
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT 1 FROM users WHERE LOWER(display_name)=LOWER(?) AND uid != ?",
            (new_name, uid)
        )
        if await cur.fetchone():
            return {"ok": False, "error": "Такое имя уже занято"}
        await db.execute("UPDATE users SET display_name=? WHERE uid=?", (new_name, uid))
        await db.commit()
    return {"ok": True, "display_name": new_name}


async def update_pin(uid: str, old_pin: str, new_pin: str) -> dict:
    if not (new_pin.isdigit() and len(new_pin) == 4):
        return {"ok": False, "error": "Новый PIN — 4 цифры"}
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT pin_hash FROM users WHERE uid=?", (uid,))
        row = await cur.fetchone()
        if not row:
            return {"ok": False, "error": "Не найден"}
        if _hash_pin(old_pin, uid) != row[0]:
            return {"ok": False, "error": "Неверный старый PIN"}
        await db.execute(
            "UPDATE users SET pin_hash=? WHERE uid=?",
            (_hash_pin(new_pin, uid), uid)
        )
        # Сброс всех сессий — пользователь должен войти заново
        await db.execute("DELETE FROM sessions WHERE uid=?", (uid,))
        await db.commit()
    return {"ok": True, "sessions_reset": True}


async def apply_streak(uid: str) -> dict:
    today = today_str()
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT streak, best_streak, last_day_played FROM users WHERE uid=?",
            (uid,)
        )
        row = await cur.fetchone()
        if not row:
            return {"ok": False}
        streak, best, last_day = row[0] or 0, row[1] or 0, row[2] or ""

        if last_day == today:
            return {"ok": True, "streak": streak, "changed": False}

        yesterday = (datetime.now(MSK) - timedelta(days=1)).strftime("%Y-%m-%d")
        if last_day == yesterday:
            streak += 1
        else:
            streak = 1

        if streak > best:
            best = streak

        await db.execute(
            "UPDATE users SET streak=?, best_streak=?, last_day_played=? WHERE uid=?",
            (streak, best, today, uid)
        )
        await db.commit()

    return {"ok": True, "streak": streak, "changed": True, "is_record": streak == best}


async def apply_score_and_coins(uid: str, score: int, game: str, is_record: bool = False) -> dict:
    score = max(0, min(int(score), 100000))
    coins = COINS_PER_GAME
    if is_record:
        coins += COINS_PER_RECORD

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE users
            SET total_score = total_score + ?,
                coins = coins + ?,
                games_played = games_played + 1,
                last_seen = ?
            WHERE uid = ?
        """, (score, coins, time.time(), uid))
        await db.commit()

        cur = await db.execute("""
            SELECT display_name, streak, best_streak, coins, total_score, games_played
            FROM users WHERE uid = ?
        """, (uid,))
        row = await cur.fetchone()

    if not row:
        return {"ok": False}

    return {
        "ok": True,
        "display_name": row[0],
        "streak": row[1] or 0,
        "best_streak": row[2] or 0,
        "coins": row[3] or 0,
        "total_score": row[4] or 0,
        "games_played": row[5] or 0,
        "coins_added": coins,
    }


async def add_coins(uid: str, amount: int, reason: str = "") -> dict:
    amount = max(0, min(int(amount), 10000))
    if amount == 0:
        return {"ok": False}
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET coins = coins + ?, last_seen = ? WHERE uid = ?",
            (amount, time.time(), uid)
        )
        await db.commit()
        cur = await db.execute("SELECT coins FROM users WHERE uid = ?", (uid,))
        row = await cur.fetchone()
    return {"ok": True, "coins": row[0] if row else 0, "added": amount}
