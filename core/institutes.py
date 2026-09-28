"""
Институты МГСУ — кланы. Игрок выбирает институт, все его очки идут в копилку.
"""
import time, aiosqlite
from config import DB_PATH


INSTITUTES = [
    {"key":"iag",     "short":"ИАГ",    "name":"Институт архитектуры и градостроительства", "emoji":"🏛️"},
    {"key":"iges",    "short":"ИГЭС",   "name":"Институт гидротехнического и энергетического строительства", "emoji":"💧"},
    {"key":"iiesm",   "short":"ИИЭСМ",  "name":"Институт инженерно-экологического строительства и механизации", "emoji":"🌱"},
    {"key":"ieucksn", "short":"ИЭУКСН", "name":"Институт экономики, управления и коммуникаций", "emoji":"📊"},
    {"key":"ictms",   "short":"ИЦТМС",  "name":"Институт цифровых технологий и моделирования", "emoji":"💻"},
    {"key":"ifks",    "short":"ИФКС",   "name":"Институт фундаментального образования", "emoji":"📐"},
    {"key":"ido",     "short":"ИДО",    "name":"Институт дистанционного образования", "emoji":"🌐"},
    {"key":"mf",      "short":"МФ",     "name":"Механический факультет", "emoji":"⚙️"},
    {"key":"ipgs",    "short":"ИПГС",   "name":"Институт промышленного и гражданского строительства", "emoji":"🏗️"},
    {"key":"pgtu",    "short":"ПГТУ",   "name":"Политехнический государственный технический университет", "emoji":"🎓"},
    {"key":"donnasa", "short":"ДОННАСА","name":"Донбасская национальная академия строительства и архитектуры", "emoji":"🏫"},
]

INSTITUTE_MAP = {i["key"]: i for i in INSTITUTES}


def get_institute(key: str):
    return INSTITUTE_MAP.get(key)


def get_short(key: str) -> str:
    inst = INSTITUTE_MAP.get(key)
    return inst["short"] if inst else "—"


async def db_init_institutes():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS institute_scores (
                uid TEXT,
                institute TEXT,
                score_sum INTEGER DEFAULT 0,
                games_count INTEGER DEFAULT 0,
                updated_at REAL,
                PRIMARY KEY (uid, institute)
            )
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_inst_sum ON institute_scores (institute, score_sum DESC)
        """)
        await db.commit()


async def add_score(uid: str, institute: str, points: int):
    """Добавить очки в копилку института. Не считается, если нет института."""
    if not institute or not uid or points <= 0:
        return
    now = time.time()
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT score_sum, games_count FROM institute_scores WHERE uid=? AND institute=?",
            (uid, institute)
        )
        row = await cur.fetchone()
        if row:
            await db.execute("""
                UPDATE institute_scores
                SET score_sum = score_sum + ?, games_count = games_count + 1, updated_at = ?
                WHERE uid=? AND institute=?
            """, (points, now, uid, institute))
        else:
            await db.execute("""
                INSERT INTO institute_scores (uid, institute, score_sum, games_count, updated_at)
                VALUES (?,?,?,?,?)
            """, (uid, institute, points, 1, now))
        await db.commit()


async def get_institutes_rating(limit: int = 11):
    """Топ институтов по сумме очков."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            SELECT institute,
                   SUM(score_sum) as total,
                   COUNT(DISTINCT uid) as players,
                   SUM(games_count) as games
            FROM institute_scores
            GROUP BY institute
            ORDER BY total DESC
            LIMIT ?
        """, (limit,))
        rows = await cur.fetchall()

    result = []
    for r in rows:
        key, total, players, games = r
        inst = INSTITUTE_MAP.get(key, {})
        avg = round(total / players) if players else 0
        result.append({
            "key": key,
            "short": inst.get("short", key),
            "name": inst.get("name", ""),
            "emoji": inst.get("emoji", "🏫"),
            "total": total or 0,
            "players": players or 0,
            "games": games or 0,
            "avg": avg,
        })
    return result


async def get_institute_players(institute_key: str, limit: int = 10):
    """Топ игроков внутри одного института."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            SELECT s.uid, s.score_sum,
                   COALESCE(u.display_name, 'Аноним') as nick
            FROM institute_scores s
            LEFT JOIN users u ON u.uid = s.uid
            WHERE s.institute = ?
            ORDER BY s.score_sum DESC
            LIMIT ?
        """, (institute_key, limit))
        rows = await cur.fetchall()
    return [
        {"uid": r[0], "score": r[1] or 0, "nick": r[2]}
        for r in rows
    ]


async def get_top_institute():
    """Институт, который сейчас на первом месте. Для плашки на главной."""
    rating = await get_institutes_rating(1)
    return rating[0] if rating else None
