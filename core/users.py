import time, hashlib, secrets, aiosqlite
from datetime import datetime, timedelta
from config import DB_PATH, MSK, today_str


def _hash_pin(pin: str, uid: str) -> str:
    return hashlib.sha256((pin + "|" + uid + "|mgsu-salt-2026").encode()).hexdigest()


def generate_uid() -> str:
    # Без похожих символов: без O, 0, I, 1, L
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
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                uid TEXT NOT NULL,
                created_at REAL,
                last_used REAL
            )
        """)
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


async def login(uid: str, pin: str) -> dict:
    uid = (uid or "").strip().upper()
    if not uid.startswith("MGSU-"):
        uid = "MGSU-" + uid
    if not (pin.isdigit() and len(pin) == 4):
        return {"ok": False, "error": "PIN — 4 цифры"}

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT uid, pin_hash, display_name FROM users WHERE uid=?", (uid,)
        )
        row = await cur.fetchone()

    if not row:
        return {"ok": False, "error": "ID не найден"}

    real_uid, pin_h, name = row
    if _hash_pin(pin, real_uid) != pin_h:
        return {"ok": False, "error": "Неверный PIN"}

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
        cur = await db.execute("SELECT uid FROM sessions WHERE token=?", (token,))
        row = await cur.fetchone()
        if not row:
            return None
        uid = row[0]
        await db.execute("UPDATE sessions SET last_used=? WHERE token=?", (time.time(), token))
        cur = await db.execute("""
            SELECT uid, display_name, created_at, last_seen,
                   streak, best_streak, coins, total_score, games_played
            FROM users WHERE uid=?
        """, (uid,))
        urow = await cur.fetchone()
        await db.commit()

    if not urow:
        return None

    return {
        "uid": urow[0],
        "display_name": urow[1],
        "created_at": urow[2],
        "last_seen": urow[3],
        "streak": urow[4],
        "best_streak": urow[5],
        "coins": urow[6],
        "total_score": urow[7],
        "games_played": urow[8],
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
        await db.commit()
    return {"ok": True}


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


# ============ ЭКОНОМИКА И ПРОГРЕСС ============

COINS_PER_GAME = 20
COINS_PER_VISIT = 5
COINS_PER_RECORD = 200


async def apply_score_and_coins(uid: str, score: int, game: str, is_record: bool = False) -> dict:
    """
    Начисляет очки и монеты за партию.
    Возвращает обновлённый профиль + сколько монет добавлено.
    """
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
