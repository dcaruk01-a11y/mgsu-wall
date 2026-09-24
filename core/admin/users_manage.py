"""
Управление пользователями из админки (режим бога).
Позволяет: менять монеты/очки/серию, выдавать персонажей,
сбрасывать PIN, банить, удалять аккаунт.
Все действия пишутся в admin_logs.
"""
import time, json, aiosqlite, hashlib
from fastapi import APIRouter, Header, HTTPException
from config import DB_PATH, MSK
from core.admin.common import check_admin

router = APIRouter()


# ============ ЛОГИ ============

async def log_action(action: str, uid: str, details: str = ""):
    """Записывает действие админа в лог."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS admin_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL,
                action TEXT,
                uid TEXT,
                details TEXT
            )
        """)
        await db.execute("""
            INSERT INTO admin_logs (ts, action, uid, details)
            VALUES (?,?,?,?)
        """, (time.time(), action, uid, details))
        await db.commit()


@router.get("/admin/api/logs")
async def admin_logs_get(limit: int = 100, token: str = Header(default="", alias="authorization")):
    if not check_admin(token.replace("Bearer ", "").strip()):
        raise HTTPException(status_code=401, detail="Unauthorized")
    limit = max(10, min(limit, 500))
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS admin_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts REAL, action TEXT, uid TEXT, details TEXT
                )
            """)
            await db.commit()
            cur = await db.execute("""
                SELECT ts, action, uid, details FROM admin_logs
                ORDER BY ts DESC LIMIT ?
            """, (limit,))
            rows = await cur.fetchall()
    except Exception:
        rows = []

    logs = [{"ts": r[0], "action": r[1], "uid": r[2], "details": r[3]} for r in rows]
    return {"logs": logs}


# ============ КАРТОЧКА ИГРОКА ============

@router.get("/admin/api/users/{uid}")
async def admin_user_detail(uid: str, token: str = Header(default="", alias="authorization")):
    if not check_admin(token.replace("Bearer ", "").strip()):
        raise HTTPException(status_code=401, detail="Unauthorized")

    uid = uid.strip().upper()
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            SELECT uid, display_name, created_at, last_seen,
                   streak, best_streak, coins, total_score, games_played,
                   COALESCE(owned_chars, '["student"]'),
                   COALESCE(active_char, 'student'),
                   COALESCE(banned, 0),
                   COALESCE(ban_reason, '')
            FROM users WHERE uid=?
        """, (uid,))
        row = await cur.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Игрок не найден")

        # Последний IP
        try:
            cur2 = await db.execute(
                "SELECT ip FROM visits WHERE uid=? ORDER BY ts DESC LIMIT 1",
                (uid,)
            )
            ip_row = await cur2.fetchone()
            last_ip = ip_row[0] if ip_row else ""
        except Exception:
            last_ip = ""

    try:
        owned = json.loads(row[9] or '["student"]')
    except Exception:
        owned = ["student"]

    return {
        "uid": row[0],
        "display_name": row[1],
        "created_at": row[2],
        "last_seen": row[3],
        "streak": row[4] or 0,
        "best_streak": row[5] or 0,
        "coins": row[6] or 0,
        "total_score": row[7] or 0,
        "games_played": row[8] or 0,
        "owned_chars": owned,
        "active_char": row[10] or "student",
        "banned": bool(row[11]),
        "ban_reason": row[12] or "",
        "last_ip": last_ip,
    }


# ============ ИЗМЕНЕНИЕ ПОЛЕЙ ============

