/* ═══════════════════════════════════════════════════════════
   АВТОСКРЫТИЕ ШАПКИ ПРИ СКРОЛЛЕ
   ═══════════════════════════════════════════════════════════ */
(function(){
  var lastY = 0;
  var hideAt = 0;
  var COOLDOWN = 350;
  var ticking = false;

  function onScroll(){
    var y = window.pageYOffset || document.documentElement.scrollTop;
    var header = document.getElementById('siteHeader');
    if (!header){ ticking = false; return; }

    if (y < 60){
      header.classList.remove('hidden');
      lastY = y;
      ticking = false;
      return;
    }

    var maxScroll = (document.documentElement.scrollHeight || document.body.scrollHeight) - window.innerHeight;
    if (y >= maxScroll - 80){
      lastY = y;
      ticking = false;
      return;
    }

    var diff = y - lastY;
    lastY = y;

    if (diff > 5){
      if (!header.classList.contains('hidden')){
        header.classList.add('hidden');
        hideAt = Date.now();
      }
    } else if (diff < -5){
      if (Date.now() - hideAt > COOLDOWN){
        header.classList.remove('hidden');
      }
    }

    ticking = false;
  }

  window.addEventListener('scroll', function(){
    if (!ticking){
      window.requestAnimationFrame(onScroll);
      ticking = true;
    }
  }, {passive: true});
})();


/* ═══════════════════════════════════════════════════════════
   ГДЕ МЫ СЕЙЧАС
   ═══════════════════════════════════════════════════════════ */
function isOnHomePage(){
  var p = location.pathname;
  return p === '/glavnaya' || p === '/' || p === '' || p === '/index.html';
}

function isGamePage(){
  return location.pathname.indexOf('/games/') === 0;
}

/* ═══════════════════════════════════════════════════════════
   СКИНЫ ПЕРСОНАЖЕЙ
   ═══════════════════════════════════════════════════════════ */
var CHAR_EMOJI = {
  student: '🎓',
  sso: '👷',
  prorab: '📋',
  builder: '🏗️',
  prof: '🧑‍🏫',
  dean: '🧑‍💼',
  legend: '👑'
};


/* ═══════════════════════════════════════════════════════════
   РЕНДЕР ШАПКИ
   ═══════════════════════════════════════════════════════════ */
function renderSiteHeader(active, opts){
  active = active || '';
  opts = opts || {};
  var container = document.getElementById('siteHeader');
  if (!container) return;

  var token = localStorage.getItem('mgsu_token') || '';
  var isLoggedIn = !!token;
  var nick = localStorage.getItem('mgsu_nick') || '';

  // ★ Скин игрока
  var activeChar = localStorage.getItem('mgsu_active_char') || 'student';
  var avatarIcon = CHAR_EMOJI[activeChar] || '🎓';

  var onHome = isOnHomePage();

  var brandHref = onHome ? '#' : '/glavnaya';
  var brandClick = onHome ? ' onclick="scrollToTop(event)"' : '';

  /* 🎮 Игры */
  var gamesHref = onHome ? '#games' : '/glavnaya#games';
  var gamesClick = onHome ? ' onclick="scrollToGames(event)"' : '';
  var gamesActive = (onHome && active === 'games') ? ' active' : '';
  var gamesLink =
    '<a href="' + gamesHref + '" data-key="games" class="site-header-link' + gamesActive + '" title="Игры"' + gamesClick + '>' +
      '<span class="site-header-link-icon">🎮</span>' +
      '<span class="site-header-link-label">Игры</span>' +
    '</a>';

  /* 🏆 Рейтинг */
  var rActive = (active === 'ratings') ? ' active' : '';
  var ratingsLink =
    '<a href="/ratings" data-key="ratings" class="site-header-link' + rActive + '" title="Рейтинг">' +
      '<span class="site-header-link-icon">🏆</span>' +
      '<span class="site-header-link-label">Рейтинг</span>' +
    '</a>';

  /* 🛍 Магазин */
  var sActive = (active === 'shop') ? ' active' : '';
  var shopLink =
    '<a href="/shop" data-key="shop" class="site-header-link' + sActive + '" title="Магазин">' +
      '<span class="site-header-link-icon">🛍</span>' +
      '<span class="site-header-link-label">Магазин</span>' +
    '</a>';

  /* ПРАВАЯ ЧАСТЬ */
  var profileHtml = '';
  if (isLoggedIn){
    profileHtml =
      '<a href="/profile" class="site-header-avatar' + (active==='profile'?' active':'') + '" title="' + (nick || 'Профиль') + '">' +
        '<span>' + avatarIcon + '</span>' +
      '</a>';
  } else {
    profileHtml =
      '<a href="/auth" class="site-header-profile' + (active==='auth'?' active':'') + '" title="Войти">' +
        '<span class="site-header-profile-icon">👤</span>' +
        '<span class="site-header-profile-label">Войти</span>' +
      '</a>';
  }

  container.className = 'site-header';
  container.innerHTML =
    '<div class="site-header-inner">' +
      '<a href="' + brandHref + '" class="site-header-brand" id="siteBrand"' + brandClick + '>' +
        '<img src="/assets/icons/logo-square.svg" alt="Лого" class="site-header-logo">' +
        '<span class="site-header-label">Игры МГСУ</span>' +
      '</a>' +
      '<nav class="site-header-nav">' +
        gamesLink +
        ratingsLink +
        shopLink +
      '</nav>' +
      profileHtml +
    '</div>';

  if (onHome){
    setupScrollSpy();
  }

  // ★ Подтягиваем профиль если залогинен (обновляем ник и скин)
  if (isLoggedIn){
    fetch('/api/auth/me', {headers:{'Authorization': 'Bearer ' + token}})
      .then(function(r){ return r.ok ? r.json() : null; })
      .then(function(d){
        if (d && d.user){
          localStorage.setItem('mgsu_nick', d.user.display_name);
          if (d.user.active_char){
            localStorage.setItem('mgsu_active_char', d.user.active_char);
          }
          var av = container.querySelector('.site-header-avatar span');
          if (av){
            var ch = d.user.active_char || 'student';
            av.textContent = CHAR_EMOJI[ch] || '🎓';
          }
          var avatarEl = container.querySelector('.site-header-avatar');
          if (avatarEl) avatarEl.title = d.user.display_name || 'Профиль';
        }
      })
      .catch(function(){});
  }
}


