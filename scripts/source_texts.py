"""Turn the editions of the sources (part 2 of the book, pp. 94–446) into one HTML page per source,
page by page, keeping bold/italic, columns and footnotes; also write the plain text of every page
(used to link each attested form to the page where it occurs).

usage: source_texts.py book.pdf out_dir pages.json
"""
import html, json, os, re, sys, unicodedata
import pdfplumber
sys.path.insert(0, os.path.dirname(__file__))
from pdflines import page_lines

pdf_path, out_dir, pages_json = sys.argv[1:4]
os.makedirs(out_dir, exist_ok=True)

LEFT, RIGHT = 56.7, 425.6
SOURCES = [  # id, title, first page, last page (table of contents of the book)
    ("1", "Источник 1. Записи Хр. Барданеса (какой-то северо-восточный диалект), 1775 г.", 94, 98),
    ("2", "Источник 2. Записи И. Рюдигера (диалект синти), 1777 г.", 99, 104),
    ("3", "Источник 3. Запись Х. Л. Кр. Бакмейстера (русскоцыганский диалект), 1778 г.", 105, 107),
    ("4", "Источник 4. Запись Х. Л. Кр. Бакмейстера (русскоцыганский диалект), 1782 г.", 108, 117),
    ("5", "Источник 5. Запись В. Ф. Зуева (сэрвицкий диалект), 1781 г.", 118, 132),
    ("6", "Источник 6. Материалы П. С. Палласа (какой-то северо-восточный диалект), 1770-е гг.", 133, 138),
    ("7", "Источник 7. Словарь Т. Нарбута (литовскоцыганский диалект), конец 1820-х гг.", 139, 168),
    ("8a", "Источник 8а. Грамматика и словарь М. Григорьева, 1851 г.", 169, 206),
    ("8b", "Источник 8б. Словарь цыганского языка М. Григорьева (дополнение, 1852 г.)", 207, 229),
    ("9a", "Источник 9а. Грамматика цыганского языка В. Н. Добровольского, 1893 г.", 230, 308),
    ("9b", "Источник 9б. Словарь цыганского языка В. Н. Добровольского", 309, 411),
    ("9v", "Источник 9в. Описание поездки к цыганам в с. Кудрявцево Ельнинского уезда", 412, 424),
    ("9g", "Источник 9г. Некоторые слова, записанные от зарубежных цыган", 425, 427),
    ("9d", "Источник 9д. Впечатления киселёвских цыган о приезжих цыганах", 428, 433),
    ("9e", "Источник 9е. Посещение австрийскими цыганами деревни в Смоленской губернии", 434, 438),
    ("10", "Источник 10. Записи Г. Ванцяна (кэлдэрарский диалект), 1890–1894 гг.", 439, 446),
]


def render_items(items):
    out, cur, buf = [], (False, False), ""
    def flush():
        nonlocal buf
        if buf:
            t = html.escape(unicodedata.normalize("NFC", buf))
            if cur[0]: t = f"<b>{t}</b>"
            if cur[1]: t = f"<i>{t}</i>"
            out.append(t)
        buf = ""
    for it in items:
        st = (bool(it[1]), bool(it[2]))
        if it[0] == " ":
            buf += " "; continue
        if st != cur:
            flush(); cur = st
        buf += it[0]
    flush()
    return "".join(out)


def pct(x):
    return max(0.0, min(95.0, (x - LEFT) / (RIGHT - LEFT) * 100))


CSS = """
:root{--bg:#faf8f4;--panel:#fff;--ink:#1f1d1a;--muted:#6b665e;--line:#e4dfd6;--accent:#8a3b12;--mark:#fbe7a1;
--data:"Charis SIL","Gentium Plus","Noto Serif",Cambria,"Times New Roman",serif;--ui:system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif}
@media (prefers-color-scheme:dark){:root{--bg:#171614;--panel:#201f1c;--ink:#ece8e1;--muted:#a39d93;--line:#35322d;--accent:#e39a6c;--mark:#5c4a12}}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 var(--ui)}
header{max-width:820px;margin:0 auto;padding:20px 20px 6px}
header a{color:var(--accent)}
h1{font:600 20px/1.3 var(--data);margin:6px 0 4px}
nav.pages{font-size:13px;color:var(--muted);margin-top:6px;line-height:1.9}
nav.pages a{color:var(--accent);text-decoration:none;margin-right:6px}
main{max-width:820px;margin:0 auto;padding:0 20px 60px;overflow-x:auto}
section.page{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:18px 22px 14px;margin:14px 0;min-width:600px;
font:15px/1.45 var(--data);scroll-margin-top:12px}
section.page:target{outline:2px solid var(--accent)}
.pno{font:12px var(--ui);color:var(--muted);text-align:right;margin-bottom:4px}
.ln{position:relative;min-height:1.45em;white-space:pre-wrap}
.row{position:relative;height:1.45em}
.row .c{position:absolute;top:0;white-space:nowrap}
.fn{font-size:12.5px;line-height:1.35;color:var(--muted)}
.fn.ln{min-height:1.3em}
.fnsep{border-top:1px solid var(--line);width:30%;margin:10px 0 6px}
mark{background:var(--mark);color:inherit}
"""

