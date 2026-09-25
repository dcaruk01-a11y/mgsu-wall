/* ===== АВТОСКРЫТИЕ ШАПКИ ПРИ СКРОЛЛЕ ===== */
(function(){
  var lastY = window.pageYOffset || 0;
  var ticking = false;

  function onScroll(){
    var y = window.pageYOffset || document.documentElement.scrollTop;
    var header = document.getElementById('siteHeader');
    if (!header){ lastY = y; ticking = false; return; }

    // У самого верха — всегда показываем
    if (y < 50){
      header.classList.remove('hidden');
      lastY = y;
      ticking = false;
      return;
    }

    // Скроллим вниз → прячем
    if (y > lastY + 4){
      header.classList.add('hidden');
    }
    // Скроллим вверх → показываем сразу
    else if (y < lastY - 4){
      header.classList.remove('hidden');
    }

    lastY = y;
    ticking = false;
  }

  window.addEventListener('scroll', function(){
    if (!ticking){
      window.requestAnimationFrame(onScroll);
      ticking = true;
    }
  }, {passive: true});

  // Следим за сменой страницы — переинициализируем при перерисовке
  var observer = new MutationObserver(function(){
    var header = document.getElementById('siteHeader');
    if (header) header.classList.remove('hidden');
  });
  document.addEventListener('DOMContentLoaded', function(){
    var header = document.getElementById('siteHeader');
    if (header){
      observer.observe(header, {childList: true, subtree: false});
    }
  });
})();


/* ===== ШАПКА ===== */
function renderSiteHeader(active, opts){
  active = active || '';
  opts = opts || {};
  var container = document.getElementById('siteHeader');
  if (!container) return;

  var token = localStorage.getItem('mgsu_token') || '';
  var isLoggedIn = !!token;
  var nick = localStorage.getItem('mgsu_nick') || '';
  var initial = nick ? nick.charAt(0).toUpperCase() : '👤';

  var navItems = [
    {key:'games',   icon:'🎮', label:'Игры',      url:'/glavnaya'},
    {key:'ratings', icon:'🏆', label:'Рейтинг',   url:'/ratings'},
    {key:'shop',    icon:'🛍', label:'Магазин',   url:'/shop'}
  ];
  if (!opts.hideAbout){
    navItems.push({key:'about', icon:'ℹ️', label:'О проекте', url:'/privacy'});
  }

  var navHtml = '';
  navItems.forEach(function(item){
    var activeCls = (item.key === active) ? ' active' : '';
    navHtml += '<a href="' + item.url + '" class="site-header-link' + activeCls + '" title="' + item.label + '">'
            +  '<span class="site-header-link-icon">' + item.icon + '</span>'
            +  '<span class="site-header-link-label">' + item.label + '</span>'
            +  '</a>';
  });

  var authHtml = '';
  if (isLoggedIn){
    authHtml = '<a href="/profile" class="site-header-avatar' + (active==='profile'?' active':'') + '" title="' + (nick || 'Профиль') + '">'
             +  '<span>' + initial + '</span>'
             +  '</a>';
  } else {
    authHtml = '<a href="/auth" class="site-header-login' + (active==='auth'?' active':'') + '">'
             +  '<span class="site-header-login-icon">👤</span>'
             +  '<span class="site-header-login-label">Войти</span>'
             +  '</a>';
  }

  container.className = 'site-header';
  container.innerHTML =
    '<div class="site-header-inner">'
    + '<a href="/glavnaya" class="site-header-brand">'
    +   '<img src="/assets/icons/logo-square.svg" alt="Лого" class="site-header-logo">'
    +   '<span class="site-header-label"><b>НИУ МГСУ</b> · Игры</span>'
    + '</a>'
    + '<nav class="site-header-nav">'
    +   navHtml
    +   '<div class="site-header-divider"></div>'
    +   authHtml
    + '</nav>'
    + '</div>';

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

/* ===== ФУТЕР ===== */
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
    +   '<a href="/privacy">Политика конфиденциальности</a>'
    +   '<span class="site-footer-dot">·</span>'
    +   '<a href="https://t.me/mgsu_wall_archive" target="_blank" rel="noopener">Telegram-канал</a>'
    + '</div>'
    + '</div>';
}


/* ===== FAVICON (шильдик вкладки, без фона) ===== */
(function(){
  // Удаляем старые иконки, если были
  document.querySelectorAll('link[rel*="icon"]').forEach(function(l){ l.remove(); });

  var links = [
    { rel: 'icon',             type: 'image/svg+xml', href: '/assets/icons/favicon.svg' },
    // Fallback для старых браузеров (можно удалить, если не нужен)
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