/* ═══════════════════════════════════════════════════════════
   СКРОЛЛ-СПАЙ (только на главной)
   ═══════════════════════════════════════════════════════════ */
function setupScrollSpy(){
  var gamesSection = document.getElementById('games');
  var gamesLink = document.querySelector('.site-header-link[data-key="games"]');
  if (!gamesSection || !gamesLink) return;

  if (!('IntersectionObserver' in window)) return;

  var observer = new IntersectionObserver(function(entries){
    entries.forEach(function(entry){
      if (entry.isIntersecting){
        gamesLink.classList.add('active');
      } else {
        gamesLink.classList.remove('active');
      }
    });
  }, {
    rootMargin: '-40% 0px -40% 0px',
    threshold: 0
  });
  observer.observe(gamesSection);
}


/* ═══════════════════════════════════════════════════════════
   ВСПОМОГАТЕЛЬНЫЕ
   ═══════════════════════════════════════════════════════════ */
function scrollToGames(e){
  var el = document.getElementById('games');
  if (!el) return;
  if (e) e.preventDefault();
  var headerH = 64;
  var top = el.getBoundingClientRect().top + window.pageYOffset - headerH - 20;
  window.scrollTo({top: top, behavior: 'smooth'});
}

function scrollToTop(e){
  if (e) e.preventDefault();
  window.scrollTo({top: 0, behavior: 'smooth'});
}


/* ═══════════════════════════════════════════════════════════
   ФУТЕР
   ═══════════════════════════════════════════════════════════ */
function renderSiteFooter(){
  var container = document.getElementById('siteFooter');
  if (!container) return;
  container.className = 'site-footer';
  container.innerHTML =
    '<div class="site-footer-inner">' +
      + '<div class="site-footer-left">© 2026 · Не является официальным сайтом НИУ МГСУ · <span class="site-version">v1.0.0</span></div>' +
      '<div class="site-footer-right">' +
        '<a href="https://t.me/mgsu_feedback_bot" target="_blank" rel="noopener">Предложить идею</a>' +
        '<span class="site-footer-dot">·</span>' +
        '<a href="/privacy">О проекте</a>' +
        '<span class="site-footer-dot">·</span>' +
        '<a href="/privacy">Политика конфиденциальности</a>' +
        '<span class="site-footer-dot">·</span>' +
        '<a href="https://t.me/mgsu_wall_archive" target="_blank" rel="noopener">Telegram-канал</a>' +
      '</div>' +
    '</div>';
}


/* ═══════════════════════════════════════════════════════════
   PWA
   ═══════════════════════════════════════════════════════════ */
