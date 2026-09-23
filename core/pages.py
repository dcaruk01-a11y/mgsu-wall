from fastapi import APIRouter
from fastapi.responses import FileResponse, RedirectResponse

router = APIRouter()


@router.get("/")
async def root():
    return RedirectResponse(url="/glavnaya", status_code=302)


@router.get("/glavnaya")
async def glavnaya():
    return FileResponse("pages/glavnaya.html")


# Старые URL — редиректы на новые
@router.get("/games")
async def games_old():
    return RedirectResponse(url="/glavnaya", status_code=302)


@router.get("/kiosk")
async def kiosk_old():
    return RedirectResponse(url="/games/ekran", status_code=302)


@router.get("/clicker")
async def clicker_old():
    return RedirectResponse(url="/games/clicker", status_code=302)


@router.get("/wall")
async def wall_old():
    return RedirectResponse(url="/games/wall", status_code=302)


# Новые URL игр
@router.get("/games/wall")
async def wall():
    return FileResponse("pages/games/wall.html")


@router.get("/games/clicker")
async def clicker():
    return FileResponse("pages/games/clicker.html")


@router.get("/games/ekran")
async def kiosk():
    return FileResponse("pages/games/kiosk.html")
@router.get("/games/broadway")
async def broadway():
    return FileResponse("pages/broadway.html")


@router.get("/games/campus")
async def campus():
    return FileResponse("pages/campus.html")


@router.get("/games/grable")
async def grable():
    return FileResponse("pages/grable.html")


# Общие страницы
@router.get("/privacy")
async def privacy():
    return FileResponse("pages/privacy.html")
