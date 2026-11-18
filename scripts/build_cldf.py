"""parsed.json -> CLDF Dictionary dataset (cldf/), search-page data (docs/data.json) and the list of sources
(docs/sources/index.html).

usage: build_cldf.py parsed.json source_pages.json root_dir
"""
import csv, html, json, os, re, sys, unicodedata
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from translit import romani, has_cyrillic

src, pages_json, root = sys.argv[1], sys.argv[2], sys.argv[3]
D = json.load(open(src, encoding="utf-8"))
PAGES = {int(k): v for k, v in json.load(open(pages_json, encoding="utf-8")).items()}
EN = json.load(open(os.path.join(HERE, "meanings_en.json"), encoding="utf-8"))
SRC = json.load(open(os.path.join(HERE, "sources.json"), encoding="utf-8"))
CLDF = os.path.join(root, "cldf"); DOCS = os.path.join(root, "docs")
os.makedirs(CLDF, exist_ok=True); os.makedirs(os.path.join(DOCS, "sources"), exist_ok=True)

LANG = "NERomani"
ABBR = {
    "Бард.": "Bard", "Бакм.": "Bakm", "Пал.": "Pal", "Лек.": "Lek", "Narb.": "Narb", "Bor.": "Bor",
    "Григ.": "Grig", "Köp.": "Kop", "Gl.": "Gl", "Поп.": "Pop", "Duhm.": "Duhm", "Гол.": "Gol",
    "Dow.-S.": "DowS", "Ziel.": "Ziel", "Добр.": "Dobr", "Шт.": "Sht", "Sowa": "Sowa",
    "Патк.": "Patk", "Пог.": "Pog", "Дор.": "Dor",
}
# sources whose text is edited in the book (part 2), by abbreviation and year -> source pages
EDITIONS = {
    ("Бард.", "1775"): ["1"], ("Бакм.", "1778"): ["3"], ("Бакм.", "1782"): ["4"], ("Пал.", "1787"): ["6"],
    ("Narb.", "1830"): ["7"], ("Григ.", "1851"): ["8a"], ("Григ.", "1852"): ["8b"],
    ("Добр.", "1893"): ["9a", "9b", "9v", "9g", "9d", "9e"],
}
EDITION_TITLES = {
    "1": "Источник 1", "2": "Источник 2", "3": "Источник 3", "4": "Источник 4", "5": "Источник 5", "6": "Источник 6",
    "7": "Источник 7", "8a": "Источник 8а", "8b": "Источник 8б", "9a": "Источник 9а", "9b": "Источник 9б",
    "9v": "Источник 9в", "9g": "Источник 9г", "9d": "Источник 9д", "9e": "Источник 9е", "10": "Источник 10",
}


def key(abbr, year):
    return f"{ABBR[abbr]}{year}"

def nf(s):
    return unicodedata.normalize("NFC", s or "")

def fold(s):
    s = unicodedata.normalize("NFD", s or "").lower()
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.replace("’", "'").replace("ʼ", "'")

def en_of(ru):
    return EN.get(nf(ru), "")


# ---------- edition pages: where does a form occur in the edited source text? ----------
PAGE_FOLD = {}
for p, v in PAGES.items():
    t = v["text"].replace("|", "").replace("=", " ")
    t = re.sub(r"-\n(?=\w)", "", t)
    PAGE_FOLD[p] = (v["source"], " " + re.sub(r"\s+", " ", fold(t)) + " ")

def edition_page(form, abbr, year):
    eds = EDITIONS.get((abbr, year))
    if not eds:
        return None
    f = fold(form).strip(" ,.;:!?")
    if len(f) < 2:
        return None
    pats = [re.compile(r"(?<![\w'])" + re.escape(f) + r"(?![\w'])"), re.compile(re.escape(f))]
    for pat in pats:
        for ed in eds:
            for p in sorted(PAGE_FOLD):
                s, t = PAGE_FOLD[p]
                if s == ed and pat.search(t):
                    return ed, p
    return eds[0], None


# ---------- headword lookup for cross-references ----------
LOOKALIKE = str.maketrans("аеорсухоі", "aeopcyxoi")

def hw_keys(h):
    h = nf(h).translate(LOOKALIKE)
    h = re.sub(r"[¹²³⁴0-9]", "", h).replace("|", "").strip()
    a = h.replace("(", "").replace(")", "")
    b = re.sub(r"\([^)]*\)", "", h)
    return {fold(a), fold(b), fold(h)}

