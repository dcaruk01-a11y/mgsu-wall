<!doctype html>
<html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Профиль · Игры МГСУ</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="/theme.css">
<link rel="stylesheet" href="/static/site-header.css">
<style>
.profile-wrap{max-width:640px;margin:0 auto;padding:24px 16px 48px;}

.profile-header{display:flex;align-items:center;gap:16px;margin-bottom:24px;}
.avatar{
  width:72px;height:72px;border-radius:50%;
  background:rgba(128,128,128,0.15);
  border:2px solid rgba(128,128,128,0.3);
  display:flex;align-items:center;justify-content:center;
  font-size:36px;flex-shrink:0;
}
.profile-info{flex:1;min-width:0;}
.profile-name-row{display:flex;align-items:center;gap:8px;flex-wrap:wrap;}
.profile-name{font-size:24px;font-weight:800;line-height:1.1;word-break:break-word;color:inherit;}
.icon-btn{
  width:28px;height:28px;border-radius:50%;
  border:1px solid rgba(128,128,128,0.3);
  background:rgba(128,128,128,0.12);
  color:inherit;opacity:0.75;
  display:inline-flex;align-items:center;justify-content:center;
  cursor:pointer;flex-shrink:0;font-size:13px;transition:all .15s;padding:0;
}
.icon-btn:hover{opacity:1;background:rgba(128,128,128,0.25);transform:scale(1.05);}

