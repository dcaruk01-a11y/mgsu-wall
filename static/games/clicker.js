/* ═══════════════════════════════════════════════════════════
   КЛИКЕР МГСУ — вся логика игры
   Подключается из pages/games/clicker.html
   ═══════════════════════════════════════════════════════════ */

renderSiteHeader('games');

/* ═══════════════════════════════════════════════════════════
   НАСТРОЙКИ
   ═══════════════════════════════════════════════════════════ */
const DURATION = 30;
const MULT_MIN = 1.0, MULT_MAX = 5.0;
const FAST_CLICK_MS = 350, SLOW_CLICK_MS = 700;
const MULT_STEP_UP = 0.18, MULT_STEP_DOWN = 0.35;
const COMBO_DECAY_INTERVAL = 300, COMBO_IDLE_THRESHOLD = 800;
const COIN_BONUS = 25;
const COIN_PENALTY = 60;
const COIN_TYPES = ['🪙', '💎', '⭐', '🔮', '🍀'];
const COIN_SPAWN_MIN = 900, COIN_SPAWN_MAX = 1800;
const COIN_FALL_MIN_MS = 3000, COIN_FALL_MAX_MS = 4800;
const SOUND_ENABLED = true, VIBRATION_ENABLED = true;
const DUEL_POLL_MS = 2000;
const DUEL_PROGRESS_MS = 1500;

const RANKS = [
  {max:50, name:'Студент', emoji:'🎓'}, {max:120, name:'ССОшник', emoji:'👷'},
  {max:220, name:'Прораб', emoji:'📋'}, {max:350, name:'Строитель', emoji:'🏗️'},
  {max:550, name:'Генподрядчик', emoji:'🏢'}, {max:800, name:'Застройщик', emoji:'🏙️'},
  {max:Infinity, name:'Легенда МГСУ', emoji:'👑'}
];
function rankFor(score){ for (const r of RANKS) if (score <= r.max) return r; return RANKS[RANKS.length - 1]; }

/* ═══════════════════════════════════════════════════════════
   СОСТОЯНИЕ
   ═══════════════════════════════════════════════════════════ */
let score = 0, timeLeft = DURATION, running = false;
let timerId = null, lastClickTime = 0, multiplier = 1.0, lastMilestone = 0;
let coinSpawnTimer = null, comboDecayTimer = null;
let myUid = '', myNick = '';
const isLoggedIn = !!localStorage.getItem('mgsu_token');

// Лимит: 1 партия в день в соло
let canPlaySolo = true;
let soloPlaysToday = 0;
let soloLimitChecked = false;

// Дуэль
let duelMode = false;
let duelCode = '';
let duelRole = '';
let duelState = null;
let duelPollTimer = null;
let duelProgressTimer = null;
let duelSubmitted = false;

/* ═══════════════════════════════════════════════════════════
   DOM
   ═══════════════════════════════════════════════════════════ */
const badge = document.getElementById('rankBadge');
const btn = document.getElementById('clickBtn');
const timerEl = document.getElementById('timer');
const timerBar = document.getElementById('timerBar');
const scoreEl = document.getElementById('scoreDisplay');
const multEl = document.getElementById('multiplier');
const startOv = document.getElementById('startOverlay');
const finishOv = document.getElementById('finishOverlay');
const shareBtn = document.getElementById('shareBtn');
const againBtn = document.getElementById('againBtn');
const finishEmoji = document.getElementById('finishEmoji');
const finishRank = document.getElementById('finishRank');
const finishScore = document.getElementById('finishScore');
const topList = document.getElementById('topList');
const meNotice = document.getElementById('meNotice');
const progressBlock = document.getElementById('progressBlock');
const toast = document.getElementById('toast');

const soloBtn = document.getElementById('soloBtn');
const soloLimitNote = document.getElementById('soloLimitNote');

const duelBar = document.getElementById('duelBar');
const duelNickYou = document.getElementById('duelNickYou');
const duelNickThem = document.getElementById('duelNickThem');
const duelScoreYou = document.getElementById('duelScoreYou');
const duelScoreThem = document.getElementById('duelScoreThem');
const duelLeaveBarBtn = document.getElementById('duelLeaveBarBtn');

const duelBtn = document.getElementById('duelBtn');
const duelPanel = document.getElementById('duelPanel');
const duelChoice = document.getElementById('duelChoice');
const duelCreateEl = document.getElementById('duelCreate');
const duelJoinEl = document.getElementById('duelJoin');
const duelLobby = document.getElementById('duelLobby');

const createCodeInput = document.getElementById('createCodeInput');
const joinCodeInput = document.getElementById('joinCodeInput');
const duelCodeShow = document.getElementById('duelCodeShow');
const duelPYou = document.getElementById('duelPYou');
const duelPThem = document.getElementById('duelPThem');
const duelWaiting = document.getElementById('duelWaiting');
const duelWaitText = document.getElementById('duelWaitText');
const duelStartBtn = document.getElementById('duelStartBtn');