def homonym(h):
    m = re.search(r"([¹²³⁴])", h)
    return {"¹": 1, "²": 2, "³": 3, "⁴": 4}[m.group(1)] if m else 0


entries, senses, atts = [], [], []
used_sources = {}
LOOK = {}      # folded headword -> list of (entry id, pos, homonym, is_main)

n = 0
for e in D["entries"]:
    n += 1; e["_id"] = f"e{n:04d}"
    for k in hw_keys(e["headword"]):
        LOOK.setdefault(k, []).append((e["_id"], e["pos"], homonym(e["headword"]), True))
    for j, s in enumerate(e["subentries"], 1):
        s["_id"] = f"{e['_id']}-{j:02d}"
        if s["label"] != "prefix":
            for k in hw_keys(s["headword"]):
                LOOK.setdefault(k, []).append((s["_id"], "", 0, False))

ROM_WORD = re.compile(r"[a-zA-Zčšžřńłśźćěáéíóúýàèìòùʼ’'|()¹²³-]*[a-zčšžáéíóúýěʼ’'][a-zA-Zčšžřńłśźćěáéíóúýàèìòùʼ’'|()¹²³-]*")

def resolve(text, self_id=None):
    """first Romani word in text -> (label, entry id or '')"""
    m = ROM_WORD.search(text or "")
    if not m:
        return None
    word = m.group(0).strip("-'’")
    rest = text[m.end():m.end() + 6]
    cands = []
    for k in hw_keys(word):
        cands = LOOK.get(k, [])
        if cands: break
    cands = [c for c in cands if c[0] != self_id]
    if not cands and "|" in word:
        # prefixed verb "do|resél": prefixed verbs are listed under their base verb
        for k in hw_keys(word.split("|", 1)[1]):
            cands = [c for c in LOOK.get(k, []) if c[0] != self_id and c[3]]
            if cands: break
    if not cands:
        return (word, "")
    # gender hint "bár м." / "bár ж.", homonym number
    g = re.match(r"\s*(м|ж)\.", rest)
    if g:
        gc = [c for c in cands if c[1].startswith(g.group(1))]
        cands = gc or cands
    hn = homonym(word)
    if hn:
        hc = [c for c in cands if c[2] == hn]
        cands = hc or cands
    mains = [c for c in cands if c[3]]
    return (word, (mains or cands)[0][0])


def forms_rows(entry_id, forms):
    out = []
    for k, f in enumerate(forms, 1):
        keys = [key(f["source"], y) for y in f["years"]] if f["source"] else []
        for y in f["years"]:
            used_sources.setdefault(key(f["source"], y), (f["source"], y))
        form = nf(f["form"])
        ed = None
        for y in f["years"]:
            ed = edition_page(form, f["source"], y)
            if ed and ed[1]: break
        row = {
            "ID": f"{entry_id}-{k}", "Entry_ID": entry_id,
            "Form": form, "Form_Latin": romani(form),
            "Script": "Cyrl" if has_cyrillic(form) else "Latn",
            "Source": ";".join(keys),
            "Source_Abbreviation": (f["source"] + " " + ", ".join(f["years"])) if f["source"] else "",
            "Edition": ed[0] if ed else "",
            "Edition_Page": str(ed[1]) if ed and ed[1] else "",
            "Editor_Note": nf(f["pre_note"]),
            "Source_Annotation": nf(f["annotation"]),
            "Source_Glosses": ";".join(nf(g) for g in f["glosses"]),
            "Sense_Numbers": ";".join(f["senses"]),
            "Uncertain": "true" if f["uncertain"] else "false",
            "Same_Form_As_Previous": "true" if f.get("repeated") else "false",
        }
        atts.append(row); out.append(row)
    return out

def web_forms(rows):
    return [[r["Form"], r["Form_Latin"], r["Source_Abbreviation"], r["Editor_Note"], r["Source_Annotation"],
             r["Uncertain"] == "true",
             (f"{r['Edition']}#p{r['Edition_Page']}" if r["Edition_Page"] else (r["Edition"] or ""))] for r in rows]

def english_meaning(senses_):
    parts = []
    for num, desc in senses_:
        t = en_of(desc) or ""
        if not t: continue
        parts.append(f"{num}. {t}" if num else t)
    return "; ".join(parts)


