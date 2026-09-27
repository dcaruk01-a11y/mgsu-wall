/* ═══════════════════════════════════════════════════════════
   АВТОСКРЫТИЕ ШАПКИ ПРИ СКРОЛЛЕ
   Фикс отскока: у самого низа страницы не реагируем,
   после скрытия — пауза 350мс перед показом
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

    // Самый верх — всегда показываем
    if (y < 60){
      header.classList.remove('hidden');
      lastY = y;
      ticking = false;
      return;
    }

    // У самого низа страницы — ИГНОРИРУЕМ (iOS отскок)
    var maxScroll = (document.documentElement.scrollHeight || document.body.scrollHeight) - window.innerHeight;
    if (y >= maxScroll - 80){
      lastY = y;
      ticking = false;
      return;
    }

    var diff = y - lastY;
    lastY = y;

    if (diff > 5){
      // Уверенный скролл вниз — прячем
      if (!header.classList.contains('hidden')){
        header.classList.add('hidden');
        hideAt = Date.now();
      }
    } else if (diff < -5){
      // Уверенный скролл вверх — показываем, но не сразу после скрытия
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
   РЕНДЕР ШАПКИ
   ═══════════════════════════════════════════════════════════ */
function renderSiteHeader(active, opts){
  active = active || 'home';
  opts = opts || {};
  var container = document.getElementById('siteHeader');
  if (!container) return;

  var token = localStorage.getItem('mgsu_token') || '';
  var isLoggedIn = !!token;
  var nick = localStorage.getItem('mgsu_nick') || '';
  var initial = nick ? nick.charAt(0).toUpperCase() : '👤';

  // На главной — не перезагружаем страницу, скроллим
  var isHome = (active === 'home' || active === 'games');

  var navHtml = '';

  // ── Игры ──
  var gamesHref = isHome ? '#games' : '/glavnaya#games';
  var gamesClick = isHome ? ' onclick="scrollToGames(event)"' : '';
  var gamesActive = (active === 'games' && !isHome) ? ' active' : '';
  navHtml += '<a href="' + gamesHref + '" data-key="games" class="site-header-link' + gamesActive + '" title="Игры"' + gamesClick + '>'
          +  '<span class="site-header-link-icon">🎮</span>'
          +  '<span class="site-header-link-label">Игры</span>'
          +  '</a>';

  // ── Рейтинг ──
  var rActive = (active === 'ratings') ? ' active' : '';
  navHtml += '<a href="/ratings" data-key="ratings" class="site-header-link' + rActive + '" title="Рейтинг">'
          +  '<span class="site-header-link-icon">🏆</span>'
          +  '<span class="site-header-link-label">Рейтинг</span>'
          +  '</a>';

  // ── Магазин ──
  var sActive = (active === 'shop') ? ' active' : '';
  navHtml += '<a href="/shop" data-key="shop" class="site-header-link' + sActive + '" title="Магазин">'
          +  '<span class="site-header-link-icon">🛍</span>'
          +  '<span class="site-header-link-label">Магазин</span>'
          +  '</a>';

  // ── Войти / профиль ──
  var authHtml = '';
  if (isLoggedIn){
    authHtml = '<a href="/profile" class="site-header-avatar' + (active==='profile'?' active':'') + '" title="' + (nick || 'Профиль') + '">'
             +  '<span>' + initial + '</span>'
             +  '</a>';
  } else {
    authHtml = '<a href="/auth" class="site-header-login' + (active==='auth'?' active':'') + '" title="Войти">'
             +  '<span class="site-header-login-icon">👤</span>'
             +  '<span class="site-header-login-label">Войти</span>'
             +  '</a>';
  }

  container.className = 'site-header';
  container.innerHTML =
    '<div class="site-header-inner">'
    + '<a href="' + (isHome ? '#' : '/glavnaya') + '" class="site-header-brand" id="siteBrand"' + (isHome ? ' onclick="scrollToTop(event)"' : '') + '>'
    +   '<img src="/assets/icons/logo-square.svg" alt="Лого" class="site-header-logo">'
    +   '<span class="site-header-label"><b>НИУ МГСУ</b> · Игры</span>'
    + '</a>'
    + '<nav class="site-header-nav">'
    +   navHtml
    +   '<div class="site-header-divider"></div>'
    +   authHtml
    + '</nav>'
    + '</div>';

  // На главной — включить scroll-spy (лого ↔ Игры)
  if (isHome){
    setupScrollSpy();
  }

  // Подтянуть ник если залогинен
  if (isLoggedIn && !nick){
    fetch('/api/auth/me', {headers:{'Authorization': 'Bearer ' + token}})
      .then(function(r){ return r.ok ? r.json() : null; })
      .then(function(d){
        if (d && d.user){
          localStorage.setItem('mgsu_nick', d.user.display_name);
          var av = container.querySelector('.site-header-avatar span');
          if (av) av.textContent = d.user.display_name.charAt(0).toUpperCase();
        }
      })
      .catch(function(){});
  }
}


/* ═══════════════════════════════════════════════════════════
   СКРОЛЛ-СПАЙ: шильдик ↔ игры
   Работает при прокрутке в обе стороны
   ═══════════════════════════════════════════════════════════ */
