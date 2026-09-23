"""
Сбор IP, подсети и часов активности.
Все заходы сохраняются в таблицу visits, агрегат по часам — в daily_hours.
"""
import time, aiosqlite
from datetime import datetime
from config import DB_PATH, MSK, today_str


def normalize_ip(ip: str) -> str:
    """Убирает IPv6-обёртку и пустые значения."""
    if not ip:
        return "unknown"
    ip = ip.strip()
    if ip.startswith("::ffff:"):
        ip = ip[7:]
    return ip


def get_subnet(ip: str) -> str:
    """
    Возвращает подсеть вида '123.45.67' (первые 3 октета IPv4).
    Для IPv6 — берёт первые 4 группы.
    """
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
    if "mobile" in ua or "android" in ua or "iphone" in ua:
        return "mobile"
    if "tablet" in ua or "ipad" in ua:
        return "tablet"
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
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_visits_day_hour
            ON visits (hour, ts)
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


async def track_visit(ip: str, user_agent: str, uid: str = ""):
    """Сохраняет заход и обновляет агрегаты."""
    ip = normalize_ip(ip)
    subnet = get_subnet(ip)
    device = classify_device(user_agent)
    now_ts = time.time()
    now_msk = datetime.now(MSK)
    hour = now_msk.hour
    day = today_str()

    async with aiosqlite.connect(DB_PATH) as db:
        # 1. Запись в visits
        await db.execute("""
            INSERT INTO visits (uid, ip, subnet, device, hour, ts)
            VALUES (?,?,?,?,?,?)
        """, (uid or "", ip, subnet, device, hour, now_ts))

        # 2. Агрегат по часам
        cur = await db.execute(
            "SELECT visits, uniques FROM daily_hours WHERE day=? AND hour=?",
            (day, hour)
        )
        row = await cur.fetchone()
        if row:
            visits, uniques = row
            inc_unique = 0
            if uid:
                # проверяем, был ли этот uid в этот час
                c2 = await db.execute(
                    "SELECT 1 FROM visits WHERE uid=? AND hour=? AND ts >= ? LIMIT 1",
                    (uid, hour, now_ts - 3600 * 24)
                )
                is_new = await c2.fetchone() is None
                inc_unique = 1 if is_new else 0
            await db.execute("""
                UPDATE daily_hours SET visits=visits+1, uniques=uniques+?
                WHERE day=? AND hour=?
            """, (inc_unique, day, hour))
        else:
            await db.execute("""
                INSERT INTO daily_hours (day, hour, visits, uniques)
                VALUES (?,?,?,?)
            """, (day, hour, 1, 1 if uid else 0))

        # 3. IP-тег (если новая подсеть — создаём запись)
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


# ============ АНАЛИТИКА ДЛЯ АДМИНКИ ============

async def get_ip_summary():
    """Список подсетей с тегами для админки."""
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
            "subnet": r[0],
            "tag": r[1],
            "label": r[2],
            "visits": r[3],
            "first_seen": r[4],
            "last_seen": r[5],
        }
        for r in rows
    ]


async def set_ip_tag(subnet: str, tag: str, label: str = ""):
    if tag not in ("mgsu", "dorm", "mobile", "other", "unknown"):
        tag = "unknown"
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE ip_tags SET tag=?, label=? WHERE subnet=?",
            (tag, label[:60], subnet)
        )
        await db.commit()
    return {"ok": True}


async def get_hourly_stats(days: int = 1):
    """
    Агрегат по часам за последние N дней.
    Возвращает список из 24 записей.
    """
    from datetime import timedelta
    days = max(1, min(days, 30))
    cutoff_day = (datetime.now(MSK) - timedelta(days=days - 1)).strftime("%Y-%m-%d")

    result = {h: {"visits": 0, "uniques": 0} for h in range(24)}

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            SELECT hour, SUM(visits), SUM(uniques)
            FROM daily_hours
            WHERE day >= ?
            GROUP BY hour
        """, (cutoff_day,))
        rows = await cur.fetchall()

    for r in rows:
        h, v, u = r[0], r[1] or 0, r[2] or 0
        if 0 <= h <= 23:
            result[h] = {"visits": v, "uniques": u}

    return [
        {"hour": h, "visits": result[h]["visits"], "uniques": result[h]["uniques"]}
        for h in range(24)
    ]


async def get_device_stats(days: int = 7):
    from datetime import timedelta
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
    """Сколько заходов в каждой категории IP."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            SELECT tag, SUM(visits) FROM ip_tags GROUP BY tag
        """)
        rows = await cur.fetchall()

    labels = {
        "mgsu": "МГСУ",
        "dorm": "Общежитие",
        "mobile": "Мобильный",
        "other": "Другое",
        "unknown": "Не размечено",
    }
    total = sum(r[1] or 0 for r in rows) or 1
    return [
        {
            "tag": r[0],
            "label": labels.get(r[0], r[0]),
            "visits": r[1] or 0,
            "pct": round((r[1] or 0) / total * 100),
        }
        for r in rows
    ]
