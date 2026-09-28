"""
Сбор IP, подсети и часов активности.
Все заходы сохраняются в visits. Есть группировка по зонам.
"""
import time, aiosqlite
from datetime import datetime, timedelta
from config import DB_PATH, MSK, today_str


def normalize_ip(ip: str) -> str:
    if not ip:
        return "unknown"
    ip = ip.strip()
    if ip.startswith("::ffff:"):
        ip = ip[7:]
    return ip


def get_subnet(ip: str) -> str:
    if not ip or ip == "unknown":
        return "unknown"
    if ":" in ip:
        parts = ip.split(":")
        return ":".join(parts[:4])
    parts = ip.split(".")
    if len(parts) >= 3:
        return ".".join(parts[:3])
    return ip


def classify_device(user_agent: str) -> str:
    ua = (user_agent or "").lower()
    if "ipad" in ua or "tablet" in ua:
        return "tablet"
    if "mobile" in ua or "android" in ua or "iphone" in ua:
        return "mobile"
    return "desktop"


async def db_init_ip():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS visits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uid TEXT,
                ip TEXT,
                subnet TEXT,
                device TEXT,
                hour INTEGER,
                ts REAL
            )
        """)
        # Миграции: page, action, user_agent
        try:
            cur = await db.execute("PRAGMA table_info(visits)")
            existing = {row[1] for row in await cur.fetchall()}
        except Exception:
            existing = set()

        for col, ddl in [
            ("page",       "ALTER TABLE visits ADD COLUMN page TEXT DEFAULT ''"),
            ("action",     "ALTER TABLE visits ADD COLUMN action TEXT DEFAULT 'visit'"),
            ("user_agent", "ALTER TABLE visits ADD COLUMN user_agent TEXT DEFAULT ''"),
        ]:
            if col not in existing:
                try:
                    await db.execute(ddl)
                except Exception as e:
                    print("visits migration:", e)

        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_visits_day_hour
            ON visits (hour, ts)
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_visits_subnet
            ON visits (subnet, ts)
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS daily_hours (
                day TEXT,
                hour INTEGER,
                visits INTEGER DEFAULT 0,
                uniques INTEGER DEFAULT 0,
                PRIMARY KEY (day, hour)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS ip_tags (
                subnet TEXT PRIMARY KEY,
                tag TEXT DEFAULT 'unknown',
                label TEXT DEFAULT '',
                first_seen REAL,
                last_seen REAL,
                visits INTEGER DEFAULT 0
            )
        """)
        await db.commit()


async def track_visit(ip: str, user_agent: str, uid: str = "",
                      page: str = "", action: str = "visit"):
    """Сохраняет заход."""
    ip = normalize_ip(ip)
    subnet = get_subnet(ip)
    device = classify_device(user_agent)
    now_ts = time.time()
    now_msk = datetime.now(MSK)
    hour = now_msk.hour
    day = today_str()

    page = (page or "")[:100]
    action = (action or "visit")[:30]
    user_agent = (user_agent or "")[:300]

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO visits (uid, ip, subnet, device, hour, ts, page, action, user_agent)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, (uid or "", ip, subnet, device, hour, now_ts, page, action, user_agent))

        # Агрегат по часам
        cur = await db.execute(
            "SELECT visits FROM daily_hours WHERE day=? AND hour=?",
            (day, hour)
        )
        row = await cur.fetchone()
        if row:
            await db.execute("""
                UPDATE daily_hours SET visits=visits+1 WHERE day=? AND hour=?
            """, (day, hour))
        else:
            await db.execute("""
                INSERT INTO daily_hours (day, hour, visits, uniques)
                VALUES (?,?,?,?)
            """, (day, hour, 1, 0))

        # IP-тег
        cur = await db.execute("SELECT subnet FROM ip_tags WHERE subnet=?", (subnet,))
        if await cur.fetchone():
            await db.execute("""
                UPDATE ip_tags SET last_seen=?, visits=visits+1 WHERE subnet=?
            """, (now_ts, subnet))
        else:
            await db.execute("""
                INSERT INTO ip_tags (subnet, tag, label, first_seen, last_seen, visits)
                VALUES (?,?,?,?,?,?)
            """, (subnet, "unknown", "", now_ts, now_ts, 1))

        await db.commit()


