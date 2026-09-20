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
      b.textContent='Стена закрыта. Откроется в '+s.opens_at+':00 по Москве.';
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
</script></body></html>"""

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
# ============ HTML: ИГРЫ МГСУ ============
GAMES_HTML = """<!doctype html>
<html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Игры МГСУ</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Manrope:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
:root{
  --blue:#0F3C73;
  --red:#AC1422;
  --grey:#808080;
  --line:#E5E7EB;
  --text:#0A0A0A;
}
*{box-sizing:border-box;margin:0;padding:0;}
body{
  font-family:'Manrope',system-ui,-apple-system,sans-serif;
  background:#fff;color:var(--text);line-height:1.5;
  -webkit-font-smoothing:antialiased;
}
.wrap{max-width:1240px;margin:0 auto;padding:0 32px;}

/* ===== HEADER ===== */
header{border-bottom:1px solid var(--line);}
.head{
  display:flex;align-items:center;justify-content:space-between;
  height:72px;
}
.brand{
  display:flex;align-items:center;gap:14px;
  font-weight:600;font-size:15px;color:var(--blue);
  letter-spacing:0.02em;text-decoration:none;
}
.brand-mark{
  width:36px;height:36px;border:1.5px solid var(--blue);
  display:flex;align-items:center;justify-content:center;
  font-weight:700;font-size:13px;color:var(--blue);
  border-radius:4px;
}
nav{display:flex;align-items:center;gap:0;}
nav a{
  color:var(--text);text-decoration:none;font-size:15px;
  padding:0 20px;height:72px;display:flex;align-items:center;
  border-left:1px solid var(--line);transition:color .15s;
}
nav a:first-child{border-left:none;}
nav a:hover{color:var(--blue);}
nav a.active{color:var(--blue);font-weight:600;}

/* ===== HERO ===== */
.hero{padding:80px 0 60px;border-bottom:1px solid var(--line);}
.eyebrow{
  display:flex;align-items:center;gap:12px;
  font-size:12px;font-weight:600;letter-spacing:0.14em;
  text-transform:uppercase;color:var(--blue);margin-bottom:20px;
}
.eyebrow::before{
  content:'';width:28px;height:2px;background:var(--blue);
}
h1{
  font-size:64px;font-weight:700;line-height:1.05;
  color:var(--blue);letter-spacing:-0.02em;margin-bottom:20px;
}
.hero p{
  font-size:18px;color:#4B5563;max-width:620px;
}

/* ===== SECTION ===== */
.section{padding:64px 0;}
h2{
  font-size:36px;font-weight:700;color:var(--blue);
  letter-spacing:-0.01em;margin-bottom:14px;
}
.section .lead{font-size:16px;color:#4B5563;max-width:640px;margin-bottom:40px;}

/* ===== CARDS ===== */
.grid{
  display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));
  gap:20px;
}
.card{
  border:1px solid var(--line);border-radius:6px;
  padding:28px;background:#fff;text-decoration:none;color:inherit;
  display:flex;flex-direction:column;min-height:230px;
  transition:border-color .15s,transform .15s;
}
.card:hover{border-color:var(--blue);transform:translateY(-2px);}
.card.live:hover{border-color:var(--blue);}
.card.soon{cursor:default;opacity:0.65;}
.card.soon:hover{transform:none;border-color:var(--line);}
.card-tag{
  display:inline-block;font-size:11px;font-weight:600;
  letter-spacing:0.1em;text-transform:uppercase;
  color:var(--blue);padding:4px 10px;border:1px solid var(--blue);
  border-radius:3px;align-self:flex-start;margin-bottom:auto;
}
.card-tag.red{color:var(--red);border-color:var(--red);}
.card-tag.grey{color:var(--grey);border-color:var(--line);}
.card h3{
  font-size:22px;font-weight:600;color:var(--blue);
  margin:18px 0 8px;letter-spacing:-0.01em;
}
.card p{font-size:14px;color:#4B5563;line-height:1.55;}
.card .arrow{
  margin-top:16px;color:var(--blue);font-size:14px;
  font-weight:600;display:flex;align-items:center;gap:6px;
}
.card.soon .arrow{display:none;}

/* ===== FOOTER ===== */
footer{border-top:1px solid var(--line);padding:32px 0;margin-top:40px;}
.foot{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px;}
.foot small{color:var(--grey);font-size:13px;}
.foot a{color:var(--blue);text-decoration:none;font-size:13px;}
.foot a:hover{text-decoration:underline;}

@media(max-width:720px){
  h1{font-size:42px;}
  h2{font-size:28px;}
  .head{height:auto;padding:16px 0;flex-direction:column;gap:12px;}
  nav a{height:auto;padding:10px 14px;font-size:14px;}
}
</style>
</head><body>

<header><div class="wrap head">
  <a class="brand" href="/games">
    <div class="brand-mark">ИГ</div>
    <span>НИУ МГСУ · Игры</span>
  </a>
  <nav>
    <a href="/games" class="active">Игры</a>
    <a href="/games#soon">Скоро</a>
    <a href="/">О проекте</a>
  </nav>
</div></header>

<section class="hero"><div class="wrap">
  <div class="eyebrow">Студенческий проект</div>
  <h1>Игры МГСУ</h1>
  <p>Интерактивные развлечения для студентов. Играй с телефона — смотри результат на большом экране.</p>
</div></section>

<section class="section"><div class="wrap">
  <h2>Выберите игру</h2>
  <p class="lead">Откройте на телефоне — и играйте. Всё, что вы делаете, видно на общем экране в реальном времени.</p>

  <div class="grid">
    <a class="card live" href="/">
      <span class="card-tag">Доступно</span>
      <h3>Стена</h3>
      <p>Рисуй с телефона — твой штрих появляется на большом экране. Раз в день стена «печатается» и уходит в архив.</p>
      <div class="arrow">Играть →</div>
    </a>

    <a class="card soon" href="/games#soon">
      <span class="card-tag grey">Скоро</span>
      <h3>Змейка</h3>
      <p>Классика на большом экране. Управление с телефона, зрители следят за игрой на стене.</p>
    </a>

    <a class="card soon" href="/games#soon">
      <span class="card-tag grey">Скоро</span>
      <h3>Опрос дня</h3>
      <p>Один вопрос — много мнений. Голосуй с телефона, результаты видны всем в реальном времени.</p>
    </a>

    <a class="card soon" href="/games#soon">
      <span class="card-tag grey">Скоро</span>
      <h3>Гонка кликов</h3>
      <p>Нажимай быстрее всех. Таблица лидеров обновляется мгновенно на общем экране.</p>
    </a>
  </div>
</div></section>

<section class="section" id="soon"><div class="wrap">
  <h2>Что дальше</h2>
  <p class="lead">Мы работаем над новыми играми. Хочешь свою идею — напиши нам в Telegram-канал архива стены.</p>
</div></section>

<footer><div class="wrap foot">
  <small>© 2026 · Студенческий проект. Не является официальным сайтом НИУ МГСУ.</small>
  <a href="/">Перейти к стене →</a>
</div></footer>

</body></html>"""

@app.get("/games")
async def games():
    return HTMLResponse(GAMES_HTML)

@app.get("/kiosk")
async def kiosk():
    return HTMLResponse(KIOSK_HTML)