const countdownOverlay = document.getElementById('countdownOverlay');
const countdownNum = document.getElementById('countdownNum');
const duelResultOverlay = document.getElementById('duelResultOverlay');
const duelVerdict = document.getElementById('duelVerdict');
const duelCardYou = document.getElementById('duelCardYou');
const duelCardThem = document.getElementById('duelCardThem');
const duelResultYouName = document.getElementById('duelResultYouName');
const duelResultYouScore = document.getElementById('duelResultYouScore');
const duelResultYouBadge = document.getElementById('duelResultYouBadge');
const duelResultThemName = document.getElementById('duelResultThemName');
const duelResultThemScore = document.getElementById('duelResultThemScore');
const duelResultThemBadge = document.getElementById('duelResultThemBadge');

/* ═══════════════════════════════════════════════════════════
   ЗВУК
   ═══════════════════════════════════════════════════════════ */
let audioCtx = null, lastSoundTime = 0;
const SOUND_THROTTLE = 15;
function initAudio(){
  if (audioCtx) return;
  try{ const AC = window.AudioContext || window.webkitAudioContext; if (AC) audioCtx = new AC(); }catch(e){}
}
function playClickSound(){
  if (!SOUND_ENABLED || !audioCtx) return;
  const now = performance.now();
  if (now - lastSoundTime < SOUND_THROTTLE) return;
  lastSoundTime = now;
  try{
    const t = audioCtx.currentTime;
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    osc.type = 'triangle';
    const freq = 1100 + Math.random() * 500;
    osc.frequency.setValueAtTime(freq, t);
    osc.frequency.exponentialRampToValueAtTime(freq * 0.55, t + 0.05);
    gain.gain.setValueAtTime(0.07, t);
    gain.gain.exponentialRampToValueAtTime(0.0001, t + 0.08);
    osc.connect(gain); gain.connect(audioCtx.destination);
    osc.start(t); osc.stop(t + 0.1);
  }catch(e){}
}
function vibrate(ms){ if (!VIBRATION_ENABLED) return; if (navigator.vibrate){ try{ navigator.vibrate(ms); }catch(e){} } }

/* ═══════════════════════════════════════════════════════════
   РАСПИСАНИЕ
   ═══════════════════════════════════════════════════════════ */
let scheduleOpen = true;
async function checkScheduleStatus(){
  try{
    const r = await fetch('/status');
    const s = await r.json();
    scheduleOpen = !!s.open;
    const banner = document.getElementById('statusBanner');
    const sub = document.getElementById('statusBannerSub');
    if (!scheduleOpen){
      sub.textContent = 'Игры доступны только в учебное время: с ' + s.opens_at + ' до ' + s.closes_at;
      banner.classList.add('show');
      if (running) stopGame();
      btn.disabled = true;
    } else {
      banner.classList.remove('show');
      if (!running) btn.disabled = false;
    }
  }catch(e){}
}
checkScheduleStatus();
setInterval(checkScheduleStatus, 60000);

/* ═══════════════════════════════════════════════════════════
   ПРОФИЛЬ + ЛИМИТ
   ═══════════════════════════════════════════════════════════ */
async function loadProfile(){
  if (!isLoggedIn) return;
  const t = localStorage.getItem('mgsu_token');
  try{
    const r = await fetch('/api/auth/me', {headers:{'Authorization': 'Bearer ' + t}});
    const d = await r.json();
    if (d && d.user){ myUid = d.user.uid; myNick = d.user.display_name; }
  }catch(e){}
  await checkSoloLimit();
}

async function checkSoloLimit(){
  if (!isLoggedIn){
    // Гости играют без лимита
    canPlaySolo = true;
    soloLimitChecked = true;
    updateSoloButton();
    return;
  }
  try{
    const r = await fetch('/clicker/can-play', {headers:{'Authorization': 'Bearer ' + localStorage.getItem('mgsu_token')}});
    const data = await r.json();
    canPlaySolo = !!data.can_play;
    soloPlaysToday = data.plays_today || 0;
    soloLimitChecked = true;
    updateSoloButton();
  }catch(e){
    canPlaySolo = true;
    soloLimitChecked = true;
    updateSoloButton();
  }
}

function updateSoloButton(){
  if (!soloBtn) return;
  if (canPlaySolo){
    soloBtn.classList.remove('disabled');
    soloBtn.disabled = false;
    soloBtn.textContent = '🎓 Играть одному';
    if (soloLimitNote) soloLimitNote.style.display = 'none';
  } else {
    soloBtn.classList.add('disabled');
    soloBtn.disabled = true;
    soloBtn.textContent = '🎓 Уже сыграно сегодня';
    if (soloLimitNote){
      soloLimitNote.textContent = 'Одна партия в день. Возвращайся завтра! 🌙';
      soloLimitNote.style.display = 'block';
    }
  }
}

loadProfile();

/* ═══════════════════════════════════════════════════════════
   ОТРИСОВКА
   ═══════════════════════════════════════════════════════════ */
