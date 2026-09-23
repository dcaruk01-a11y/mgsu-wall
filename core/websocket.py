import json, time
from fastapi import WebSocket, WebSocketDisconnect, APIRouter
import core.state as state
from core.storage import save_stroke, delete_stroke, load_today_strokes


class Hub:
    def __init__(self):
        self.clients = set()
    async def connect(self, ws):
        await ws.accept()
        self.clients.add(ws)
        for s in await load_today_strokes():
            await ws.send_text(json.dumps({"type": "stroke", **s}))
    def disconnect(self, ws):
        self.clients.discard(ws)
    async def broadcast(self, msg):
        data = json.dumps(msg)
        dead = []
        for c in list(self.clients):
            try:
                await c.send_text(data)
            except Exception:
                dead.append(c)
        for d in dead:
            self.disconnect(d)


hub = Hub()
connection_strokes: dict = {}

router = APIRouter()


@router.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await hub.connect(ws)
    connection_strokes[ws] = []
    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except Exception:
                continue
            t = msg.get("type")
            if t == "stroke":
                if not state.is_open_now():
                    continue
                stroke = {
                    "x0": float(msg["x0"]), "y0": float(msg["y0"]),
                    "x1": float(msg["x1"]), "y1": float(msg["y1"]),
                    "color": str(msg.get("color", "#ffffff"))[:9],
                    "width": max(1, min(40, int(msg.get("width", 4)))),
                    "ts": time.time(),
                }
                new_id = await save_stroke(stroke)
                connection_strokes[ws].append(new_id)
                await hub.broadcast({"type": "stroke", "id": new_id, **stroke})
            elif t == "undo":
                ids = connection_strokes.get(ws, [])
                if not ids:
                    continue
                last_id = ids.pop()
                await delete_stroke(last_id)
                await hub.broadcast({"type": "remove", "id": last_id})
    except WebSocketDisconnect:
        connection_strokes.pop(ws, None)
        hub.disconnect(ws)
    except Exception:
        connection_strokes.pop(ws, None)
        hub.disconnect(ws)
