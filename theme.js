// изменено 2026-09-21 17:40
// Переключатель оформления сайта: Авто / Тёмная / Светлая — как в мини-аппе бота.
// Кнопка-иконка в шапке открывает поповер с сегментом. Общий для index.html и stats.html.
// Хранение: localStorage 'budni_site_theme' = 'dark' | 'light'; ключа нет = Авто (по системе).
// Стартовую тему (анти-вспышка) выставляет инлайн-скрипт в <head> каждой страницы —
// он читает тот же ключ. Здесь — только UI и смена темы уже после загрузки.
(function () {
  var host = document.getElementById('themeMenu');
  if (!host) return;

  var KEY = 'budni_site_theme';
  var MODES = [['auto', 'Авто'], ['dark', 'Тёмная'], ['light', 'Светлая']];
  var LABEL = { auto: 'Авто', dark: 'Тёмная', light: 'Светлая' };

  // иконки — inline SVG, один стиль обводки (stroke 1.8), цвет наследуется от кнопки
  var ICONS = {
    auto: '<circle cx="12" cy="12" r="8.5"/><path d="M12 3.5v17a8.5 8.5 0 0 1 0-17z" fill="currentColor" stroke="none"/>',
    dark: '<path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z"/>',
    light: '<circle cx="12" cy="12" r="4"/><path d="M12 2.5v2.2M12 19.3v2.2M2.5 12h2.2M19.3 12h2.2M5.3 5.3l1.6 1.6M17.1 17.1l1.6 1.6M18.7 5.3l-1.6 1.6M6.9 17.1l-1.6 1.6"/>'
  };
  function svg(mode) {
    return '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" ' +
      'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + ICONS[mode] + '</svg>';
  }

  function readMode() {
    try {
      var v = localStorage.getItem(KEY);
      return (v === 'dark' || v === 'light') ? v : 'auto';
    } catch (e) { return 'auto'; }
  }
  function saveMode(m) {
    try {
      if (m === 'auto') localStorage.removeItem(KEY); else localStorage.setItem(KEY, m);
    } catch (e) {}
  }

  var mq = window.matchMedia ? matchMedia('(prefers-color-scheme: light)') : null;
  function apply(mode) {
    var scheme = mode === 'auto' ? ((mq && mq.matches) ? 'light' : 'dark') : mode;
    document.documentElement.setAttribute('data-theme', scheme);
  }

  // ---------- стили (внутри, чтобы не дублировать в двух страницах) ----------
  var css = document.createElement('style');
  css.textContent =
    '.theme-menu{ position:relative; flex:none; }' +
    '.theme-btn{ width:44px; height:44px; display:flex; align-items:center; justify-content:center; ' +
      'background:transparent; border:1px solid var(--border-soft); border-radius:10px; color:var(--ink-50); ' +
      'cursor:pointer; transition:border-color .25s var(--ease), background .25s var(--ease); }' +
    '.theme-btn:hover, .theme-btn[aria-expanded="true"]{ border-color:var(--blue-500); color:var(--blue-300); }' +
    '.theme-pop{ position:absolute; top:calc(100% + 10px); right:0; z-index:60; width:264px; padding:14px; ' +
      'background:var(--navy-800); border:1px solid var(--border-soft); border-radius:14px; ' +
      'box-shadow:0 18px 44px -18px rgba(0,0,0,.55); ' +
      'opacity:0; transform:translateY(-6px); pointer-events:none; visibility:hidden; ' +
      'transition:opacity .2s var(--ease), transform .2s var(--ease), visibility 0s linear .2s; }' +
    '.theme-pop.is-open{ opacity:1; transform:none; pointer-events:auto; visibility:visible; transition-delay:0s; }' +
    '.theme-pop-label{ font-family:"JetBrains Mono",monospace; font-size:11.5px; letter-spacing:.14em; ' +
      'text-transform:uppercase; color:var(--ink-500); margin-bottom:10px; }' +
    '.theme-seg{ display:flex; gap:4px; padding:4px; background:var(--navy-950); border-radius:10px; }' +
    '.theme-opt{ flex:1; min-height:44px; padding:0 4px; border:1px solid transparent; border-radius:8px; ' +
      'background:transparent; color:var(--ink-300); font-family:"Inter",sans-serif; font-size:13.5px; font-weight:600; ' +
      'cursor:pointer; transition:background .2s var(--ease), color .2s var(--ease); }' +
    '.theme-opt:hover{ color:var(--ink-50); }' +
    '.theme-opt.is-on{ background:var(--navy-700); border-color:var(--border-soft); color:var(--ink-50); }' +
    '.theme-btn:focus-visible, .theme-opt:focus-visible{ outline:2px solid var(--blue-400); outline-offset:2px; }' +
    '@media (max-width:560px){ .theme-menu{ position:static; } ' +
      '.theme-pop{ left:var(--gutter,16px); right:var(--gutter,16px); width:auto; top:calc(100% + 8px); } }' +
    '@media (prefers-reduced-motion: reduce){ .theme-pop{ transition:none; } }';
  document.head.appendChild(css);

  // ---------- разметка ----------
  host.classList.add('theme-menu');
  host.removeAttribute('style');
  host.innerHTML =
    '<button type="button" class="theme-btn" id="themeBtn" aria-haspopup="true" aria-expanded="false" aria-controls="themePop"></button>' +
    '<div class="theme-pop" id="themePop" role="dialog" aria-label="Оформление">' +
      '<div class="theme-pop-label">Оформление</div>' +
      '<div class="theme-seg" role="radiogroup" aria-label="Оформление">' +
        MODES.map(function (m) {
          return '<button type="button" class="theme-opt" role="radio" data-mode="' + m[0] + '">' + m[1] + '</button>';
        }).join('') +
      '</div>' +
    '</div>';

  var btn = host.querySelector('#themeBtn');
  var pop = host.querySelector('#themePop');
  var opts = host.querySelectorAll('.theme-opt');

  function refresh() {
    var mode = readMode();
    btn.innerHTML = svg(mode);
    btn.setAttribute('aria-label', 'Оформление: ' + LABEL[mode]);
    opts.forEach(function (o) {
      var on = o.getAttribute('data-mode') === mode;
      o.classList.toggle('is-on', on);
      o.setAttribute('aria-checked', on ? 'true' : 'false');
    });
  }

  function setOpen(open) {
    pop.classList.toggle('is-open', open);
    btn.setAttribute('aria-expanded', open ? 'true' : 'false');
  }

  btn.addEventListener('click', function (e) { e.stopPropagation(); setOpen(!pop.classList.contains('is-open')); });
  pop.addEventListener('click', function (e) { e.stopPropagation(); });
  document.addEventListener('click', function () { setOpen(false); });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && pop.classList.contains('is-open')) { setOpen(false); btn.focus(); }
  });

  opts.forEach(function (o) {
    o.addEventListener('click', function () {
      var mode = o.getAttribute('data-mode');
      saveMode(mode); apply(mode); refresh();
    });
  });

  // в режиме «Авто» следуем за системой вживую
  if (mq) {
    var onSys = function () { if (readMode() === 'auto') apply('auto'); };
    if (mq.addEventListener) mq.addEventListener('change', onSys); else if (mq.addListener) mq.addListener(onSys);
  }

  refresh();
})();