function updateScore(newScore){
  score = Math.max(0, Math.round(newScore));
  scoreEl.textContent = score;
  let color = '';
  if      (score >= 500) color = '#FF6B6B';
  else if (score >= 350) color = '#FF8A3C';
  else if (score >= 200) color = '#FFB347';
  else if (score >= 100) color = '#FFD24A';
  else if (score >= 50)  color = '#A6E22E';
  scoreEl.style.color = color || '';

  const milestone = Math.floor(score / 50) * 50;
  if (milestone > lastMilestone && milestone > 0){
    lastMilestone = milestone;
    try{
      scoreEl.getAnimations().forEach(a => a.cancel());
      scoreEl.animate([{transform:'scale(1)'},{transform:'scale(1.35)'},{transform:'scale(1)'}],
        {duration:400, easing:'ease-out'});
    }catch(e){}
  }
  if (milestone < lastMilestone) lastMilestone = milestone;
}
function updateMultiplier(){
  multEl.textContent = 'x' + multiplier.toFixed(1);
  multEl.classList.remove('hot','blazing');
  btn.classList.remove('hot','blazing');
  if (multiplier >= 3.5){ multEl.classList.add('blazing'); btn.classList.add('blazing'); }
  else if (multiplier >= 2.0){ multEl.classList.add('hot'); btn.classList.add('hot'); }
}
function updateRank(){
  const r = rankFor(score);
  if (badge.textContent !== r.name){
    badge.textContent = r.name;
    badge.classList.add('up');
    setTimeout(() => badge.classList.remove('up'), 250);
  }
  btn.textContent = r.emoji;
}
function punchButton(){
  try{
    btn.getAnimations().forEach(a => a.cancel());
    btn.animate([{transform:'scale(1)'},{transform:'scale(0.88)'},{transform:'scale(1)'}],
      {duration:140, easing:'cubic-bezier(.2,1.4,.5,1)'});
  }catch(e){
    btn.style.transform = 'scale(0.9)';
    setTimeout(() => { btn.style.transform = ''; }, 90);
  }
}

/* ═══════════════════════════════════════════════════════════
   КЛИК
   ═══════════════════════════════════════════════════════════ */
function handleClick(){
  if (!running || !scheduleOpen) return;
  const now = performance.now();
  const dt = now - lastClickTime;
  lastClickTime = now;

  if (dt > 0 && dt < FAST_CLICK_MS) multiplier = Math.min(MULT_MAX, multiplier + MULT_STEP_UP);
  else if (dt > SLOW_CLICK_MS) multiplier = Math.max(MULT_MIN, multiplier - MULT_STEP_DOWN);

  const points = Math.max(1, Math.round(multiplier));
  updateScore(score + points);
  updateMultiplier();
  updateRank();
  punchButton();
  playClickSound();
  vibrate(8);

  const rect = btn.getBoundingClientRect();
  spawnFloat(rect.left + rect.width / 2 + (Math.random() - 0.5) * 50,
             rect.top + rect.height * 0.3, '+' + points, false);

  if (duelMode) duelScoreYou.textContent = score;
}

let lastTouchAt = 0;
function onTouchStart(e){ e.preventDefault(); lastTouchAt = Date.now(); handleClick(); }
function onMouseDown(e){ if (Date.now() - lastTouchAt < 700) return; e.preventDefault(); handleClick(); }
btn.addEventListener('touchstart', onTouchStart, {passive: false});
btn.addEventListener('mousedown', onMouseDown);

document.addEventListener('keydown', (e) => {
  if (e.code === 'Space'){
    e.preventDefault();
    if (!running || !scheduleOpen) return;
    if (e.repeat) return;
    handleClick();
  }
});

/* ═══════════════════════════════════════════════════════════
   МОНЕТКИ
   ═══════════════════════════════════════════════════════════ */
function spawnCoin(){
  if (!running) return;
  const coin = document.createElement('div');
  coin.className = 'falling-coin';
  coin.textContent = COIN_TYPES[Math.floor(Math.random() * COIN_TYPES.length)];
  const side = Math.random() < 0.5 ? 'left' : 'right';
  const offset = 6 + Math.random() * 18;
  coin.style[side] = offset + '%';
  const duration = COIN_FALL_MIN_MS + Math.random() * (COIN_FALL_MAX_MS - COIN_FALL_MIN_MS);
  coin.style.animationDuration = duration + 'ms';

  let handled = false;
  function onHit(e){
    if (handled || !running) return;
    handled = true;
    if (e){ e.preventDefault(); e.stopPropagation(); }
    coin.classList.add('caught');
    updateScore(score + COIN_BONUS);
    spawnFloatAt(coin, '+' + COIN_BONUS, false);
    playClickSound();
    vibrate(15);
    setTimeout(() => coin.remove(), 240);
    if (duelMode) duelScoreYou.textContent = score;
  }
  coin.addEventListener('touchstart', onHit, {passive: false});
  coin.addEventListener('mousedown', onHit);
  coin.addEventListener('animationend', () => {
    if (handled) return;
    if (!running){ coin.remove(); return; }
    handled = true;
    updateScore(score - COIN_PENALTY);
    spawnFloatAt(coin, '-' + COIN_PENALTY, true);
    vibrate(30);
    coin.remove();
    if (duelMode) duelScoreYou.textContent = score;
  });
  setTimeout(() => { if (coin.parentNode && !handled) coin.remove(); }, duration + 500);
  document.body.appendChild(coin);

  const next = COIN_SPAWN_MIN + Math.random() * (COIN_SPAWN_MAX - COIN_SPAWN_MIN);
  coinSpawnTimer = setTimeout(spawnCoin, next);
}
function spawnFloatAt(el, text, isBad){ const rect = el.getBoundingClientRect(); spawnFloat(rect.left + rect.width/2, rect.top + rect.height/2, text, isBad); }
function spawnFloat(x, y, text, isBad){
  const el = document.createElement('div');
  el.className = 'float-num ' + (isBad ? 'bad' : 'good');
  el.textContent = text;
  el.style.left = x + 'px'; el.style.top = y + 'px';
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 1100);
}

