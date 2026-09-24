"""Статистика и экспорт в Excel."""
import io, time
from datetime import datetime, timedelta
from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import Response
from openpyxl import Workbook

from config import MSK
import core.state as state
import core.analytics as analytics
from core.admin.common import check_admin

router = APIRouter()


@router.get("/admin/api/stats")
async def admin_stats(token: str = Header(default="", alias="authorization")):
    if not check_admin(token.replace("Bearer ", "").strip()):
        raise HTTPException(status_code=401, detail="Unauthorized")
    analytics.cleanup_old()
    state.clicker_reset_if_needed()
    return {
        "health": analytics.project_health(),
        "metrics": analytics.all_metrics(),
        "uptime_sec": int(time.time() - state.started_at),
        "clicker_top": [
            {"nick": e["nick"], "score": e["score"], "rank": e["rank"]}
            for e in state.clicker_top
        ],
    }


@router.get("/admin/api/export")
async def admin_export(period: str = "7", token: str = Header(default="", alias="authorization")):
    if not check_admin(token.replace("Bearer ", "").strip()):
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        days = int(period)
    except Exception:
        days = 7
    days = max(1, min(days, 90))

    cutoff = (datetime.now(MSK) - timedelta(days=days)).strftime("%Y-%m-%d")

    wb = Workbook()
    ws = wb.active
    ws.title = "Статистика"

    headers = [
        "Дата", "Заходы", "Уникальные", "Новые", "Вернувшиеся",
        "Стена", "Кликер", "Бродвей", "Кампус", "Грабли",
        "Ср. счёт кликера", "Ср. сессия (сек)",
    ]
    ws.append(headers)
    for cell in ws[1]:
        cell.font = cell.font.copy(bold=True)

    for d in sorted(analytics.history.keys()):
        if d < cutoff:
            continue
        day = analytics.history[d]
        avg_score = round(sum(day["clicker_scores"]) / len(day["clicker_scores"])) if day["clicker_scores"] else 0
        avg_sess = round(sum(day["sessions"]) / len(day["sessions"])) if day["sessions"] else 0
        g = day["games"]
        ws.append([
            d, day["visits"], analytics.uniq_count(day),
            day["new"], day["returning"],
            g.get("wall", 0), g.get("clicker", 0), g.get("broadway", 0),
            g.get("campus", 0), g.get("grable", 0),
            avg_score, avg_sess,
        ])

    widths = [12, 10, 12, 10, 12, 8, 10, 10, 10, 8, 16, 16]
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[chr(64 + i)].width = w

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    filename = f"mgsu-stats-{days}d.xlsx"
    return Response(
        content=buf.read(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