web = []
derived_from = {}   # id -> list of base ids
for e in D["entries"]:
    eid = e["_id"]
    mean = nf(e["meaning"])
    der = [resolve(x, eid) for x in e["notes"]["derivation"]]
    der = [d for d in der if d]
    comp = []
    for c in e["notes"]["composition"]:
        for part in re.split(r"\s\+\s", c):
            r = resolve(part, eid)
            if r: comp.append(r)
    see = [resolve(x, eid) or (x, "") for x in e["see_also"]]
    for d in der:
        if d[1]: derived_from.setdefault(d[1], []).append(eid)
    entries.append({
        "ID": eid, "Language_ID": LANG, "Headword": nf(e["headword"]),
        "Paradigm": nf(e["paradigm"]), "Part_Of_Speech": nf(e["pos"]),
        "Main_Entry_ID": "", "Subentry_Type": "",
        "Meaning": mean, "Meaning_English": english_meaning(e["senses"]),
        "Distribution": "; ".join(e["notes"]["distribution"]),
        "Derived_From": "; ".join(e["notes"]["derivation"]),
        "Derived_From_ID": ";".join(d[1] for d in der if d[1]),
        "Composition": "; ".join(e["notes"]["composition"]),
        "Composition_IDs": ";".join(c[1] for c in comp if c[1]),
        "Header_Notes": "; ".join(e["notes"]["other"]),
        "Etymology": nf(e["etymology"]),
        "See_Also": ";".join(nf(x) for x in e["see_also"]),
        "See_Also_IDs": ";".join(s[1] for s in see if s[1]),
        "Letter": e["letter"], "Book_Order": int(eid[1:]),
    })
    for k, (num, desc) in enumerate(e["senses"], 1):
        senses.append({"ID": f"{eid}-s{k}", "Entry_ID": eid, "Sense_Number": num,
                       "Description": nf(desc), "Description_English": en_of(desc)})
    fr = forms_rows(eid, e["forms"])
    subs_web = []
    for s in e["subentries"]:
        sid = s["_id"]; sm = nf(s["meaning"])
        ssee = [resolve(x, sid) or (x, "") for x in s["see_also"]]
        entries.append({
            "ID": sid, "Language_ID": LANG, "Headword": nf(s["headword"]), "Paradigm": "",
            "Part_Of_Speech": "", "Main_Entry_ID": eid, "Subentry_Type": s["label"],
            "Meaning": sm, "Meaning_English": en_of(sm) if sm else "", "Distribution": "",
            "Derived_From": "", "Derived_From_ID": "", "Composition": "", "Composition_IDs": "",
            "Header_Notes": "", "Etymology": "",
            "See_Also": ";".join(nf(x) for x in s["see_also"]), "See_Also_IDs": ";".join(x[1] for x in ssee if x[1]),
            "Letter": s["letter"], "Book_Order": int(eid[1:]),
        })
        if sm:
            senses.append({"ID": f"{sid}-s1", "Entry_ID": sid, "Sense_Number": "",
                           "Description": sm, "Description_English": en_of(sm)})
        sfr = forms_rows(sid, s["forms"])
        subs_web.append({"id": sid, "l": s["label"], "h": nf(s["headword"]), "m": sm, "en": en_of(sm) if sm else "",
                         "sa": [list(x) for x in ssee], "f": web_forms(sfr)})
    web.append({"id": eid, "L": e["letter"], "h": nf(e["headword"]), "p": nf(e["paradigm"]), "pos": nf(e["pos"]),
                "m": mean, "en": english_meaning(e["senses"]),
                "dist": "; ".join(e["notes"]["distribution"]),
                "dr": [list(d) for d in der], "cp": [list(c) for c in comp],
                "oth": "; ".join(e["notes"]["other"]),
                "et": nf(e["etymology"]), "sa": [list(x) for x in see],
                "f": web_forms(fr), "s": subs_web})

# reverse links: derivatives of each entry
HW = {w["id"]: w["h"] for w in web}
for w in web:
    w["ds"] = [[HW[d], d] for d in derived_from.get(w["id"], [])]


def write(name, rows):
    with open(os.path.join(CLDF, name), "w", newline="", encoding="utf-8") as fh:
        wr = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        wr.writeheader(); wr.writerows(rows)

write("entries.csv", entries)
write("senses.csv", senses)
write("attestations.csv", atts)
write("languages.csv", [{"ID": LANG, "Name": "North-Eastern Romani (18th–19th-century sources)",
                         "Glottocode": "", "ISO639P3code": "rmy", "Macroarea": "Eurasia"}])

# ---------- sources ----------
def bibesc(s):
    return s.replace("{", "\\{").replace("}", "\\}")

def src_info(abbr, year):
    for v in SRC.values():
        if v["abbr"] == abbr and year in v["years"]:
            return v
    return None

