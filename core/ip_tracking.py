"""
Сбор IP, visitor_id, подсети и часов активности.
visitor_id — анонимный ID браузера (в localStorage).
Именно он используется для подсчёта ЛЮДЕЙ, а не IP.
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


def classify_device_brand(user_agent: str) -> str:
    """iPhone / Android / Windows / Mac / Linux / другое"""
    ua = (user_agent or "").lower()
    if "iphone" in ua:
        return "iPhone"
    if "ipad" in ua:
        return "iPad"
    if "android" in ua:
        return "Android"
    if "windows" in ua:
        return "Windows"
    if "macintosh" in ua or "mac os" in ua:
        return "Mac"
    if "linux" in ua:
        return "Linux"
    return "другое"


async def db_init_ip():
    async with aiosqlite.connect(DB_PATH) as db:
        # ═══ Таблица visits ═══
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

        # ═══ Миграции visits ═══
        try:
            cur = await db.execute("PRAGMA table_info(visits)")
            existing = {row[1] for row in await cur.fetchall()}
        except Exception:
            existing = set()

        for col, ddl in [
            ("page",        "ALTER TABLE visits ADD COLUMN page TEXT DEFAULT ''"),
            ("action",      "ALTER TABLE visits ADD COLUMN action TEXT DEFAULT 'visit'"),
            ("user_agent",  "ALTER TABLE visits ADD COLUMN user_agent TEXT DEFAULT ''"),
            ("visitor_id",  "ALTER TABLE visits ADD COLUMN visitor_id TEXT DEFAULT ''"),
            ("source",      "ALTER TABLE visits ADD COLUMN source TEXT DEFAULT ''"),
        ]:
            if col not in existing:
                try:
                    await db.execute(ddl)
                except Exception as e:
                    print("visits migration:", e)

        # ═══ Таблица visitors — реестр уникальных посетителей ═══
        await db.execute("""
            CREATE TABLE IF NOT EXISTS visitors (
                visitor_id TEXT PRIMARY KEY,
                first_seen REAL,
                last_seen REAL,
                first_source TEXT DEFAULT '',
                is_admin INTEGER DEFAULT 0,
                linked_uid TEXT DEFAULT '',
                device_brand TEXT DEFAULT '',
                device_type TEXT DEFAULT ''
            )
        """)

        # ═══ Индексы ═══
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_visits_day_hour
            ON visits (hour, ts)
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_visits_subnet
            ON visits (subnet, ts)
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_visits_vid
            ON visits (visitor_id, ts)
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_visitors_first
            ON visitors (first_seen)
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
                      page: str = "", action: str = "visit",
                      visitor_id: str = "", source: str = ""):
    """Сохраняет заход. visitor_id — главный идентификатор человека."""
    ip = normalize_ip(ip)
    subnet = get_subnet(ip)
    device = classify_device(user_agent)
    device_brand = classify_device_brand(user_agent)
    now_ts = time.time()
    now_msk = datetime.now(MSK)
    hour = now_msk.hour
    day = today_str()

    page = (page or "")[:100]
    action = (action or "visit")[:30]
    user_agent = (user_agent or "")[:300]
    visitor_id = (visitor_id or "")[:64]
    source = (source or "")[:40]
    uid = (uid or "")[:64]

    async with aiosqlite.connect(DB_PATH) as db:
        # 1. Пишем заход
        await db.execute("""
            INSERT INTO visits
            (uid, ip, subnet, device, hour, ts, page, action, user_agent, visitor_id, source)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, (uid, ip, subnet, device, hour, now_ts, page, action,
              user_agent, visitor_id, source))

        # 2. Обновляем реестр visitors
        if visitor_id:
            cur = await db.execute(
                "SELECT visitor_id, is_admin, linked_uid FROM visitors WHERE visitor_id=?",
                (visitor_id,)
            )
            row = await cur.fetchone()
            if row:
                # уже есть — обновляем last_seen и linked_uid
                new_linked = row[2] or uid
                await db.execute("""
                    UPDATE visitors SET last_seen=?, linked_uid=?, device_brand=?, device_type=?
                    WHERE visitor_id=?
                """, (now_ts, new_linked, device_brand, device, visitor_id))
            else:
                await db.execute("""
                    INSERT INTO visitors
                    (visitor_id, first_seen, last_seen, first_source, is_admin, linked_uid, device_brand, device_type)
                    VALUES (?,?,?,?,0,?,?,?)
                """, (visitor_id, now_ts, now_ts, source, uid, device_brand, device))

        # 3. Агрегат по часам
        cur = await db.execute(
            "SELECT visits FROM daily_hours WHERE day=? AND hour=?",
            (day, hour)
        )
        r2 = await cur.fetchone()
        if r2:
            await db.execute("""
                UPDATE daily_hours SET visits=visits+1 WHERE day=? AND hour=?
            """, (day, hour))
        else:
            await db.execute("""
                INSERT INTO daily_hours (day, hour, visits, uniques)
                VALUES (?,?,?,?)
            """, (day, hour, 1, 0))

        # 4. IP-тег
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