# ═══════════════════════════════════════════════════════════
# ЖИВАЯ ЛЕНТА
# ═══════════════════════════════════════════════════════════
async def get_live_feed(limit: int = 60, days: int = 7):
    limit = max(10, min(limit, 200))
    days = max(1, min(days, 90))
    cutoff = time.time() - days * 86400

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            SELECT v.ts, v.ip, v.subnet, v.device, v.uid, v.page, v.action,
                   COALESCE(u.display_name, '') as nick,
                   COALESCE(u.active_char, 'student') as active_char
            FROM visits v
            LEFT JOIN users u ON u.uid = v.uid
            WHERE v.ts > ?
            ORDER BY v.ts DESC
            LIMIT ?
        """, (cutoff, limit))
        rows = await cur.fetchall()

    result = []
    for r in rows:
        ts, ip, subnet, device, uid, page, action, nick, active_char = r
        result.append({
            "ts": ts,
            "ip": ip,
            "subnet": subnet,
            "device": device or "desktop",
            "uid": uid or "",
            "nick": nick or "",
            "active_char": active_char or "student",
            "page": page or "",
            "action": action or "visit",
            "logged_in": bool(uid),
        })
    return result


# ═══════════════════════════════════════════════════════════
# ЗОНЫ IP — с устройствами и игроками
# ═══════════════════════════════════════════════════════════
async def get_ip_zones(days: int = 7, sort_by: str = "visits"):
    days = max(1, min(days, 90))
    cutoff = time.time() - days * 86400

    order = "visits DESC"
    if sort_by == "recent":
        order = "last_seen DESC"
    elif sort_by == "users":
        order = "users_count DESC"

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(f"""
            SELECT subnet,
                   COUNT(*) as visits,
                   COUNT(DISTINCT CASE WHEN uid != '' THEN uid END) as users_count,
                   SUM(CASE WHEN device = 'mobile' THEN 1 ELSE 0 END) as mobile_count,
                   MIN(ts) as first_seen,
                   MAX(ts) as last_seen
            FROM visits
            WHERE ts > ?
            GROUP BY subnet
            ORDER BY {order}
            LIMIT 100
        """, (cutoff,))
        rows = await cur.fetchall()

        zones = []
        for r in rows:
            subnet = r[0]
            if subnet == "unknown":
                continue

            # Игроки с этого subnet
            cur2 = await db.execute("""
                SELECT DISTINCT uid FROM visits
                WHERE subnet = ? AND uid != '' AND ts > ?
                LIMIT 10
            """, (subnet, cutoff))
            uids = [row[0] for row in await cur2.fetchall()]

            users = []
            if uids:
                placeholders = ",".join("?" * len(uids))
                cur3 = await db.execute(
                    f"SELECT uid, display_name FROM users WHERE uid IN ({placeholders})",
                    uids
                )
                nick_map = {row[0]: row[1] for row in await cur3.fetchall()}
                users = [{"uid": u, "nick": nick_map.get(u, "?")} for u in uids]

            # Устройства — берём User-Agent и упрощаем
            cur4 = await db.execute("""
                SELECT DISTINCT user_agent FROM visits
                WHERE subnet = ? AND user_agent != '' AND ts > ?
                LIMIT 30
            """, (subnet, cutoff))
            agents = [row[0] for row in await cur4.fetchall()]
            devices = _simplify_agents(agents)

            # Тег
            cur5 = await db.execute(
                "SELECT tag, label FROM ip_tags WHERE subnet=?", (subnet,)
            )
            tag_row = await cur5.fetchone()
            tag = tag_row[0] if tag_row else "unknown"
            label = tag_row[1] if tag_row else ""

            zones.append({
                "subnet": subnet,
                "visits": r[1] or 0,
                "users_count": r[2] or 0,
                "mobile_count": r[3] or 0,
                "first_seen": r[4],
                "last_seen": r[5],
                "tag": tag,
                "label": label,
                "users": users,
                "devices": devices,
            })

    return zones


def _simplify_agents(agents: list) -> list:
    """Превращает User-Agent в понятные названия устройств."""
    result = []
    seen = set()
    for ua in agents:
        ua_l = (ua or "").lower()
        name = "Неизвестно"
        if "iphone" in ua_l:
            name = "iPhone (Safari)"
            if "crios" in ua_l:
                name = "iPhone (Chrome)"
        elif "ipad" in ua_l:
            name = "iPad"
        elif "android" in ua_l:
            name = "Android"
        elif "windows" in ua_l:
            name = "Windows ПК"
        elif "macintosh" in ua_l or "mac os" in ua_l:
            name = "Mac"
        elif "linux" in ua_l:
            name = "Linux"
        if name not in seen:
            seen.add(name)
            result.append(name)
    return result[:5]


async def set_ip_tag(subnet: str, tag: str, label: str = ""):
    if tag not in ("mgsu", "dorm", "mobile", "other", "unknown"):
        tag = "unknown"
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO ip_tags (subnet, tag, label, first_seen, last_seen, visits)
            VALUES (?, ?, ?, ?, ?, 0)
            ON CONFLICT(subnet) DO UPDATE SET tag=?, label=?
        """, (subnet, tag, label[:60], time.time(), time.time(), tag, label[:60]))
        await db.commit()
    return {"ok": True}