.profile-score{text-align:right;flex-shrink:0;margin-left:auto;}
.profile-score-val{font-size:22px;font-weight:900;color:#FFB347;font-variant-numeric:tabular-nums;line-height:1;}
.profile-score-lbl{font-size:10px;font-weight:800;letter-spacing:0.12em;text-transform:uppercase;opacity:0.55;margin-top:4px;}

.profile-uid{
  font-family:monospace;font-size:12px;opacity:0.7;margin-top:6px;
  padding:3px 10px;border-radius:999px;
  background:rgba(128,128,128,0.12);
  display:inline-flex;align-items:center;gap:6px;
  cursor:pointer;transition:background .15s;color:inherit;
}
.profile-uid:hover{background:rgba(128,128,128,0.22);}
.profile-uid-copy{font-size:11px;opacity:0.6;}

.card{padding:18px 20px;border-radius:14px;background:rgba(128,128,128,0.10);border:1px solid rgba(128,128,128,0.18);margin-bottom:14px;}
.card h3{font-size:12px;font-weight:700;letter-spacing:0.12em;text-transform:uppercase;opacity:0.6;margin:0 0 12px;}

.rank-line{display:flex;align-items:center;gap:12px;margin-bottom:12px;}
.rank-emoji{font-size:36px;line-height:1;flex-shrink:0;}
.rank-meta{flex:1;min-width:0;}
.rank-name{font-size:17px;font-weight:800;line-height:1.1;}
.rank-next{font-size:11px;opacity:0.6;margin-top:3px;}

.rank-bar{height:6px;border-radius:3px;background:rgba(128,128,128,0.20);overflow:hidden;margin-bottom:8px;}
.rank-bar-fill{height:100%;background:linear-gradient(90deg,#6FA8FF,#B794F6);border-radius:3px;transition:width .4s;}
.rank-progress-text{font-size:11px;opacity:0.55;text-align:center;font-variant-numeric:tabular-nums;}

.rank-bonus{
  margin-top:12px;padding:10px 14px;border-radius:10px;
  background:rgba(255,180,80,0.08);border:1px solid rgba(255,180,80,0.28);
  display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;
}
.rank-bonus-lbl{font-size:10px;font-weight:800;letter-spacing:0.12em;text-transform:uppercase;opacity:0.6;margin-bottom:3px;}
.rank-bonus-val{font-size:18px;font-weight:900;color:#FFB347;}
.rank-bonus-next{font-size:11px;opacity:0.75;text-align:right;line-height:1.35;}

.inst-line{display:flex;align-items:center;gap:12px;}
.inst-emoji{font-size:32px;line-height:1;flex-shrink:0;}
.inst-meta{flex:1;min-width:0;}
.inst-short{font-size:16px;font-weight:900;line-height:1.1;}
.inst-name{font-size:11px;opacity:0.6;margin-top:2px;line-height:1.3;}
.inst-score{text-align:right;flex-shrink:0;}
.inst-score-val{font-size:20px;font-weight:900;color:#6FA8FF;font-variant-numeric:tabular-nums;line-height:1;}
.inst-score-lbl{font-size:10px;font-weight:800;letter-spacing:0.1em;text-transform:uppercase;opacity:0.55;margin-top:4px;}

.inst-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:8px;margin-top:4px;}
.inst-item{
  padding:12px 8px;border-radius:12px;
  border:2px solid rgba(128,128,128,0.25);
  background:rgba(128,128,128,0.06);
  cursor:pointer;font-family:inherit;color:inherit;
  text-align:center;transition:transform .1s, background .15s, border-color .15s;
}
.inst-item:hover{background:rgba(111,168,255,0.15);border-color:rgba(111,168,255,0.55);transform:translateY(-2px);}
.inst-item-emoji{font-size:24px;line-height:1;margin-bottom:4px;}
.inst-item-short{font-size:13px;font-weight:900;}
.inst-item-name{font-size:9px;opacity:0.6;margin-top:2px;line-height:1.25;}

.inst-actions{margin-top:12px;display:flex;justify-content:flex-end;}
.inst-change-btn{
  padding:8px 16px;border-radius:8px;
  background:rgba(255,77,94,0.12);
  border:1px solid rgba(255,77,94,0.4);
  color:#FF8B8B;font-family:inherit;font-size:12px;font-weight:700;
  cursor:pointer;transition:all .15s;
}
.inst-change-btn:hover{background:rgba(255,77,94,0.25);color:#fff;}

.tasks-list{display:flex;flex-direction:column;gap:8px;}
.task-item{padding:12px 14px;border-radius:10px;background:rgba(128,128,128,0.10);border:1px solid rgba(128,128,128,0.18);}
.task-item.done{background:rgba(74,222,128,0.10);border-color:rgba(74,222,128,0.35);}
.task-head{display:flex;justify-content:space-between;align-items:flex-start;gap:10px;margin-bottom:8px;}
.task-text{font-size:13px;font-weight:600;line-height:1.4;flex:1;color:inherit;}
.task-reward{font-size:11px;font-weight:700;padding:3px 8px;border-radius:999px;background:rgba(128,128,128,0.15);color:#4ADE80;white-space:nowrap;}
.task-item.done .task-reward{background:#4ADE80;color:#0a1f0f;}
.task-progress-bar{height:5px;border-radius:3px;background:rgba(128,128,128,0.20);overflow:hidden;margin-bottom:5px;}
.task-progress-fill{height:100%;background:#6FA8FF;transition:width .3s;}
.task-item.done .task-progress-fill{background:#4ADE80;}
.task-progress-text{font-size:11px;opacity:0.6;font-variant-numeric:tabular-nums;}
.tasks-empty{padding:14px;text-align:center;opacity:0.6;font-size:12px;}

.positions-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;}
.position-item{
  text-align:center;padding:12px 4px;border-radius:10px;
  background:rgba(128,128,128,0.08);
  border:1px solid rgba(128,128,128,0.18);
}
.position-lbl{font-size:9px;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;opacity:0.6;margin-bottom:4px;}
.position-val{font-size:20px;font-weight:900;font-variant-numeric:tabular-nums;}

.logout-row{text-align:center;padding:20px 0 4px;}
.btn-logout{
  min-width:200px;padding:12px 24px;border-radius:10px;
  border:1px solid rgba(255,77,94,0.4);
  background:rgba(255,77,94,0.08);
  color:#FF4D5E;font-family:inherit;font-size:14px;font-weight:700;
  cursor:pointer;transition:all .15s;
}
.btn-logout:hover{background:rgba(255,77,94,0.18);}

.settings-modal{
  position:fixed;inset:0;z-index:2000;
  background:rgba(5,14,31,0.85);
  backdrop-filter:blur(12px);
  display:none;align-items:center;justify-content:center;padding:20px;
}
.settings-modal.open{display:flex;}
.settings-box{
  background:rgba(20,26,44,0.96);
  border:1px solid rgba(128,128,128,0.30);
  border-radius:18px;padding:26px 24px;max-width:420px;width:100%;color:#fff;
}
.settings-box h3{font-size:19px;font-weight:800;margin:0 0 18px;color:#fff;}
.settings-tabs{display:flex;background:rgba(255,255,255,0.06);border-radius:999px;padding:4px;margin-bottom:18px;}
.settings-tab{
  flex:1;padding:9px;border:0;background:transparent;color:#fff;
  font-family:inherit;font-size:12px;font-weight:700;border-radius:999px;
  cursor:pointer;opacity:0.6;transition:all .15s;
}
.settings-tab.active{background:rgba(255,255,255,0.18);opacity:1;}
.settings-pane{display:none;}
.settings-pane.active{display:block;}
.settings-actions{display:flex;gap:8px;margin-top:12px;}
.field{margin-bottom:12px;}
.field label{display:block;font-size:10px;font-weight:700;letter-spacing:0.14em;text-transform:uppercase;opacity:0.6;margin-bottom:6px;}
.field input{
  width:100%;padding:11px 14px;border-radius:10px;
  background:rgba(128,128,128,0.10);
  border:1px solid rgba(128,128,128,0.25);
  color:inherit;font-family:inherit;font-size:14px;
  outline:none;box-sizing:border-box;
}
.field input:focus{border-color:rgba(128,128,128,0.6);}
.btn{
  padding:11px 18px;border-radius:10px;
  border:1px solid rgba(128,128,128,0.3);
  background:rgba(128,128,128,0.10);
  color:inherit;font-family:inherit;font-size:13px;font-weight:700;
  cursor:pointer;transition:all .15s;
}
.btn:hover{background:rgba(128,128,128,0.20);}
.btn-primary{background:rgba(128,128,128,0.28);}
.err{color:#FF4D5E;font-size:12px;margin-top:6px;min-height:16px;}
.forgot-hint{
  margin-top:12px;padding:12px 14px;border-radius:10px;
  background:rgba(128,128,128,0.10);
  border:1px dashed rgba(128,128,128,0.3);
  font-size:12px;line-height:1.5;text-align:center;
}
.forgot-hint a{color:#4ADE80;font-weight:700;text-decoration:none;}
.settings-close{
  position:absolute;top:12px;right:12px;
  width:30px;height:30px;border-radius:50%;
  border:0;background:rgba(255,255,255,0.10);color:#fff;
  cursor:pointer;font-size:14px;
}

.hide{display:none !important;}
.loading{padding:60px 20px;text-align:center;opacity:0.5;}

/* Скелетоны */
.skeleton{
  background:linear-gradient(90deg,
    rgba(128,128,128,0.10) 0%,
    rgba(128,128,128,0.18) 50%,
    rgba(128,128,128,0.10) 100%);
  background-size:200% 100%;
  animation:skeletonLoad 1.4s ease-in-out infinite;
  border-radius:8px;
}
@keyframes skeletonLoad{
  0%{background-position:200% 0;}
  100%{background-position:-200% 0;}
}
.skeleton-line{height:14px;margin-bottom:8px;}
.skeleton-line.short{width:60%;}
.skeleton-block{height:60px;}
</style>
</head><body>

<div id="siteHeader"></div>

<div class="profile-wrap">

  <div id="loading" class="loading">Загрузка…</div>

  <div id="content" class="hide">

    <div class="profile-header">
      <div class="avatar" id="pAvatar">🎓</div>
      <div class="profile-info">
        <div class="profile-name-row">
          <div class="profile-name" id="pName">—</div>
          <button class="icon-btn" id="editNameBtn" title="Сменить имя">✏️</button>
          <button class="icon-btn" id="editPinBtn" title="Сменить PIN">🔑</button>
        </div>
        <div class="profile-uid" id="pUid" title="Нажми, чтобы скопировать">
          <span id="pUidText">—</span>
          <span class="profile-uid-copy">📋</span>
        </div>
      </div>
      <div class="profile-score">
        <div class="profile-score-val" id="pScore">0</div>
        <div class="profile-score-lbl">очков</div>
      </div>
    </div>

    <div class="card">
      <h3>🏅 Ранг</h3>
      <div class="rank-line">
        <div class="rank-emoji" id="rankEmoji">🎓</div>
        <div class="rank-meta">
          <div class="rank-name" id="rankName">Первокурсник</div>
          <div class="rank-next" id="rankNext">До «Студент» 📚</div>
        </div>
      </div>
      <div class="rank-bar"><div class="rank-bar-fill" id="rankProgressFill" style="width:0%"></div></div>
      <div class="rank-progress-text" id="rankProgressText">—</div>
      <div class="rank-bonus">
        <div>
          <div class="rank-bonus-lbl">Бонус к монетам</div>
          <div class="rank-bonus-val" id="rankBonusNow">+0%</div>
        </div>
        <div class="rank-bonus-next" id="rankBonusNextBox">
          Следующий ранг<br>даст <b style="color:#FFD700;">+5%</b>
        </div>
      </div>
    </div>

    <div class="card" id="instituteCard">
      <h3>🏛 Институт</h3>
      <div id="instituteBox">
        <div class="tasks-empty">Загрузка…</div>
      </div>
    </div>

    <div class="card">
      <h3>🏆 Достижения <span id="achCounter" style="opacity:0.7;font-weight:600;letter-spacing:0;font-size:11px;margin-left:auto;">0 / 0</span></h3>
      <div id="achievementsBox">
        <div class="tasks-empty">Загрузка…</div>
      </div>
    </div>

    <div class="card">
      <h3>🎯 Задания на сегодня</h3>
      <div class="tasks-list" id="tasksList">
        <div class="tasks-empty">Загрузка…</div>
      </div>
    </div>

    <div class="card">
      <h3>🏆 Мои позиции в рейтинге</h3>
      <div id="myRatingsBox">
        <div class="tasks-empty">Загрузка…</div>
      </div>
    </div>

    <div class="card">
      <h3>📊 Статистика</h3>
      <div class="positions-grid">
        <div class="position-item">
          <div class="position-lbl">🔥 Серия</div>
          <div class="position-val" id="pStreak">0</div>
        </div>
        <div class="position-item">
          <div class="position-lbl">💰 Монеты</div>
          <div class="position-val" id="pCoins">0</div>
        </div>
        <div class="position-item">
          <div class="position-lbl">🎮 Партий</div>
          <div class="position-val" id="pGames">0</div>
        </div>
      </div>
    </div>

    <div class="logout-row">
      <button class="btn-logout" id="btnLogout">🚪 Выйти</button>
    </div>

  </div>
</div>

<div class="settings-modal" id="settingsModal">
  <div class="settings-box" style="position:relative;">
    <button class="settings-close" id="settingsClose">✕</button>
    <h3>⚙️ Настройки</h3>
    <div class="settings-tabs">
      <button class="settings-tab active" data-pane="name">✏️ Имя</button>
      <button class="settings-tab" data-pane="pin">🔑 PIN</button>
    </div>
    <div class="settings-pane active" id="paneName">
      <div class="field">
        <label>Новое имя</label>
        <input type="text" id="newName" placeholder="Новое имя" maxlength="20">
      </div>
      <div class="err" id="nameErr"></div>
      <div class="settings-actions">
        <button class="btn btn-primary" id="btnSaveName" style="flex:1;">Сохранить</button>
      </div>
    </div>
    <div class="settings-pane" id="panePin">
      <div class="field">
        <label>Старый PIN</label>
        <input type="tel" id="oldPin" placeholder="••••" maxlength="4" inputmode="numeric">
      </div>
      <div class="field">
        <label>Новый PIN</label>
        <input type="tel" id="newPin" placeholder="••••" maxlength="4" inputmode="numeric">
      </div>
      <div class="err" id="pinErr"></div>
      <div class="settings-actions">
        <button class="btn btn-primary" id="btnSavePin" style="flex:1;">Сохранить</button>
      </div>
      <div class="forgot-hint">
        🔑 Забыл старый PIN? Напиши нам в Telegram — сбросим вручную.<br>
        <a href="https://t.me/mgsu_feedback_bot?start=forgot_pin" target="_blank" rel="noopener">Открыть бота →</a>
      </div>
    </div>
  </div>
</div>

<div id="siteFooter"></div>

<script src="/static/site-header.js"></script>
<script>
renderSiteHeader('profile');
renderSiteFooter();

const LS_TOKEN = 'mgsu_token';
const LS_UID = 'mgsu_uid';
const token = localStorage.getItem(LS_TOKEN);

if (!token) location.href = '/auth';

const P_EMOJI = {
  student:'🎓', sso:'👷', prorab:'📋',
  builder:'🏗️', prof:'🧑‍🏫', dean:'🧑‍💼', legend:'👑'
};

let allInstitutes = [];
let myInstituteKey = '';
let currentUser = null;

async function api(path, opts){
  opts = opts || {};
  const headers = Object.assign({'Content-Type':'application/json'}, opts.headers || {});
  if (token) headers['Authorization'] = 'Bearer ' + token;
  const res = await fetch(path, Object.assign({}, opts, {headers: headers}));
  if (res.status === 401){
    localStorage.removeItem(LS_TOKEN);
    localStorage.removeItem(LS_UID);
    localStorage.removeItem('mgsu_nick');
    localStorage.removeItem('mgsu_active_char');
    localStorage.removeItem('mgsu_active_frame');
    location.href = '/auth';
    throw new Error('unauthorized');
  }
  return { status: res.status, data: await res.json() };
}

function escapeHtml(s){
  return String(s).replace(/[&<>"']/g, function(c){
    return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];
  });
}

/* ═══════════════════════════════════════════════════════════
   ЗАГРУЗКА — ОДИН ЗАПРОС
   ═══════════════════════════════════════════════════════════ */
async function loadMe(){
  try{
    const res = await api('/api/profile/full');
    if (res.status !== 200){ location.href = '/auth'; return; }

    const d = res.data;
    currentUser = d.user;
    setUser(d.user);

    document.getElementById('loading').classList.add('hide');
    document.getElementById('content').classList.remove('hide');

    // Институт
    allInstitutes = d.institutes_list || [];
    myInstituteKey = currentUser.institute || '';
    if (d.institute){
      renderInstituteFromData(d.institute);
    } else {
      renderInstitutePicker();
    }

    // Задания
    renderTasks({ logged_in: true, tasks: d.tasks || [] });

    // Позиции
    const positions = d.positions || {};
    renderMyRatings({
      me: {
        uid: currentUser.uid,
        nick: currentUser.display_name,
        coins: currentUser.coins || 0,
        day: positions.day,
        week: positions.week,
        all: positions.all,
      }
    });

    // Ачивки — счётчик
    const counter = document.getElementById('achCounter');
    if (counter){
      counter.textContent = (d.achievements_unlocked || 0) + ' / ' + (d.achievements_total || 0);
    }

    // Ачивки — список (второй запрос, но он один)
    loadAchievements();
  }catch(e){
    console.error('loadMe error:', e);
    document.getElementById('loading').classList.add('hide');
    document.getElementById('content').classList.remove('hide');
  }
}

function setUser(u){
  document.getElementById('pName').textContent = u.display_name;
  document.getElementById('pUidText').textContent = u.uid;
  document.getElementById('pStreak').textContent = u.streak || 0;
  document.getElementById('pCoins').textContent = u.coins || 0;
  document.getElementById('pScore').textContent = u.total_score || 0;
  document.getElementById('pGames').textContent = u.games_played || 0;

  const av = document.getElementById('pAvatar');
  if (av && u.active_char) av.textContent = P_EMOJI[u.active_char] || '🎓';

  if (u.active_char){
    try{ localStorage.setItem('mgsu_active_char', u.active_char); }catch(e){}
  }

  if (u.rank){
    const r = u.rank;
    document.getElementById('rankEmoji').textContent = r.emoji;
    document.getElementById('rankName').textContent = r.name;

    const nextEl = document.getElementById('rankNext');
    const fill = document.getElementById('rankProgressFill');
    const txt = document.getElementById('rankProgressText');

    if (r.next){
      nextEl.textContent = 'До «' + r.next.name + '» ' + r.next.emoji;
      fill.style.width = Math.round(r.progress * 100) + '%';
      const needScore = Math.max(0, r.next.min_score - r.total_score);
      const needGames = Math.max(0, r.next.min_games - r.games_played);
      const parts = [];
      if (needScore > 0) parts.push(needScore + ' очков');
      if (needGames > 0) parts.push(needGames + ' партий');
      txt.textContent = 'Осталось: ' + (parts.join(' · ') || '—');
    } else {
      nextEl.textContent = 'Максимальный ранг достигнут';
      fill.style.width = '100%';
      txt.textContent = '👑 Ты — легенда';
    }

    const bonusNow = r.bonus_pct || 0;
    const bonusEl = document.getElementById('rankBonusNow');
    if (bonusEl){
      bonusEl.textContent = '+' + bonusNow + '%';
      bonusEl.style.color = bonusNow > 0 ? '#FFB347' : 'rgba(128,128,128,0.6)';
    }

    const bonusNextBox = document.getElementById('rankBonusNextBox');
    if (bonusNextBox){
      if (r.next && r.next.bonus_pct !== undefined){
        bonusNextBox.innerHTML = 'Следующий ранг<br>даст <b style="color:#FFD700;">+' + r.next.bonus_pct + '%</b>';
      } else {
        bonusNextBox.innerHTML = '<b style="color:#FFD700;">Максимум</b><br>бонуса';
      }
    }
  }

  localStorage.setItem('mgsu_nick', u.display_name);
  const headerAvatar = document.querySelector('.site-header-avatar span');
  if (headerAvatar){
    headerAvatar.textContent = P_EMOJI[u.active_char] || '🎓';
  }
}

/* ═══════════════════════════════════════════════════════════
   ИНСТИТУТ
   ═══════════════════════════════════════════════════════════ */
function renderInstituteFromData(info){
  const box = document.getElementById('instituteBox');
  if (!box || !info) return;

  box.innerHTML =
    '<div class="inst-line">' +
      '<div class="inst-emoji">' + info.emoji + '</div>' +
      '<div class="inst-meta">' +
        '<div class="inst-short">' + escapeHtml(info.short) + '</div>' +
        '<div class="inst-name">' + escapeHtml(info.name) + '</div>' +
      '</div>' +
      '<div class="inst-score">' +
        '<div class="inst-score-val">' + info.my_score + '</div>' +
        '<div class="inst-score-lbl">моих очков</div>' +
      '</div>' +
    '</div>' +
    '<div style="margin-top:14px;padding:12px 14px;border-radius:10px;background:rgba(111,168,255,0.08);border:1px solid rgba(111,168,255,0.22);font-size:12px;line-height:1.5;">' +
      '<div style="display:flex;justify-content:space-between;margin-bottom:4px;">' +
        '<span style="opacity:0.6;">Копилка института:</span>' +
        '<b style="color:#6FA8FF;">' + info.total + '</b>' +
      '</div>' +
      '<div style="display:flex;justify-content:space-between;margin-bottom:4px;">' +
        '<span style="opacity:0.6;">Место в топе:</span>' +
        '<b>#' + info.rank + '</b>' +
      '</div>' +
      '<div style="display:flex;justify-content:space-between;">' +
        '<span style="opacity:0.6;">Игроков в институте:</span>' +
        '<b>' + info.players + '</b>' +
      '</div>' +
    '</div>' +
    '<div class="inst-actions">' +
      '<button class="inst-change-btn" id="btnChangeInstitute">Сменить институт</button>' +
    '</div>';

  const btn = document.getElementById('btnChangeInstitute');
  if (btn){
    btn.onclick = function(){
      const warn = 'СМЕНА ИНСТИТУТА\n\n' +
        'Весь прогресс обнулится:\n' +
        '• Очки: 0\n• Монеты: 0\n• Серия дней: 0\n• Партии: 0\n• Скины: только Студент 🎓\n\n' +
        'Имя, UID и PIN сохранятся.\n\nСменить сейчас?';
      if (!confirm(warn)) return;
      myInstituteKey = '';
      renderInstitutePicker();
    };
  }
}

function renderInstitutePicker(){
  const box = document.getElementById('instituteBox');
  if (!box) return;

  if (!allInstitutes.length){
    box.innerHTML = '<div class="tasks-empty">Институты не загружены</div>';
    return;
  }

  let html = '<div style="font-size:12px;opacity:0.7;margin-bottom:12px;line-height:1.5;">' +
    'Выбери свой институт. Все очки пойдут в его копилку. ' +
    '<b style="color:#FF8B8B;">Смена института обнуляет прогресс.</b>' +
    '</div>';
  html += '<div class="inst-grid">';
  allInstitutes.forEach(function(i){
    html +=
      '<button class="inst-item" data-key="' + escapeHtml(i.key) + '" type="button">' +
        '<div class="inst-item-emoji">' + i.emoji + '</div>' +
        '<div class="inst-item-short">' + escapeHtml(i.short) + '</div>' +
        '<div class="inst-item-name">' + escapeHtml(i.name.slice(0, 45)) + '</div>' +
      '</button>';
  });
  html += '</div>';
  box.innerHTML = html;

  document.querySelectorAll('.inst-item').forEach(function(b){
    b.onclick = function(){ chooseInstitute(b.dataset.key); };
  });
}

async function chooseInstitute(key){
  const inst = allInstitutes.find(function(i){ return i.key === key; });
  if (!inst) return;

  if (myInstituteKey && myInstituteKey !== key){
    if (!confirm('Смена института = обнуление прогресса. Продолжить?')) return;
  } else if (!myInstituteKey){
    if (!confirm('Выбрать «' + inst.short + '»?\n\nВсе твои очки пойдут в копилку этого института.')) return;
  }

  try{
    const r = await api('/api/institutes/set', {
      method:'POST',
      body: JSON.stringify({institute: key})
    });
    if (r.status !== 200){
      alert(r.data.detail || 'Ошибка');
      return;
    }
    alert('Институт «' + inst.short + '» выбран!');
    location.reload();
  }catch(e){
    alert('Ошибка соединения');
  }
}

/* ═══════════════════════════════════════════════════════════
   ЗАДАНИЯ
   ═══════════════════════════════════════════════════════════ */
function renderTasks(data){
  const box = document.getElementById('tasksList');
  if (!box) return;
  if (!data.logged_in){
    box.innerHTML = '<div class="tasks-empty">Войди в аккаунт</div>';
    return;
  }
  if (!data.tasks || !data.tasks.length){
    box.innerHTML = '<div class="tasks-empty">Задания появятся утром</div>';
    return;
  }
  box.innerHTML = '';
  data.tasks.forEach(function(t){
    const item = document.createElement('div');
    item.className = 'task-item' + (t.done ? ' done' : '');
    const pct = t.target ? Math.min(100, Math.round(t.progress / t.target * 100)) : 0;
    item.innerHTML =
      '<div class="task-head">' +
        '<div class="task-text">' + escapeHtml(t.text) + '</div>' +
        '<div class="task-reward">+' + t.reward + '</div>' +
      '</div>' +
      '<div class="task-progress-bar"><div class="task-progress-fill" style="width:' + pct + '%"></div></div>' +
      '<div class="task-progress-text">' + (t.done ? '✓ Выполнено' : t.progress + ' / ' + t.target) + '</div>';
    box.appendChild(item);
  });
}

/* ═══════════════════════════════════════════════════════════
   ПОЗИЦИИ
   ═══════════════════════════════════════════════════════════ */
function renderMyRatings(data){
  const box = document.getElementById('myRatingsBox');
  if (!box) return;
  const me = data.me;
  if (!me){
    box.innerHTML = '<div class="tasks-empty">Сыграй партию — увидишь свою позицию.</div>';
    return;
  }
  const posData = [
    {label: 'Сегодня',   pos: me.day ? me.day.pos : null},
    {label: 'Неделя',    pos: me.week ? me.week.pos : null},
    {label: 'Всё время', pos: me.all ? me.all.pos : null},
  ];
  let html = '<div class="positions-grid">';
  posData.forEach(function(p){
    const val = p.pos ? ('#' + p.pos) : '—';
    const color = p.pos && p.pos <= 3 ? '#FFD700' : 'inherit';
    html +=
      '<div class="position-item">' +
        '<div class="position-lbl">' + p.label + '</div>' +
        '<div class="position-val" style="color:' + color + ';">' + val + '</div>' +
      '</div>';
  });
  html += '</div>';
  html += '<div style="margin-top:12px;text-align:center;">' +
    '<a href="/ratings" style="color:#6FA8FF;text-decoration:none;font-size:12px;font-weight:700;">Смотреть весь рейтинг →</a>' +
  '</div>';
  box.innerHTML = html;
}

/* ═══════════════════════════════════════════════════════════
   ДОСТИЖЕНИЯ
   ═══════════════════════════════════════════════════════════ */
async function loadAchievements(){
  try{
    const r = await api('/api/achievements');
    renderAchievements(r.data);
  }catch(e){
    const box = document.getElementById('achievementsBox');
    if (box) box.innerHTML = '<div class="tasks-empty">Не удалось загрузить</div>';
  }
}

function renderAchievements(data){
  const box = document.getElementById('achievementsBox');
  const counter = document.getElementById('achCounter');
  if (!box) return;

  const list = data.achievements || [];
  if (counter){
    counter.textContent = (data.unlocked || 0) + ' / ' + (data.total || 0);
  }
  if (!list.length){
    box.innerHTML = '<div class="tasks-empty">Пока нет достижений</div>';
    return;
  }
  let html = '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(72px,1fr));gap:8px;">';
  list.forEach(function(a){
    const unlocked = a.unlocked;
    html +=
      '<div title="' + escapeHtml(a.desc) + '" style="' +
        'padding:10px 4px;border-radius:12px;text-align:center;cursor:help;' +
        'background:' + (unlocked ? 'rgba(255,180,80,0.12)' : 'rgba(128,128,128,0.06)') + ';' +
        'border:1px solid ' + (unlocked ? 'rgba(255,180,80,0.4)' : 'rgba(128,128,128,0.15)') + ';' +
        'opacity:' + (unlocked ? '1' : '0.4') + ';' +
        'filter:' + (unlocked ? 'none' : 'grayscale(1)') + ';' +
      '">' +
        '<div style="font-size:26px;line-height:1;margin-bottom:4px;">' + (unlocked ? a.emoji : '🔒') + '</div>' +
        '<div style="font-size:9px;font-weight:700;line-height:1.2;opacity:0.85;">' + escapeHtml(a.name) + '</div>' +
      '</div>';
  });
  html += '</div>';
  box.innerHTML = html;
}

/* ═══════════════════════════════════════════════════════════
   КОПИРОВАНИЕ UID
   ═══════════════════════════════════════════════════════════ */
document.getElementById('pUid').addEventListener('click', async function(){
  try{
    const uid = document.getElementById('pUidText').textContent;
    await navigator.clipboard.writeText(uid);
    const el = document.getElementById('pUid');
    const old = el.querySelector('.profile-uid-copy').textContent;
    el.querySelector('.profile-uid-copy').textContent = '✓';
    setTimeout(function(){ el.querySelector('.profile-uid-copy').textContent = old; }, 1200);
  }catch(e){}
});

/* ═══════════════════════════════════════════════════════════
   МОДАЛКА НАСТРОЕК
   ═══════════════════════════════════════════════════════════ */
const settingsModal = document.getElementById('settingsModal');

document.getElementById('editNameBtn').onclick = function(){
  document.getElementById('newName').value = document.getElementById('pName').textContent;
  switchPane('name');
  settingsModal.classList.add('open');
  document.getElementById('nameErr').textContent = '';
};

document.getElementById('editPinBtn').onclick = function(){
  document.getElementById('oldPin').value = '';
  document.getElementById('newPin').value = '';
  switchPane('pin');
  settingsModal.classList.add('open');
  document.getElementById('pinErr').textContent = '';
};

document.getElementById('settingsClose').onclick = function(){
  settingsModal.classList.remove('open');
};

settingsModal.addEventListener('click', function(e){
  if (e.target === settingsModal) settingsModal.classList.remove('open');
});

function switchPane(name){
  document.querySelectorAll('.settings-tab').forEach(function(t){
    t.classList.toggle('active', t.dataset.pane === name);
  });
  document.querySelectorAll('.settings-pane').forEach(function(p){
    p.classList.toggle('active', p.id === 'pane' + name.charAt(0).toUpperCase() + name.slice(1));
  });
}

document.querySelectorAll('.settings-tab').forEach(function(t){
  t.onclick = function(){ switchPane(t.dataset.pane); };
});

document.getElementById('btnSaveName').onclick = async function(){
  const newName = document.getElementById('newName').value.trim();
  const errEl = document.getElementById('nameErr');
  errEl.textContent = '';
  if (!newName){ errEl.textContent = 'Введи имя'; return; }
  if (newName.length > 20){ errEl.textContent = 'Имя — до 20 символов'; return; }
  try{
    const res = await api('/api/auth/update-name', {
      method:'POST',
      body: JSON.stringify({display_name: newName})
    });
    if (res.status !== 200){ errEl.textContent = res.data.detail || 'Ошибка'; return; }
    document.getElementById('pName').textContent = res.data.display_name;
    localStorage.setItem('mgsu_nick', res.data.display_name);
    settingsModal.classList.remove('open');
  }catch(e){ errEl.textContent = 'Ошибка'; }
};

document.getElementById('btnSavePin').onclick = async function(){
  const oldPin = document.getElementById('oldPin').value.trim();
  const newPin = document.getElementById('newPin').value.trim();
  const errEl = document.getElementById('pinErr');
  errEl.textContent = '';

  if (!oldPin){ errEl.textContent = 'Введи старый PIN'; return; }
  if (!/^\d{4}$/.test(newPin)){ errEl.textContent = 'Новый PIN — 4 цифры'; return; }

  try{
    const res = await api('/api/auth/update-pin', {
      method:'POST',
      body: JSON.stringify({old_pin: oldPin, new_pin: newPin})
    });

    if (res.status !== 200){
      errEl.innerHTML = (res.data.detail || 'Ошибка') +
        '<br><span style="opacity:0.7;font-size:12px;">Забыл старый PIN? Напиши в Telegram-бота.</span>';
      return;
    }

    settingsModal.classList.remove('open');
    alert('PIN изменён. Войди заново.');
    localStorage.removeItem(LS_TOKEN);
    localStorage.removeItem(LS_UID);
    localStorage.removeItem('mgsu_nick');
    localStorage.removeItem('mgsu_active_char');
    localStorage.removeItem('mgsu_active_frame');
    location.href = '/auth';
  }catch(e){ errEl.textContent = 'Ошибка'; }
};

document.getElementById('btnLogout').onclick = async function(){
  try{ await api('/api/auth/logout', {method:'POST'}); }catch(e){}
  localStorage.removeItem(LS_TOKEN);
  localStorage.removeItem(LS_UID);
  localStorage.removeItem('mgsu_nick');
  localStorage.removeItem('mgsu_active_char');
  localStorage.removeItem('mgsu_active_frame');
  location.href = '/auth';
};

['oldPin','newPin'].forEach(function(id){
  document.getElementById(id).addEventListener('input', function(e){
    e.target.value = e.target.value.replace(/\D/g,'').slice(0,4);
  });
});

loadMe();
</script>

</body></html>
