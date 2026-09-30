#!/usr/bin/env python3
# изменено 2026-09-30 19:50
"""
Генератор SEO-страниц «работа по профессии и городу» для budni-by.site.

  python3 _tools/gen_seo.py _tools/data.json

Вход — JSON из _tools/export.sql (живые вакансии БЕЗ контактов, копии уже схлопнуты).
Выход (в корень репо): rabota/index.html, rabota/<город>/index.html,
rabota/<город>/<профессия>/index.html, sitemap.xml (+ блок в llms.txt).
Только стандартная библиотека. Идемпотентно: перед генерацией папка rabota/ пересоздаётся
содержимым заново (старые страницы, у которых не набралось вакансий, исчезают).

Правила качества (чтобы не плодить «тонкие» страницы):
  • страница «город × профессия» — только если в ней >= MIN_PAGE живых вакансий;
  • в тексте нет телефонов/@username/ссылок — контакты только в боте (это и воронка, и приватность);
  • все данные — реальные, из базы; никаких выдуманных цифр.
"""
import html
import json
import os
import re
import shutil
import statistics
import sys
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://budni-by.site"
BOT = "https://t.me/Budni_BY_Bot"
MIN_PAGE = 5          # минимум вакансий на страницу «город × профессия»
MIN_HUB = 10          # минимум вакансий на страницу города
FRESH_DAYS = 45       # старше — в страницы не берём (в базе живут до 60 дней)
MINSK_TZ = timezone(timedelta(hours=3))
MONTHS = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа",
          "сентября", "октября", "ноября", "декабря"]

# ── города: (slug, «в …» — предложный падеж). Только эти города получают страницы. ──
CITIES = {
    "Минск": ("minsk", "в Минске"), "Брест": ("brest", "в Бресте"), "Витебск": ("vitebsk", "в Витебске"),
    "Гродно": ("grodno", "в Гродно"), "Гомель": ("gomel", "в Гомеле"), "Могилёв": ("mogilev", "в Могилёве"),
    "Солигорск": ("soligorsk", "в Солигорске"), "Дзержинск": ("dzerzhinsk", "в Дзержинске"),
    "Борисов": ("borisov", "в Борисове"), "Бобруйск": ("bobrujsk", "в Бобруйске"),
    "Барановичи": ("baranovichi", "в Барановичах"), "Орша": ("orsha", "в Орше"), "Пинск": ("pinsk", "в Пинске"),
    "Мозырь": ("mozyr", "в Мозыре"), "Лида": ("lida", "в Лиде"), "Молодечно": ("molodechno", "в Молодечно"),
    "Полоцк": ("polotsk", "в Полоцке"), "Новополоцк": ("novopolotsk", "в Новополоцке"),
    "Жодино": ("zhodino", "в Жодино"), "Слуцк": ("slutsk", "в Слуцке"), "Жлобин": ("zhlobin", "в Жлобине"),
    "Слоним": ("slonim", "в Слониме"), "Светлогорск": ("svetlogorsk", "в Светлогорске"),
    "Кобрин": ("kobrin", "в Кобрине"), "Речица": ("rechitsa", "в Речице"),
    "Волковыск": ("volkovysk", "в Волковыске"), "Сморгонь": ("smorgon", "в Сморгони"),
    "Смолевичи": ("smolevichi", "в Смолевичах"), "Заславль": ("zaslavl", "в Заславле"),
    "Боровляны": ("borovlyany", "в Боровлянах"), "Колодищи": ("kolodishchi", "в Колодищах"),
    "Фаниполь": ("fanipol", "в Фаниполе"), "Жабинка": ("zhabinka", "в Жабинке"),
    "Калинковичи": ("kalinkovichi", "в Калинковичах"), "Горки": ("gorki", "в Горках"),
    "Осиповичи": ("osipovichi", "в Осиповичах"),
}
# районы самого Минска — в страницу «Минск» (держать в паре с MINSK_DISTRICTS в api/format.py)
MINSK_DISTRICTS = {"шабаны", "уручье", "каменная горка", "лошица", "сухарево", "копище", "колядичи", "чижовка", "зелёный луг", "зеленый луг"}


