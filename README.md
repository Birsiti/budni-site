<!-- изменено 2026-09-21 18:50 -->
# budni-site — публичный сайт Будни_BY

Боевой репозиторий сайта **https://budni-by.site** (GitHub Pages, ветка `main`, корень репо).
Отвечает за одно: чтобы Будни_BY находили Google, Яндекс и ИИ-ассистенты, а не только через Telegram.
Мини-аппы бота живут в другом репо — `Birsiti/Budni`. Бэкенд — `budni-pilot` (iMac).

## Что где

| Файл | Зачем |
|---|---|
| `index.html` | лендинг: hero + живая карточка статистики, «как устроено», «кому подходит», профессии, сферы, география, FAQ (+ FAQPage JSON-LD) |
| `stats.html` | публичная статистика: всего, по сферам, по областям |
| `theme.js` | переключатель оформления Авто / Тёмная / Светлая (общий для обеих страниц, стили внутри) |
| `app.js` | копия `apiCall` и хелперов из мини-аппа; сайт ходит в API за `public_stats` |
| `og-image.png` | превью ссылки (1200×630) для og:image / twitter:image |
| `_og/og.html`, `_og/README.txt` | исходник картинки и команда перерендера; папка `_…` Pages не публикует |
| `robots.txt`, `sitemap.xml`, `llms.txt` | индексация; `Disallow: /admin/`, `/client/` |
| `CNAME` | `budni-by.site` |

## Данные

Единственная динамика — `public_stats` (`POST https://budni.tg-studio.xyz/exec`, тело `{"action":"public_stats"}`, без токена).
Ответ: `total`, `bySector{}`, `byOblast{}`. Если API недоступен, страница остаётся рабочей: число показывает «—», список сфер прячется.
Строка «Другое» в топе сфер на главной скрыта намеренно.

## Деплой

`git push` в `main` → Pages пересобирает за 1–2 минуты. Сборка: `gh api repos/Birsiti/budni-site/pages/builds/latest`.
Версия-стамп `<!-- изменено ГГГГ-ММ-ДД ЧЧ:ММ -->` первой строкой каждого изменённого файла.
Скрипты подключены с `?v=…` (кэш-бастинг) — при правке `theme.js` / `app.js` поднимать версию в HTML.

## Домен и HTTPS

- Домен куплен на hoster.by. DNS: «Расширенный DNS-редактор» (`Домены → Управление DNS`), NS `u1/u2.hoster.by`.
- 4 записи `A` на `185.199.108–111.153` (IP GitHub Pages). AAAA и CAA нет.
- Сертификат GitHub Pages выпускается сам. Если `https_certificate` пуст, а по https отдаётся `*.github.io` — в `Settings → Pages` удалить и заново вписать Custom domain (это создаёт коммиты `Delete CNAME` / `Create CNAME` — перед своим `git push` сделать `git pull --rebase`).
- `Enforce HTTPS` включена 2026-09-21 (`gh api -X PUT repos/Birsiti/budni-site/pages -F https_enforced=true`).
- **Грабля hoster.by:** в поле «Домен» панель сама дописывает зону. Для записи на корень домена вводить `budni-by.site.` (с точкой в конце), иначе получится `budni-by.site.budni-by.site.` и запись не сработает.

## Поисковики

| | Как подтверждено | Что нельзя удалять |
|---|---|---|
| Яндекс.Вебмастер | мета-тег `yandex-verification` в `<head>` `index.html` | тег |
| Google Search Console (ресурс-домен) | DNS TXT `google-site-verification=…` на `budni-by.site.` | TXT-запись в hoster.by |

Токен вида `google-site-verification=…` — для DNS. Мета-тег Google выглядит иначе (`content` без префикса) и выдаётся только для ресурса «URL prefix». Токены не взаимозаменяемы.

## Переключатель темы

`localStorage['budni_site_theme']` = `dark` | `light`; ключа нет = «Авто» (следует за системной темой, в том числе вживую).
Стартовую тему без вспышки выставляет инлайн-скрипт в `<head>` каждой страницы — он читает тот же ключ. `theme.js` отвечает только за UI (кнопка + поповер) и смену темы после загрузки. На экранах ≤560px поповер раскрывается на всю ширину шапки.

## og:image

`_og/og.html` → `og-image.png`. Перерендер из корня репо:

```
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --hide-scrollbars --force-device-scale-factor=1 --window-size=1200,630 --virtual-time-budget=8000 --screenshot="$PWD/og-image.png" "file://$PWD/_og/og.html"
```

Число вакансий на картинку намеренно не вынесено — чтобы не устаревало. Если Telegram показывает старое превью, сбросить кэш через `@WebpageBot`.

## Проверка вёрстки

Headless-Chrome не даёт окно уже ~500px, поэтому мобильную ширину проверять через `<iframe style="width:390px">` с тестовой страницей. На macOS `sed -i` требует `-i ''`.

## Планы

- Отдельные страницы под город / профессию для реального ранжирования → тогда переезд на Astro + Netlify (как tg-studio.by). Пока страница одна, статичного HTML хватает.
- Разметка `JobPosting` — нужен отдельный URL на вакансию, которого нет.
- Региональность в Яндекс.Вебмастере (Беларусь / Минск), Bing (импорт из Search Console).

## Черновик

`Birsiti/Budni/site-draft/` — песочница, копия этого репо (синхронизирована 2026-09-21, коммит `e0a7165`). Боевой — только здесь.
