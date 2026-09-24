/* Общее меню для всех страниц админки */
function renderAdminMenu(active){
  const items = [
    {key:'dashboard', label:'📊 Дашборд', url:'/admin'},
    {key:'users',     label:'👥 Пользователи', url:'/admin/users'},
    {key:'games',     label:'🎮 Игры', url:'/admin/games'},
    {key:'content',   label:'📅 Контент-план', url:'/admin/content'},
    {key:'analytics', label:'📈 Аналитика', url:'/admin/analytics'},
    {key:'design',    label:'🎨 Дизайн', url:'/admin/design'},
    {key:'team',      label:'💼 Команда', url:'/admin/team'},
    {key:'schedule',  label:'⏰ Расписание', url:'/admin/schedule'},
    {key:'system',    label:'🖥 Система', url:'/admin/system'},
    {key:'links',     label:'🔗 Ссылки', url:'/admin/links'},
    {key:'todo',      label:'📝 Задачи', url:'/admin/todo'},
  ];

  let html = '<nav class="admin-menu">';
  html += '<div class="admin-menu-title">Админка МГСУ</div>';
  items.forEach(it => {
    const cls = (it.key === active) ? 'admin-menu-item active' : 'admin-menu-item';
    html += '<a href="' + it.url + '" class="' + cls + '">' + it.label + '</a>';
  });
  html += '<div class="admin-menu-footer">';
  html += '<a href="/glavnaya" target="_blank" class="admin-menu-item">🌐 Открыть сайт</a>';
  html += '<a href="#" id="adminLogoutBtn" class="admin-menu-item admin-menu-logout">🚪 Выйти</a>';
  html += '</div>';
  html += '</nav>';

  const container = document.getElementById('adminMenuContainer');
  if (container) container.innerHTML = html;

  const logoutBtn = document.getElementById('adminLogoutBtn');
  if (logoutBtn){
    logoutBtn.addEventListener('click', async (e) => {
      e.preventDefault();
      const token = localStorage.getItem('mgsu_admin_token') || '';
      try{
        await fetch('/admin/api/logout', {
          method:'POST',
          headers: {'Authorization': 'Bearer ' + token}
        });
      }catch(err){}
      localStorage.removeItem('mgsu_admin_token');
      location.href = '/admin/login';
    });
  }
}

/* Общая проверка авторизации */
function adminRequireToken(){
  const token = localStorage.getItem('mgsu_admin_token');
  if (!token) location.href = '/admin/login';
  return token;
}

/* Общий api с токеном */
async function adminApi(path, opts = {}){
  const token = localStorage.getItem('mgsu_admin_token') || '';
  const headers = Object.assign({'Content-Type':'application/json'}, opts.headers || {});
  if (token) headers['Authorization'] = 'Bearer ' + token;
  const res = await fetch(path, Object.assign({}, opts, {headers}));
  if (res.status === 401){
    localStorage.removeItem('mgsu_admin_token');
    location.href = '/admin/login';
    throw new Error('unauthorized');
  }
  if (!res.ok) throw new Error('HTTP ' + res.status + ' для ' + path);
  return res.json();
}