(function(){
  if (!document.querySelector('link[rel="manifest"]')){
    var link = document.createElement('link');
    link.rel = 'manifest';
    link.href = '/static/manifest.json';
    document.head.appendChild(link);
  }

  var metas = [
    {name:'apple-mobile-web-app-capable',           content:'yes'},
    {name:'apple-mobile-web-app-status-bar-style',  content:'black-translucent'},
    {name:'apple-mobile-web-app-title',             content:'МГСУ Игры'},
    {name:'mobile-web-app-capable',                 content:'yes'},
    {name:'theme-color',                            content:'#0F3C73'},
    {name:'format-detection',                       content:'telephone=no'}
  ];
  metas.forEach(function(m){
    var existing = document.querySelector('meta[name="' + m.name + '"]');
    if (existing){ existing.content = m.content; }
    else {
      var meta = document.createElement('meta');
      meta.name = m.name;
      meta.content = m.content;
      document.head.appendChild(meta);
    }
  });

  if (!document.querySelector('link[rel="apple-touch-icon"]')){
    var ati = document.createElement('link');
    ati.rel = 'apple-touch-icon';
    ati.href = '/assets/icons/logo-square.svg';
    document.head.appendChild(ati);
  }
})();


/* ═══════════════════════════════════════════════════════════
   FAVICON
   ═══════════════════════════════════════════════════════════ */
(function(){
  document.querySelectorAll('link[rel*="icon"]:not([rel="apple-touch-icon"])').forEach(function(l){ l.remove(); });
  var links = [
    { rel: 'icon',             type: 'image/svg+xml', href: '/assets/icons/favicon.svg' },
    { rel: 'alternate icon',   type: 'image/png',     href: '/assets/icons/favicon.svg' },
    { rel: 'mask-icon',                               href: '/assets/icons/favicon.svg', color: '#0F3C73' }
  ];
  links.forEach(function(ic){
    var link = document.createElement('link');
    link.rel = ic.rel;
    if (ic.type) link.type = ic.type;
    if (ic.color) link.setAttribute('color', ic.color);
    link.href = ic.href;
    document.head.appendChild(link);
  });
})();


/* ═══════════════════════════════════════════════════════════
   FEEDBACK POPUP
   ═══════════════════════════════════════════════════════════ */
