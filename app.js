// изменено 2026-09-20 02:10
// ============================================================
// Будни_BY — общий рантайм для client.html и admin.html.
// Грузится ПОСЛЕ https://telegram.org/js/telegram-web-app.js и инлайн-скрипта
// установки темы в <head>, но ДО фиче-модулей (deck.js, admin-*.js и т.д.).
//
// Namespace плоский, без IIFE и без сборщиков (конвенция студии) — все
// объявления ниже становятся глобальными и доступны каждому модулю.
// Экспортирует: tg, telegramUser, APPS_SCRIPT_URL, SECTORS, SECTOR_LIST,
// haptic, applyTelegramTheme, initTelegram, alertAsync, confirmAsync,
// escapeHtml, apiCall, bindPhoneMask, formatPhoneTail.
// ============================================================

var tg = window.Telegram ? window.Telegram.WebApp : null;

// ---------- личные настройки посетителя (тема + вибрация), localStorage ----------
// Тема: '' = как в Telegram/системе, 'light'/'dark' = ручной оверрайд.
// Синхронно применяется и в инлайн-скрипте <head> (анти-вспышка) — там своя копия
// логики чтения budni_prefs.theme.
var PREFS = { theme: '', haptics: true };
try {
  var _prefs = JSON.parse(localStorage.getItem('budni_prefs') || '{}');
  PREFS.theme = (_prefs.theme === 'light' || _prefs.theme === 'dark') ? _prefs.theme : '';
  PREFS.haptics = _prefs.haptics !== false;
} catch (e) {}

function savePrefs() {
  try { localStorage.setItem('budni_prefs', JSON.stringify(PREFS)); } catch (e) {}
}

function resolveScheme() {
  if (PREFS.theme) return PREFS.theme;
  return (tg && tg.colorScheme) ? tg.colorScheme
    : (matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark');
}

// ВСТАВЬ реальный URL деплоя Apps Script (тот же, что BUDNI_APPS_SCRIPT_URL).
// Одно место на оба мини-аппа — раньше дублировалось в двух HTML.
var APPS_SCRIPT_URL = 'https://budni.tg-studio.xyz/exec';

// сферы — синхронизировано с SECTORS в structurer.py и SECTOR_BUCKETS в Apps Script
var SECTORS = [
  ['Производство и строительство', '🏗️'], ['Транспорт и логистика', '🚚'],
  ['Торговля и услуги', '🛍️'], ['Гостиничный и ресторанный бизнес', '🏨'],
  ['Сельское хозяйство', '🌾'], ['Здравоохранение', '🏥'], ['Образование', '🎓'],
  ['Финансы и бухгалтерия', '📊'], ['IT и разработка', '💻'], ['Охрана и безопасность', '🛡️'],
  ['Офис и администрирование', '🗃️'], ['Клининг и уборка', '🧹'], ['Другое', '🗂️'],
];
var SECTOR_LIST = SECTORS.map(function (s) { return s[0]; });

function haptic(style) {
  if (!PREFS.haptics) return; // выключено в настройках
  if (tg && tg.HapticFeedback) {
    if (['success', 'error', 'warning'].includes(style)) tg.HapticFeedback.notificationOccurred(style);
    else tg.HapticFeedback.impactOccurred(style || 'light');
  }
}

function applyTelegramTheme() {
  const scheme = resolveScheme();
  document.documentElement.setAttribute('data-theme', scheme);
  if (tg) {
    const s = getComputedStyle(document.documentElement);
    try { tg.setHeaderColor(s.getPropertyValue('--surface').trim()); tg.setBackgroundColor(s.getPropertyValue('--bg').trim()); } catch (e) {}
  }
}

// Промис-обёртка над showAlert — внутри Telegram нативный алерт, window.alert
// только как фолбэк вне Telegram. Не звать window.alert напрямую в модулях.
function alertAsync(message) {
  return new Promise((resolve) => {
    if (tg && tg.showAlert && tg.isVersionAtLeast && tg.isVersionAtLeast('6.2')) {
      try { tg.showAlert(message, resolve); return; } catch (e) {}
    }
    window.alert(message); resolve();
  });
}

// То же для confirm.
function confirmAsync(message) {
  return new Promise((resolve) => {
    if (tg && tg.showConfirm && tg.isVersionAtLeast && tg.isVersionAtLeast('6.2')) {
      try { tg.showConfirm(message, resolve); return; } catch (e) {}
    }
    resolve(window.confirm(message));
  });
}

function initTelegram() {
  if (!tg) return;
  tg.ready(); tg.expand();
  applyTelegramTheme();
  tg.onEvent && tg.onEvent('themeChanged', applyTelegramTheme);
  if (tg.isVersionAtLeast && tg.isVersionAtLeast('7.7')) { try { tg.disableVerticalSwipes(); } catch (e) {} }
}

function escapeHtml(str) {
  return String(str || '').replace(/[&<>"']/g, function (c) {
    return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
  });
}

// ---------- пользователь: реальный Telegram ID, либо демо-id для теста вне Telegram ----------
function getOrCreateDemoUser() {
  let id = localStorage.getItem('budni_demo_id');
  if (!id) { id = 'demo-' + Math.random().toString(36).slice(2, 10); localStorage.setItem('budni_demo_id', id); }
  return { id: id, username: 'гость' };
}
var telegramUser = (tg && tg.initDataUnsafe && tg.initDataUnsafe.user) ? tg.initDataUnsafe.user : getOrCreateDemoUser();

// Низкоуровневый POST на Apps Script. client.html и admin.html оборачивают
// его в свой apiPost со своей авторизацией (initData у клиента, token у
// админки) — без явного Content-Type, иначе браузер шлёт preflight OPTIONS,
// который Apps Script веб-апп не обрабатывает.
// extraHeaders — необязательный (админка передаёт X-Admin-Token сюда, а не
// в query/body — не оседает в логах туннеля/истории браузера). Клиентский
// apiPost его не передаёт: без лишних заголовков нет CORS-preflight на
// каждый запрос ленты — там трафик выше и важна скорость.
async function apiCall(payload, extraHeaders) {
  const res = await fetch(APPS_SCRIPT_URL, {
    method: 'POST',
    headers: extraHeaders,
    body: JSON.stringify(payload),
  });
  return res.json();
}

// ---------- маска телефона +375 XX-XXX-XX-XX ----------
function bindPhoneMask(el) {
  el.addEventListener('input', function () {
    const digits = el.value.replace(/\D/g, '').slice(0, 9);
    let out = digits;
    if (digits.length > 2) out = digits.slice(0, 2) + '-' + digits.slice(2);
    if (digits.length > 5) out = digits.slice(0, 2) + '-' + digits.slice(2, 5) + '-' + digits.slice(5);
    if (digits.length > 7) out = digits.slice(0, 2) + '-' + digits.slice(2, 5) + '-' + digits.slice(5, 7) + '-' + digits.slice(7);
    el.value = out;
  });
}

// 9 цифр (или строка с мусором/префиксом) -> "XX-XXX-XX-XX", иначе '' .
function formatPhoneTail(value) {
  let d = String(value || '').replace(/\D/g, '');
  if (d.length > 9 && d.slice(0, 3) === '375') d = d.slice(3);
  d = d.slice(-9);
  if (d.length !== 9) return '';
  return d.slice(0, 2) + '-' + d.slice(2, 5) + '-' + d.slice(5, 7) + '-' + d.slice(7);
}

// tel:-ссылка из телефона (для «позвонить» по тапу)
function telHref(phone) {
  // в поле может быть несколько номеров через ", " (db.pg.norm_phone) —
  // на звонок берём только первый, иначе после чистки не-цифр они склеятся
  // в один невалидный номер
  const first = String(phone || '').split(',')[0];
  const d = first.replace(/[^\d+]/g, '');
  if (d.replace(/\D/g, '').length < 6) return '';
  return d[0] === '+' ? d : '+' + d;
}

// ---------- дата рождения / возраст ----------
var RU_MONTHS_GEN = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
  'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'];