def title_of(v):
    d = v["description"]
    return d[len(v["author"]) + 2:] if v["author"] and d.startswith(v["author"] + ", ") else d

bib = ["""@book{Kozhanov2025,
  author = {Кожанов, Кирилл А.},
  title = {Цыганский язык в источниках XVIII–XIX вв. (из архивов России и Литвы)},
  address = {Санкт-Петербург},
  publisher = {Маматов},
  year = {2025},
  isbn = {978-5-91076-297-2}
}
"""]
web_sources = {}
for k in sorted(used_sources, key=lambda x: (used_sources[x][1], x)):
    abbr, year = used_sources[k]
    v = src_info(abbr, year)
    eds = EDITIONS.get((abbr, year), [])
    if v is None:
        bib.append(f"@misc{{{k},\n  title = {{“{abbr} {year}”: not in the list of sources of Kozhanov 2025, probably a misprint}},\n"
                   f"  year = {{{year}}},\n  note = {{Abbreviation in Kozhanov 2025: {abbr} {year}}}\n}}\n")
        web_sources[f"{abbr} {year}"] = {"key": k, "author": "", "title": "Not in the book's list of sources — probably a misprint.",
                                          "pubs": [], "eds": []}
        continue
    pubs = "; ".join(f"[{p['key']}] {p['reference']}" for p in v["publications"])
    fields = [f"  author = {{{bibesc(v['author'])}}}" if v["author"] else None,
              f"  title = {{{bibesc(title_of(v))}}}", f"  year = {{{year}}}",
              f"  note = {{Abbreviation in Kozhanov 2025: {abbr} {year}" + (f". Published in: {bibesc(pubs)}" if pubs else "")
              + (". Edited in Kozhanov 2025: " + ", ".join(EDITION_TITLES[e] for e in eds) if eds else "") + "}"]
    bib.append(f"@misc{{{k},\n" + ",\n".join(f for f in fields if f) + "\n}\n")
    web_sources[f"{abbr} {year}"] = {"key": k, "author": v["author"], "title": title_of(v),
                                      "pubs": [[p["key"], p["reference"]] for p in v["publications"]],
                                      "eds": [[e, EDITION_TITLES[e]] for e in eds]}
arch = [l.strip() for l in open(os.path.join(HERE, "archives.txt"), encoding="utf-8") if l.strip()]
cur = None; ai = 0; archive_rows = []
for line in arch:
    if line.startswith("Электронные базы данных"):
        cur = "ELECTRONIC"; continue
    if cur == "ELECTRONIC" or not re.search(r"\(г\. ", line):
        ai += 1
        if cur == "ELECTRONIC":
            name, url = [x.strip() for x in line.split("—", 1)]
            bib.append(f"@misc{{db{ai},\n  title = {{{bibesc(name)}}},\n  url = {{{url}}}\n}}\n")
        else:
            bib.append(f"@unpublished{{archive{ai},\n  title = {{{bibesc(line)}}},\n  note = {{{bibesc(cur or '')}}}\n}}\n")
        archive_rows.append((cur, line))
    else:
        cur = line
open(os.path.join(CLDF, "sources.bib"), "w", encoding="utf-8").write("\n".join(bib))

