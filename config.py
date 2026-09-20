import os
from datetime import datetime, timezone, timedelta

# Telegram
TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", "")
TG_CHAT_ID = os.environ.get("TG_CHAT_ID", "")
TG_FEEDBACK_BOT_TOKEN = os.environ.get("TG_FEEDBACK_BOT_TOKEN", "")
TG_ADMIN_ID = os.environ.get("TG_ADMIN_ID", "")

# Холст
CANVAS_W, CANVAS_H = 1920, 1080
STROKE_COOLDOWN = 0.0

# Хранилище
DB_PATH = "wall.db"
SNAPSHOT_DIR = "snapshots"
os.makedirs(SNAPSHOT_DIR, exist_ok=True)

# Рабочие часы (по Москве)
OPEN_HOUR = 8
CLOSE_HOUR = 17

MSK = timezone(timedelta(hours=3))

def is_open():
    now = datetime.now(MSK)
    return OPEN_HOUR <= now.hour < CLOSE_HOUR

def today_str():
    return datetime.now(MSK).strftime("%Y-%m-%d")