/* ═══════════════════════════════════════════════════════════
   ИГРА
   ═══════════════════════════════════════════════════════════ */
function resetGameState(){
  updateScore(0);
  timeLeft = DURATION;
  timerEl.textContent = timeLeft;
  timerEl.classList.remove('low');
  timerBar.style.width = '100%';
  timerBar.classList.remove('low');
  multiplier = 1.0;
  lastClickTime = performance.now();
  lastMilestone = 0;
  badge.textContent = 'Студент';
  btn.textContent = '🎓';
  updateMultiplier();
  document.querySelectorAll('.falling-coin').forEach(c => c.remove());
  running = true;
}
function runGameLoop(){
  clearInterval(timerId);
  timerId = setInterval(tick, 1000);
  clearInterval(comboDecayTimer);
  comboDecayTimer = setInterval(() => {
    if (!running) return;
    const idle = performance.now() - lastClickTime;
    if (idle > COMBO_IDLE_THRESHOLD){
      multiplier = Math.max(MULT_MIN, multiplier - 0.15);
      updateMultiplier();
    }
  }, COMBO_DECAY_INTERVAL);
  clearTimeout(coinSpawnTimer);
  spawnCoin();
}
function tick(){
  timeLeft -= 1;
  timerEl.textContent = Math.max(0, timeLeft);
  timerBar.style.width = Math.max(0, (timeLeft / DURATION) * 100) + '%';
  if (timeLeft <= 5){ timerEl.classList.add('low'); timerBar.classList.add('low'); }
  if (timeLeft <= 0) stopGame();
}

// Сброс в исходное состояние
function goHome(){
  stopDuelPolling();
  clearInterval(timerId);
  clearInterval(comboDecayTimer);
  clearTimeout(coinSpawnTimer);
  document.querySelectorAll('.falling-coin').forEach(c => c.remove());

  running = false;
  duelMode = false;
  duelCode = '';
  duelRole = '';
  duelSubmitted = false;

  finishOv.classList.add('hide');
  duelResultOverlay.classList.add('hide');
  duelPanel.classList.add('hide');
  duelBar.classList.add('hide');
  countdownOverlay.classList.add('hide');
  startOv.classList.remove('hide');

  badge.textContent = 'Студент';
  btn.textContent = '🎓';
  updateScore(0);
  updateMultiplier();

  // Обновляем состояние кнопки соло
  checkSoloLimit();
}

function startSolo(){
  if (!scheduleOpen){ checkScheduleStatus(); return; }
  if (!canPlaySolo){
    showToast('Уже сыграно сегодня 🌙', true);
    return;
  }
  initAudio();
  if (audioCtx && audioCtx.state === 'suspended') audioCtx.resume().catch(()=>{});
  duelMode = false;
  duelBar.classList.add('hide');
  resetGameState();
  startOv.classList.add('hide');
  finishOv.classList.add('hide');
  duelResultOverlay.classList.add('hide');
  duelPanel.classList.add('hide');
  progressBlock.style.display = 'none';
  runGameLoop();
}

async function stopGame(){
  if (!running) return;
  running = false;
  clearInterval(timerId);
  clearInterval(comboDecayTimer);
  clearTimeout(coinSpawnTimer);
  document.querySelectorAll('.falling-coin').forEach(c => c.remove());

  if (duelMode){
    await duelSubmitScore(score);
    return;
  }

  const r = rankFor(score);
  finishEmoji.textContent = r.emoji;
  finishRank.textContent = r.name;
  finishScore.textContent = score;
  finishOv.classList.remove('hide');
  meNotice.style.display = 'none';
  progressBlock.style.display = 'none';
  topList.innerHTML = '<div class="top-empty">Загрузка…</div>';

  try{
    const headers = {'Content-Type':'application/json'};
    const t = localStorage.getItem('mgsu_token');
    if (t) headers['Authorization'] = 'Bearer ' + t;
    const res = await fetch('/clicker/score', {
      method:'POST', headers,
      body: JSON.stringify({nick: '', score: score, rank: r.name, mode: 'solo'})
    });
    const data = await res.json();
    renderTop(data.top || [], score, data.position);
    renderProgress(data);
    // После партии — обновить флаг лимита
    canPlaySolo = false;
    updateSoloButton();
  }catch(e){
    topList.innerHTML = '<div class="top-empty">Не удалось загрузить топ</div>';
  }
}