@router.post("/admin/api/users/set")
async def admin_user_set(payload: dict, token: str = Header(default="", alias="authorization")):
    if not check_admin(token.replace("Bearer ", "").strip()):
        raise HTTPException(status_code=401, detail="Unauthorized")

    uid = str(payload.get("uid", "")).strip().upper()
    if not uid:
        raise HTTPException(status_code=400, detail="uid required")

    fields = {}
    for k in ("coins", "total_score", "streak", "best_streak"):
        if k in payload:
            try:
                v = int(payload[k])
                fields[k] = max(0, min(v, 999999999))
            except Exception:
                pass

    if not fields:
        raise HTTPException(status_code=400, detail="Нет полей для обновления")

    sets = ", ".join(f"{k}=?" for k in fields.keys())
    vals = list(fields.values()) + [uid]

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE users SET {sets} WHERE uid=?", vals)
        await db.commit()

    details = ", ".join(f"{k}={v}" for k, v in fields.items())
    await log_action("set_fields", uid, details)
    return {"ok": True, "updated": fields}


# ============ ПЕРСОНАЖИ ============

ALL_CHARS = ["student", "sso", "prorab", "builder", "prof", "dean", "legend"]


@router.post("/admin/api/users/give-char")
async def admin_user_give_char(payload: dict, token: str = Header(default="", alias="authorization")):
    if not check_admin(token.replace("Bearer ", "").strip()):
        raise HTTPException(status_code=401, detail="Unauthorized")

    uid = str(payload.get("uid", "")).strip().upper()
    char = str(payload.get("char", "")).strip()
    if char not in ALL_CHARS:
        raise HTTPException(status_code=400, detail="Неизвестный персонаж")

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT COALESCE(owned_chars, '[\"student\"]') FROM users WHERE uid=?",
            (uid,)
        )
        row = await cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Игрок не найден")
        try:
            owned = json.loads(row[0] or '["student"]')
        except Exception:
            owned = ["student"]
        if char not in owned:
            owned.append(char)
        await db.execute(
            "UPDATE users SET owned_chars=? WHERE uid=?",
            (json.dumps(owned), uid)
        )
        await db.commit()

    await log_action("give_char", uid, char)
    return {"ok": True, "owned": owned}


@router.post("/admin/api/users/revoke-char")
async def admin_user_revoke_char(payload: dict, token: str = Header(default="", alias="authorization")):
    if not check_admin(token.replace("Bearer ", "").strip()):
        raise HTTPException(status_code=401, detail="Unauthorized")

    uid = str(payload.get("uid", "")).strip().upper()
    char = str(payload.get("char", "")).strip()
    if char == "student":
        raise HTTPException(status_code=400, detail="Студента забрать нельзя")

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT COALESCE(owned_chars, '[\"student\"]'), COALESCE(active_char, 'student') FROM users WHERE uid=?",
            (uid,)
        )
        row = await cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Игрок не найден")
        try:
            owned = json.loads(row[0] or '["student"]')
        except Exception:
            owned = ["student"]

        owned = [c for c in owned if c != char]
        if not owned:
            owned = ["student"]
        active = row[1] if row[1] in owned else "student"

        await db.execute(
            "UPDATE users SET owned_chars=?, active_char=? WHERE uid=?",
            (json.dumps(owned), active, uid)
        )
        await db.commit()

    await log_action("revoke_char", uid, char)
    return {"ok": True, "owned": owned, "active": active}


@router.post("/admin/api/users/set-active-char")
async def admin_user_set_active_char(payload: dict, token: str = Header(default="", alias="authorization")):
    if not check_admin(token.replace("Bearer ", "").strip()):
        raise HTTPException(status_code=401, detail="Unauthorized")

    uid = str(payload.get("uid", "")).strip().upper()
    char = str(payload.get("char", "")).strip()
    if char not in ALL_CHARS:
        raise HTTPException(status_code=400, detail="Неизвестный персонаж")

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT COALESCE(owned_chars, '[\"student\"]') FROM users WHERE uid=?",
            (uid,)
        )
        row = await cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Игрок не найден")
        try:
            owned = json.loads(row[0] or '["student"]')
        except Exception:
            owned = ["student"]

        if char not in owned:
            owned.append(char)

        await db.execute(
            "UPDATE users SET owned_chars=?, active_char=? WHERE uid=?",
            (json.dumps(owned), char, uid)
        )
        await db.commit()

    await log_action("set_active_char", uid, char)
    return {"ok": True, "active": char, "owned": owned}