def key(s: str) -> str:
    return (s or "").strip().lower().replace("ё", "е")


CITY_BY_KEY = {key(n): n for n in CITIES}

# ── профессии: (slug, название, «вакансии …» род.п., «работа …» твор.п., regex по должности) ──
PROFS = [
    ("voditel-mezhdunarodnik", "Водитель-международник", "водителя-международника", "водителем-международником", r"международ"),
    ("voditel-taksi", "Водитель такси", "водителя такси", "водителем такси", r"такси"),
    ("voditel", "Водитель", "водителя", "водителем", r"водител"),
    ("gruzchik", "Грузчик", "грузчика", "грузчиком", r"грузчик|разгрузчик"),
    ("prodavec", "Продавец", "продавца", "продавцом", r"продав"),
    ("kassir", "Кассир", "кассира", "кассиром", r"кассир"),
    ("povar", "Повар", "повара", "поваром", r"повар|сушист|пиццер|шаурм"),
    ("pekar-konditer", "Пекарь, кондитер", "пекаря и кондитера", "пекарем или кондитером", r"кондитер|пекар"),
    ("uborshchik", "Уборщик, уборщица", "уборщика и уборщицы", "уборщиком или уборщицей", r"уборщ|клинер|уборк|хозяюшк|хозяйк"),
    ("dvornik", "Дворник", "дворника", "дворником", r"дворник"),
    ("podsobnyj-rabochij", "Подсобный рабочий", "подсобного рабочего", "подсобным рабочим", r"подсобн|разнорабоч"),
    ("komplektovshchik", "Комплектовщик", "комплектовщика", "комплектовщиком", r"комплектовщ|сборщик заказ"),
    ("kladovshchik", "Кладовщик", "кладовщика", "кладовщиком", r"кладовщик|работник склада"),
    ("buhgalter", "Бухгалтер", "бухгалтера", "бухгалтером", r"бухгалтер"),
    ("menedzher-po-prodazham", "Менеджер по продажам", "менеджера по продажам", "менеджером по продажам", r"менеджер по продаж|специалист по продаж|торговый представ"),
    ("menedzher", "Менеджер", "менеджера", "менеджером", r"менеджер"),
    ("administrator", "Администратор", "администратора", "администратором", r"администратор"),
    ("oficiant", "Официант", "официанта", "официантом", r"официант"),
    ("barmen-barista", "Бармен, бариста", "бармена и бариста", "барменом или бариста", r"бармен|бариста|хостес"),
    ("kurer", "Курьер", "курьера", "курьером", r"курьер"),
    ("ohrannik", "Охранник, сторож", "охранника и сторожа", "охранником или сторожем", r"охранн|сторож"),
    ("svarshchik", "Сварщик", "сварщика", "сварщиком", r"свар"),
    ("avtoslesar", "Автослесарь, автомеханик", "автослесаря и автомеханика", "автослесарем или автомехаником", r"автослесар|автомеханик|автоэлектрик|шиномонтаж|автомойщик|мойщик автомоб|автомаляр"),
    ("slesar", "Слесарь", "слесаря", "слесарем", r"слесар"),
    ("elektrik", "Электромонтёр, электрик", "электромонтёра и электрика", "электромонтёром или электриком", r"электромонтер|электромонтаж|электрик"),
    ("otdelochnik", "Отделочник, маляр, штукатур", "отделочника, маляра и штукатура", "отделочником, маляром или штукатуром", r"отделочник|маляр|штукатур|плиточник|фасадчик|облицовщик"),
    ("stroitel", "Каменщик, бетонщик, плотник", "каменщика, бетонщика и плотника", "каменщиком, бетонщиком или плотником", r"каменщик|бетонщик|арматурщик|плотник|кровельщик|строител"),
    ("montazhnik", "Монтажник", "монтажника", "монтажником", r"монтажник"),
    ("mashinist", "Машинист, тракторист", "машиниста и тракториста", "машинистом или трактористом", r"тракторист|машинист|экскаватор"),
    ("master-prorab", "Мастер, прораб", "мастера и прораба", "мастером или прорабом", r"прораб|мастер участка|мастер смены|мастер цеха|мастер производ|мастер общестро|мастер строит"),
    ("inzhener", "Инженер", "инженера", "инженером", r"инженер"),
    ("shveya", "Швея", "швеи", "швеёй", r"швея|портной|закройщ"),
    ("upakovshchik", "Упаковщик, фасовщик", "упаковщика и фасовщика", "упаковщиком или фасовщиком", r"упаков|фасов|укладчик"),
    ("sborshchik", "Сборщик", "сборщика", "сборщиком", r"сборщик"),
    ("stanochnik", "Станочник, токарь", "станочника и токаря", "станочником или токарем", r"станочник|токар|фрезеровщ"),
    ("operator", "Оператор", "оператора", "оператором", r"оператор"),
    ("medik", "Медицинский работник", "медицинского работника", "медицинским работником", r"санитар|медицинск|медсестр|врач|фельдшер|ветеринар"),
    ("pedagog", "Воспитатель, учитель", "воспитателя и учителя", "воспитателем или учителем", r"воспитател|учител|педагог"),
    ("parikmakher", "Парикмахер, мастер маникюра", "парикмахера и мастера маникюра", "парикмахером или мастером маникюра", r"парикмахер|маникюр|мастер ногтев|массажист"),
    ("kuhonnyj-rabochij", "Кухонный рабочий, мойщик посуды", "кухонного рабочего и мойщика посуды", "кухонным рабочим или мойщиком посуды", r"кухонн|посуд"),
]
PROF_RE = [(p, re.compile(p[4])) for p in PROFS]
PROF_BY_SLUG = {p[0]: p for p in PROFS}