function renderTop(top, myScore, pos){
  if (!top.length){ topList.innerHTML = '<div class="top-empty">Пока никого. Ты первый!</div>'; return; }
  topList.innerHTML = '';
  let iAmInTop = false;
  top.forEach((e, i) => {
    let isMe = false;
    if (isLoggedIn && myUid) isMe = (e.uid && e.uid === myUid);
    else isMe = (e.score === myScore && !iAmInTop);
    if (isMe) iAmInTop = true;
    const row = document.createElement('div');
    row.className = 'top-row' + (isMe ? ' me' : '');
    row.innerHTML = '<span class="top-pos">' + (i + 1) + '</span><span class="top-nick"></span><span class="top-score">' + e.score + '</span>';
    row.querySelector('.top-nick').textContent = e.nick;
    topList.appendChild(row);
  });
  if (!iAmInTop && pos){
    meNotice.style.display = 'block';
    meNotice.textContent = 'Ты — ' + pos + '-е место с ' + myScore + ' очками';
  } else meNotice.style.display = 'none';
}

function renderProgress(data){
  if (!data.logged_in){
    progressBlock.innerHTML = '<div class="progress-guest">💡 Хочешь монеты и топ? <a href="/auth">Создай аккаунт</a></div>';
    progressBlock.style.display = 'block';
    return;
  }
  let html = '';
  if (data.progress && data.progress.coins_added) html += '<div class="progress-line">💰 +' + data.progress.coins_added + ' монет</div>';
  if (data.progress){
    html += '<div class="progress-line">🏆 Всего очков: <b>' + data.progress.total_score + '</b></div>';
    html += '<div class="progress-line">🎮 Партий: <b>' + data.progress.games_played + '</b></div>';
  }
  if (data.streak !== null && data.streak !== undefined){
    html += '<div class="progress-line">🔥 Серия: <b>' + data.streak + ' дней</b>';
    if (data.streak_changed) html += ' <span style="color:#4ADE80;">+1</span>';
    html += '</div>';
  }
  html += '<div style="margin-top:10px;"><a href="/profile" class="progress-link">Открыть профиль →</a></div>';
  progressBlock.innerHTML = html;
  progressBlock.style.display = 'block';
}

/* ═══════════════════════════════════════════════════════════
   ДУЭЛЬ — навигация
   ═══════════════════════════════════════════════════════════ */
function duelHeaders(){
  const t = localStorage.getItem('mgsu_token') || '';
  return { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + t };
}

function showScreen(name){
  duelChoice.classList.add('hide');
  duelCreateEl.classList.add('hide');
  duelJoinEl.classList.add('hide');
  duelLobby.classList.add('hide');
  if (name === 'choice') duelChoice.classList.remove('hide');
  if (name === 'create') duelCreateEl.classList.remove('hide');
  if (name === 'join')   duelJoinEl.classList.remove('hide');
  if (name === 'lobby')  duelLobby.classList.remove('hide');
}

function openDuelPanel(){
  if (!isLoggedIn){
    showToast('Войди в аккаунт');
    setTimeout(() => location.href = '/auth', 1200);
    return;
  }
  duelPanel.classList.remove('hide');
  startOv.classList.add('hide');
  finishOv.classList.add('hide');
  duelResultOverlay.classList.add('hide');
  showScreen('choice');
}

async function createRoom(){
  const code = (createCodeInput.value || '').toUpperCase().replace(/[^A-Z0-9]/g,'').slice(0,4);
  if (code.length !== 4){
    createCodeInput.classList.add('err');
    showToast('Код — 4 символа', true);
    return;
  }
  try{
    const r = await fetch('/api/duel/create', {
      method:'POST', headers: duelHeaders(),
      body: JSON.stringify({code})
    });
    if (!r.ok){
      const err = await r.json().catch(()=>({}));
      createCodeInput.classList.add('err');
      showToast(err.detail || 'Ошибка', true);
      return;
    }
    const data = await r.json();
    duelCode = data.code;
    duelRole = 'host';
    duelMode = true;
    createCodeInput.classList.remove('err');
    goToLobby();
  }catch(e){ showToast('Ошибка соединения', true); }
}

async function joinRoom(){
  const code = (joinCodeInput.value || '').toUpperCase().replace(/[^A-Z0-9]/g,'').slice(0,4);
  if (code.length !== 4){
    joinCodeInput.classList.add('err');
    showToast('Код — 4 символа', true);
    return;
  }
  try{
    const r = await fetch('/api/duel/join', {
      method:'POST', headers: duelHeaders(),
      body: JSON.stringify({code})
    });
    if (!r.ok){
      const err = await r.json().catch(()=>({}));
      joinCodeInput.classList.add('err');
      showToast(err.detail || 'Комната не найдена', true);
      return;
    }
    const data = await r.json();
    duelCode = data.code;
    duelRole = 'guest';
    duelMode = true;
    joinCodeInput.classList.remove('err');
    goToLobby();
  }catch(e){ showToast('Ошибка соединения', true); }
}