json.dump({"entries": web, "sources": web_sources},
          open(os.path.join(DOCS, "data.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))

# ---------- list of sources page ----------
E = html.escape
rows = []
for name, v in web_sources.items():
    pubs = "".join(f"<li><span class=k>[{E(p[0])}]</span> {E(p[1])}</li>" for p in v["pubs"])
    eds = " · ".join(f'<a href="{e[0]}.html">{E(e[1])}</a>' for e in v["eds"])
    rows.append(f'<div class="src" id="{E(v["key"])}"><div class="abbr">{E(name)}</div><div>'
                f'<div>{E(v["author"])}{", " if v["author"] else ""}{E(v["title"])}</div>'
                + (f"<ul>{pubs}</ul>" if pubs else "")
                + (f'<div class="ed">Text in the book: {eds}</div>' if eds else "") + "</div></div>")
edlist = "".join(f'<li><a href="{i}.html">{E(t)}</a></li>' for i, t in [
    ("1", "Источник 1. Записи Хр. Барданеса, 1775 г."), ("2", "Источник 2. Записи И. Рюдигера (синти), 1777 г."),
    ("3", "Источник 3. Запись Х. Л. Кр. Бакмейстера, 1778 г."), ("4", "Источник 4. Запись Х. Л. Кр. Бакмейстера, 1782 г."),
    ("5", "Источник 5. Запись В. Ф. Зуева (сэрвицкий), 1781 г."), ("6", "Источник 6. Материалы П. С. Палласа"),
    ("7", "Источник 7. Словарь Т. Нарбута"), ("8a", "Источник 8а. Грамматика и словарь М. Григорьева, 1851 г."),
    ("8b", "Источник 8б. Словарь М. Григорьева (дополнение, 1852 г.)"), ("9a", "Источник 9а. Грамматика В. Н. Добровольского, 1893 г."),
    ("9b", "Источник 9б. Словарь В. Н. Добровольского"), ("9v", "Источник 9в. Описание поездки к цыганам в с. Кудрявцево"),
    ("9g", "Источник 9г. Слова, записанные от зарубежных цыган"), ("9d", "Источник 9д. Впечатления киселёвских цыган о приезжих цыганах"),
    ("9e", "Источник 9е. Посещение австрийскими цыганами деревни в Смоленской губернии"),
    ("10", "Источник 10. Записи Г. Ванцяна (кэлдэрарский), 1890–1894 гг.")])
arch_html, last = [], None
for c, line in archive_rows:
    if c != last:
        arch_html.append(f"<h3>{E('Электронные базы данных' if c == 'ELECTRONIC' else c or '')}</h3>"); last = c
    arch_html.append(f"<div class=arch>{E(line)}</div>")
page = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sources — North-Eastern Romani in 18th–19th-century sources</title><style>
:root{{--bg:#faf8f4;--panel:#fff;--ink:#1f1d1a;--muted:#6b665e;--line:#e4dfd6;--accent:#8a3b12;
--data:"Charis SIL","Gentium Plus","Noto Serif",Cambria,"Times New Roman",serif;--ui:system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif}}
@media (prefers-color-scheme:dark){{:root{{--bg:#171614;--panel:#201f1c;--ink:#ece8e1;--muted:#a39d93;--line:#35322d;--accent:#e39a6c}}}}
body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 var(--ui)}}
.w{{max-width:900px;margin:0 auto;padding:22px 20px 60px}} a{{color:var(--accent)}}
h1{{font:600 22px var(--data);margin:8px 0}} h2{{font:600 17px var(--data);margin:28px 0 8px}} h3{{font:600 14px var(--ui);color:var(--muted);margin:16px 0 4px}}
.src{{display:grid;grid-template-columns:130px 1fr;gap:12px;background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:10px 14px;margin:8px 0;font-family:var(--data);scroll-margin-top:10px}}
.src:target{{outline:2px solid var(--accent)}} .abbr{{font-weight:600;color:var(--accent)}}
ul{{margin:6px 0 0;padding-left:18px;font-size:14px;color:var(--muted)}} .k{{color:var(--ink)}} .ed{{margin-top:6px;font:13px var(--ui)}}
.arch{{font-family:var(--data);font-size:14px;margin:2px 0 2px 12px}} ol li{{font-family:var(--data);margin:3px 0}}
@media(max-width:600px){{.src{{grid-template-columns:1fr}}}}
</style></head><body><div class="w"><a href="../index.html">← Word index</a>
<h1>Sources</h1>
<p>Sources of the forms in the index, as abbreviated in the book, with the description from the list of sources (pp. 8–9) and the publication from the bibliography. Sources edited in the book link to their text.</p>
{''.join(rows)}
<h2>Texts of the sources (part 2 of the book)</h2><ol style="list-style:none;padding:0">{edlist}</ol>
<h2>Archival sources</h2>{''.join(arch_html)}
</div></body></html>"""
open(os.path.join(DOCS, "sources", "index.html"), "w", encoding="utf-8").write(page)

linked = sum(1 for a in atts if a["Edition_Page"]); edit = sum(1 for a in atts if a["Edition"])
print(len(entries), "entries/subentries;", len(senses), "senses;", len(atts), "attestations;", len(used_sources), "source-years")
print("derivation links", sum(1 for e in entries if e["Derived_From_ID"]), "of", sum(1 for e in entries if e["Derived_From"]),
      "; forms located in edited texts", linked, "of", edit,
      "; senses without English", sum(1 for s in senses if not s["Description_English"]))

# ---------- search page ----------
tpl = open(os.path.join(HERE, "index.template.html"), encoding="utf-8").read()
page = tpl.replace("__REPO__", os.environ.get("REPO", "burushona"))
open(os.path.join(DOCS, "index.html"), "w", encoding="utf-8").write(page)
open(os.path.join(DOCS, ".nojekyll"), "w").write("")
