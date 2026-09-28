<!doctype html>
<html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Аналитика · Админка МГСУ</title>
<link rel="stylesheet" href="/static/admin.css">
<style>
.page-header{margin-bottom:20px;display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:14px;}
.page-title{font-size:28px;font-weight:800;color:#fff;margin:0 0 6px;}
.page-sub{font-size:14px;color:rgba(255,255,255,0.55);}

.period-tabs{display:flex;gap:6px;background:rgba(255,255,255,0.05);border-radius:10px;padding:4px;}
.period-tab{padding:8px 16px;border:0;background:transparent;color:rgba(255,255,255,0.6);font-family:inherit;font-size:13px;font-weight:700;border-radius:8px;cursor:pointer;transition:all .15s;white-space:nowrap;}
.period-tab:hover{color:#fff;}
.period-tab.active{background:rgba(255,255,255,0.15);color:#fff;}

/* ═══ ПУЛЬС ═══ */
.pulse-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-bottom:24px;}
.pulse-card{
  padding:24px 22px;border-radius:16px;
  background:linear-gradient(180deg, rgba(255,255,255,0.06), rgba(255,255,255,0.02));
  border:1px solid rgba(255,255,255,0.12);
  position:relative;overflow:hidden;
}
.pulse-card::before{
  content:'';position:absolute;top:0;left:0;right:0;height:3px;
  background:linear-gradient(90deg,#6FA8FF,#4ADE80);
}
.pulse-card.green::before{background:linear-gradient(90deg,#4ADE80,#22c55e);}
.pulse-card.blue::before{background:linear-gradient(90deg,#6FA8FF,#3b82f6);}
.pulse-icon{font-size:26px;line-height:1;margin-bottom:10px;opacity:0.9;}
.pulse-label{font-size:11px;font-weight:800;letter-spacing:0.14em;text-transform:uppercase;color:rgba(255,255,255,0.55);margin-bottom:10px;}
.pulse-value{font-size:44px;font-weight:900;color:#fff;font-variant-numeric:tabular-nums;line-height:1;letter-spacing:-0.03em;}
.pulse-delta{display:inline-block;margin-top:10px;font-size:12px;font-weight:800;padding:3px 10px;border-radius:999px;}
.pulse-delta.up{background:rgba(74,222,128,0.18);color:#4ADE80;}
.pulse-delta.down{background:rgba(255,77,94,0.18);color:#FF6B7B;}
.pulse-delta.flat{background:rgba(255,255,255,0.08);color:rgba(255,255,255,0.6);}
.pulse-hint{font-size:12px;color:rgba(255,255,255,0.5);margin-top:8px;line-height:1.4;}

/* ═══ ОБЗОР ═══ */
.overview-row{
  display:grid;
  grid-template-columns:repeat(auto-fill,minmax(180px,1fr));
  gap:12px;margin-bottom:20px;
}
.ov-card{
  padding:16px 18px;border-radius:12px;
  background:rgba(255,255,255,0.04);
  border:1px solid rgba(255,255,255,0.10);
}
.ov-label{font-size:10px;font-weight:800;letter-spacing:0.12em;text-transform:uppercase;color:rgba(255,255,255,0.5);margin-bottom:8px;}
.ov-value{font-size:26px;font-weight:900;color:#fff;font-variant-numeric:tabular-nums;line-height:1;}
.ov-sub{font-size:11px;color:rgba(255,255,255,0.55);margin-top:6px;}
.ov-sub b{color:#fff;}

/* ═══ ВОРОНКА ═══ */
.funnel{
  padding:22px;border-radius:16px;
  background:rgba(255,255,255,0.03);
  border:1px solid rgba(255,255,255,0.08);
  margin-bottom:24px;
}
.funnel-step{
  display:flex;align-items:center;gap:16px;
  padding:14px 18px;border-radius:12px;
  background:rgba(255,255,255,0.04);
  position:relative;overflow:hidden;
  margin-bottom:6px;
}
.funnel-step-fill{
  position:absolute;left:0;top:0;bottom:0;
  background:linear-gradient(90deg,rgba(111,168,255,0.20),rgba(111,168,255,0.04));
  z-index:0;transition:width .5s;
}
.funnel-content{position:relative;z-index:1;display:flex;align-items:center;gap:14px;width:100%;}
.funnel-icon{font-size:22px;line-height:1;width:30px;text-align:center;flex-shrink:0;}
.funnel-label{flex:1;font-size:14px;font-weight:600;color:rgba(255,255,255,0.9);}
.funnel-pct{font-size:12px;font-weight:800;color:rgba(255,255,255,0.55);padding:3px 9px;border-radius:999px;background:rgba(255,255,255,0.06);}
.funnel-count{font-size:22px;font-weight:900;color:#fff;font-variant-numeric:tabular-nums;min-width:50px;text-align:right;}

/* ═══ Блоки общие ═══ */
.block{margin-bottom:28px;}
.block h2{font-size:18px;font-weight:800;color:#fff;margin-bottom:14px;display:flex;align-items:center;gap:10px;}
.block h2 small{font-size:12px;font-weight:500;color:rgba(255,255,255,0.4);}

/* ═══ УСТРОЙСТВА ═══ */
.device-row{display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:10px;margin-bottom:14px;}
.device-card{padding:14px 16px;border-radius:12px;background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.10);}
.device-label{font-size:11px;font-weight:800;letter-spacing:0.1em;text-transform:uppercase;color:rgba(255,255,255,0.55);margin-bottom:6px;}
.device-value{font-size:22px;font-weight:900;color:#fff;font-variant-numeric:tabular-nums;}
.device-brands{display:flex;gap:6px;flex-wrap:wrap;}
.brand-pill{padding:5px 12px;border-radius:999px;font-size:12px;font-weight:700;background:rgba(111,168,255,0.12);border:1px solid rgba(111,168,255,0.35);color:#8BC0FF;}
.brand-pill b{color:#fff;margin-left:4px;}

/* ═══ ЧАСЫ ═══ */
.hours-chart{display:flex;align-items:flex-end;gap:3px;height:130px;padding:16px 4px 0;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);border-radius:14px;}
.hour-col{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:flex-end;height:100%;gap:2px;}
.hour-stack{width:100%;display:flex;flex-direction:column;justify-content:flex-end;height:100%;}
.hour-bar-mobile{background:#FFB347;border-radius:3px 3px 0 0;}
.hour-bar-desktop{background:#6FA8FF;border-radius:0 0 3px 3px;}
.hour-label{font-size:9px;color:rgba(255,255,255,0.4);font-variant-numeric:tabular-nums;}
.hours-legend{display:flex;gap:14px;justify-content:center;margin-top:12px;font-size:12px;color:rgba(255,255,255,0.7);}
.hours-legend-item{display:flex;align-items:center;gap:6px;}
.hours-legend-dot{width:10px;height:10px;border-radius:3px;}

/* ═══ ДЕТАЛИ ═══ */
.details-toggle{
  display:inline-flex;align-items:center;gap:10px;
  padding:12px 20px;border-radius:12px;
  background:rgba(255,255,255,0.05);
  border:1px solid rgba(255,255,255,0.12);
  color:#fff;font-family:inherit;font-size:14px;font-weight:700;
  cursor:pointer;transition:all .15s;
  margin-bottom:16px;
}
.details-toggle:hover{background:rgba(255,255,255,0.10);}
.details-toggle .arrow{transition:transform .2s;display:inline-block;}
.details-toggle.open .arrow{transform:rotate(90deg);}
.details-content{display:none;}
.details-content.open{display:block;}

/* Лента */
.feed-box{border-radius:14px;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);overflow:hidden;margin-bottom:24px;}
.feed-head{display:grid;grid-template-columns:80px 60px 130px 1fr 100px;gap:10px;padding:12px 16px;background:rgba(0,0,0,0.20);font-size:10px;font-weight:800;letter-spacing:0.1em;text-transform:uppercase;color:rgba(255,255,255,0.5);}
.feed-row{display:grid;grid-template-columns:80px 60px 130px 1fr 100px;gap:10px;padding:10px 16px;border-top:1px solid rgba(255,255,255,0.05);font-size:13px;align-items:center;}
.feed-row:hover{background:rgba(255,255,255,0.03);}
.feed-time{font-family:monospace;font-size:12px;color:rgba(255,255,255,0.7);}
.feed-device{font-size:18px;text-align:center;}
.feed-subnet{font-family:monospace;font-size:12px;color:#6FA8FF;}
.feed-who{display:flex;align-items:center;gap:8px;overflow:hidden;}
.feed-nick{color:#fff;font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.feed-guest{color:rgba(255,255,255,0.5);font-style:italic;}
.feed-action{padding:3px 8px;border-radius:999px;font-size:10px;font-weight:800;text-transform:uppercase;text-align:center;}
.feed-action.visit{background:rgba(111,168,255,0.15);color:#6FA8FF;}
.feed-action.register{background:rgba(74,222,128,0.2);color:#4ADE80;}
.feed-action.login{background:rgba(180,120,255,0.18);color:#C0A0FF;}
.feed-action.game{background:rgba(255,180,80,0.2);color:#FFB347;}

/* Зоны IP (упрощённые) */
.zone-card{padding:14px 16px;border-radius:12px;background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);margin-bottom:8px;}
.zone-head{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:8px;}
.zone-subnet{font-family:monospace;font-size:14px;font-weight:800;color:#fff;}
.zone-stats{font-size:12px;color:rgba(255,255,255,0.7);display:flex;gap:14px;flex-wrap:wrap;margin-bottom:6px;}
.zone-stats b{color:#fff;}
.zone-pills{display:flex;gap:6px;flex-wrap:wrap;}
.zone-pill{padding:3px 9px;border-radius:999px;font-size:11px;background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.12);color:rgba(255,255,255,0.85);}

.empty{padding:40px;text-align:center;color:rgba(255,255,255,0.4);font-size:14px;}

@media(max-width:720px){
  .pulse-grid{grid-template-columns:1fr;gap:10px;}
  .pulse-value{font-size:36px;}
  .feed-head{display:none;}
  .feed-row{grid-template-columns:70px 40px 1fr;grid-template-areas:"time device who" "subnet subnet action";gap:6px;padding:12px 14px;}
  .feed-time{grid-area:time;}
  .feed-device{grid-area:device;}
  .feed-subnet{grid-area:subnet;font-size:11px;}
  .feed-who{grid-area:who;}
  .feed-action{grid-area:action;justify-self:flex-end;}
}
</style>
</head><body class="admin-page">

<div class="admin-shell">
  <aside class="admin-sidebar" id="adminMenuContainer"></aside>
  <main class="admin-main">

    <div class="page-header">
      <div>
        <h1 class="page-title">Аналитика</h1>
        <div class="page-sub">Что происходит с проектом</div>
      </div>
      <div class="period-tabs">
        <button class="period-tab" data-days="1">Сегодня</button>
        <button class="period-tab active" data-days="7">7 дней</button>
        <button class="period-tab" data-days="30">30 дней</button>
      </div>
    </div>

    <!-- ═══════ ПУЛЬС ═══════ -->
    <div class="pulse-grid" id="pulseGrid">
      <div class="pulse-card blue">
        <div class="pulse-icon">👥</div>
        <div class="pulse-label">Посетители</div>
        <div class="pulse-value" id="pulseVisitors">—</div>
        <div class="pulse-delta flat" id="pulseVisitorsDelta">—</div>
        <div class="pulse-hint">по уникальным браузерам</div>
      </div>
      <div class="pulse-card green">
        <div class="pulse-icon">🎮</div>
        <div class="pulse-label">Играли</div>
        <div class="pulse-value" id="pulsePlayed">—</div>
        <div class="pulse-delta flat" id="pulsePlayedDelta">—</div>
        <div class="pulse-hint">хотя бы раз за период</div>
      </div>
      <div class="pulse-card">
        <div class="pulse-icon">🔁</div>
        <div class="pulse-label">Возврат D1</div>
        <div class="pulse-value" id="pulseD1">—</div>
        <div class="pulse-delta flat" id="pulseD1Delta">—</div>
        <div class="pulse-hint" id="pulseD1Hint">вернулись на следующий день</div>
      </div>
    </div>

    <!-- ═══════ ОБЗОР ═══════ -->
    <div class="block">
      <h2>📊 Обзор <small id="overviewPeriod"></small></h2>
      <div class="overview-row" id="overviewRow"></div>
    </div>

    <!-- ═══════ ПУТЬ ═══════ -->
    <div class="block">
      <h2>🎯 Путь пользователя</h2>
      <div class="funnel" id="funnelBox">
        <div class="empty">Загрузка…</div>
      </div>
    </div>

    <!-- ═══════ УСТРОЙСТВА ═══════ -->
    <div class="block">
      <h2>📱 Устройства</h2>
      <div class="device-row" id="deviceRow"></div>
      <div class="device-brands" id="deviceBrands"></div>
    </div>

    <!-- ═══════ ЧАСЫ ═══════ -->
    <div class="block">
      <h2>🕐 Когда заходят</h2>
      <div class="hours-chart" id="hoursChart"></div>
      <div class="hours-legend">
        <div class="hours-legend-item"><div class="hours-legend-dot" style="background:#6FA8FF;"></div><span>💻 Компьютер</span></div>
        <div class="hours-legend-item"><div class="hours-legend-dot" style="background:#FFB347;"></div><span>📱 Телефон</span></div>
      </div>
    </div>

    <!-- ═══════ ДЕТАЛИ ═══════ -->
    <button class="details-toggle" id="detailsToggle">
      <span class="arrow">▶</span>
      <span>🔧 Технические детали</span>
    </button>

    <div class="details-content" id="detailsContent">

      <div class="block">
        <h2>📡 Живая лента <small id="feedRange"></small></h2>
        <div style="margin-bottom:10px;">
          <label style="font-size:12px;color:rgba(255,255,255,0.6);cursor:pointer;user-select:none;">
            <input type="checkbox" id="showAdmin" style="margin-right:6px;">
            показывать мои заходы (админ)
          </label>
        </div>
        <div class="feed-box">
          <div class="feed-head">
            <span>Время</span>
            <span>Девайс</span>
            <span>Подсеть</span>
            <span>Кто</span>
            <span>Действие</span>
          </div>
          <div id="feedBody"></div>
        </div>
      </div>

      <div class="block">
        <h2>🌐 IP и подсети</h2>
        <div id="zonesBox"><div class="empty">Загрузка…</div></div>
      </div>

    </div>

  </main>
</div>

<script src="/static/admin-menu.js"></script>
<script>
const token = adminRequireToken();
renderAdminMenu('analytics');

let currentDays = 7;
let showAdminFeed = false;

function escapeHtml(s){
  return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

function fmtTime(ts){
  if (!ts) return '—';
  const d = new Date(ts * 1000);
  const now = new Date();
  const isToday = d.toDateString() === now.toDateString();
  const time = d.toLocaleTimeString('ru-RU', {hour:'2-digit', minute:'2-digit'});
  if (isToday) return time;
  return d.toLocaleDateString('ru-RU', {day:'2-digit', month:'2-digit'}) + ' ' + time;
}

function deviceIcon(d){
  if (d === 'mobile' || d === 'tablet') return '📱';
  return '💻';
}

const ACTION_LABELS = {
  visit: 'Заход',
  register: 'Регистрация',
  login: 'Вход',
  game: 'Игра',
};

const CHAR_EMOJI = {
  student:'🎓', sso:'👷', prorab:'📋', builder:'🏗️',
  prof:'🧑‍🏫', dean:'🧑‍💼', legend:'👑'
};

/* Период */
document.querySelectorAll('.period-tab').forEach(t => {
  t.onclick = () => {
    document.querySelectorAll('.period-tab').forEach(x => x.classList.remove('active'));
    t.classList.add('active');
    currentDays = parseInt(t.dataset.days);
    loadAll();
  };
});

/* Детали toggle */
const detailsToggle = document.getElementById('detailsToggle');
const detailsContent = document.getElementById('detailsContent');
detailsToggle.onclick = () => {
  detailsToggle.classList.toggle('open');
  detailsContent.classList.toggle('open');
  if (detailsContent.classList.contains('open')){
    loadFeed();
    loadZones();
  }
};

/* Админ feed toggle */
document.getElementById('showAdmin').onchange = (e) => {
  showAdminFeed = e.target.checked;
  loadFeed();
};

/* ═══════ Дельты ═══════ */
function renderDelta(el, delta, suffix){
  if (delta === null || delta === undefined){
    el.className = 'pulse-delta flat';
    el.textContent = 'нет данных';
    return;
  }
  if (delta > 0){
    el.className = 'pulse-delta up';
    el.textContent = '↑ ' + delta + '%';
  } else if (delta < 0){
    el.className = 'pulse-delta down';
    el.textContent = '↓ ' + Math.abs(delta) + '%';
  } else {
    el.className = 'pulse-delta flat';
    el.textContent = '= 0%';
  }
}

/* ═══════ ОБЗОР ═══════ */
async function loadOverview(){
  try{
    const d = await adminApi('/admin/api/overview?days=' + currentDays);

    document.getElementById('pulseVisitors').textContent = d.visitors;
    document.getElementById('pulsePlayed').textContent = d.played;
    document.getElementById('pulseD1').textContent = d.d1_pct + '%';

    renderDelta(document.getElementById('pulseVisitorsDelta'), d.visitors_delta);
    renderDelta(document.getElementById('pulsePlayedDelta'), d.played_delta);
    document.getElementById('pulseD1Delta').className = 'pulse-delta flat';
    document.getElementById('pulseD1Delta').textContent = d.d1_count + ' из ' + d.d1_total;
    document.getElementById('pulseD1Hint').textContent =
      d.d1_total ? 'вернулись на след. день' : 'пока нет данных';

    document.getElementById('overviewPeriod').textContent = 'за ' + d.days + ' дн.';

    const row = document.getElementById('overviewRow');
    const cards = [
      {label:'🆕 Новые', value: d.new_visitors, sub:'первый раз на сайте'},
      {label:'🔁 Вернувшиеся', value: d.returning, sub:'заходили ранее'},
      {label:'🎉 Регистрации', value: d.registered, sub: d.registered_delta !== null ? (d.registered_delta >= 0 ? '+' : '') + d.registered_delta + '%' : 'нет сравнения'},
      {label:'🎮 Всего партий', value: d.games, sub: d.games_delta !== null ? (d.games_delta >= 0 ? '+' : '') + d.games_delta + '%' : 'нет сравнения'},
      {label:'📊 Партий на игрока', value: d.played ? (d.games / d.played).toFixed(1) : '0', sub:'среднее'},
    ];
    row.innerHTML = cards.map(c =>
      '<div class="ov-card">' +
        '<div class="ov-label">' + c.label + '</div>' +
        '<div class="ov-value">' + c.value + '</div>' +
        '<div class="ov-sub">' + c.sub + '</div>' +
      '</div>'
    ).join('');
  }catch(e){ console.warn('overview:', e); }
}

/* ═══════ ВОРОНКА ═══════ */
async function loadFunnel(){
  try{
    const d = await adminApi('/admin/api/funnel-v2?days=' + currentDays);
    const box = document.getElementById('funnelBox');
    const steps = d.steps || [];
    if (!steps.length){
      box.innerHTML = '<div class="empty">Пока нет данных</div>';
      return;
    }
    const max = Math.max(1, ...steps.map(s => s.value));
    box.innerHTML = '';
    steps.forEach((s, i) => {
      const fillPct = (s.value / max) * 100;
      const el = document.createElement('div');
      el.className = 'funnel-step';
      el.innerHTML =
        '<div class="funnel-step-fill" style="width:' + fillPct + '%"></div>' +
        '<div class="funnel-content">' +
          '<span class="funnel-icon">' + s.icon + '</span>' +
          '<span class="funnel-label">' + s.label + '</span>' +
          (i > 0 ? '<span class="funnel-pct">' + s.pct + '%</span>' : '') +
          '<span class="funnel-count">' + s.value + '</span>' +
        '</div>';
      box.appendChild(el);
    });
  }catch(e){ console.warn('funnel:', e); }
}

/* ═══════ УСТРОЙСТВА ═══════ */
async function loadDevices(){
  try{
    const d = await adminApi('/admin/api/devices?days=' + currentDays);
    const total = (d.mobile + d.desktop + d.tablet) || 1;
    const row = document.getElementById('deviceRow');
    row.innerHTML =
      '<div class="device-card"><div class="device-label">📱 Телефоны</div><div class="device-value">' + d.mobile + '</div></div>' +
      '<div class="device-card"><div class="device-label">💻 Компьютеры</div><div class="device-value">' + d.desktop + '</div></div>' +
      '<div class="device-card"><div class="device-label">📟 Планшеты</div><div class="device-value">' + d.tablet + '</div></div>';

    const brands = document.getElementById('deviceBrands');
    const list = d.brands || [];
    if (!list.length){
      brands.innerHTML = '<span style="font-size:12px;opacity:0.4;">устройства начнут определяться по новым заходам</span>';
    } else {
      brands.innerHTML = list.map(b =>
        '<span class="brand-pill">' + escapeHtml(b.name) + '<b>' + b.count + '</b></span>'
      ).join('');
    }
  }catch(e){ console.warn('devices:', e); }
}

/* ═══════ ЧАСЫ ═══════ */
async function loadHours(){
  try{
    const r = await adminApi('/admin/api/hours-full?days=' + currentDays);
    const hours = r.hours || [];
    const chart = document.getElementById('hoursChart');
    const max = Math.max(1, ...hours.map(h => h.visits));
    chart.innerHTML = '';
    hours.forEach(h => {
      const totalH = (h.visits / max) * 100;
      const mobPct = h.visits ? (h.mobile / h.visits) * totalH : 0;
      const deskPct = h.visits ? (h.desktop / h.visits) * totalH : 0;
      const col = document.createElement('div');
      col.className = 'hour-col';
      col.title = h.hour + ':00 — всего ' + h.visits + ' (💻' + h.desktop + ' / 📱' + h.mobile + ')';
      col.innerHTML =
        '<div class="hour-stack">' +
          '<div class="hour-bar-mobile" style="height:' + mobPct + '%"></div>' +
          '<div class="hour-bar-desktop" style="height:' + deskPct + '%"></div>' +
        '</div>' +
        '<div class="hour-label">' + h.hour + '</div>';
      chart.appendChild(col);
    });
  }catch(e){ console.warn('hours:', e); }
}

/* ═══════ ЛЕНТА ═══════ */
async function loadFeed(){
  try{
    const url = '/admin/api/feed?days=' + currentDays + '&limit=60&admin=' + (showAdminFeed ? 1 : 0);
    const r = await adminApi(url);
    const feed = r.feed || [];
    const body = document.getElementById('feedBody');
    document.getElementById('feedRange').textContent = '(последние ' + feed.length + ')';

    if (!feed.length){
      body.innerHTML = '<div class="empty">Пока пусто</div>';
      return;
    }

    body.innerHTML = '';
    feed.forEach(item => {
      const row = document.createElement('div');
      row.className = 'feed-row';
      const actionLabel = ACTION_LABELS[item.action] || item.action;
      const who = item.logged_in
        ? '<span>' + (CHAR_EMOJI[item.active_char] || '🎓') + '</span><span class="feed-nick">' + escapeHtml(item.nick) + '</span>'
        : '<span>👻</span><span class="feed-guest">Гость</span>';
      const adminTag = item.is_admin ? ' 👑' : '';
      row.innerHTML =
        '<span class="feed-time">' + fmtTime(item.ts) + adminTag + '</span>' +
        '<span class="feed-device">' + deviceIcon(item.device) + '</span>' +
        '<span class="feed-subnet">' + escapeHtml(item.subnet) + '.*</span>' +
        '<span class="feed-who">' + who + '</span>' +
        '<span class="feed-action ' + item.action + '">' + actionLabel + '</span>';
      body.appendChild(row);
    });
  }catch(e){ console.warn('feed:', e); }
}

/* ═══════ ЗОНЫ ═══════ */
async function loadZones(){
  try{
    const r = await adminApi('/admin/api/zones?days=' + currentDays);
    const zones = r.zones || [];
    const box = document.getElementById('zonesBox');
    if (!zones.length){
      box.innerHTML = '<div class="empty">Пока нет данных</div>';
      return;
    }
    box.innerHTML = '';
    zones.slice(0, 20).forEach(z => {
      const el = document.createElement('div');
      el.className = 'zone-card';
      const users = (z.users || []).length
        ? z.users.map(u => '<span class="zone-pill">' + escapeHtml(u.nick) + '</span>').join('')
        : '<span class="zone-pill" style="opacity:0.5;">только гости</span>';
      el.innerHTML =
        '<div class="zone-head">' +
          '<span class="zone-subnet">' + escapeHtml(z.subnet) + '.*</span>' +
        '</div>' +
        '<div class="zone-stats">' +
          '<span>📊 <b>' + z.visits + '</b> заходов</span>' +
          '<span>👤 <b>' + z.users_count + '</b> игроков</span>' +
          '<span>🕐 ' + fmtTime(z.last_seen) + '</span>' +
        '</div>' +
        '<div class="zone-pills">' + users + '</div>';
      box.appendChild(el);
    });
  }catch(e){ console.warn('zones:', e); }
}

/* ═══════ ЗАГРУЗКА ВСЕГО ═══════ */
function loadAll(){
  loadOverview();
  loadFunnel();
  loadDevices();
  loadHours();
  if (detailsContent.classList.contains('open')){
    loadFeed();
    loadZones();
  }
}

loadAll();
setInterval(loadAll, 60000);
</script>

</body></html>