function goToLobby(){
  showScreen('lobby');
  duelCodeShow.textContent = duelCode;
  duelPYou.textContent = '🧑 ' + (myNick || 'Ты');
  duelPThem.textContent = '⏳ Ждём…';
  duelPThem.classList.add('empty');
  duelWaiting.style.display = 'flex';
  duelStartBtn.classList.add('hide');

  if (duelRole === 'host'){
    document.getElementById('duelLobbyTitle').textContent = 'Ждём соперника…';
    duelWaitText.textContent = 'Отправь код другу';
  } else {
    document.getElementById('duelLobbyTitle').textContent = 'В комнате!';
    duelWaitText.textContent = 'Ждём, пока хост начнёт';
  }

  startPolling();
}

async function leaveRoom(){
  stopDuelPolling();
  if (duelCode){
    try{
      await fetch('/api/duel/leave', {
        method:'POST', headers: duelHeaders(),
        body: JSON.stringify({code: duelCode})
      });
    }catch(e){}
  }
  duelCode = '';
  duelRole = '';
  duelMode = false;
  duelPanel.classList.add('hide');
  startOv.classList.remove('hide');
}

async function duelStart(){
  try{
    const r = await fetch('/api/duel/start', {
      method:'POST', headers: duelHeaders(),
      body: JSON.stringify({code: duelCode})
    });
    if (!r.ok){
      const err = await r.json().catch(()=>({}));
      showToast(err.detail || 'Ошибка', true);
      return;
    }
  }catch(e){ showToast('Ошибка', true); }
}

function startPolling(){
  stopDuelPolling();
  pollDuelStatus();
  duelPollTimer = setInterval(() => {
    if (document.hidden) return;
    pollDuelStatus();
  }, DUEL_POLL_MS);
}
function stopDuelPolling(){
  if (duelPollTimer){ clearInterval(duelPollTimer); duelPollTimer = null; }
  if (duelProgressTimer){ clearInterval(duelProgressTimer); duelProgressTimer = null; }
}

async function pollDuelStatus(){
  if (!duelCode) return;
  try{
    const r = await fetch('/api/duel/status?code=' + encodeURIComponent(duelCode), {headers: duelHeaders()});
    if (r.status === 404 || r.status === 403){
      stopDuelPolling();
      showToast('Комната закрыта');
      duelCode = ''; duelRole = ''; duelMode = false;
      duelPanel.classList.add('hide');
      startOv.classList.remove('hide');
      return;
    }
    if (!r.ok) return;
    const data = await r.json();
    applyDuelState(data);
  }catch(e){}
}

function applyDuelState(data){
  const room = data.room;
  duelState = room;

  if (room.status === 'playing' || room.status === 'finished'){
    if (duelRole === 'host'){
      duelNickYou.textContent = room.host.nick;
      duelNickThem.textContent = room.guest ? room.guest.nick : 'Соперник';
      duelScoreThem.textContent = (room.guest && room.guest.score != null) ? room.guest.score : 0;
    } else {
      duelNickYou.textContent = room.guest.nick;
      duelNickThem.textContent = room.host.nick;
      duelScoreThem.textContent = room.host.score != null ? room.host.score : 0;
    }
  }

  if (room.guest){
    duelPThem.textContent = '🧑 ' + room.guest.nick;
    duelPThem.classList.remove('empty');
    duelWaiting.style.display = 'none';
    if (duelRole === 'host'){
      duelStartBtn.classList.remove('hide');
      if (room.status === 'ready' || room.status === 'waiting'){
        document.getElementById('duelLobbyTitle').textContent = 'Соперник на месте!';
        duelWaitText.textContent = 'Готов начать';
      }
    } else {
      document.getElementById('duelLobbyTitle').textContent = 'В комнате!';
      duelWaitText.textContent = 'Ждём, пока хост начнёт';
    }
  } else {
    duelPThem.textContent = '⏳ Ждём…';
    duelPThem.classList.add('empty');
    duelWaiting.style.display = 'flex';
    duelStartBtn.classList.add('hide');
  }

  if (room.status === 'playing' && !running && countdownOverlay.classList.contains('hide')){
    stopDuelPolling();
    startCountdown(room.start_at);
  }
  if (room.status === 'finished' && !running && duelResultOverlay.classList.contains('hide')){
    showDuelResult(room);
  }
}

function startCountdown(startAt){
  duelPanel.classList.add('hide');
  startOv.classList.add('hide');
  finishOv.classList.add('hide');
  duelResultOverlay.classList.add('hide');
  countdownOverlay.classList.remove('hide');

  if (duelState){
    duelNickYou.textContent = myNick || 'Ты';
    const opp = duelRole === 'host'
      ? (duelState.guest ? duelState.guest.nick : 'Соперник')
      : duelState.host.nick;
    duelNickThem.textContent = opp;
  }

  function tickCountdown(){
    const now = Date.now() / 1000;
    const left = startAt - now;
    if (left <= 0){
      countdownNum.textContent = 'GO!';
      countdownNum.classList.add('go');
      setTimeout(() => {
        countdownOverlay.classList.add('hide');
        countdownNum.classList.remove('go');
        beginDuelPlay();
      }, 400);
      return;
    }
    const sec = Math.ceil(left);
    countdownNum.textContent = sec;
    countdownNum.style.animation = 'none';
    void countdownNum.offsetWidth;
    countdownNum.style.animation = '';
    setTimeout(tickCountdown, 100);
  }
  tickCountdown();
}