(function(){
  if (window.__mgsuFeedbackInit) return;
  window.__mgsuFeedbackInit = true;

  var onGame = isGamePage();
  var onHome = isOnHomePage();

  if (onGame){
    try{
      var key = 'mgsu_games_seen_' + location.pathname;
      if (!sessionStorage.getItem(key)){
        sessionStorage.setItem(key, '1');
        var cnt = parseInt(localStorage.getItem('mgsu_games_count') || '0', 10) + 1;
        localStorage.setItem('mgsu_games_count', String(cnt));
      }
    }catch(e){}
    return;
  }

  var token = '';
  try{ token = localStorage.getItem('mgsu_token') || ''; }catch(e){}

  function shouldShowByGames(){
    var count = 0;
    try{ count = parseInt(localStorage.getItem('mgsu_games_count') || '0', 10); }catch(e){}
    if (count < 3) return false;
    try{ if (localStorage.getItem('mgsu_feedback_submitted') === '1') return false; }catch(e){}
    var DISMISS_COOLDOWN = 30 * 24 * 60 * 60 * 1000;
    var lastDismiss = 0;
    try{ lastDismiss = parseInt(localStorage.getItem('mgsu_feedback_dismissed_at') || '0', 10); }catch(e){}
    if (lastDismiss && Date.now() - lastDismiss < DISMISS_COOLDOWN) return false;
    return true;
  }

  function showFeedbackPopup(fromAdmin){
    if (document.getElementById('mgsuFbOverlay')) return;

    var overlay = document.createElement('div');
    overlay.className = 'mgsu-fb-overlay';
    overlay.id = 'mgsuFbOverlay';
    overlay.innerHTML =
      '<div class="mgsu-fb-card" role="dialog" aria-modal="true">' +
        '<div class="mgsu-fb-emoji">💌</div>' +
        '<h2>' + (fromAdmin ? 'Разработчик просит отзыв' : 'Как тебе игры?') + '</h2>' +
        '<p class="mgsu-fb-text">' +
          'Привет! Я разработчик этого проекта. ' +
          'Хочу, чтобы в него играли с удовольствием, а для этого мне нужна <b>твоя обратная связь</b>.<br><br>' +
          'Поставь оценку и напиши пару слов — что нравится, что улучшить?' +
        '</p>' +
        '<div class="mgsu-fb-stars" id="mgsuFbStars">' +
          '<button type="button" class="mgsu-fb-star" data-star="1">⭐</button>' +
          '<button type="button" class="mgsu-fb-star" data-star="2">⭐</button>' +
          '<button type="button" class="mgsu-fb-star" data-star="3">⭐</button>' +
          '<button type="button" class="mgsu-fb-star" data-star="4">⭐</button>' +
          '<button type="button" class="mgsu-fb-star" data-star="5">⭐</button>' +
        '</div>' +
        '<textarea class="mgsu-fb-textarea" id="mgsuFbText" maxlength="500" placeholder="Что улучшить? Что добавить? Что не понравилось? (необязательно)"></textarea>' +
        '<div class="mgsu-fb-actions">' +
          '<button type="button" class="mgsu-fb-send" id="mgsuFbSend">Отправить разработчику</button>' +
          '<button type="button" class="mgsu-fb-later" id="mgsuFbLater">Может быть позже</button>' +
        '</div>' +
        '<div class="mgsu-fb-hint">Одно сообщение уйдёт разработчику. Спасибо! 🙏</div>' +
      '</div>';

    document.body.appendChild(overlay);
    requestAnimationFrame(function(){ overlay.classList.add('show'); });

    if (fromAdmin && token){
      fetch('/api/feedback/seen', {
        method:'POST',
        headers:{'Authorization':'Bearer ' + token}
      }).catch(function(){});
    }

    var selectedStars = 0;
    var starBtns = overlay.querySelectorAll('.mgsu-fb-star');

    starBtns.forEach(function(b){
      b.addEventListener('click', function(){
        var n = parseInt(b.getAttribute('data-star'), 10);
        selectedStars = n;
        starBtns.forEach(function(x){
          var v = parseInt(x.getAttribute('data-star'), 10);
          x.classList.toggle('active', v <= n);
          if (v === n){
            x.classList.remove('pulse');
            void x.offsetWidth;
            x.classList.add('pulse');
          }
        });
      });
    });

    function closeFeedback(){
      overlay.classList.remove('show');
      setTimeout(function(){ if (overlay.parentNode) overlay.remove(); }, 300);
    }

    document.getElementById('mgsuFbLater').addEventListener('click', function(){
      try{ localStorage.setItem('mgsu_feedback_dismissed_at', String(Date.now())); }catch(e){}
      closeFeedback();
    });

    document.getElementById('mgsuFbSend').addEventListener('click', async function(){
      if (!selectedStars){
        starBtns.forEach(function(x){
          x.classList.remove('pulse');
          void x.offsetWidth;
          x.classList.add('pulse');
        });
        return;
      }
      var text = (document.getElementById('mgsuFbText').value || '').trim();
      var sendBtn = document.getElementById('mgsuFbSend');
      sendBtn.disabled = true;
      sendBtn.textContent = 'Отправляю…';
      try{
        var headers = {'Content-Type': 'application/json'};
        if (token) headers['Authorization'] = 'Bearer ' + token;
        var r = await fetch('/api/feedback/app', {
          method:'POST',
          headers: headers,
          body: JSON.stringify({
            stars: selectedStars,
            text: text,
            page: location.pathname,
            ua: navigator.userAgent.slice(0, 200)
          })
        });
        if (r.ok){
          try{ localStorage.setItem('mgsu_feedback_submitted', '1'); }catch(e){}
          sendBtn.textContent = '✓ Отправлено!';
          sendBtn.style.background = 'linear-gradient(135deg,#4ADE80,#22c55e)';
          setTimeout(closeFeedback, 1200);
        } else {
          sendBtn.disabled = false;
          sendBtn.textContent = 'Отправить разработчику';
        }
      }catch(e){
        sendBtn.disabled = false;
        sendBtn.textContent = 'Отправить разработчику';
      }
    });

    overlay.addEventListener('click', function(e){
      if (e.target === overlay){
        try{ localStorage.setItem('mgsu_feedback_dismissed_at', String(Date.now())); }catch(e){}
        closeFeedback();
      }
    });
  }

  async function checkAdminRequest(){
    if (!token) return false;
    try{
      var r = await fetch('/api/feedback/check', {
        headers:{'Authorization':'Bearer ' + token}
      });
      var data = await r.json();
      return !!data.pending;
    }catch(e){ return false; }
  }

  async function init(){
    var adminPending = await checkAdminRequest();

    if (adminPending){
      setTimeout(function(){ showFeedbackPopup(true); }, 2000);
      return;
    }

    if (!onHome) return;
    if (!shouldShowByGames()) return;
    setTimeout(function(){ showFeedbackPopup(false); }, 4000);
  }

  init();
})();
