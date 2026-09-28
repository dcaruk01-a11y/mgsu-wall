import time, hashlib, secrets, json, aiosqlite
from datetime import datetime, timedelta
from config import DB_PATH, MSK, today_str


COINS_PER_GAME = 20
COINS_PER_VISIT = 5
COINS_PER_RECORD = 200
SESSION_TTL = 30 * 24 * 3600


def _hash_pin(pin: str, uid: str) -> str:
    return hashlib.sha256((pin + "|" + uid + "|mgsu-salt-2026").encode()).hexdigest()

# ═══════════════════════════════════════════════════════════
# КЭШ ПОЛЬЗОВАТЕЛЕЙ — чтобы 5 запросов = 1 поход в Turso
# ═══════════════════════════════════════════════════════════
_user_cache: dict = {}         # token -> {"data": dict, "ts": float}
_uid_tokens: dict = {}         # uid -> set of tokens (для инвалидации)
_USER_CACHE_TTL = 10.0         # 10 секунд


def _cache_get(token: str):
    if not token:
        return None
    entry = _user_cache.get(token)
    if not entry:
        return None
    if time.time() - entry["ts"] > _USER_CACHE_TTL:
        _user_cache.pop(token, None)
        return None
    return entry["data"]


def _cache_set(token: str, data: dict):
    if not token or not data:
        return
    _user_cache[token] = {"data": data, "ts": time.time()}
    uid = data.get("uid")
    if uid:
        _uid_tokens.setdefault(uid, set()).add(token)


def invalidate_user_cache(uid: str):
    """Очистить кэш всех токенов игрока. Вызывать после любых изменений."""
    if not uid:
        return
    tokens = _uid_tokens.pop(uid, set())
    for t in tokens:
        _user_cache.pop(t, None)


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

        try:
            cur = await db.execute("PRAGMA table_info(users)")
            existing = {row[1] for row in await cur.fetchall()}
        except Exception:
            existing = set()

        migrations = [
            ("owned_chars", "ALTER TABLE users ADD COLUMN owned_chars TEXT DEFAULT '[\"student\"]'"),
            ("active_char", "ALTER TABLE users ADD COLUMN active_char TEXT DEFAULT 'student'"),
            ("char_colors", "ALTER TABLE users ADD COLUMN char_colors TEXT DEFAULT '{}'"),
            ("chat_id", "ALTER TABLE users ADD COLUMN chat_id TEXT DEFAULT ''"),
            ("notify_enabled", "ALTER TABLE users ADD COLUMN notify_enabled INTEGER DEFAULT 0"),
            ("banned", "ALTER TABLE users ADD COLUMN banned INTEGER DEFAULT 0"),
            ("ban_reason", "ALTER TABLE users ADD COLUMN ban_reason TEXT DEFAULT ''"),
            ("feedback_request_at", "ALTER TABLE users ADD COLUMN feedback_request_at REAL DEFAULT 0"),
            ("feedback_seen_at", "ALTER TABLE users ADD COLUMN feedback_seen_at REAL DEFAULT 0"),
            ("institute", "ALTER TABLE users ADD COLUMN institute TEXT DEFAULT ''"),
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

    blocked, wait_sec = await guard.check_blocked(uid, ip)
    if blocked:
        mins = (wait_sec + 59) // 60
        return {"ok": False, "error": f"Слишком много попыток. Подожди {mins} мин."}

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT uid, pin_hash, display_name, COALESCE(banned, 0), COALESCE(ban_reason, '') FROM users WHERE uid=?",
            (uid,)
        )
        row = await cur.fetchone()

    if not row:
        await guard.record_attempt(uid, ip, False)
        return {"ok": False, "error": "ID не найден"}

    if row[3]:
        reason = row[4] or "Нарушение правил"
        return {"ok": False, "error": f"Аккаунт заблокирован: {reason}"}

    real_uid, pin_h, name = row[0], row[1], row[2]
    if _hash_pin(pin, real_uid) != pin_h:
        await guard.record_attempt(uid, ip, False)
        return {"ok": False, "error": "Неверный PIN"}

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


import time, hashlib, secrets, json, aiosqlite
from datetime import datetime, timedelta
from config import DB_PATH, MSK, today_str


COINS_PER_GAME = 20
COINS_PER_VISIT = 5
COINS_PER_RECORD = 200
SESSION_TTL = 30 * 24 * 3600


# ═══════════════════════════════════════════════════════════
# КЭШ ПОЛЬЗОВАТЕЛЕЙ — чтобы 5 запросов = 1 поход в Turso
# ═══════════════════════════════════════════════════════════
_user_cache: dict = {}
_uid_tokens: dict = {}
_USER_CACHE_TTL = 10.0