function beginDuelPlay(){
  initAudio();
  if (audioCtx && audioCtx.state === 'suspended') audioCtx.resume().catch(()=>{});
  duelSubmitted = false;
  resetGameState();
  duelBar.classList.remove('hide');
  duelScoreYou.textContent = 0;
  duelScoreThem.textContent = 0;
  runGameLoop();

  clearInterval(duelProgressTimer);
  duelProgressTimer = setInterval(async () => {
    if (!running || !duelCode) return;
    if (document.hidden) return;
    try{
      await fetch('/api/duel/progress', {
        method:'POST', headers: duelHeaders(),
        body: JSON.stringify({code: duelCode, score: score})
      });
    }catch(e){}
  }, DUEL_PROGRESS_MS);

  startPolling();
}

async function duelSubmitScore(finalScore){
  if (duelSubmitted) return;
  duelSubmitted = true;
  clearInterval(duelProgressTimer);
  duelBar.classList.add('hide');

  try{
    const r = await fetch('/api/duel/submit', {
      method:'POST', headers: duelHeaders(),
      body: JSON.stringify({code: duelCode, score: finalScore})
    });
    if (r.ok){
      const data = await r.json();
      if (data.room && data.room.status === 'finished'){
        showDuelResult(data.room);
      } else {
        duelResultOverlay.classList.remove('hide');
        duelVerdict.textContent = 'Ждём соперника…';
        duelVerdict.className = 'duel-verdict';
        duelResultYouName.textContent = myNick || 'Ты';
        duelResultYouScore.textContent = finalScore;
        duelResultYouBadge.textContent = '✓ Готово';
        duelResultThemName.textContent = 'Соперник';
        duelResultThemScore.textContent = '...';
        duelResultThemBadge.textContent = 'Играет';
        duelCardYou.className = 'duel-result-card';
        duelCardThem.className = 'duel-result-card';
        startPolling();
      }
    }
  }catch(e){ showToast('Не удалось отправить'); }
}

function showDuelResult(room){
  stopDuelPolling();
  duelSubmitted = true;
  duelBar.classList.add('hide');

  const youScore = duelRole === 'host' ? room.host.score : room.guest.score;
  const themScore = duelRole === 'host' ? room.guest.score : room.host.score;
  const themNick = duelRole === 'host' ? room.guest.nick : room.host.nick;

  duelResultYouName.textContent = myNick || 'Ты';
  duelResultYouScore.textContent = youScore;
  duelResultThemName.textContent = themNick;
  duelResultThemScore.textContent = themScore;

  duelCardYou.classList.remove('win','lose','draw');
  duelCardThem.classList.remove('win','lose','draw');

  if (youScore > themScore){
    duelVerdict.textContent = '🏆 Победа!';
    duelVerdict.className = 'duel-verdict win';
    duelCardYou.classList.add('win');
    duelCardThem.classList.add('lose');
    duelResultYouBadge.textContent = 'Победитель';
    duelResultThemBadge.textContent = 'Проиграл';
  } else if (youScore < themScore){
    duelVerdict.textContent = '😞 Проигрыш';
    duelVerdict.className = 'duel-verdict lose';
    duelCardYou.classList.add('lose');
    duelCardThem.classList.add('win');
    duelResultYouBadge.textContent = 'Проиграл';
    duelResultThemBadge.textContent = 'Победитель';
  } else {
    duelVerdict.textContent = '🤝 Ничья';
    duelVerdict.className = 'duel-verdict draw';
    duelCardYou.classList.add('draw');
    duelCardThem.classList.add('draw');
    duelResultYouBadge.textContent = 'Ничья';
    duelResultThemBadge.textContent = 'Ничья';
  }

  duelResultOverlay.classList.remove('hide');

  // Отправляем результат в общий счёт (режим duel — не считается как партия)
  const r = rankFor(youScore);
  try{
    const headers = {'Content-Type':'application/json'};
    const t = localStorage.getItem('mgsu_token');
    if (t) headers['Authorization'] = 'Bearer ' + t;
    fetch('/clicker/score', {
      method:'POST', headers,
      body: JSON.stringify({nick: '', score: youScore, rank: r.name, mode: 'duel'})
    }).catch(()=>{});
  }catch(e){}
}

/* ═══════════════════════════════════════════════════════════
   КНОПКИ
   ═══════════════════════════════════════════════════════════ */
soloBtn.addEventListener('click', startSolo);
duelBtn.addEventListener('click', openDuelPanel);

document.getElementById('btnShowCreate').addEventListener('click', () => {
  createCodeInput.value = '';
  createCodeInput.classList.remove('err');
  showScreen('create');
  setTimeout(() => createCodeInput.focus(), 100);
});
document.getElementById('btnShowJoin').addEventListener('click', () => {
  joinCodeInput.value = '';
  joinCodeInput.classList.remove('err');
  showScreen('join');
  setTimeout(() => joinCodeInput.focus(), 100);
});
document.getElementById('btnBackFromChoice').addEventListener('click', () => {
  duelPanel.classList.add('hide');
  startOv.classList.remove('hide');
});