CONTACT_RE = re.compile(r"(https?://\S+|t\.me/\S+|@\w{3,}|[\w.+-]+@[\w-]+\.\w+|\+?\d[\d\s()\-]{7,}\d)", re.I)


def junk_position(position: str) -> bool:
    """Списки должностей от кадровых агентств («Грузчик, Комплектовщик, Уборщица, …») и
    слишком длинные заголовки — в SEO-страницы не берём: там нет одной профессии."""
    p = position or ""
    return p.count(",") >= 2 or p.count("/") >= 2 or len(p) > 80


def classify(position: str):
    k = key((position or "").split(",")[0])
    for p, rx in PROF_RE:
        if rx.search(k):
            return p[0]
    return None


def clean(text: str, limit: int) -> str:
    t = CONTACT_RE.sub("", text or "")
    t = re.sub(r"\s+", " ", t).strip(" ,;:-–—·")
    if len(t) > limit:
        t = t[:limit].rsplit(" ", 1)[0].rstrip(" ,;:-–—·") + "…"
    return t


def plural(n: int, one: str, few: str, many: str) -> str:
    n = abs(n)
    if n % 10 == 1 and n % 100 != 11:
        return one
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return few
    return many


def vac_word(n: int) -> str:
    return f"{n} {plural(n, 'вакансия', 'вакансии', 'вакансий')}"


def esc(s) -> str:
    return html.escape(str(s or ""), quote=True)


def fmt_date(iso: str, today: datetime) -> str:
    try:
        d = datetime.fromisoformat(iso).astimezone(MINSK_TZ)
    except Exception:
        return ""
    days = (today.date() - d.date()).days
    if days <= 0:
        return "сегодня"
    if days == 1:
        return "вчера"
    return f"{d.day} {MONTHS[d.month - 1]}" + (f" {d.year}" if d.year != today.year else "")


def salary_hint(items: list):
    vals = sorted(float(v["salary_amount"]) for v in items
                  if v.get("salary_amount") and (v.get("salary_currency") or "").upper() == "BYN"
                  and 300 <= float(v["salary_amount"]) <= 15000)
    if len(vals) < 5:
        return None
    q = statistics.quantiles(vals, n=4)
    lo, hi = round(q[0] / 50) * 50, round(q[2] / 50) * 50
    if lo == hi:
        return None
    return f"обычно от {lo} до {hi} BYN", len(vals)