async def mark_admin_visitor(visitor_id: str):
    """Помечает visitor_id как админский — исключается из статистики."""
    if not visitor_id:
        return
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT visitor_id FROM visitors WHERE visitor_id=?", (visitor_id,)
        )
        if await cur.fetchone():
            await db.execute(
                "UPDATE visitors SET is_admin=1 WHERE visitor_id=?", (visitor_id,)
            )
        else:
            now = time.time()
            await db.execute("""
                INSERT INTO visitors
                (visitor_id, first_seen, last_seen, first_source, is_admin, linked_uid, device_brand, device_type)
                VALUES (?,?,?,'admin',1,'','','')
            """, (visitor_id, now, now))
        await db.commit()


async def link_visitor_to_uid(visitor_id: str, uid: str):
    """Связывает visitor_id с uid после регистрации/логина."""
    if not visitor_id or not uid:
        return
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE visitors SET linked_uid=? WHERE visitor_id=?
        """, (uid, visitor_id))
        await db.commit()


# ═══════════════════════════════════════════════════════════
# ОБЗОР — главные цифры
# ═══════════════════════════════════════════════════════════
async def get_overview(days: int = 7):
    """Главные цифры за период."""
    days = max(1, min(days, 90))
    now_ts = time.time()
    cutoff = now_ts - days * 86400
    prev_cutoff = cutoff - days * 86400

    async with aiosqlite.connect(DB_PATH) as db:
        # 1. Уникальные посетители за период (не админы)
        cur = await db.execute("""
            SELECT COUNT(DISTINCT v.visitor_id)
            FROM visits v
            JOIN visitors vi ON vi.visitor_id = v.visitor_id
            WHERE v.ts > ? AND v.visitor_id != '' AND vi.is_admin = 0
        """, (cutoff,))
        visitors_now = (await cur.fetchone())[0] or 0

        # 2. То же за прошлый период (для сравнения)
        cur = await db.execute("""
            SELECT COUNT(DISTINCT v.visitor_id)
            FROM visits v
            JOIN visitors vi ON vi.visitor_id = v.visitor_id
            WHERE v.ts > ? AND v.ts <= ? AND v.visitor_id != '' AND vi.is_admin = 0
        """, (prev_cutoff, cutoff))
        visitors_prev = (await cur.fetchone())[0] or 0

        # 3. Новые (first_seen в этом периоде)
        cur = await db.execute("""
            SELECT COUNT(*) FROM visitors
            WHERE first_seen > ? AND visitor_id != '' AND is_admin = 0
        """, (cutoff,))
        new_visitors = (await cur.fetchone())[0] or 0

        # 4. Вернувшиеся = всего - новые
        returning = max(0, visitors_now - new_visitors)

        # 5. Зарегистрированные uid (всего)
        cur = await db.execute("""
            SELECT COUNT(*) FROM users WHERE created_at > ?
        """, (cutoff,))
        registered_now = (await cur.fetchone())[0] or 0

        cur = await db.execute("""
            SELECT COUNT(*) FROM users WHERE created_at > ? AND created_at <= ?
        """, (prev_cutoff, cutoff))
        registered_prev = (await cur.fetchone())[0] or 0

        # 6. Играли хотя бы раз (уникальные uid в scores)
        cur = await db.execute("""
            SELECT COUNT(DISTINCT uid) FROM scores WHERE ts > ?
        """, (cutoff,))
        played_now = (await cur.fetchone())[0] or 0

        cur = await db.execute("""
            SELECT COUNT(DISTINCT uid) FROM scores WHERE ts > ? AND ts <= ?
        """, (prev_cutoff, cutoff))
        played_prev = (await cur.fetchone())[0] or 0

        # 7. Всего партий
        cur = await db.execute("""
            SELECT COUNT(*) FROM scores WHERE ts > ?
        """, (cutoff,))
        games_now = (await cur.fetchone())[0] or 0

        cur = await db.execute("""
            SELECT COUNT(*) FROM scores WHERE ts > ? AND ts <= ?
        """, (prev_cutoff, cutoff))
        games_prev = (await cur.fetchone())[0] or 0

        # 8. D1 retention — из тех, кто зарегался за период, кто вернулся на след. день
        cur = await db.execute("""
            SELECT u.uid, u.created_at
            FROM users u
            WHERE u.created_at > ?
        """, (cutoff,))
        reg_rows = await cur.fetchall()

    # D1 считаем в Python (Turso не умеет date arithmetic в SQL)
    d1_count = 0
    d1_total = 0
    for uid, created in reg_rows:
        if not uid or not created:
            continue
        d1_total += 1
        next_day_start = created + 86400
        next_day_end = created + 2 * 86400
        # Отдельный запрос — но их немного, только для D1
        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute("""
                SELECT 1 FROM visits
                WHERE uid=? AND ts > ? AND ts < ?
                LIMIT 1
            """, (uid, next_day_start, next_day_end))
            if await cur.fetchone():
                d1_count += 1

    d1_pct = round(d1_count / d1_total * 100) if d1_total else 0

    def delta(now, prev):
        if prev == 0:
            return None
        return round((now - prev) / prev * 100)

    return {
        "days": days,
        "visitors": visitors_now,
        "visitors_delta": delta(visitors_now, visitors_prev),
        "new_visitors": new_visitors,
        "returning": returning,
        "registered": registered_now,
        "registered_delta": delta(registered_now, registered_prev),
        "played": played_now,
        "played_delta": delta(played_now, played_prev),
        "games": games_now,
        "games_delta": delta(games_now, games_prev),
        "d1_pct": d1_pct,
        "d1_count": d1_count,
        "d1_total": d1_total,
    }


# ═══════════════════════════════════════════════════════════
# ВОРОНКА v2 — чистая, без дублей
# ═══════════════════════════════════════════════════════════
async def get_funnel_v2(days: int = 7):
    days = max(1, min(days, 90))
    cutoff = time.time() - days * 86400

    async with aiosqlite.connect(DB_PATH) as db:
        # 1. Посетители
        cur = await db.execute("""
            SELECT COUNT(DISTINCT v.visitor_id)
            FROM visits v
            JOIN visitors vi ON vi.visitor_id = v.visitor_id
            WHERE v.ts > ? AND v.visitor_id != '' AND vi.is_admin = 0
        """, (cutoff,))
        step1 = (await cur.fetchone())[0] or 0

        # 2. Зарегались
        cur = await db.execute("SELECT COUNT(*) FROM users WHERE created_at > ?", (cutoff,))
        step2 = (await cur.fetchone())[0] or 0

        # 3. Сыграли
        cur = await db.execute(
            "SELECT COUNT(DISTINCT uid) FROM scores WHERE ts > ?", (cutoff,)
        )
        step3 = (await cur.fetchone())[0] or 0

        # 4. Вернулись (2+ заходов)
        cur = await db.execute("""
            SELECT COUNT(*) FROM (
                SELECT v.visitor_id, COUNT(*) as cnt
                FROM visits v
                JOIN visitors vi ON vi.visitor_id = v.visitor_id
                WHERE v.ts > ? AND v.visitor_id != '' AND vi.is_admin = 0
                GROUP BY v.visitor_id
                HAVING cnt >= 2
            )
        """, (cutoff,))
        step4 = (await cur.fetchone())[0] or 0

    def pct(a, b):
        return round(a / b * 100) if b else 0

    return {
        "steps": [
            {"icon": "👥", "label": "Посетители", "value": step1, "pct": 100},
            {"icon": "🎉", "label": "Зарегались", "value": step2, "pct": pct(step2, step1)},
            {"icon": "🎮", "label": "Сыграли", "value": step3, "pct": pct(step3, step2)},
            {"icon": "🔁", "label": "Вернулись", "value": step4, "pct": pct(step4, step3)},
        ]
    }


# ═══════════════════════════════════════════════════════════
# ЖИВАЯ ЛЕНТА
# ═══════════════════════════════════════════════════════════
async def get_live_feed(limit: int = 60, days: int = 7, include_admin: bool = False):
    limit = max(10, min(limit, 200))
    days = max(1, min(days, 90))
    cutoff = time.time() - days * 86400

    async with aiosqlite.connect(DB_PATH) as db:
        if include_admin:
            cur = await db.execute("""
                SELECT v.ts, v.ip, v.subnet, v.device, v.uid, v.page, v.action,
                       COALESCE(u.display_name, '') as nick,
                       COALESCE(u.active_char, 'student') as active_char,
                       COALESCE(vi.is_admin, 0) as is_admin
                FROM visits v
                LEFT JOIN users u ON u.uid = v.uid
                LEFT JOIN visitors vi ON vi.visitor_id = v.visitor_id
                WHERE v.ts > ?
                ORDER BY v.ts DESC
                LIMIT ?
            """, (cutoff, limit))
        else:
            cur = await db.execute("""
                SELECT v.ts, v.ip, v.subnet, v.device, v.uid, v.page, v.action,
                       COALESCE(u.display_name, '') as nick,
                       COALESCE(u.active_char, 'student') as active_char,
                       0 as is_admin
                FROM visits v
                LEFT JOIN users u ON u.uid = v.uid
                LEFT JOIN visitors vi ON vi.visitor_id = v.visitor_id
                WHERE v.ts > ? AND COALESCE(vi.is_admin, 0) = 0
                ORDER BY v.ts DESC
                LIMIT ?
            """, (cutoff, limit))
        rows = await cur.fetchall()

    result = []
    for r in rows:
        ts, ip, subnet, device, uid, page, action, nick, active_char, is_admin = r
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
            "is_admin": bool(is_admin),
        })
    return result


# ═══════════════════════════════════════════════════════════
# УСТРОЙСТВА — агрегация по брендам
# ═══════════════════════════════════════════════════════════
async def get_devices(days: int = 7):
    days = max(1, min(days, 90))
    cutoff = time.time() - days * 86400

    async with aiosqlite.connect(DB_PATH) as db:
        # По типу устройства
        cur = await db.execute("""
            SELECT
                SUM(CASE WHEN v.device = 'mobile' THEN 1 ELSE 0 END) as mobile,
                SUM(CASE WHEN v.device = 'desktop' THEN 1 ELSE 0 END) as desktop,
                SUM(CASE WHEN v.device = 'tablet' THEN 1 ELSE 0 END) as tablet
            FROM visits v
            JOIN visitors vi ON vi.visitor_id = v.visitor_id
            WHERE v.ts > ? AND vi.is_admin = 0
        """, (cutoff,))
        r = await cur.fetchone()
        mobile = r[0] or 0
        desktop = r[1] or 0
        tablet = r[2] or 0

        # По бренду
        cur = await db.execute("""
            SELECT device_brand, COUNT(*) as cnt
            FROM visitors
            WHERE is_admin = 0 AND device_brand != ''
            GROUP BY device_brand
            ORDER BY cnt DESC
        """)
        brand_rows = await cur.fetchall()

    return {
        "mobile": mobile,
        "desktop": desktop,
        "tablet": tablet,
        "brands": [{"name": b[0], "count": b[1]} for b in brand_rows],
    }


# ═══════════════════════════════════════════════════════════
# ЧАСЫ С РАЗБИВКОЙ ПО УСТРОЙСТВАМ
# ═══════════════════════════════════════════════════════════
async def get_hourly_full(days: int = 7):
    days = max(1, min(days, 90))
    cutoff = time.time() - days * 86400

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            SELECT v.hour,
                   COUNT(*) as visits,
                   SUM(CASE WHEN v.device = 'mobile' THEN 1 ELSE 0 END) as mobile,
                   SUM(CASE WHEN v.device = 'desktop' THEN 1 ELSE 0 END) as desktop,
                   SUM(CASE WHEN v.device = 'tablet' THEN 1 ELSE 0 END) as tablet
            FROM visits v
            JOIN visitors vi ON vi.visitor_id = v.visitor_id
            WHERE v.ts > ? AND vi.is_admin = 0
            GROUP BY v.hour
        """, (cutoff,))
        rows = await cur.fetchall()

    result = {h: {"visits": 0, "mobile": 0, "desktop": 0, "tablet": 0} for h in range(24)}
    for r in rows:
        h = r[0]
        if 0 <= h <= 23:
            result[h] = {
                "visits": r[1] or 0,
                "mobile": r[2] or 0,
                "desktop": r[3] or 0,
                "tablet": r[4] or 0,
            }

    return [{"hour": h, **result[h]} for h in range(24)]


