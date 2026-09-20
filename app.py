import os, json, time, asyncio
from datetime import datetime, timezone, timedelta
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import aiosqlite
import httpx
from PIL import Image, ImageDraw

# ============ НАСТРОЙКИ ============
TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", "")
TG_CHAT_ID = os.environ.get("TG_CHAT_ID", "")

CANVAS_W, CANVAS_H = 1920, 1080
STROKE_COOLDOWN = 0.0
DB_PATH = "wall.db"

# Рабочие часы стены (по Москве)
OPEN_HOUR = 8
CLOSE_HOUR = 17

MSK = timezone(timedelta(hours=3))

def is_open():
    now = datetime.now(MSK)
    return OPEN_HOUR <= now.hour < CLOSE_HOUR

SNAPSHOT_DIR = "snapshots"
os.makedirs(SNAPSHOT_DIR, exist_ok=True)

app = FastAPI()

# ============ БАЗА ДАННЫХ ============
async def db_init():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS strokes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                day TEXT, x0 REAL, y0 REAL, x1 REAL, y1 REAL,
                color TEXT, width INTEGER, ts REAL
            )
        """)
        await db.commit()

def today_str():
    return datetime.now(MSK).strftime("%Y-%m-%d")

async def save_stroke(s):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO strokes(day,x0,y0,x1,y1,color,width,ts) VALUES (?,?,?,?,?,?,?,?)",
            (today_str(), s["x0"], s["y0"], s["x1"], s["y1"], s["color"], s["width"], s["ts"])
        )
        await db.commit()

async def load_today_strokes():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT x0,y0,x1,y1,color,width,ts FROM strokes WHERE day=? ORDER BY id",
            (today_str(),)
        )
        rows = await cur.fetchall()
    return [dict(zip(["x0","y0","x1","y1","color","width","ts"], r)) for r in rows]

async def clear_today():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM strokes WHERE day=?", (today_str(),))
        await db.commit()

# ============ ХАБ WEBSOCKET ============
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

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await hub.connect(ws)
    last = 0.0
    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except Exception:
                continue
            if msg.get("type") != "stroke":
                continue
            if not is_open():
                continue
            stroke = {
                "x0": float(msg["x0"]), "y0": float(msg["y0"]),
                "x1": float(msg["x1"]), "y1": float(msg["y1"]),
                "color": str(msg.get("color", "#ffffff"))[:9],
                "width": max(1, min(40, int(msg.get("width", 4)))),
                "ts": time.time(),
            }
            await save_stroke(stroke)
            await hub.broadcast({"type": "stroke", **stroke})
    except WebSocketDisconnect:
        hub.disconnect(ws)
    except Exception:
        hub.disconnect(ws)

# ============ СНИМОК И TELEGRAM ============
async def make_snapshot():
    img = Image.new("RGB", (CANVAS_W, CANVAS_H), (10, 10, 14))
    d = ImageDraw.Draw(img)
    for s in await load_today_strokes():
        d.line([s["x0"], s["y0"], s["x1"], s["y1"]],
               fill=s["color"], width=s["width"])
    path = os.path.join(SNAPSHOT_DIR, f"{today_str()}.png")
    img.save(path)
    return path

async def post_to_telegram(path):
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        print("Telegram не настроен")
        return
    caption = f"Стена МГСУ — {today_str()}"
    try:
        async with httpx.AsyncClient(timeout=60) as c:
            with open(path, "rb") as f:
                r = await c.post(
                    f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendPhoto",
                    data={"chat_id": TG_CHAT_ID, "caption": caption},
                    files={"photo": f},
                )
                print("Telegram:", r.status_code)
    except Exception as e:
        print("Ошибка Telegram:", e)

async def daily_loop():
    while True:
        now = datetime.now(MSK)
        target = now.replace(hour=17, minute=0, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        wait = (target - now).total_seconds()
        print(f"До снимка: {wait/3600:.1f} ч")
        await asyncio.sleep(wait)
        try:
            strokes = await load_today_strokes()
            if not strokes:
                print("Холст пустой — снимок не делаем")
                continue
            print("Снимок дня...")
            path = await make_snapshot()
            await post_to_telegram(path)
            await clear_today()
            await hub.broadcast({"type": "reset"})
            print("Готово!")
        except Exception as e:
            print("Ошибка:", e)

@app.on_event("startup")
async def on_startup():
    await db_init()
    asyncio.create_task(daily_loop())
@app.get("/status")
async def status_endpoint():
    now = datetime.now(MSK)
    return {
        "open": is_open(),
        "opens_at": OPEN_HOUR,
        "closes_at": CLOSE_HOUR,
        "current_hour_msk": now.hour,
    }
@app.get("/snapshot")
async def manual_snapshot():
    path = await make_snapshot()
    await post_to_telegram(path)
    return {"ok": True, "path": path}

# ============ HTML: РИСОВАЛКА ============
INDEX_HTML = """<!doctype html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<title>Нарисуй на стене МГСУ</title>
<style>
html,body{margin:0;background:#0a0a0e;color:#fff;font-family:system-ui;overscroll-behavior:none;touch-action:none;height:100%;}
canvas{display:block;width:100vw;height:70vh;background:#000;touch-action:none;}
.bar{display:flex;gap:10px;padding:10px;flex-wrap:wrap;align-items:center;}
.sw{width:36px;height:36px;border-radius:50%;border:3px solid #444;cursor:pointer;}
.sw.active{border-color:#fff;transform:scale(1.15);}
input[type=range]{flex:1;min-width:120px;}
p{padding:0 12px;color:#888;font-size:14px;margin:6px 0;}
</style></head><body>
<canvas id="c"></canvas>
<div class="bar" id="colors"></div>
<div class="bar"><input type="range" id="w" min="2" max="30" value="6"></div>
<div id="banner" style="display:none;background:#ff3b30;color:#fff;padding:14px;text-align:center;font-weight:bold;"></div>
<p>Штрих появляется на большом экране через секунду. В 17:00 стена «печатается» и уходит в архив.</p>
<script>
const W=1920,H=1080;
const c=document.getElementById('c');
const ctx=c.getContext('2d');
c.width=W;c.height=H;
const COLORS=['#ffffff','#ff3b30','#ff9500','#ffcc00','#34c759','#00c7be','#30b0ff','#5856d6','#af52de','#ff2d55'];
let color=COLORS[0], width=6;
const palette=document.getElementById('colors');
COLORS.forEach((col,i)=>{
  const b=document.createElement('div');
  b.className='sw'+(i===0?' active':'');
  b.style.background=col;
  b.onclick=()=>{color=col;document.querySelectorAll('.sw').forEach(x=>x.classList.remove('active'));b.classList.add('active');};
  palette.appendChild(b);
});
document.getElementById('w').oninput=e=>width=+e.target.value;
let ws,queue=[];
function connect(){
  ws=new WebSocket((location.protocol==='https:'?'wss://':'ws://')+location.host+'/ws');
  ws.onopen=()=>queue.splice(0).forEach(m=>ws.send(m));
  ws.onclose=()=>setTimeout(connect,1500);
  ws.onmessage=e=>{
    const m=JSON.parse(e.data);
    if(m.type==='stroke')draw(m.x0,m.y0,m.x1,m.y1,m.color,m.width);
    if(m.type==='reset')ctx.clearRect(0,0,W,H);
  };
}
connect();
function draw(x0,y0,x1,y1,col,w){
  ctx.strokeStyle=col;ctx.lineWidth=w;ctx.lineCap='round';ctx.lineJoin='round';
  ctx.beginPath();ctx.moveTo(x0,y0);ctx.lineTo(x1,y1);ctx.stroke();
}
let drawing=false,last=null;
function pos(e){
  const r=c.getBoundingClientRect();
  const p=e.touches?e.touches[0]:e;
  return {x:(p.clientX-r.left)*(W/r.width),y:(p.clientY-r.top)*(H/r.height)};
}
function start(e){e.preventDefault();drawing=true;last=pos(e);}
function move(e){
  if(!drawing)return;e.preventDefault();
  const p=pos(e);
  const s={x0:last.x,y0:last.y,x1:p.x,y1:p.y,color,width};
  draw(s.x0,s.y0,s.x1,s.y1,color,width);
  const msg=JSON.stringify({type:'stroke',...s});
  ws&&ws.readyState===1?ws.send(msg):queue.push(msg);
  last=p;
}
function end(){drawing=false;last=null;}
c.addEventListener('touchstart',start,{passive:false});
c.addEventListener('touchmove',move,{passive:false});
c.addEventListener('touchend',end);
c.addEventListener('mousedown',start);
c.addEventListener('mousemove',move);
c.addEventListener('mouseup',end);
c.addEventListener('mouseleave',end);

async function checkStatus(){
  try{
    const r = await fetch('/status');
    const s = await r.json();
    const b = document.getElementById('banner');
    if(!s.open){
      b.style.display='block';
      b.textContent='🔒 Стена закрыта. Откроется в '+s.opens_at+':00 по Москве.';
      c.style.pointerEvents='none';
      c.style.opacity='0.4';
    } else {
      b.style.display='none';
      c.style.pointerEvents='auto';
      c.style.opacity='1';
    }
  }catch(e){}
}
checkStatus();
setInterval(checkStatus, 60000);
</script></body></html>

KIOSK_HTML = """<!doctype html>
<html><head><meta charset="utf-8"><title>MGSU Wall</title>
<style>html,body{margin:0;background:#000;overflow:hidden;height:100%;}
canvas{display:block;width:100vw;height:100vh;background:#000;}</style>
</head><body><canvas id="c"></canvas>
<script>
const W=1920,H=1080,c=document.getElementById('c'),ctx=c.getContext('2d');
c.width=W;c.height=H;
let ws;
(function conn(){
  ws=new WebSocket((location.protocol==='https:'?'wss://':'ws://')+location.host+'/ws');
  ws.onclose=()=>setTimeout(conn,1500);
  ws.onmessage=e=>{
    const m=JSON.parse(e.data);
    if(m.type==='stroke'){
      ctx.strokeStyle=m.color;ctx.lineWidth=m.width;ctx.lineCap='round';
      ctx.beginPath();ctx.moveTo(m.x0,m.y0);ctx.lineTo(m.x1,m.y1);ctx.stroke();
    }
    if(m.type==='reset')ctx.clearRect(0,0,W,H);
  };
})();
</script></body></html>"""

@app.get("/")
async def index():
    return HTMLResponse(INDEX_HTML)

@app.get("/kiosk")
async def kiosk():
    return HTMLResponse(KIOSK_HTML)
