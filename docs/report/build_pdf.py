#!/usr/bin/env python3
"""Render the owner report to PDF through Chromium's own print pipeline.

No LaTeX in this container, and wkhtmltopdf would need installing; Chromium is
already here for the screenshot harness and its print engine handles the web
fonts, the wide tables and the page breaks without another dependency.
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = "/agent/workspace/Agro-Site"
sys.path.insert(0, os.path.join(REPO, ".qa"))

M = json.load(open(os.path.join(HERE, "metrics.json"), encoding="utf-8"))


def git(*args):
    return subprocess.run(["git", "-C", REPO, *args],
                          capture_output=True, text=True, check=True).stdout.strip()


COMMITS = [l.split(" ", 1) for l in git("log", "--format=%h %s",
                                        "feat/reference-grade-redesign..HEAD").splitlines()]
DIFFSTAT = git("diff", "--shortstat", "feat/reference-grade-redesign..HEAD")

METRICS = [
    ("Текст, недоступный скринридеру (главная, до скролла)", "73,81 %", "5,37 %", "≤ 20 %", True),
    ("Заголовков в дереве доступности (главная)", "1 из 23", "23 из 23", "23 из 23", True),
    ("axe: нарушений serious + critical (27 стр.)", "100", "0", "0", True),
    ("axe: нарушений любого правила, вкл. best-practice", "169", "0", "—", True),
    ("Нарушений контраста (страница раскрыта, 36 стр.)", "144", "0", "0", True),
    ("TBT мобайл, V1 / V2 / V3", "654 / 678 / 571 мс", "247 / 208 / 237 мс", "&lt; 300 мс", True),
    ("TBT десктоп, V1 / V2 / V3", "72 / 48 / 36 мс", "10 / 5 / 0 мс", "—", True),
    ("Самая длинная задача, мобайл", "439 мс", "217 мс", "—", True),
    ("CLS, все шесть конфигураций", "до 0,0282 (всплески 0,068)", "0,0000", "≤ 0,005", True),
    ("LCP мобайл, V1 / V2 / V3", "1072 / 1056 / 972 мс", "1100 / 1052 / 1048 мс", "≤ 1200 мс", None),
    ("ScrollTrigger на главной", "83 / 86 / 83", "83 / 86 / 83", "без изменений", True),
    ("Твинов на главной", "137 / 141 / 136", "137 / 141 / 136", "без изменений", True),
    ("Кадры при прокрутке", "p50 16,7 / p95 33,3 мс", "p50 16,7 / p95 33,3 мс", "не хуже", True),
    ("Кадров дольше 50 мс", "0", "0", "0", True),
    ("HTML-файлов в чистой сборке", "92", "146", "146", True),
    ("URL в sitemap.xml", "30", "48", "48", True),
    ("index.html, gzip", "37,3 КБ", "37,4 КБ", "—", True),
    ("Первый экран целиком, gzip", "201,0 КБ", "201,7 КБ", "&lt; 420 КБ", True),
    ("Сторонних запросов", "0", "0", "0", True),
]

PIXELS = [
    ("A + B1/B2 — доступность, порционная инициализация", "0,0212 %", "0", "PASS"),
    ("B3 — контраст", "0,1572 %", "12", "намеренно"),
    ("B4/B5 — мёртвые шрифты, предзагрузка", "0,0357 %", "0", "PASS"),
    ("C — страницы культур", "0,0245 %", "0", "PASS"),
    ("D — юридические страницы, SEO", "0,0218 %", "0", "PASS"),
    ("После B3 → финал (итоговый гейт регрессии)", "0,0357 %", "0", "PASS"),
]

TOOLS = [
    ("tools/verify.py", "ALL CHECKS PASSED, 0 warnings. 48 индексируемых = 48 URL в sitemap, 0 дублей title и description"),
    ("tools/geometry_audit.py", "parallax 0, glyph 0, shadow 0, centre 0, overflow 0 — 7 семейств страниц × 3 вариации × 5 ширин × 4 глубины"),
    ("tools/visual_smoke.py", "224 снимка, 0 находок"),
    ("tools/interaction_smoke.py", "drawer, rails, accordion, detail-страницы, формы, reduced motion, no-JS — пройдено"),
    (".qa/keyboard.py", "полный обход табом 5 страниц, 0 остановок с нераскрытым reveal-контейнером"),
    (".qa/contrast.py", "0 нарушений на 36 страницах при полностью раскрытой странице"),
    (".qa/a11y.py", "axe WCAG 2.0/2.1/2.2 A+AA и best-practice: 0 нарушений на 27 страницах"),
]

CSS_ROWS = [
    (".form__note-link", "новый класс",
     "Подчёркивание по hover/focus у ссылки на политику конфиденциальности в строке согласия. "
     "Переопределений под вариации нет намеренно: правило — <code>border-bottom: 1px solid currentColor</code>, "
     "цвет наследуется от <code>.form__note</code>, у которого обработка вариаций уже есть "
     "(<code>.form--dark .form__note</code>). Три идентичных переопределения были бы шумом."),
    ("--muted-on-light: #6f6f6f", "новый токен",
     "Серый для текста на светлом. 5,02:1 на белом, 4,59:1 на <code>--grey-100</code>. "
     "<code>--grey-300</code> не тронут — на тёмном он корректен."),
    ("--lime-on-light: #5a7714", "новый токен",
     "Лайм для текста на светлом. 5,14:1 и 4,70:1, тон 77,6° против 77,1° у оригинала. "
     "<code>--lime-lo</code> не тронут — в тёмной шапке он работает."),
    (".detail-meta svg", "новое правило существующего класса",
     "Размер шевронов в хлебных крошках. Инлайновый SVG без внутреннего размера растягивается "
     "на весь контейнер — один неразмеченный разделитель занимал весь вьюпорт. Размер взят у "
     "<code>.detail-back svg</code>. Ни одна существующая страница не имеет SVG внутри "
     "<code>.detail-meta</code> — проверено по собранному выводу."),
    (".detail-hero__copy h1", "новое правило существующего класса",
     "<code>hyphens: auto</code> + <code>overflow-wrap: anywhere</code>. «конфіденційності» набирается "
     "в 300 px при 284 px колонки на 320-пиксельном экране. Оба свойства включаются только когда слово "
     "не помещается в строку целиком."),
    ("a[href], button, input, …", "новое правило, селекторы элементов",
     "<code>scroll-margin-block</code>, чтобы браузер доводил сфокусированный элемент до линии триггера "
     "и из-под липкой шапки. Участвует только в арифметике scroll-into-view, в раскладке — нет."),
]

NOT_DONE = [
    ("LCP на 30–80 мс хуже эталона",
     "V1 1072→1100 мс, V3 972→1048 мс. Цена предзагрузки <code>geistmono.woff2</code>: второй шрифт "
     "конкурирует за полосу с hero-картинкой. В обмен исчезла перерисовка hero при подмене шрифта, "
     "и CLS на V2 desktop упал с 0,0282 (всплески до 0,068 в 3–5 прогонах из 10) до 0,0000 на 10 из 10. "
     "Порог ≤ 1200 мс держится с запасом, а CLS ≤ 0,005 иначе был недостижим. Снимается одной строкой "
     "в <code>base.html.j2</code>, если приоритет обратный."),
    ("Ссылок на культуры нет в аккордеоне на главной и на услугах",
     "Панель культуры — это <code>&lt;button&gt;</code>, управляющий аккордеоном. Вложить "
     "<code>&lt;a&gt;</code> внутрь <code>&lt;button&gt;</code> нельзя (невалидная разметка, вложенный "
     "интерактив), а замена кнопки на ссылку ломает раскрытие панели на тач-устройствах, где нет hover. "
     "Чистого места без сдвига пикселей нет. Культуры перелинкованы через подвал (четыре ссылки "
     "«Продукції» ведут на свои страницы, текст не менялся), блок «Інші культури» на каждой странице "
     "культуры и sitemap."),
    ("Юридические страницы не в подвале",
     "Там нет текста-носителя: добавление видимой строки в колонку или изменение длины строки сдвигает "
     "пиксели. Доступны из строки согласия под формой, друг из друга и из sitemap."),
    ("Article.image — одно соотношение сторон",
     "Google просит 16:9, 4:3 и 1:1. Новостные фото есть только в 3:2 (обе ширины теперь отдаются "
     "массивом). Остальные пропорции требуют новых кропов из <code>build_images.py</code>."),
    ("Кеш-заголовки не исправлены",
     "На GitHub Pages ими управлять нельзя. Хеши в имена файлов не добавлял — ломает "
     "<code>.nojekyll</code>-раскладку и ссылки. Описано в документации как аргумент за переезд."),
    ("llms.txt не создавал",
     "97 % таких файлов на 137 000 доменов не получили ни одного запроса за месяц, Google их игнорирует."),
    ("Счётчики при reduced-motion печатают «14200»",
     "Корректный рендерер <code>renderCounterFinal()</code> в <code>app.js</code> есть и сознательно "
     "не подключён: это изменит то, что видят такие посетители."),
    ("FAQPage не удалён",
     "Разметка валидна и помогает понимать сущности, но сниппета от неё ждать не стоит — "
     "зафиксировано в документации."),
]

DECISIONS = [
    ("Обработчик форм", "Обе формы неактивны: валидация работает, отправка ничего не передаёт. "
     "Пока его нет, каждая заявка теряется молча. Подключение обязывает сразу поправить раздел 2 "
     "политики конфиденциальности — сейчас она честно говорит, что данные не передаются и не хранятся."),
    ("ЄДРПОУ, ІПН, соцсети, код Search Console", "Ключи в <code>content/uk.json</code> заведены пустыми, "
     "разметка появляется сама при заполнении. Придуманный ЄДРПОУ в графе знаний хуже отсутствующего."),
    ("Координаты в LocalBusiness", "49.0716, 29.3608 — получены геокодированием по адресу и не проверены на месте."),
    ("Базисы поставки на страницах культур", "EXW элеватор / FCA / CPT порт Одеса. Если компания фактически "
     "не продаёт на CPT — это коммерческое утверждение, а не опечатка."),
    ("Ссылки на юридические документы в подвале", "Если согласны на небольшое видимое изменение подвала — "
     "добавлю строку в колонку «Партнерам»."),
    ("Подчёркивание ссылки в строке согласия", "Сейчас неотличима от текста в покое (так строка осталась "
     "пиксель в пиксель), подчёркивается по hover/focus. Постоянное подчёркивание — лучшая ссылка "
     "и небольшое видимое изменение."),
    ("Апостроф", "Контент использует U+0027, подмножество шрифта несёт и типографский U+02BC. "
     "Миграция — сплошная замена по всему контенту."),
    ("Сертификаты", "ISO, GMP+, органика — покупатели их ищут, места в контенте под них пока нет."),
]

FINDINGS = [
    ("Три инструмента сборки писали за пределы репозитория",
     "<code>build_fonts.py</code>, <code>build_images.py</code> и <code>build_logo.py</code> имели "
     "абсолютный путь <code>/agent/workspace/agro/…</code> — каталога с таким именем в репозитории нет, "
     "то есть запустить их против реальных ассетов было нельзя. Именно поэтому два осиротевших "
     "<code>woff2</code> (34 КБ) прожили так долго: <code>build_fonts.py</code> чистит устаревшие файлы "
     "перед сборкой — в другом каталоге. Все три теперь берут корень от <code>__file__</code>."),
    ("verify.py держал число страниц тремя литералами",
     "92 / 36 / 24 — любое добавление страницы валило прогон. Теперь считает из "
     "<code>variants.json</code> и контента, и получил межстраничные проверки: множество sitemap против "
     "множества индексируемых, дубли title и description, self-canonical, взаимность hreflang, кириллица "
     "на английских страницах, <code>Product</code> с <code>additionalProperty</code>, "
     "<code>BreadcrumbList</code> ниже корня."),
    ("visual_smoke считал «ещё грузится» за «битая картинка»",
     "Проверка была <code>!complete || naturalWidth === 0</code>. Первая половина — нормальное состояние "
     "страницы с двадцатью lazy-изображениями ниже первого экрана: инструмент выдавал находку на каждой "
     "главной при каждом узком вьюпорте, и в эталоне тоже. Битая — это <code>complete &amp;&amp; "
     "naturalWidth === 0</code>."),
    ("404.html правки не требовал",
     "Все три доменно-абсолютных пути уже подставляются из константы <code>SUBPATH</code>. Переезд "
     "на свой домен — правка двух строк в <code>build_site.py</code> (<code>BASE</code> и "
     "<code>SUBPATH</code>)."),
    ("Пять нарушений контраста были существующими багами V2, а не дрейфом токенов",
     "Тёмные полосы <code>#services</code>, оба тёмных detail-hero и цена в <code>#terms</code> не были "
     "добавлены в собственные on-dark правила вариации, а <code>.v2 .detail-back</code> вообще не был "
     "ограничен панелью и красил ссылку серым по белому (1,69:1)."),
]

CSS = """
@page { size: A4; margin: 16mm 14mm 14mm; }
* { box-sizing: border-box; }
body { font: 10pt/1.5 "DejaVu Sans", sans-serif; color: #16181a; margin: 0;
       -webkit-print-color-adjust: exact; print-color-adjust: exact; }