# ============ PIN / БАН / УДАЛЕНИЕ ============

@router.post("/admin/api/users/reset-pin")
async def admin_user_reset_pin(payload: dict, token: str = Header(default="", alias="authorization")):
    if not check_admin(token.replace("Bearer ", "").strip()):
        raise HTTPException(status_code=401, detail="Unauthorized")

    uid = str(payload.get("uid", "")).strip().upper()
    new_pin = str(payload.get("new_pin", "1234")).strip()

    if not (new_pin.isdigit() and len(new_pin) == 4):
        raise HTTPException(status_code=400, detail="PIN — 4 цифры")

    pin_hash = hashlib.sha256(
        (new_pin + "|" + uid + "|mgsu-salt-2026").encode()
    ).hexdigest()

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT 1 FROM users WHERE uid=?", (uid,))
        if not await cur.fetchone():
            raise HTTPException(status_code=404, detail="Игрок не найден")

        await db.execute("UPDATE users SET pin_hash=? WHERE uid=?", (pin_hash, uid))
        await db.execute("DELETE FROM sessions WHERE uid=?", (uid,))
        await db.commit()

    await log_action("reset_pin", uid, f"новый PIN: {new_pin}")
    return {"ok": True, "new_pin": new_pin}


@router.post("/admin/api/users/ban")
async def admin_user_ban(payload: dict, token: str = Header(default="", alias="authorization")):
    if not check_admin(token.replace("Bearer ", "").strip()):
        raise HTTPException(status_code=401, detail="Unauthorized")

    uid = str(payload.get("uid", "")).strip().upper()
    reason = str(payload.get("reason", "Нарушение правил"))[:200]

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT 1 FROM users WHERE uid=?", (uid,))
        if not await cur.fetchone():
            raise HTTPException(status_code=404, detail="Игрок не найден")

        await db.execute(
            "UPDATE users SET banned=1, ban_reason=? WHERE uid=?",
            (reason, uid)
        )
        await db.execute("DELETE FROM sessions WHERE uid=?", (uid,))
        await db.commit()

    await log_action("ban", uid, reason)
    return {"ok": True}


@router.post("/admin/api/users/unban")
async def admin_user_unban(payload: dict, token: str = Header(default="", alias="authorization")):
    if not check_admin(token.replace("Bearer ", "").strip()):
        raise HTTPException(status_code=401, detail="Unauthorized")

    uid = str(payload.get("uid", "")).strip().upper()

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET banned=0, ban_reason='' WHERE uid=?",
            (uid,)
        )
        await db.commit()

    await log_action("unban", uid, "")
    return {"ok": True}


@router.post("/admin/api/users/delete")
async def admin_user_delete(payload: dict, token: str = Header(default="", alias="authorization")):
    if not check_admin(token.replace("Bearer ", "").strip()):
        raise HTTPException(status_code=401, detail="Unauthorized")

    uid = str(payload.get("uid", "")).strip().upper()
    confirm = str(payload.get("confirm", "")).strip().upper()

    if uid != confirm:
        raise HTTPException(status_code=400, detail="Подтверди удаление — введи UID ещё раз")

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM users WHERE uid=?", (uid,))
        await db.execute("DELETE FROM sessions WHERE uid=?", (uid,))
        try:
            await db.execute("DELETE FROM scores WHERE uid=?", (uid,))
            await db.execute("DELETE FROM user_tasks WHERE uid=?", (uid,))
            await db.execute("DELETE FROM visits WHERE uid=?", (uid,))
        except Exception:
            pass
        await db.commit()

    await log_action("delete_user", uid, "удалён навсегда")
    return {"ok": True}