# ═══════════════════════════════════════════════════════════
# ЧАСЫ С РАЗБИВКОЙ ПО УСТРОЙСТВАМ
# ═══════════════════════════════════════════════════════════
async def get_hourly_full(days: int = 7):
    days = max(1, min(days, 90))
    cutoff = time.time() - days * 86400

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            SELECT hour,
                   COUNT(*) as visits,
                   SUM(CASE WHEN device = 'mobile' THEN 1 ELSE 0 END) as mobile,
                   SUM(CASE WHEN device = 'desktop' THEN 1 ELSE 0 END) as desktop,
                   SUM(CASE WHEN device = 'tablet' THEN 1 ELSE 0 END) as tablet,
                   COUNT(DISTINCT CASE WHEN uid != '' THEN uid END) as uniques
            FROM visits
            WHERE ts > ?
            GROUP BY hour
        """, (cutoff,))
        rows = await cur.fetchall()

    result = {h: {"visits": 0, "mobile": 0, "desktop": 0, "tablet": 0, "uniques": 0} for h in range(24)}
    for r in rows:
        h = r[0]
        if 0 <= h <= 23:
            result[h] = {
                "visits": r[1] or 0,
                "mobile": r[2] or 0,
                "desktop": r[3] or 0,
                "tablet": r[4] or 0,
                "uniques": r[5] or 0,
            }

    return [{"hour": h, **result[h]} for h in range(24)]


async def get_hourly_stats(days: int = 1):
    """Оставлено для совместимости."""
    hourly = await get_hourly_full(days)
    return [{"hour": h["hour"], "visits": h["visits"], "uniques": h["uniques"]} for h in hourly]


# ═══════════════════════════════════════════════════════════
# ВОРОНКА
# ═══════════════════════════════════════════════════════════
async def get_funnel(days: int = 7):
    days = max(1, min(days, 90))
    cutoff = time.time() - days * 86400

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT COUNT(DISTINCT ip) FROM visits WHERE ts > ? AND ip != 'unknown'",
            (cutoff,)
        )
        visits_ips = (await cur.fetchone())[0] or 0

        cur = await db.execute(
            "SELECT COUNT(DISTINCT uid) FROM visits WHERE ts > ? AND uid != ''",
            (cutoff,)
        )
        users_seen = (await cur.fetchone())[0] or 0

        cur = await db.execute(
            "SELECT COUNT(*) FROM users WHERE created_at > ?",
            (cutoff,)
        )
        registered = (await cur.fetchone())[0] or 0

        cur = await db.execute(
            "SELECT COUNT(DISTINCT uid) FROM scores WHERE ts > ?",
            (cutoff,)
        )
        played = (await cur.fetchone())[0] or 0

        cur = await db.execute("""
            SELECT COUNT(*) FROM (
                SELECT uid, COUNT(DISTINCT substr(date(ts, 'unixepoch'), 1, 10)) as days
                FROM visits
                WHERE ts > ? AND uid != ''
                GROUP BY uid
                HAVING days >= 2
            )
        """, (cutoff,))
        returned = (await cur.fetchone())[0] or 0

    return {
        "ips": visits_ips,
        "users": users_seen,
        "registered": registered,
        "played": played,
        "returned": returned,
    }


# ═══════════════════════════════════════════════════════════
# СВОДКА
# ═══════════════════════════════════════════════════════════
async def get_summary(days: int = 7):
    days = max(1, min(days, 90))
    cutoff = time.time() - days * 86400

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            SELECT COUNT(*) as visits,
                   COUNT(DISTINCT ip) as uniq_ips,
                   COUNT(DISTINCT CASE WHEN uid != '' THEN uid END) as uniq_users,
                   SUM(CASE WHEN device = 'mobile' THEN 1 ELSE 0 END) as mobile,
                   SUM(CASE WHEN device = 'desktop' THEN 1 ELSE 0 END) as desktop
            FROM visits WHERE ts > ?
        """, (cutoff,))
        r = await cur.fetchone()

    return {
        "visits": r[0] or 0,
        "uniq_ips": r[1] or 0,
        "uniq_users": r[2] or 0,
        "mobile": r[3] or 0,
        "desktop": r[4] or 0,
    }


# ═══════════════════════════════════════════════════════════
# СТАРЫЕ ФУНКЦИИ (для совместимости)
# ═══════════════════════════════════════════════════════════
async def get_ip_summary():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            SELECT subnet, tag, label, visits, first_seen, last_seen
            FROM ip_tags
            ORDER BY visits DESC
            LIMIT 50
        """)
        rows = await cur.fetchall()
    return [
        {
            "subnet": r[0], "tag": r[1], "label": r[2],
            "visits": r[3], "first_seen": r[4], "last_seen": r[5],
        }
        for r in rows
    ]


async def get_device_stats(days: int = 7):
    days = max(1, min(days, 30))
    cutoff_ts = time.time() - days * 86400
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            SELECT device, COUNT(*) FROM visits
            WHERE ts >= ? GROUP BY device
        """, (cutoff_ts,))
        rows = await cur.fetchall()
    total = sum(r[1] for r in rows) or 1
    return [
        {"device": r[0] or "unknown", "count": r[1], "pct": round(r[1] / total * 100)}
        for r in rows
    ]


async def get_geo_summary():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            SELECT tag, SUM(visits) FROM ip_tags GROUP BY tag
        """)
        rows = await cur.fetchall()
    labels = {
        "mgsu": "МГСУ", "dorm": "Общежитие", "mobile": "Мобильный",
        "other": "Другое", "unknown": "Не размечено",
    }
    total = sum(r[1] or 0 for r in rows) or 1
    return [
        {
            "tag": r[0], "label": labels.get(r[0], r[0]),
            "visits": r[1] or 0, "pct": round((r[1] or 0) / total * 100),
        }
        for r in rows
    ]
