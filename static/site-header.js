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

  // ── Игры (на главной — скролл к секции) ──
  var gamesHref = isHome ? '#games' : '/glavnaya#games';
  var gamesClick = isHome ? ' onclick="scrollToGames(event)"' : '';
  navHtml += '<a href="' + gamesHref + '" data-key="games" class="site-header-link" title="Игры"' + gamesClick + '>'
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
   ═══════════════════════════════════════════════════════════ */
function setupScrollSpy(){
  var gamesSection = document.getElementById('games');
  var brand = document.getElementById('siteBrand');
  var gamesLink = document.querySelector('.site-header-link[data-key="games"]');
  if (!gamesSection || !brand || !gamesLink) return;

  brand.classList.add('active');
  gamesLink.classList.remove('active');

  if (!('IntersectionObserver' in window)) return;

  var observer = new IntersectionObserver(function(entries){
    entries.forEach(function(entry){
      if (entry.isIntersecting){
        brand.classList.remove('active');
        gamesLink.classList.add('active');
      } else {
        brand.classList.add('active');
        gamesLink.classList.remove('active');
      }
    });
  }, {
    rootMargin: '-80px 0px -40% 0px',
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
   ФУТЕР (О проекте переехал сюда)
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
   FAVICON
   ═══════════════════════════════════════════════════════════ */
(function(){
  document.querySelectorAll('link[rel*="icon"]').forEach(function(l){ l.remove(); });
  var links = [
    { rel: 'icon',             type: 'image/svg+xml', href: '/assets/icons/favicon.svg' },
    { rel: 'alternate icon',   type: 'image/png',     href: '/assets/icons/favicon.svg' },
    { rel: 'apple-touch-icon',                        href: '/assets/icons/favicon.svg' },
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