JS = """
// highlight a form passed as #p123:form
(function(){var h=decodeURIComponent(location.hash.slice(1));var m=h.match(/^(p\\d+)(?::(.+))?$/);if(!m)return;
var sec=document.getElementById(m[1]);if(!sec)return;sec.scrollIntoView();if(!m[2])return;
function fold(s){return s.normalize('NFD').replace(/[\\u0300-\\u036f]/g,'').toLowerCase();}
var q=fold(m[2]);var w=document.createTreeWalker(sec,NodeFilter.SHOW_TEXT);var n;
while(n=w.nextNode()){var t=n.nodeValue,f='',map=[];for(var i=0;i<t.length;i++){var c=fold(t[i]);for(var k=0;k<c.length;k++){f+=c[k];map.push(i);}}
var p=f.indexOf(q);if(p<0)continue;var a=map[p],b=map[p+q.length-1]+1;while(b<t.length&&/[\\u0300-\\u036f]/.test(t[b]))b++;
var r=document.createRange();r.setStart(n,a);r.setEnd(n,b);var mk=document.createElement('mark');r.surroundContents(mk);mk.scrollIntoView({block:'center'});break;}})();
"""


def main():
    pages_text = {}
    with pdfplumber.open(pdf_path) as pdf:
        for sid, title, first, last in SOURCES:
            body = []
            for pno in range(first, last + 1):
                lines = page_lines(pdf.pages[pno - 1])
                lines = [L for L in lines if not (L["size"] >= 11.5 and re.fullmatch(r"\d{1,3}", L["text"].strip()))]
                out, fn_started, plain = [], False, []
                for L in lines:
                    fn = L["size"] < 9
                    if fn and not fn_started:
                        out.append('<div class="fnsep"></div>'); fn_started = True
                    cls = "fn " if fn else ""
                    plain.append(L["text"])
                    cells = L.get("cells") or [{"x0": L["x0"], "items": L["items"]}]
                    if len(cells) == 1:
                        ind = pct(cells[0]["x0"])
                        style = f' style="margin-left:{ind:.1f}%"' if ind > 0.5 else ""
                        out.append(f'<div class="{cls}ln"{style}>{render_items(cells[0]["items"])}</div>')
                    else:
                        cs = "".join(f'<span class="c" style="left:{pct(c["x0"]):.1f}%">{render_items(c["items"])}</span>' for c in cells)
                        out.append(f'<div class="{cls}row">{cs}</div>')
                pages_text[pno] = {"source": sid, "text": unicodedata.normalize("NFC", "\n".join(plain))}
                body.append(f'<section class="page" id="p{pno}"><div class="pno">p. {pno}</div>{"".join(out)}</section>')
            nav = " ".join(f'<a href="#p{p}">{p}</a>' for p in range(first, last + 1))
            doc = f"""<!DOCTYPE html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title><style>{CSS}</style></head>
<body><header><a href="../index.html">← Word index</a> · <a href="index.html">All sources</a>
<h1>{html.escape(title)}</h1>
<div style="font-size:13px;color:var(--muted)">Edition and commentary from K. A. Kozhanov, <i>Цыганский язык в источниках XVIII–XIX вв.</i> St Petersburg 2025, pp. {first}–{last}.</div>
<nav class="pages">Pages: {nav}</nav></header>
<main>{"".join(body)}</main><script>{JS}</script></body></html>"""
            open(os.path.join(out_dir, f"{sid}.html"), "w", encoding="utf-8").write(doc)
            print(sid, first, last)
    json.dump(pages_text, open(pages_json, "w", encoding="utf-8"), ensure_ascii=False)


if __name__ == "__main__":
    main()
