"""
Аналитика и статистика проекта.
Всё в памяти, без записи на диск.
Хранит историю за последние 7 дней — этого достаточно для retention и трендов.
"""
import time
from datetime import datetime, timedelta
from config import MSK, today_str


# ============ ИСТОРИЯ ============

HISTORY_DAYS = 7

# {date_str: {
#     "visits": int,
#     "uniques": set(),
#     "new": int,
#     "returning": int,
#     "games": {"wall": 0, "clicker": 0, ...},
#     "clicker_scores": [int, int, ...],
#     "sessions": [float, ...],
# }}
history: dict = {}

# Все uid, которые когда-либо заходили (для «новый vs вернувшийся»)
all_seen_uids: set = set()


def _today():
    return today_str()


def _ensure_day(date_str=None):
    d = date_str or _today()
    if d not in history:
        history[d] = {
            "visits": 0,
            "uniques": set(),
            "new": 0,
            "returning": 0,
            "games": {"wall": 0, "clicker": 0, "broadway": 0, "campus": 0, "grable": 0},
            "clicker_scores": [],
            "sessions": [],
        }
    return history[d]


def cleanup_old():
    """Удаляет дни старше HISTORY_DAYS."""
    cutoff = (datetime.now(MSK) - timedelta(days=HISTORY_DAYS)).strftime("%Y-%m-%d")
    for d in list(history.keys()):
        if d < cutoff:
            del history[d]


# ============ ЗАПИСЬ СОБЫТИЙ ============

def track_visit(uid: str = ""):
    day = _ensure_day()
    day["visits"] += 1

    if uid and len(uid) < 64:
        if uid in day["uniques"]:
            return  # уже заходил сегодня
        day["uniques"].add(uid)

        if uid in all_seen_uids:
            day["returning"] += 1
        else:
            day["new"] += 1
            all_seen_uids.add(uid)


def track_game(name: str):
    day = _ensure_day()
    if name in day["games"]:
        day["games"][name] += 1


def track_clicker_score(score: int):
    day = _ensure_day()
    if 0 <= score <= 100000:
        day["clicker_scores"].append(score)


def track_session(seconds: float):
    day = _ensure_day()
    if 1 <= seconds <= 3600:
        day["sessions"].append(seconds)


# ============ ПОМОЩНИКИ АНАЛИЗА ============

def _metric(key, title, value, status, verdict, hint=""):
    """status: good / warn / bad / neutral"""
    return {
        "key": key,
        "title": title,
        "value": value,
        "status": status,
        "verdict": verdict,
        "hint": hint,
    }


def _avg(lst):
    return sum(lst) / len(lst) if lst else 0


def _yesterday_str():
    return (datetime.now(MSK) - timedelta(days=1)).strftime("%Y-%m-%d")


# ============ МЕТРИКИ С ВЕРДИКТАМИ ============

def m_visits_today():
    v = _ensure_day()["visits"]
    if v >= 30:
        return _metric("visits", "Заходов сегодня", v, "good",
                       "Отличный трафик — люди активно заходят.",
                       "Продолжай распространять — стикеры, афиши, QR.")
    if v >= 10:
        return _metric("visits", "Заходов сегодня", v, "warn",
                       "Средний трафик. Можно больше.",
                       "Проверь афиши и QR-коды — все ли на месте?")
    if v >= 1:
        return _metric("visits", "Заходов сегодня", v, "bad",
                       "Мало заходов.",
                       "Проблема в распространении — нужны афиши, QR, стикеры.")
    return _metric("visits", "Заходов сегодня", 0, "bad",
                   "Сегодня ещё никто не зашёл.",
                   "Проверь, работает ли сайт. Запусти распространение.")


def m_uniques_today():
    d = _ensure_day()
    u = len(d["uniques"])
    total = d["visits"]
    if u == 0:
        return _metric("uniques", "Уникальных пользователей", 0, "bad",
                       "Никто не зашёл.",
                       "Запусти распространение.")
    if total and u / total > 0.8:
        return _metric("uniques", "Уникальных пользователей", u, "good",
                       f"Почти все заходы ({u} из {total}) — новые люди.",
                       "Охват растёт — хорошо.")
    if total and u / total > 0.4:
        return _metric("uniques", "Уникальных пользователей", u, "warn",
                       f"{u} из {total} заходов — разные люди.",
                       "Часть заходов — повторные. Это нормально.")
    return _metric("uniques", "Уникальных пользователей", u, "neutral",
                   f"{u} из {total} заходов. Много повторных.",
                   "Проверь, не «залипают» ли одни и те же.")