function setupScrollSpy(){
  var gamesSection = document.getElementById('games');
  var brand = document.getElementById('siteBrand');
  var gamesLink = document.querySelector('.site-header-link[data-key="games"]');
  if (!gamesSection || !brand || !gamesLink) return;

  // Сразу делаем активным бренд
  brand.classList.add('active');
  gamesLink.classList.remove('active');

  if (!('IntersectionObserver' in window)) return;

  var observer = new IntersectionObserver(function(entries){
    entries.forEach(function(entry){
      if (entry.isIntersecting){
        // Секция игр видна — активна "Игры"
        brand.classList.remove('active');
        gamesLink.classList.add('active');
      } else {
        // Секция игр ушла с экрана — активен бренд
        brand.classList.add('active');
        gamesLink.classList.remove('active');
      }
    });
  }, {
    // Срабатывает, когда секция игр появилась в центральной части экрана
    rootMargin: '-40% 0px -40% 0px',
    threshold: 0
  });

  observer.observe(gamesSection);
}


/* ═══════════════════════════════════════════════════════════
   ВСПОМОГАТЕЛЬНОЕ
   ═══════════════════════════════════════════════════════════ */
function scrollToGames(e){
  var el = document.getElementById('games');
  if (!el) return;
  if (e) e.preventDefault();
  var headerH = 60;
  var top = el.getBoundingClientRect().top + window.pageYOffset - headerH - 20;
  window.scrollTo({top: top, behavior: 'smooth'});
}

function scrollToTop(e){
  if (e) e.preventDefault();
  window.scrollTo({top: 0, behavior: 'smooth'});
}


/* ═══════════════════════════════════════════════════════════
   ФУТЕР (О проекте здесь)
   ═══════════════════════════════════════════════════════════ */
function renderSiteFooter(){
  var container = document.getElementById('siteFooter');
  if (!container) return;
  container.className = 'site-footer';
  container.innerHTML =
    '<div class="site-footer-inner">'
    + '<div class="site-footer-left">© 2026 · Не является официальным сайтом НИУ МГСУ</div>'
    + '<div class="site-footer-right">'
    +   '<a href="https://t.me/mgsu_feedback_bot" target="_blank" rel="noopener">Предложить идею</a>'
    +   '<span class="site-footer-dot">·</span>'
    +   '<a href="/privacy">О проекте</a>'
    +   '<span class="site-footer-dot">·</span>'
    +   '<a href="/privacy">Политика конфиденциальности</a>'
    +   '<span class="site-footer-dot">·</span>'
    +   '<a href="https://t.me/mgsu_wall_archive" target="_blank" rel="noopener">Telegram-канал</a>'
    + '</div>'
    + '</div>';
}


/* ═══════════════════════════════════════════════════════════
   PWA — манифест + мета-теги
   ═══════════════════════════════════════════════════════════ */
(function(){
  // 1. Манифест
  if (!document.querySelector('link[rel="manifest"]')){
    var link = document.createElement('link');
    link.rel = 'manifest';
    link.href = '/static/manifest.json';
    document.head.appendChild(link);
  }

  // 2. Мета-теги для iOS
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
    if (existing){
      existing.content = m.content;
    } else {
      var meta = document.createElement('meta');
      meta.name = m.name;
      meta.content = m.content;
      document.head.appendChild(meta);
    }
  });

  // 3. Apple touch icon
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
   FEEDBACK POPUP — показывается после 3-х игр
   ═══════════════════════════════════════════════════════════ */
(function(){
  if (window.__mgsuFeedbackInit) return;
  window.__mgsuFeedbackInit = true;

  var isGamePage = location.pathname.indexOf('/games/') === 0;
  var isHome = location.pathname === '/glavnaya' || location.pathname === '/' || location.pathname === '';

  // ─── На странице игры — считаем +1 (раз за сессию на каждую игру) ───
  if (isGamePage){
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

  // ─── На других страницах — не показываем ───
  if (!isHome) return;

  // ─── Проверки ───
  var count = 0;
  try{ count = parseInt(localStorage.getItem('mgsu_games_count') || '0', 10); }catch(e){}
  if (count < 3) return;

  try{ if (localStorage.getItem('mgsu_feedback_submitted') === '1') return; }catch(e){}

  var DISMISS_COOLDOWN = 30 * 24 * 60 * 60 * 1000; // 30 дней
  var lastDismiss = 0;
  try{ lastDismiss = parseInt(localStorage.getItem('mgsu_feedback_dismissed_at') || '0', 10); }catch(e){}
  if (lastDismiss && Date.now() - lastDismiss < DISMISS_COOLDOWN) return;

  // ─── Показываем через 4 секунды ───
  setTimeout(function(){
    if (document.getElementById('mgsuFbOverlay')) return;

    var overlay = document.createElement('div');
    overlay.className = 'mgsu-fb-overlay';
    overlay.id = 'mgsuFbOverlay';
    overlay.innerHTML =
      '<div class="mgsu-fb-card" role="dialog" aria-modal="true">' +
        '<div class="mgsu-fb-emoji">💌</div>' +
        '<h2>Как тебе игры?</h2>' +
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
        // Мигаем звёздочками — просим поставить оценку
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
        var token = localStorage.getItem('mgsu_token') || '';
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
  }, 4000);
})();