# ───────────────────────────── HTML ─────────────────────────────

def head(title: str, desc: str, path: str, extra_ld: str = "") -> str:
    url = f"{SITE}{path}"
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<meta name="robots" content="index, follow">
<link rel="canonical" href="{url}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Будни_BY">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:url" content="{url}">
<meta property="og:locale" content="ru_RU">
<meta property="og:image" content="{SITE}/og-image.png">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Crect width='100' height='100' rx='22' fill='%232AABEE'/%3E%3Ctext x='50' y='68' font-size='58' text-anchor='middle' fill='white' font-family='sans-serif'%3E%D0%91%3C/text%3E%3C/svg%3E">
{extra_ld}<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Chakra+Petch:wght@500;600;700&family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/seo.css?v=20260930">
<script>
(function () {{
  var saved = null;
  try {{ saved = localStorage.getItem('budni_site_theme'); }} catch (e) {{}}
  var theme = (saved === 'light' || saved === 'dark') ? saved
    : (matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark');
  document.documentElement.setAttribute('data-theme', theme);
}})();
</script>
</head>
<body>
<header id="siteHeader">
  <div class="wrap nav">
    <a class="brand" href="/">
      <span class="brand-mark">Б</span>
      <span class="brand-name">Будни_BY<span>ВАКАНСИИ В БЕЛАРУСИ</span></span>
    </a>
    <div class="nav-right">
      <div id="themeMenu" style="width:44px;height:44px"></div>
      <a class="btn btn-primary btn-sm" href="{BOT}?startapp=src_seo_header" target="_blank" rel="noopener">Открыть бота</a>
    </div>
  </div>
</header>
<main class="wrap page">
"""


def foot() -> str:
    return f"""</main>
<footer>
  <div class="wrap footer-inner">
    <a class="brand" href="/">
      <span class="brand-mark">Б</span>
      <span class="brand-name">Будни_BY</span>
    </a>
    <div class="footer-links">
      <a href="/rabota/">Вакансии по городам</a>
      <a href="{BOT}" target="_blank" rel="noopener">Бот</a>
      <a href="https://t.me/Budni_BY_Group" target="_blank" rel="noopener">Группа</a>
      <a href="https://t.me/Budni_BY" target="_blank" rel="noopener">Канал</a>
      <a href="/stats.html">Статистика</a>
    </div>
    <p class="footer-note">Будни_BY — независимый агрегатор вакансий, не государственный сервис. Объявления собираются из открытых источников; контакты работодателя — в боте.</p>
  </div>
</footer>
<script src="/theme.js?v=20260921a"></script>
</body>
</html>
"""


def crumbs(items: list) -> str:
    """items: [(название, путь или None)] — видимые крошки + BreadcrumbList JSON-LD."""
    vis = " <span aria-hidden=\"true\">/</span> ".join(
        f'<a href="{esc(u)}">{esc(t)}</a>' if u else f"<span>{esc(t)}</span>" for t, u in items)
    return f'<nav class="crumbs" aria-label="Навигация">{vis}</nav>\n'


def crumbs_ld(items: list) -> str:
    els = [{"@type": "ListItem", "position": i + 1, "name": t, **({"item": SITE + u} if u else {})}
           for i, (t, u) in enumerate(items)]
    data = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": els}
    return '<script type="application/ld+json">\n' + json.dumps(data, ensure_ascii=False) + "\n</script>\n"


def vac_card(v: dict, today: datetime) -> str:
    meta = [x for x in (clean(v.get("company"), 60), clean(v.get("salary_text"), 70) or None) if x]
    date = fmt_date(v["last_seen_at"], today)
    bits = []
    if v.get("schedule"):
        bits.append(clean(v["schedule"], 90))
    duties = [clean(d, 90) for d in (v.get("duties") or [])[:2] if clean(d, 90)]
    if duties:
        bits.append("; ".join(duties))
    tags = []
    if v.get("no_experience"):
        tags.append('<span class="tag">без опыта</span>')
    if v.get("employment_type") == "подработка":
        tags.append('<span class="tag">подработка</span>')
    return (
        '<li class="vac"><div class="vac-top">'
        f'<h3>{esc(clean(v["position"], 90))}</h3>'
        f'<time class="vac-date" datetime="{esc(v["last_seen_at"][:10])}">{esc(date)}</time></div>'
        + (f'<p class="vac-meta">{esc(" · ".join(meta))}</p>' if meta else "")
        + (f'<p class="vac-text">{esc(" — ".join(b for b in bits if b))}</p>' if bits else "")
        + (f'<div class="tags">{"".join(tags)}</div>' if tags else "")
        + "</li>\n"
    )


def cta(text: str, src: str) -> str:
    return (f'<div class="cta-band"><div><strong>{esc(text)}</strong>'
            '<span>Контакты работодателей и свайп-подбор — в боте Telegram. Бесплатно, без регистрации.</span></div>'
            f'<a class="btn btn-primary" href="{BOT}?startapp={esc(src)}" target="_blank" rel="noopener">Смотреть в Telegram</a></div>\n')


def write(path: str, content: str) -> None:
    full = os.path.join(ROOT, path.lstrip("/"))
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        f.write(content)


# ───────────────────────────── сборка ─────────────────────────────

def main(data_path: str) -> None:
    today = datetime.now(MINSK_TZ)
    rows = json.load(open(data_path, encoding="utf-8")) or []
    horizon = today - timedelta(days=FRESH_DAYS)

    # (город, профессия) -> вакансии; город -> все вакансии
    by_city: dict[str, list] = {}
    by_pair: dict[tuple, list] = {}
    for v in rows:
        try:
            if datetime.fromisoformat(v["last_seen_at"]).astimezone(MINSK_TZ) < horizon:
                continue
        except Exception:
            continue
        if junk_position(v.get("position")):
            continue
        ck = key(v.get("city"))
        city = "Минск" if ck in MINSK_DISTRICTS else CITY_BY_KEY.get(ck)
        if not city:
            continue
        prof = classify(v.get("position"))
        v["_prof"] = prof
        by_city.setdefault(city, []).append(v)
        if prof:
            by_pair.setdefault((city, prof), []).append(v)
    for lst in list(by_city.values()) + list(by_pair.values()):
        lst.sort(key=lambda x: x["last_seen_at"], reverse=True)

    out_dir = os.path.join(ROOT, "rabota")
    if os.path.isdir(out_dir):
        shutil.rmtree(out_dir)

    pages: list[tuple] = []   # (путь, lastmod, приоритет)
    lastmod = today.strftime("%Y-%m-%d")

    hub_cities = [c for c in CITIES if len(by_city.get(c, [])) >= MIN_HUB]
    pair_pages = {(c, p) for (c, p), lst in by_pair.items() if len(lst) >= MIN_PAGE and c in hub_cities}

    # ── страницы «город × профессия» ──
    for (city, pslug) in sorted(pair_pages):
        cslug, loc = CITIES[city]
        _, pname, pgen, pinstr, _ = PROF_BY_SLUG[pslug]
        items = by_pair[(city, pslug)]
        n = len(items)
        path = f"/rabota/{cslug}/{pslug}/"
        h1 = f"Работа {pinstr} {loc}"
        title = f"Работа {pinstr} {loc} — {vac_word(n)} | Будни_BY"
        noexp = sum(1 for v in items if v.get("no_experience"))
        sal = salary_hint(items)
        companies = []
        for v in items:
            c = clean(v.get("company"), 40)
            if c and c not in companies:
                companies.append(c)
        desc = (f"Вакансии {pgen} {loc}: {vac_word(n)}"
                + (f", {noexp} без опыта" if noexp else "")
                + (f"; зарплата {sal[0]}" if sal else "")
                + ". Актуальные объявления обновляются каждый день, отклик — в Telegram.")
        ct = [("Главная", "/"), ("Вакансии по городам", "/rabota/"), (city, f"/rabota/{cslug}/"), (pname, None)]
        ld = crumbs_ld([(t, u if u else path) for t, u in ct])
        html_ = head(title, desc, path, ld) + crumbs(ct)
        html_ += f'<h1>{esc(h1)}</h1>\n'
        facts = [f"В базе Будни_BY сейчас <b>{vac_word(n)}</b> по профессии «{esc(pname)}» {esc(loc)}."]
        if noexp:
            facts.append(f"Без опыта работы — {noexp}.")
        if sal:
            facts.append(f"Зарплата: {esc(sal[0])} (по {sal[1]} объявлениям с указанной суммой).")
        if companies[:4]:
            facts.append("Среди работодателей: " + esc(", ".join(companies[:4])) + ".")
        html_ += f'<p class="lead">{" ".join(facts)}</p>\n'
        html_ += f'<p class="updated">Обновлено {today.day} {MONTHS[today.month - 1]} {today.year}</p>\n'
        html_ += cta(f"Откликнуйтесь на вакансии {pgen} {loc}", f"src_seo_{cslug}_{pslug}")
        html_ += '<ul class="vac-list">\n' + "".join(vac_card(v, today) for v in items[:30]) + "</ul>\n"
        if n > 30:
            html_ += f'<p class="more">Показаны 30 самых свежих из {n}. Остальные — в боте.</p>\n'
        html_ += cta(f"Ещё больше вакансий {loc}", f"src_seo_{cslug}_{pslug}_b")
        # перелинковка: другие профессии в городе, эта профессия в других городах
        others = sorted(((p, len(by_pair[(city, p)])) for (c, p) in pair_pages if c == city and p != pslug),
                        key=lambda x: -x[1])[:12]
        if others:
            html_ += f'<h2>Другие вакансии {esc(loc)}</h2>\n<div class="chips">' + "".join(
                f'<a class="chip" href="/rabota/{cslug}/{p}/">{esc(PROF_BY_SLUG[p][1])} <b>{k}</b></a>' for p, k in others) + "</div>\n"
        same = sorted(((c, len(by_pair[(c, pslug)])) for (c, p) in pair_pages if p == pslug and c != city),
                      key=lambda x: -x[1])[:10]
        if same:
            html_ += f'<h2>{esc(pname)} — вакансии в других городах</h2>\n<div class="chips">' + "".join(
                f'<a class="chip" href="/rabota/{CITIES[c][0]}/{pslug}/">{esc(c)} <b>{k}</b></a>' for c, k in same) + "</div>\n"
        html_ += foot()
        write(path + "index.html", html_)
        pages.append((path, lastmod, "0.7"))

    # ── страницы городов ──
    for city in hub_cities:
        cslug, loc = CITIES[city]
        items = by_city[city]
        n = len(items)
        path = f"/rabota/{cslug}/"
        profs = sorted(((p, len(by_pair[(city, p)])) for (c, p) in pair_pages if c == city), key=lambda x: -x[1])
        title = f"Работа и вакансии {loc} — {vac_word(n)} | Будни_BY"
        top = ", ".join(PROF_BY_SLUG[p][1].lower() for p, _ in profs[:5])
        desc = (f"Актуальные вакансии и подработка {loc}: {vac_word(n)}"
                + (f" — {top}" if top else "") + ". База обновляется каждый день, отклик в Telegram бесплатно.")
        ct = [("Главная", "/"), ("Вакансии по городам", "/rabota/"), (city, None)]
        html_ = head(title, desc, path, crumbs_ld([(t, u if u else path) for t, u in ct])) + crumbs(ct)
        html_ += f'<h1>Работа и вакансии {esc(loc)}</h1>\n'
        html_ += (f'<p class="lead">В базе Будни_BY сейчас <b>{vac_word(n)}</b> {esc(loc)}. '
                  'Выберите профессию или откройте бота — там свайп-подбор под вашу сферу и контакты работодателей.</p>\n')
        html_ += f'<p class="updated">Обновлено {today.day} {MONTHS[today.month - 1]} {today.year}</p>\n'
        html_ += cta(f"Свайп-подбор вакансий {loc}", f"src_seo_{cslug}")
        if profs:
            html_ += f'<h2>Вакансии по профессиям {esc(loc)}</h2>\n<div class="chips">' + "".join(
                f'<a class="chip" href="/rabota/{cslug}/{p}/">{esc(PROF_BY_SLUG[p][1])} <b>{k}</b></a>' for p, k in profs) + "</div>\n"
        html_ += f'<h2>Свежие вакансии {esc(loc)}</h2>\n<ul class="vac-list">\n' + "".join(vac_card(v, today) for v in items[:15]) + "</ul>\n"
        html_ += foot()
        write(path + "index.html", html_)
        pages.append((path, lastmod, "0.8"))

    # ── общий список городов ──
    path = "/rabota/"
    total = sum(len(by_city[c]) for c in hub_cities)
    title = f"Вакансии и работа в Беларуси по городам — {vac_word(total)} | Будни_BY"
    desc = "Вакансии и подработка по городам Беларуси: Минск, Брест, Витебск, Гомель, Гродно, Могилёв и другие. Актуальные объявления, обновление каждый день."
    ct = [("Главная", "/"), ("Вакансии по городам", None)]
    html_ = head(title, desc, path, crumbs_ld([(t, u if u else path) for t, u in ct])) + crumbs(ct)
    html_ += "<h1>Вакансии и работа в Беларуси по городам</h1>\n"
    html_ += f'<p class="lead">Сейчас в базе <b>{vac_word(total)}</b> в {len(hub_cities)} {plural(len(hub_cities), "городе", "городах", "городах")} страны. Выберите город.</p>\n'
    html_ += f'<p class="updated">Обновлено {today.day} {MONTHS[today.month - 1]} {today.year}</p>\n'
    html_ += '<div class="chips chips-lg">' + "".join(
        f'<a class="chip" href="/rabota/{CITIES[c][0]}/">{esc(c)} <b>{len(by_city[c])}</b></a>'
        for c in sorted(hub_cities, key=lambda c: -len(by_city[c]))) + "</div>\n"
    prof_totals: dict[str, int] = {}
    for (c, p) in pair_pages:
        prof_totals[p] = prof_totals.get(p, 0) + len(by_pair[(c, p)])
    html_ += "<h2>Популярные профессии</h2>\n<div class=\"chips\">" + "".join(
        f'<a class="chip" href="/rabota/minsk/{p}/">{esc(PROF_BY_SLUG[p][1])} · Минск</a>'
        for p, _ in sorted(prof_totals.items(), key=lambda x: -x[1])[:14] if ("Минск", p) in pair_pages) + "</div>\n"
    html_ += cta("Свайп-подбор вакансий под ваш город", "src_seo_hub")
    html_ += foot()
    write(path + "index.html", html_)
    pages.append((path, lastmod, "0.9"))

    # ── sitemap.xml ──
    base = [("/", "2026-09-21", "1.0", "weekly"), ("/stats.html", lastmod, "0.6", "daily")]
    urls = "".join(
        f"  <url>\n    <loc>{SITE}{p}</loc>\n    <lastmod>{lm}</lastmod>\n    <changefreq>{cf}</changefreq>\n    <priority>{pr}</priority>\n  </url>\n"
        for p, lm, pr, cf in base) + "".join(
        f"  <url>\n    <loc>{SITE}{p}</loc>\n    <lastmod>{lm}</lastmod>\n    <changefreq>daily</changefreq>\n    <priority>{pr}</priority>\n  </url>\n"
        for p, lm, pr in pages)
    with open(os.path.join(ROOT, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + urls + "</urlset>\n")

    print(f"вакансий на входе: {len(rows)}, в городах-страницах: {total}")
    print(f"страниц: городов {len(hub_cities)}, «город × профессия» {len(pair_pages)}, всего {len(pages)} (+ список городов)")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "_tools", "data.json"))
