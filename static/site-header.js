/**
 * Единая шапка сайта.
 * Использование на странице:
 *   <link rel="stylesheet" href="/static/site-header.css">
 *   <div id="siteHeader"></div>
 *   ...
 *   <script src="/static/site-header.js"></script>
 *   <script>renderSiteHeader('glavnaya');</script>
 *
 * active: 'games' | 'ratings' | 'shop' | 'profile' | 'auth' | ''
 */
function renderSiteHeader(active){
  active = active || '';
  var container = document.getElementById('siteHeader');
  if (!container) return;

  var token = localStorage.getItem('mgsu_token') || '';
  var isLoggedIn = !!token;
  var nick = localStorage.getItem('mgsu_nick') || '';
  var initial = nick ? nick.charAt(0).toUpperCase() : '👤';

  // Навигационные ссылки
  var navItems = [
    {key:'games',   icon:'🎮', label:'Игры',    url:'/glavnaya'},
    {key:'ratings', icon:'🏆', label:'Рейтинг', url:'/ratings'},
    {key:'shop',    icon:'🛍', label:'Магазин', url:'/shop'}
  ];

  var navHtml = '';
  navItems.forEach(function(item){
    var activeCls = (item.key === active) ? ' active' : '';
    navHtml += '<a href="' + item.url + '" class="site-header-link' + activeCls + '" title="' + item.label + '">'
            +  '<span class="site-header-link-icon">' + item.icon + '</span>'
            +  '<span class="site-header-link-label">' + item.label + '</span>'
            +  '</a>';
  });

  // Профиль / войти
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
    +   '<img src="/assets/Logo/logo.svg" alt="Лого" class="site-header-logo">'
    +   '<span class="site-header-label"><b>НИУ МГСУ</b> · Игры</span>'
    + '</a>'
    + '<nav class="site-header-nav">'
    +   navHtml
    +   '<div class="site-header-divider"></div>'
    +   authHtml
    + '</nav>'
    + '</div>';

  // Если залогинен, но ник не в кэше — подгружаем
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


/* Автосохранение ника в localStorage при логине */
(function(){
  // Ловим момент, когда ник попадёт в localStorage вручную через другие страницы
  var observer = setInterval(function(){
    var token = localStorage.getItem('mgsu_token');
    var nick = localStorage.getItem('mgsu_nick');
    if (!token){
      // если разлогинились — чистим ник
      if (nick) localStorage.removeItem('mgsu_nick');
      return;
    }
    if (nick) return;
    // Подгружаем ник
    fetch('/api/auth/me', {headers:{'Authorization': 'Bearer ' + token}})
      .then(function(r){ return r.ok ? r.json() : null; })
      .then(function(d){
        if (d && d.user){
          localStorage.setItem('mgsu_nick', d.user.display_name);
          // Обновляем аватар, если он есть в DOM
          var av = document.querySelector('.site-header-avatar span');
          if (av) av.textContent = d.user.display_name.charAt(0).toUpperCase();
          clearInterval(observer);
        }
      })
      .catch(function(){});
  }, 1500);
})();


/* Рендер единого футера */
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
