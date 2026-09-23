from fastapi import APIRouter
from fastapi.responses import Response
import core.state as state

router = APIRouter()

THEME_FILES = {
    "classic":   "static/public.css",
    "retro":     "static/retro.css",
    "notebook":  "static/notebook.css",
    "cyberpunk": "static/cyberpunk.css",
    "cozy":      "static/cozy.css",
}


@router.get("/theme.css")
async def theme_css():
    theme = state.theme_config.get("current", "classic")
    path = THEME_FILES.get(theme, THEME_FILES["classic"])
    try:
        with open(path, "r", encoding="utf-8") as f:
            css = f.read()
    except Exception as e:
        print("theme.css error:", e)
        css = "/* theme not found */"
    return Response(
        content=css,
        media_type="text/css",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
        },
    )