function ageFromISO(iso) {
  const m = String(iso || '').match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!m) return null;
  const b = new Date(+m[1], +m[2] - 1, +m[3]);
  const n = new Date();
  let a = n.getFullYear() - b.getFullYear();
  if (n.getMonth() < b.getMonth() || (n.getMonth() === b.getMonth() && n.getDate() < b.getDate())) a--;
  return (a >= 14 && a <= 80) ? a : null;
}

function plYears(n) {
  const d10 = n % 10, d100 = n % 100;
  if (d10 === 1 && d100 !== 11) return n + ' год';
  if (d10 >= 2 && d10 <= 4 && (d100 < 12 || d100 > 14)) return n + ' года';
  return n + ' лет';
}

function fmtBirth(iso) {
  const m = String(iso || '').match(/^(\d{4})-(\d{2})-(\d{2})/);
  return m ? (+m[3]) + ' ' + RU_MONTHS_GEN[+m[2] - 1] + ' ' + m[1] : '';
}

// поделиться текстом через штатный share-лист Telegram. Ссылка на бота
// идёт ТОЛЬКО через url= — сама превью-карточка сверху сообщения это
// стандартное поведение Telegram для t.me-ссылки в тексте, от места в
// строке не зависит (пробовали text=-only с футером внизу — ссылка
// всё равно всплывала наверх, только вдобавок дублировалась). Свой футер
// в text= не добавляем — иначе будет два упоминания ссылки на одно превью.
function shareText(text) {
  const url = 'https://t.me/share/url?url=' + encodeURIComponent('https://t.me/Budni_BY_Bot') +
    '&text=' + encodeURIComponent(String(text || '').slice(0, 3500));
  if (tg && tg.openTelegramLink) { try { tg.openTelegramLink(url); return; } catch (e) {} }
  window.open(url, '_blank');
}
