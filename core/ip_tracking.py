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
# ЗОНЫ IP — ОПТИМИЗИРОВАНО (5 запросов вместо 230)
# ═══════════════════════════════════════════════════════════
async def get_ip_zones(days: int = 7, sort_by: str = "visits"):
    days = max(1, min(days, 90))
    cutoff = time.time() - days * 86400

    order_map = {
        "visits": "visits DESC",
        "recent": "last_seen DESC",
        "users":  "users_count DESC",
    }
    order = order_map.get(sort_by, "visits DESC")

    async with aiosqlite.connect(DB_PATH) as db:
        # 1. Агрегация по подсетям
        cur = await db.execute(f"""
            SELECT subnet,
                   COUNT(*) as visits,
                   COUNT(DISTINCT CASE WHEN uid != '' THEN uid END) as users_count,
                   SUM(CASE WHEN device = 'mobile' THEN 1 ELSE 0 END) as mobile_count,
                   MIN(ts) as first_seen,
                   MAX(ts) as last_seen
            FROM visits
            WHERE ts > ? AND subnet != 'unknown'
            GROUP BY subnet
            ORDER BY {order}
            LIMIT 40
        """, (cutoff,))
        rows = await cur.fetchall()

        if not rows:
            return []

        subnets = [r[0] for r in rows]
        placeholders = ",".join("?" * len(subnets))

        # 2. Игроки по всем подсетям одним запросом
        cur = await db.execute(f"""
            SELECT DISTINCT subnet, uid
            FROM visits
            WHERE subnet IN ({placeholders})
              AND uid != ''
              AND ts > ?
        """, subnets + [cutoff])
        uid_rows = await cur.fetchall()

        subnet_uids = {}
        all_uids = set()
        for sub, uid in uid_rows:
            lst = subnet_uids.setdefault(sub, [])
            if len(lst) < 10:
                lst.append(uid)
            all_uids.add(uid)

        # 3. Ники по всем uid
        nick_map = {}
        if all_uids:
            uid_list = list(all_uids)
            ph2 = ",".join("?" * len(uid_list))
            cur = await db.execute(
                f"SELECT uid, display_name FROM users WHERE uid IN ({ph2})",
                uid_list
            )
            nick_map = {r[0]: r[1] for r in await cur.fetchall()}

        # 4. User-Agent'ы по подсетям
        cur = await db.execute(f"""
            SELECT DISTINCT subnet, user_agent
            FROM visits
            WHERE subnet IN ({placeholders})
              AND user_agent != ''
              AND ts > ?
            LIMIT 2000
        """, subnets + [cutoff])
        agent_rows = await cur.fetchall()

        subnet_agents = {}
        for sub, ua in agent_rows:
            s = subnet_agents.setdefault(sub, set())
            if len(s) < 30:
                s.add(ua)

        # 5. Теги
        cur = await db.execute(f"""
            SELECT subnet, tag, label FROM ip_tags
            WHERE subnet IN ({placeholders})
        """, subnets)
        tag_map = {r[0]: (r[1], r[2]) for r in await cur.fetchall()}

    zones = []
    for r in rows:
        subnet = r[0]
        uids = subnet_uids.get(subnet, [])
        users = [{"uid": u, "nick": nick_map.get(u, "?")} for u in uids]

        agents = list(subnet_agents.get(subnet, set()))
        devices = _simplify_agents(agents)

        tag_row = tag_map.get(subnet, ("unknown", ""))

        zones.append({
            "subnet": subnet,
            "visits": r[1] or 0,
            "users_count": r[2] or 0,
            "mobile_count": r[3] or 0,
            "first_seen": r[4],
            "last_seen": r[5],
            "tag": tag_row[0],
            "label": tag_row[1],
            "users": users,
            "devices": devices,
        })

    return zones


def _simplify_agents(agents: list) -> list:
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
        cur = await db.execute("SELECT subnet FROM ip_tags WHERE subnet=?", (subnet,))
        row = await cur.fetchone()
        if row:
            await db.execute(
                "UPDATE ip_tags SET tag=?, label=? WHERE subnet=?",
                (tag, label[:60], subnet)
            )
        else:
            await db.execute(
                "INSERT INTO ip_tags (subnet, tag, label, first_seen, last_seen, visits) "
                "VALUES (?,?,?,?,?,0)",
                (subnet, tag, label[:60], time.time(), time.time())
            )
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
    hourly = await get_hourly_full(days)
    return [{"hour": h["hour"], "visits": h["visits"], "uniques": h["uniques"]} for h in hourly]


# ═══════════════════════════════════════════════════════════
# ВОРОНКА — УБРАН date(ts, 'unixepoch') — Turso не поддерживает
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

        # Turso не умеет date(ts, 'unixepoch') — считаем по количеству заходов
        cur = await db.execute("""
            SELECT COUNT(*) FROM (
                SELECT uid, COUNT(*) as cnt
                FROM visits
                WHERE ts > ? AND uid != ''
                GROUP BY uid
                HAVING cnt >= 2
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
# СТАРЫЕ ФУНКЦИИ
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