document.getElementById('btnCreateRoom').addEventListener('click', createRoom);
document.getElementById('btnBackFromCreate').addEventListener('click', () => showScreen('choice'));

document.getElementById('btnJoinRoom').addEventListener('click', joinRoom);
document.getElementById('btnBackFromJoin').addEventListener('click', () => showScreen('choice'));

document.getElementById('duelLeaveBtn').addEventListener('click', leaveRoom);
duelStartBtn.addEventListener('click', duelStart);

duelLeaveBarBtn.addEventListener('click', async () => {
  if (running){
    if (!confirm('Выйти из дуэли? Результат не отправится.')) return;
    running = false;
    clearInterval(timerId);
    clearInterval(comboDecayTimer);
    clearTimeout(coinSpawnTimer);
    document.querySelectorAll('.falling-coin').forEach(c => c.remove());
    if (duelCode){
      try{
        await fetch('/api/duel/leave', {
          method:'POST', headers: duelHeaders(),
          body: JSON.stringify({code: duelCode})
        });
      }catch(e){}
    }
  }
  goHome();
});

duelCodeShow.addEventListener('click', async () => {
  try{ await navigator.clipboard.writeText(duelCode); showToast('Код скопирован ✓'); }catch(e){}
});

document.getElementById('duelShareBtn').addEventListener('click', async () => {
  const url = location.origin + '/games/clicker?duel=' + duelCode;
  const text = `Сыграем в дуэль в Кликере МГСУ? Код: ${duelCode}\n${url}`;
  try{
    if (navigator.share) await navigator.share({ text, url });
    else { await navigator.clipboard.writeText(text); showToast('Скопировано ✓'); }
  }catch(e){}
});

[createCodeInput, joinCodeInput].forEach(inp => {
  inp.addEventListener('input', (e) => {
    e.target.value = e.target.value.toUpperCase().replace(/[^A-Z0-9]/g,'').slice(0,4);
    e.target.classList.remove('err');
  });
  inp.addEventListener('keydown', (e) => {
    if (e.key === 'Enter'){
      if (inp === createCodeInput) createRoom();
      else joinRoom();
    }
  });
});

againBtn.addEventListener('click', () => {
  if (!canPlaySolo){
    showToast('Возвращайся завтра 🌙', true);
    return;
  }
  startSolo();
});
document.getElementById('soloHomeBtn').addEventListener('click', goHome);

document.getElementById('duelAgainBtn').addEventListener('click', async () => {
  if (duelCode){
    try{
      await fetch('/api/duel/leave', {
        method:'POST', headers: duelHeaders(),
        body: JSON.stringify({code: duelCode})
      });
    }catch(e){}
  }
  stopDuelPolling();
  clearInterval(timerId);
  clearInterval(comboDecayTimer);
  clearTimeout(coinSpawnTimer);
  document.querySelectorAll('.falling-coin').forEach(c => c.remove());

  duelMode = false;
  duelCode = '';
  duelRole = '';
  duelSubmitted = false;
  running = false;

  duelResultOverlay.classList.add('hide');
  duelBar.classList.add('hide');
  countdownOverlay.classList.add('hide');
  finishOv.classList.add('hide');

  duelPanel.classList.remove('hide');
  showScreen('choice');
});

document.getElementById('duelExitBtn').addEventListener('click', goHome);

shareBtn.addEventListener('click', async () => {
  const r = rankFor(score);
  const text = `Я ${r.name} ${r.emoji} — ${score} очков за 30 секунд в «Кликере МГСУ». А ты?\nhttps://mgsu-wall.onrender.com/games/clicker`;
  try{
    if (navigator.share) await navigator.share({text});
    else { await navigator.clipboard.writeText(text); showToast('Скопировано!'); }
  }catch(err){
    try{ await navigator.clipboard.writeText(text); showToast('Скопировано!'); }
    catch(e2){ showToast(text); }
  }
});

function showToast(text, isError){
  toast.textContent = text;
  toast.className = 'toast show' + (isError ? ' err' : '');
  setTimeout(() => { toast.className = 'toast'; }, 1800);
}

/* ═══════════════════════════════════════════════════════════
   АВТО-ВХОД ПО ?duel=CODE
   ═══════════════════════════════════════════════════════════ */
window.addEventListener('load', () => {
  const params = new URLSearchParams(location.search);
  const codeFromUrl = params.get('duel');
  if (!codeFromUrl) return;
  if (!isLoggedIn){
    alert('Войди в аккаунт, чтобы принять приглашение');
    setTimeout(() => location.href = '/auth', 600);
    return;
  }
  const code = codeFromUrl.toUpperCase().replace(/[^A-Z0-9]/g,'').slice(0,4);
  if (code.length !== 4) return;

  setTimeout(async () => {
    duelPanel.classList.remove('hide');
    startOv.classList.add('hide');
    joinCodeInput.value = code;
    await joinRoom();
    history.replaceState(null, '', '/games/clicker');
  }, 500);
});

updateMultiplier();
updateRank();
document.addEventListener('touchstart', initAudio, {once: true, passive: true});
document.addEventListener('mousedown', initAudio, {once: true});