h1 { font-size: 21pt; line-height: 1.15; letter-spacing: -.02em; margin: 0 0 4mm; }
h2 { font-size: 13pt; margin: 9mm 0 3mm; padding-bottom: 1.6mm;
     border-bottom: 2px solid #1d2b12; letter-spacing: -.01em; break-after: avoid; }
h3 { font-size: 10.5pt; margin: 5mm 0 1.6mm; break-after: avoid; }
p { margin: 0 0 2.6mm; }
code { font: 8.6pt/1.35 "DejaVu Sans Mono", monospace; background: #f1f3ec;
       padding: .4mm 1mm; border-radius: 1mm; }
table { width: 100%; border-collapse: collapse; margin: 0 0 3mm; font-size: 8.7pt; }
th { text-align: left; background: #1d2b12; color: #fff; padding: 1.7mm 2mm;
     font-weight: 600; font-size: 8pt; letter-spacing: .03em; text-transform: uppercase; }
td { padding: 1.6mm 2mm; border-bottom: .3pt solid #d9ded1; vertical-align: top; }
tr { break-inside: avoid; }
.num { font-family: "DejaVu Sans Mono", monospace; white-space: nowrap; }
.ok { color: #2f6a1e; font-weight: 700; }
.warn { color: #9a6207; font-weight: 700; }
.int { color: #8a4b12; font-weight: 700; }
.lead { font-size: 10.5pt; color: #3d4348; margin-bottom: 5mm; }
.meta { font-size: 8.4pt; color: #5b6169; border-left: 2.4pt solid #c6f24e;
        padding: 2mm 0 2mm 3mm; margin: 0 0 6mm; }
.meta b { color: #16181a; }
figure { margin: 3mm 0 5mm; break-inside: avoid; }
figure img { width: 100%; border: .3pt solid #ccd2c4; }
figcaption { font-size: 8pt; color: #5b6169; margin-top: 1.5mm; }
.kv { break-inside: avoid; margin-bottom: 3.4mm; }
.kv b { display: block; font-size: 9.6pt; margin-bottom: .8mm; }
.kv span { display: block; font-size: 9pt; color: #3d4348; }
.callout { background: #f7f9f3; border: .3pt solid #ccd2c4; border-left: 2.4pt solid #c6f24e;
           padding: 3mm 3.5mm; margin: 0 0 5mm; font-size: 9.2pt; break-inside: avoid; }
.callout b { color: #16181a; }
.page-break { break-before: page; }
ol { margin: 0 0 3mm; padding-left: 5mm; }
li { margin-bottom: 1.6mm; font-size: 9.2pt; }
.commit { font-size: 8.6pt; margin-bottom: 1.4mm; }
.commit code { background: #e7ecdf; }
"""


def esc(s):
    return s


def build_html():
    rows_m = "".join(
        f"<tr><td>{n}</td><td class='num'>{b}</td><td class='num'><b>{a}</b></td>"
        f"<td class='num'>{t}</td><td>"
        + ("<span class='ok'>✔</span>" if ok else "<span class='warn'>см. §6</span>")
        + "</td></tr>"
        for n, b, a, t, ok in METRICS)

    rows_p = "".join(
        f"<tr><td>{n}</td><td class='num'>{w}</td><td class='num'>{o}</td><td>"
        + (f"<span class='int'>{v}</span>" if v == "намеренно" else f"<span class='ok'>{v}</span>")
        + "</td></tr>"
        for n, w, o, v in PIXELS)

    rows_t = "".join(f"<tr><td class='num'>{t}</td><td>{r}</td></tr>" for t, r in TOOLS)
    rows_c = "".join(f"<tr><td class='num'>{s}</td><td>{k}</td><td>{w}</td></tr>"
                     for s, k, w in CSS_ROWS)
    commits = "".join(f"<div class='commit'><code>{h}</code> &nbsp;{s}</div>"
                      for h, s in COMMITS)
    not_done = "".join(f"<div class='kv'><b>{t}</b><span>{d}</span></div>" for t, d in NOT_DONE)
    decisions = "".join(f"<li><b>{t}.</b> {d}</li>" for t, d in DECISIONS)
    findings = "".join(f"<div class='kv'><b>{t}</b><span>{d}</span></div>" for t, d in FINDINGS)

    return f"""<!DOCTYPE html>
<html lang="ru"><head><meta charset="utf-8"><style>{CSS}</style></head><body>

<h1>ТОВ «ЦЕНТРАГРО ПЛЮС» — отчёт о работе</h1>
<p class="lead">Доступность, время блокировки, страницы культур, юридические страницы
и SEO. Пять фаз, каждая измерена относительно эталона, снятого до первой правки.</p>

<div class="meta">
<b>Репозиторий:</b> github.com/xxxquide/Agro-Site<br>
<b>Ветка:</b> <code>feat/a11y-perf-crops-seo</code>, отведена от <code>feat/reference-grade-redesign</code><br>
<b>Коммитов:</b> {len(COMMITS)}, по одному на фазу &nbsp;·&nbsp; <b>Диффстат:</b> {DIFFSTAT}<br>
<b>Дата:</b> 7 августа 2026 &nbsp;·&nbsp; В <code>main</code> не коммичено, деплой не выполнялся
</div>

<div class="callout">
<b>Главный принцип приёмки.</b> Существующие страницы обязаны остаться пиксель в пиксель.
Порог — доля пикселей с отличием более 30 по любому каналу ≤ 0,05 %. Единственное
намеренное визуальное изменение за весь проход — фаза B3 (контраст), она вынесена
в отдельный коммит и откатывается независимо. Пересборка после коммита даёт
<b>0 изменённых файлов</b>: артефакты в репозитории в точности соответствуют источникам.
</div>

<h2>Коммиты</h2>
{commits}

<h2>1. Метрики</h2>
<table>
<thead><tr><th style="width:38%">Метрика</th><th>До</th><th>После</th><th>Цель</th><th style="width:8%">Статус</th></tr></thead>
<tbody>{rows_m}</tbody></table>

<h2>2. Попиксельное сравнение</h2>
<p>Матрица — 39 снимков, после фазы C — 54 (добавились страницы культур): главная
V1/V2/V3 × 1440×900 и 412×823 × позиции 0/2000/4200/7600, услуги V1/V2/V3, статья,
контакты, о нас, блог, профиль, EN-главная, страница культуры V1/V2/V3.</p>
<table>
<thead><tr><th style="width:52%">Фаза</th><th>Худший снимок</th><th>Сверх порога</th><th>Вердикт</th></tr></thead>
<tbody>{rows_p}</tbody></table>

<div class="callout">
<b>Шум измерен отдельно.</b> Два прогона одной и той же сборки расходятся до 0,0102 %
(до 0,036 % на снимках главной в позиции 2000 — там линия триггера проходит ровно
по столбчатой диаграмме). Чтобы получить такой шум, харнесс пришлось починить:
позиция скролла набирается колёсиком, а не <code>scrollTo</code> (Lenis держит свою
цель и перезаписывает программный скролл), и перед кадром сбрасываются бесконечные
анимации и снимается <code>will-change</code> — из-за него слова заголовков
переключались между grayscale- и subpixel-сглаживанием. Без этих двух правок одна
и та же сборка расходилась с собой на 1,36 %.
</div>

<h2>3. Единственное намеренное визуальное изменение — фаза B3</h2>
<p><code>--grey-300</code> и <code>--lime-lo</code> — цвета для тёмных поверхностей,
и на белом давали 1,69:1 и 1,37:1 против требуемых 4,5:1. Оба исходных токена не
тронуты; добавлены два для текста на светлом. Менялась только светлота, и только
до прохождения порога. Проверял и на <code>--grey-100</code>, не только на белом:
серая панель на контактах стоит примерно 0,4 пункта отношения, и «граничный»
#767676 проходит на белом (4,54:1) и не проходит на #f4f5f1 (4,14:1).</p>
<figure>
<img src="contrast-before-after.png">
<figcaption>Фрагменты до / после, обрезаны вплотную и увеличены ×3. Позиция, кегль,
насыщенность и трекинг не менялись — изменилась только светлота.</figcaption>
</figure>

<h2>4. Страницы культур: три вариации оформили их сами</h2>
<p>Семь культур делили одну страницу <code>/services/</code>. Теперь у каждой своя:
<code>/services/&lt;slug&gt;/</code>, 42 новые страницы, 14 индексируемых.
<code>crop.html.j2</code> не упоминает <code>V</code> и не вводит ни одного нового
класса — только те, что <code>07-variants.css</code> уже знает. Поэтому вариации
оформили страницу самостоятельно: на одной и той же странице расходится от 4 % до
59 % пикселей в зависимости от глубины скролла.</p>
<figure>
<img src="crop-three-variations.png">
<figcaption>Одна и та же страница культуры в трёх вариациях: hero и блок условий
сделки, собранный на карточках <code>plan</code> из <code>sec_terms</code>.</figcaption>
</figure>
<figure>
<img src="article-vs-crop.png">
<figcaption>Страница культуры рядом с блоговой статьёй той же вариации: одна
типографика, одна вёрстка списков, одна мера строки.</figcaption>
</figure>

<h2>5. Новые CSS-классы и токены</h2>
<p>Один новый класс за весь проход. Остальное — новые правила для существующих классов.</p>
<table>
<thead><tr><th style="width:26%">Селектор / токен</th><th style="width:20%">Тип</th><th>Обоснование</th></tr></thead>
<tbody>{rows_c}</tbody></table>

<h2>6. Что не сделано и почему</h2>
{not_done}

<h2>7. Требует решения владельца</h2>
<ol>{decisions}</ol>
<p style="font-size:9pt;color:#3d4348">Полный список — в <code>docs/CONTENT-GUIDE.md</code>,
раздел «Что надо добавить до запуска», где к каждому факту указан файл и ключ,
а также перекрёстные проверки, которые должны сходиться: земельный банк = сумма
семи площадей; полоса ёмкости нарисована как 46 000 / 58 000.</p>

<h2>8. Проверки: что и чем измерено</h2>
<table>
<thead><tr><th style="width:30%">Инструмент</th><th>Результат</th></tr></thead>
<tbody>{rows_t}</tbody></table>

<h2>9. Побочные находки</h2>
{findings}

<h2>10. Документация</h2>
<div class="kv"><b>README.md</b><span>Таблица весов перемерена: обещала 97,0 КБ для
<code>index.html</code> при фактических 155,2 КБ — расхождение 59 %, снималось восемью
коммитами ранее. Обновлены счётчики страниц и URL. Добавлены разделы «Доступность:
контракт reveal-слоя» и «Страницы культур» с инструкцией на одну запись в JSON.</span></div>
<div class="kv"><b>docs/ARCHITECTURE.md</b><span>Новый. Тройной цикл генерации, как
вариации работают через класс на <code>body</code>, почему шаблоны detail-страниц не
знают про <code>V</code>, и обе половины контракта моушн-слоя — чтобы следующий
человек не вернул <code>visibility: hidden</code>, посчитав <code>opacity</code>
небрежностью.</span></div>
<div class="kv"><b>docs/CONTENT-GUIDE.md</b><span>Новый. Карта «факт о компании →
файл и ключ», перекрёстные проверки, которые должны сходиться, девять пунктов
«добавить до запуска» и известные ограничения.</span></div>
<div class="kv"><b>CHANGELOG.md</b><span>Одна запись на проход, по фазам, в стиле
существующих.</span></div>

<h2>11. Как забрать ветку</h2>
<div class="callout">
<b>Ветка существует только в песочнице.</b> В контейнере нет ни <code>gh</code>, ни
токена, ни credential helper — <code>git push</code> отвечает
<code>could not read Username for 'https://github.com'</code>. Отправить её в
<code>origin</code> я не могу: нужны ваши доступы. Живой сайт при этом в
безопасности — GitHub&nbsp;Pages отдаёт <code>d3525bf</code> из
<code>feat/reference-grade-redesign</code>, моя ветка его не касается.
</div>
<p>Три варианта, по убыванию удобства:</p>
<ol>
<li><b>Дать доступ</b> — персональный токен с правом <code>repo</code> или подключить
GitHub-интеграцию. Тогда я запушу <code>feat/a11y-perf-crops-seo</code> сам и открою
pull request в <code>feat/reference-grade-redesign</code>.</li>
<li><b>Bundle</b> — <code>agro-site-feat-a11y-perf-crops-seo.bundle</code> (420 КБ),
самодостаточный файл со всеми шестью коммитами:
<br><code>git fetch ../agro-site-feat-a11y-perf-crops-seo.bundle feat/a11y-perf-crops-seo:feat/a11y-perf-crops-seo</code>
<br>затем <code>git push -u origin feat/a11y-perf-crops-seo</code>.</li>
<li><b>Патчи</b> — шесть файлов <code>0001…0006-*.patch</code> из
<code>git format-patch</code>, применяются через <code>git am *.patch</code> на
<code>feat/reference-grade-redesign</code>.</li>
</ol>
<p style="font-size:9pt;color:#3d4348">Все три артефакта лежат рядом с этим отчётом.
Bundle предпочтительнее: он переносит коммиты вместе с их авторством и датами,
патчи — только содержимое.</p>

</body></html>"""


def main():
    html_path = os.path.join(HERE, "report.html")
    with open(html_path, "w", encoding="utf-8") as fh:
        fh.write(build_html())

    from playwright.sync_api import sync_playwright
    out = os.path.join(HERE, "CENTRAGRO-report-2026-08-07.pdf")
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        p = b.new_page()
        p.goto("file://" + html_path, wait_until="load")
        p.wait_for_timeout(900)
        p.pdf(path=out, format="A4", print_background=True,
              margin={"top": "16mm", "bottom": "14mm", "left": "14mm", "right": "14mm"},
              display_header_footer=True,
              header_template="<div></div>",
              footer_template="<div style='width:100%;font:8pt \"DejaVu Sans\",sans-serif;"
                              "color:#8a9096;padding:0 14mm;display:flex;justify-content:space-between'>"
                              "<span>ЦЕНТРАГРО ПЛЮС · feat/a11y-perf-crops-seo</span>"
                              "<span class='pageNumber'></span></div>")
        b.close()
    print(f"PDF -> {out}  ({os.path.getsize(out)/1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