def m_new_vs_returning():
    d = _ensure_day()
    new_n = d["new"]
    ret_n = d["returning"]
    if new_n + ret_n == 0:
        return _metric("new_ret", "Новые vs вернувшиеся", "0 / 0", "neutral",
                       "Пока нет данных.",
                       "")
    pct = round(ret_n / (new_n + ret_n) * 100)
    value = f"{new_n} новых · {ret_n} вернулись"
    if pct >= 40:
        return _metric("new_ret", "Новые vs вернувшиеся", value, "good",
                       f"{pct}% вернулись — отлично! Проект удерживает.",
                       "Механики возврата работают — не сломай.")
    if pct >= 20:
        return _metric("new_ret", "Новые vs вернувшиеся", value, "warn",
                       f"{pct}% вернулись — средне.",
                       "Добавь ежедневные задания, монетки, серию дней.")
    return _metric("new_ret", "Новые vs вернувшиеся", value, "bad",
                   f"Только {pct}% вернулись — плохо.",
                   "Игры не вовлекают или не хватает причины вернуться.")


def m_retention_d1():
    y = _yesterday_str()
    if y not in history:
        return _metric("ret_d1", "Возврат на следующий день (D1)", "—", "neutral",
                       "Метрика появится завтра, когда будет история за вчера.",
                       "")
    y_uniques = history[y]["uniques"]
    if not y_uniques:
        return _metric("ret_d1", "Возврат на следующий день (D1)", "—", "neutral",
                       "Вчера не было уникальных пользователей.",
                       "")
    t_uniques = _ensure_day()["uniques"]
    returned = y_uniques & t_uniques
    pct = round(len(returned) / len(y_uniques) * 100)
    value = f"{pct}% ({len(returned)} из {len(y_uniques)})"
    if pct >= 30:
        return _metric("ret_d1", "Возврат на следующий день (D1)", value, "good",
                       "Треть вчерашних вернулась — очень хорошо.",
                       "Проект удерживает. Продолжай в том же духе.")
    if pct >= 15:
        return _metric("ret_d1", "Возврат на следующий день (D1)", value, "warn",
                       "Возвращаются, но мало.",
                       "Добавь ежедневные задания и награды за возврат.")
    return _metric("ret_d1", "Возврат на следующий день (D1)", value, "bad",
                   "Плохо возвращаются.",
                   "Игры не вовлекают или не хватает причины вернуться.")


def m_avg_session():
    s = _ensure_day()["sessions"]
    if not s:
        return _metric("avg_sess", "Средняя сессия", "—", "neutral",
                       "Сессии пока не измеряются на всех страницах.",
                       "")
    avg = round(_avg(s))
    value = f"{avg} сек"
    if avg >= 120:
        return _metric("avg_sess", "Средняя сессия", value, "good",
                       "Долго играют — контент заходит.",
                       "")
    if avg >= 30:
        return _metric("avg_sess", "Средняя сессия", value, "warn",
                       "Средняя сессия короткая.",
                       "Усложни игры или добавь цели.")
    return _metric("avg_sess", "Средняя сессия", value, "bad",
                   "Очень короткие сессии — люди уходят сразу.",
                   "Правила непонятны или игры скучные.")


def m_online():
    from core.websocket import hub
    n = len(hub.clients)
    if n >= 5:
        return _metric("online", "Онлайн сейчас", n, "good",
                       "Активность идёт — люди на сайте.",
                       "")
    if n >= 1:
        return _metric("online", "Онлайн сейчас", n, "warn",
                       "Кто-то один есть. Не густо.",
                       "")
    return _metric("online", "Онлайн сейчас", 0, "neutral",
                   "Пока никого.",
                   "Это нормально в непиковое время.")


def m_total_games():
    d = _ensure_day()
    total = sum(d["games"].values())
    if total >= 40:
        return _metric("games", "Игр сыграно", total, "good",
                       "Много партий за день — игры заходят.",
                       "")
    if total >= 10:
        return _metric("games", "Игр сыграно", total, "warn",
                       "Средне. Есть куда расти.",
                       "Проверь, какие игры никто не запускает.")
    if total >= 1:
        return _metric("games", "Игр сыграно", total, "bad",
                       "Мало партий.",
                       "Игры не находят аудиторию или плохо продвигаются.")
    return _metric("games", "Игр сыграно", 0, "bad",
                   "Сегодня никто не играл.",
                   "Проверь, работают ли игры. Напомни о себе в TG.")