def _cache_get(token: str):
    if not token:
        return None
    entry = _user_cache.get(token)
    if not entry:
        return None
    if time.time() - entry["ts"] > _USER_CACHE_TTL:
        _user_cache.pop(token, None)
        return None
    return entry["data"]


def _cache_set(token: str, data: dict):
    if not token or not data:
        return
    _user_cache[token] = {"data": data, "ts": time.time()}
    uid = data.get("uid")
    if uid:
        _uid_tokens.setdefault(uid, set()).add(token)


def invalidate_user_cache(uid: str):
    if not uid:
        return
    tokens = _uid_tokens.pop(uid, set())
    for t in tokens:
        _user_cache.pop(t, None)


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

        try:
            cur = await db.execute("PRAGMA table_info(users)")
            existing = {row[1] for row in await cur.fetchall()}
        except Exception:
            existing = set()

        migrations = [
            ("owned_chars", "ALTER TABLE users ADD COLUMN owned_chars TEXT DEFAULT '[\"student\"]'"),
            ("active_char", "ALTER TABLE users ADD COLUMN active_char TEXT DEFAULT 'student'"),
            ("char_colors", "ALTER TABLE users ADD COLUMN char_colors TEXT DEFAULT '{}'"),
            ("chat_id", "ALTER TABLE users ADD COLUMN chat_id TEXT DEFAULT ''"),
            ("notify_enabled", "ALTER TABLE users ADD COLUMN notify_enabled INTEGER DEFAULT 0"),
            ("banned", "ALTER TABLE users ADD COLUMN banned INTEGER DEFAULT 0"),
            ("ban_reason", "ALTER TABLE users ADD COLUMN ban_reason TEXT DEFAULT ''"),
            ("feedback_request_at", "ALTER TABLE users ADD COLUMN feedback_request_at REAL DEFAULT 0"),
            ("feedback_seen_at", "ALTER TABLE users ADD COLUMN feedback_seen_at REAL DEFAULT 0"),
            ("institute", "ALTER TABLE users ADD COLUMN institute TEXT DEFAULT ''"),
            ("active_frame", "ALTER TABLE users ADD COLUMN active_frame TEXT DEFAULT ''"),
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

    blocked, wait_sec = await guard.check_blocked(uid, ip)
    if blocked:
        mins = (wait_sec + 59) // 60
        return {"ok": False, "error": f"Слишком много попыток. Подожди {mins} мин."}

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT uid, pin_hash, display_name, COALESCE(banned, 0), COALESCE(ban_reason, '') FROM users WHERE uid=?",
            (uid,)
        )
        row = await cur.fetchone()

    if not row:
        await guard.record_attempt(uid, ip, False)
        return {"ok": False, "error": "ID не найден"}

    if row[3]:
        reason = row[4] or "Нарушение правил"
        return {"ok": False, "error": f"Аккаунт заблокирован: {reason}"}

    real_uid, pin_h, name = row[0], row[1], row[2]
    if _hash_pin(pin, real_uid) != pin_h:
        await guard.record_attempt(uid, ip, False)
        return {"ok": False, "error": "Неверный PIN"}

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

    cached = _cache_get(token)
    if cached is not None:
        return cached

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT uid, created_at FROM sessions WHERE token=?", (token,)
        )
        row = await cur.fetchone()
        if not row:
            return None
        uid, created_at = row

        if created_at and (time.time() - created_at) > SESSION_TTL:
            await db.execute("DELETE FROM sessions WHERE token=?", (token,))
            await db.commit()
            return None

        await db.execute("UPDATE sessions SET last_used=? WHERE token=?", (time.time(), token))
        cur = await db.execute("""
            SELECT uid, display_name, created_at, last_seen,
                   streak, best_streak, coins, total_score, games_played,
                   COALESCE(owned_chars, '["student"]'),
                   COALESCE(active_char, 'student'),
                   COALESCE(institute, ''),
                   COALESCE(active_frame, '')
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

    data = {
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
        "institute": urow[11] or "",
        "active_frame": urow[12] or "",
    }

    _cache_set(token, data)
    return data


async def logout(token: str):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT uid FROM sessions WHERE token=?", (token,))
        row = await cur.fetchone()
        if row:
            invalidate_user_cache(row[0])
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
    invalidate_user_cache(uid)
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
        await db.execute("DELETE FROM sessions WHERE uid=?", (uid,))
        await db.commit()
    invalidate_user_cache(uid)
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

    invalidate_user_cache(uid)
    return {"ok": True, "streak": streak, "changed": True, "is_record": streak == best}


async def apply_score_and_coins(uid: str, score: int, game: str, is_record: bool = False,
                                daily_mult: float = 1.0, rank_bonus_pct: int = 0) -> dict:
    score = max(0, min(int(score), 100000))
    daily_mult = max(0.1, min(float(daily_mult or 1.0), 1.0))

    base_coins = int(round(COINS_PER_GAME * daily_mult))

    if rank_bonus_pct > 0:
        base_coins = int(round(base_coins * (1 + rank_bonus_pct / 100.0)))

    coins = base_coins
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

    invalidate_user_cache(uid)
    return {
        "ok": True,
        "display_name": row[0],
        "streak": row[1] or 0,
        "best_streak": row[2] or 0,
        "coins": row[3] or 0,
        "total_score": row[4] or 0,
        "games_played": row[5] or 0,
        "coins_added": coins,
        "rank_bonus_pct": rank_bonus_pct,
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
    invalidate_user_cache(uid)
    return {"ok": True, "coins": row[0] if row else 0, "added": amount}


# ═══════════════════════════════════════════════════════════
# ИНСТИТУТ
# ═══════════════════════════════════════════════════════════
async def set_institute(uid: str, institute: str) -> dict:
    from core.institutes import INSTITUTES, reset_player_institute
    valid_keys = {i["key"] for i in INSTITUTES}
    if institute not in valid_keys:
        return {"ok": False, "error": "Неизвестный институт"}

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT institute FROM users WHERE uid=?", (uid,))
        row = await cur.fetchone()
        if not row:
            return {"ok": False, "error": "Игрок не найден"}

        old_institute = (row[0] or "").strip()
        is_change = bool(old_institute and old_institute != institute)

        if is_change:
            await db.execute("""
                UPDATE users SET
                    institute = ?,
                    total_score = 0,
                    coins = 0,
                    streak = 0,
                    best_streak = 0,
                    games_played = 0,
                    last_day_played = '',
                    owned_chars = '["student"]',
                    active_char = 'student'
                WHERE uid = ?
            """, (institute, uid))
        else:
            await db.execute(
                "UPDATE users SET institute = ? WHERE uid = ?",
                (institute, uid)
            )
        await db.commit()

    if is_change:
        try:
            await reset_player_institute(uid)
        except Exception as e:
            print("reset_player_institute error:", e)

    invalidate_user_cache(uid)
    return {"ok": True, "institute": institute, "was_change": is_change}


# ═══════════════════════════════════════════════════════════
# РАНГ
# ═══════════════════════════════════════════════════════════

ACCOUNT_RANKS = [
    {"key":"freshman",  "name":"Первокурсник", "emoji":"🎓", "min_score":0,      "min_games":0},
    {"key":"student",   "name":"Студент",      "emoji":"📚", "min_score":3000,   "min_games":10},
    {"key":"expert",    "name":"Знаток",       "emoji":"✏️", "min_score":10000,  "min_games":30},
    {"key":"activist",  "name":"Активист",     "emoji":"🎯", "min_score":25000,  "min_games":60},
    {"key":"headman",   "name":"Староста",     "emoji":"🏅", "min_score":50000,  "min_games":100},
    {"key":"commander", "name":"Командир",     "emoji":"🎖",  "min_score":100000, "min_games":200},
    {"key":"legend",    "name":"Легенда МГСУ", "emoji":"👑", "min_score":200000, "min_games":400},
]

RANK_BONUSES = {
    "freshman":  0,
    "student":   5,
    "expert":    10,
    "activist":  15,
    "headman":   20,
    "commander": 30,
    "legend":    50,
}


def get_account_rank(total_score: int, games_played: int) -> dict:
    total_score = int(total_score or 0)
    games_played = int(games_played or 0)

    current = ACCOUNT_RANKS[0]
    current_idx = 0
    for i, r in enumerate(ACCOUNT_RANKS):
        if total_score >= r["min_score"] and games_played >= r["min_games"]:
            current = r
            current_idx = i

    next_rank = ACCOUNT_RANKS[current_idx + 1] if current_idx + 1 < len(ACCOUNT_RANKS) else None

    progress = 1.0
    if next_rank:
        score_pct = total_score / next_rank["min_score"] if next_rank["min_score"] else 1.0
        games_pct = games_played / next_rank["min_games"] if next_rank["min_games"] else 1.0
        progress = min(1.0, min(score_pct, games_pct))

    bonus_pct = RANK_BONUSES.get(current["key"], 0)

    return {
        "key": current["key"],
        "name": current["name"],
        "emoji": current["emoji"],
        "bonus_pct": bonus_pct,
        "next": {
            "key": next_rank["key"],
            "name": next_rank["name"],
            "emoji": next_rank["emoji"],
            "min_score": next_rank["min_score"],
            "min_games": next_rank["min_games"],
            "bonus_pct": RANK_BONUSES.get(next_rank["key"], 0),
        } if next_rank else None,
        "progress": round(progress, 3),
        "total_score": total_score,
        "games_played": games_played,
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


async def apply_score_and_coins(uid: str, score: int, game: str, is_record: bool = False,
                                daily_mult: float = 1.0, rank_bonus_pct: int = 0) -> dict:
    score = max(0, min(int(score), 100000))
    daily_mult = max(0.1, min(float(daily_mult or 1.0), 1.0))

    base_coins = int(round(COINS_PER_GAME * daily_mult))

    if rank_bonus_pct > 0:
        base_coins = int(round(base_coins * (1 + rank_bonus_pct / 100.0)))

    coins = base_coins
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
        "rank_bonus_pct": rank_bonus_pct,
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


# ═══════════════════════════════════════════════════════════
# ИНСТИТУТ — привязка и смена
# ═══════════════════════════════════════════════════════════
async def set_institute(uid: str, institute: str) -> dict:
    """
    Привязать или сменить институт.
    Смена = обнуление прогресса (очки, монеты, streak, партии, скины).
    Институт можно менять в любое время.
    """
    from core.institutes import INSTITUTES, reset_player_institute
    valid_keys = {i["key"] for i in INSTITUTES}
    if institute not in valid_keys:
        return {"ok": False, "error": "Неизвестный институт"}

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT institute FROM users WHERE uid=?", (uid,))
        row = await cur.fetchone()
        if not row:
            return {"ok": False, "error": "Игрок не найден"}

        old_institute = (row[0] or "").strip()
        is_change = bool(old_institute and old_institute != institute)

        if is_change:
            # Обнуляем прогресс
            await db.execute("""
                UPDATE users SET
                    institute = ?,
                    total_score = 0,
                    coins = 0,
                    streak = 0,
                    best_streak = 0,
                    games_played = 0,
                    last_day_played = '',
                    owned_chars = '["student"]',
                    active_char = 'student'
                WHERE uid = ?
            """, (institute, uid))
        else:
            await db.execute(
                "UPDATE users SET institute = ? WHERE uid = ?",
                (institute, uid)
            )
        await db.commit()

    # Обнуляем очки в старом институте (после закрытия соединения, чтобы не было lock)
    if is_change:
        try:
            await reset_player_institute(uid)
        except Exception as e:
            print("reset_player_institute error:", e)

    return {
        "ok": True,
        "institute": institute,
        "was_change": is_change,
    }


# ═══════════════════════════════════════════════════════════
# РАНГ
# ═══════════════════════════════════════════════════════════

ACCOUNT_RANKS = [
    {"key":"freshman",  "name":"Первокурсник", "emoji":"🎓", "min_score":0,      "min_games":0},
    {"key":"student",   "name":"Студент",      "emoji":"📚", "min_score":3000,   "min_games":10},
    {"key":"expert",    "name":"Знаток",       "emoji":"✏️", "min_score":10000,  "min_games":30},
    {"key":"activist",  "name":"Активист",     "emoji":"🎯", "min_score":25000,  "min_games":60},
    {"key":"headman",   "name":"Староста",     "emoji":"🏅", "min_score":50000,  "min_games":100},
    {"key":"commander", "name":"Командир",     "emoji":"🎖",  "min_score":100000, "min_games":200},
    {"key":"legend",    "name":"Легенда МГСУ", "emoji":"👑", "min_score":200000, "min_games":400},
]

RANK_BONUSES = {
    "freshman":  0,
    "student":   5,
    "expert":    10,
    "activist":  15,
    "headman":   20,
    "commander": 30,
    "legend":    50,
}


def get_account_rank(total_score: int, games_played: int) -> dict:
    total_score = int(total_score or 0)
    games_played = int(games_played or 0)

    current = ACCOUNT_RANKS[0]
    current_idx = 0
    for i, r in enumerate(ACCOUNT_RANKS):
        if total_score >= r["min_score"] and games_played >= r["min_games"]:
            current = r
            current_idx = i

    next_rank = ACCOUNT_RANKS[current_idx + 1] if current_idx + 1 < len(ACCOUNT_RANKS) else None

    progress = 1.0
    if next_rank:
        score_pct = total_score / next_rank["min_score"] if next_rank["min_score"] else 1.0
        games_pct = games_played / next_rank["min_games"] if next_rank["min_games"] else 1.0
        progress = min(1.0, min(score_pct, games_pct))

    bonus_pct = RANK_BONUSES.get(current["key"], 0)

    return {
        "key": current["key"],
        "name": current["name"],
        "emoji": current["emoji"],
        "bonus_pct": bonus_pct,
        "next": {
            "key": next_rank["key"],
            "name": next_rank["name"],
            "emoji": next_rank["emoji"],
            "min_score": next_rank["min_score"],
            "min_games": next_rank["min_games"],
            "bonus_pct": RANK_BONUSES.get(next_rank["key"], 0),
        } if next_rank else None,
        "progress": round(progress, 3),
        "total_score": total_score,
        "games_played": games_played,
    }