async def get_hourly_stats(days: int = 1):
    hourly = await get_hourly_full(days)
    return [{"hour": h["hour"], "visits": h["visits"], "uniques": 0} for h in hourly]


# ═══════════════════════════════════════════════════════════
# СВОДКА (для совместимости)
# ═══════════════════════════════════════════════════════════
async def get_summary(days: int = 7):
    days = max(1, min(days, 90))
    cutoff = time.time() - days * 86400

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            SELECT COUNT(*) as visits,
                   COUNT(DISTINCT v.visitor_id) as uniq_visitors,
                   COUNT(DISTINCT CASE WHEN v.uid != '' THEN v.uid END) as uniq_users,
                   SUM(CASE WHEN v.device = 'mobile' THEN 1 ELSE 0 END) as mobile,
                   SUM(CASE WHEN v.device = 'desktop' THEN 1 ELSE 0 END) as desktop
            FROM visits v
            JOIN visitors vi ON vi.visitor_id = v.visitor_id
            WHERE v.ts > ? AND vi.is_admin = 0
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
# ЗОНЫ IP — упрощённая версия
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
        cur = await db.execute(f"""
            SELECT v.subnet,
                   COUNT(*) as visits,
                   COUNT(DISTINCT CASE WHEN v.uid != '' THEN v.uid END) as users_count,
                   SUM(CASE WHEN v.device = 'mobile' THEN 1 ELSE 0 END) as mobile_count,
                   MIN(v.ts) as first_seen,
                   MAX(v.ts) as last_seen
            FROM visits v
            JOIN visitors vi ON vi.visitor_id = v.visitor_id
            WHERE v.ts > ? AND v.subnet != 'unknown' AND vi.is_admin = 0
            GROUP BY v.subnet
            ORDER BY {order}
            LIMIT 40
        """, (cutoff,))
        rows = await cur.fetchall()

        if not rows:
            return []

        subnets = [r[0] for r in rows]
        placeholders = ",".join("?" * len(subnets))

        cur = await db.execute(f"""
            SELECT DISTINCT v.subnet, v.uid
            FROM visits v
            JOIN visitors vi ON vi.visitor_id = v.visitor_id
            WHERE v.subnet IN ({placeholders})
              AND v.uid != ''
              AND v.ts > ?
              AND vi.is_admin = 0
        """, subnets + [cutoff])
        uid_rows = await cur.fetchall()

        subnet_uids = {}
        all_uids = set()
        for sub, uid in uid_rows:
            lst = subnet_uids.setdefault(sub, [])
            if len(lst) < 10:
                lst.append(uid)
            all_uids.add(uid)

        nick_map = {}
        if all_uids:
            uid_list = list(all_uids)
            ph2 = ",".join("?" * len(uid_list))
            cur = await db.execute(
                f"SELECT uid, display_name FROM users WHERE uid IN ({ph2})",
                uid_list
            )
            nick_map = {r[0]: r[1] for r in await cur.fetchall()}

    zones = []
    for r in rows:
        subnet = r[0]
        uids = subnet_uids.get(subnet, [])
        users = [{"uid": u, "nick": nick_map.get(u, "?")} for u in uids]

        zones.append({
            "subnet": subnet,
            "visits": r[1] or 0,
            "users_count": r[2] or 0,
            "mobile_count": r[3] or 0,
            "first_seen": r[4],
            "last_seen": r[5],
            "tag": "unknown",
            "label": "",
            "users": users,
            "devices": [],
        })

    return zones


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
# СТАРЫЕ ФУНКЦИИ (совместимость)
# ═══════════════════════════════════════════════════════════
async def get_ip_summary():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            SELECT subnet, tag, label, visits, first_seen, last_seen
            FROM ip_tags ORDER BY visits DESC LIMIT 50
        """)
        rows = await cur.fetchall()
    return [{"subnet": r[0], "tag": r[1], "label": r[2],
             "visits": r[3], "first_seen": r[4], "last_seen": r[5]} for r in rows]


async def get_device_stats(days: int = 7):
    d = await get_devices(days)
    total = (d["mobile"] + d["desktop"] + d["tablet"]) or 1
    out = []
    if d["mobile"]:
        out.append({"device": "mobile", "count": d["mobile"], "pct": round(d["mobile"]/total*100)})
    if d["desktop"]:
        out.append({"device": "desktop", "count": d["desktop"], "pct": round(d["desktop"]/total*100)})
    if d["tablet"]:
        out.append({"device": "tablet", "count": d["tablet"], "pct": round(d["tablet"]/total*100)})
    return out


async def get_geo_summary():
    return []