def m_games_breakdown():
    d = _ensure_day()
    g = d["games"]
    total = sum(g.values())
    if total == 0:
        return _metric("games_break", "По играм", "—", "neutral", "Пока пусто.", "")
    top = sorted(g.items(), key=lambda x: -x[1])[:3]
    top = [(k, v) for k, v in top if v > 0]
    value = " · ".join(f"{k}: {v}" for k, v in top)
    if len(top) == 1:
        return _metric("games_break", "По играм", value, "warn",
                       f"Играют только в «{top[0][0]}». Остальные не заходят.",
                       "Продвигай другие игры или переделай их.")
    return _metric("games_break", "По играм", value, "neutral",
                   "Несколько игр в обороте.",
                   "")


def m_clicker_avg():
    scores = _ensure_day()["clicker_scores"]
    if not scores:
        return _metric("clicker_avg", "Средний счёт в кликере", "—", "neutral",
                       "Сегодня в кликер не играли.",
                       "")
    avg = round(_avg(scores))
    value = f"{avg} ({len(scores)} партий)"
    if avg >= 200:
        return _metric("clicker_avg", "Средний счёт в кликере", value, "good",
                       "Высокие результаты — игроки опытные или игра лёгкая.",
                       "Можно добавить уровни сложности.")
    if avg >= 80:
        return _metric("clicker_avg", "Средний счёт в кликере", value, "good",
                       "Средний результат — баланс хороший.",
                       "")
    if avg >= 30:
        return _metric("clicker_avg", "Средний счёт в кликере", value, "warn",
                       "Низковато — игра сложная или игроки новички.",
                       "")
    return _metric("clicker_avg", "Средний счёт в кликере", value, "bad",
                   "Слишком низкие результаты.",
                   "Возможно, правила непонятны или кнопка не отзывается.")


def m_memory():
    try:
        import psutil
        mb = round(psutil.Process().memory_info().rss / 1024 / 1024, 1)
    except Exception:
        return _metric("mem", "Память сервера", "—", "neutral", "", "")
    value = f"{mb} МБ из 512"
    pct = mb / 512 * 100
    if pct >= 85:
        return _metric("mem", "Память сервера", value, "bad",
                       "Сервер почти забит. Скоро может упасть.",
                       "Пора переезжать на платный тариф Render.")
    if pct >= 60:
        return _metric("mem", "Память сервера", value, "warn",
                       "Памяти становится много.",
                       "Следи за ростом — при 85% переезд на платный.")
    return _metric("mem", "Память сервера", value, "good",
                   "Запаса много.",
                   "")


def m_cpu():
    try:
        import psutil
        c = round(psutil.cpu_percent(interval=0.1), 1)
    except Exception:
        return _metric("cpu", "Загрузка CPU", "—", "neutral", "", "")
    value = f"{c}%"
    if c >= 80:
        return _metric("cpu", "Загрузка CPU", value, "bad",
                       "Процессор перегружен.",
                       "Много запросов — возможно, спам или пик нагрузки.")
    if c >= 50:
        return _metric("cpu", "Загрузка CPU", value, "warn",
                       "Средняя нагрузка.",
                       "Следи за трендом.")
    return _metric("cpu", "Загрузка CPU", value, "good",
                   "Загрузка в норме.",
                   "")


# ============ ОБЩИЙ СТАТУС ПРОЕКТА ============

def project_health():
    """Возвращает общий статус проекта по совокупности метрик."""
    metrics = [
        m_visits_today(),
        m_new_vs_returning(),
        m_retention_d1(),
        m_total_games(),
        m_memory(),
    ]
    # Считаем баллы: good=2, warn=1, bad=-1, neutral=0
    score = 0
    for m in metrics:
        s = m["status"]
        if s == "good":
            score += 2
        elif s == "warn":
            score += 1
        elif s == "bad":
            score -= 1

    if score >= 6:
        return {"status": "good", "label": "Проект здоров", "text": "Всё идёт хорошо. Продолжай в том же духе."}
    if score >= 2:
        return {"status": "warn", "label": "Есть что улучшить", "text": "Проект живой, но есть слабые места. Посмотри вердикты ниже."}
    return {"status": "bad", "label": "Нужно внимание", "text": "Проект просел. Смотри рекомендации в карточках ниже."}


# ============ СПИСОК ВСЕХ МЕТРИК ============

def all_metrics():
    return [
        m_online(),
        m_visits_today(),
        m_uniques_today(),
        m_new_vs_returning(),
        m_retention_d1(),
        m_avg_session(),
        m_total_games(),
        m_games_breakdown(),
        m_clicker_avg(),
        m_memory(),
        m_cpu(),
    ]
