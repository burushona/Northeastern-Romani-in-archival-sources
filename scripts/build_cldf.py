"""parsed.json -> CLDF Dictionary dataset (cldf/) + compact JSON for the search page (docs/data.json)."""
import csv, json, os, re, sys, unicodedata
sys.path.insert(0, os.path.dirname(__file__))
from translit import romani, russian, has_cyrillic

src, root = sys.argv[1], sys.argv[2]
D = json.load(open(src))
CLDF = os.path.join(root, "cldf")
DOCS = os.path.join(root, "docs")
os.makedirs(CLDF, exist_ok=True); os.makedirs(DOCS, exist_ok=True)

LANG = "NERomani"
# abbreviation as in the book -> neutral ASCII key stem (full references to be added in sources.bib)
ABBR = {
    "Бард.": "Bard", "Бакм.": "Bakm", "Пал.": "Pal", "Лек.": "Lek", "Narb.": "Narb", "Bor.": "Bor",
    "Григ.": "Grig", "Köp.": "Kop", "Gl.": "Gl", "Поп.": "Pop", "Duhm.": "Duhm", "Гол.": "Gol",
    "Dow.-S.": "DowS", "Ziel.": "Ziel", "Добр.": "Dobr", "Шт.": "Sht", "Sowa": "Sowa",
    "Патк.": "Patk", "Пог.": "Pog", "Дор.": "Dor",
}

def key(abbr, year):
    return f"{ABBR[abbr]}{year}"

def nf(s):
    return unicodedata.normalize("NFC", s or "")

entries, senses, atts = [], [], []
used_sources = {}
web = []

def add_forms(entry_id, forms):
    out = []
    for k, f in enumerate(forms, 1):
        keys = [key(f["source"], y) for y in f["years"]] if f["source"] else []
        for y in f["years"]:
            used_sources.setdefault(key(f["source"], y), (f["source"], y))
        form = nf(f["form"])
        row = {
            "ID": f"{entry_id}-{k}",
            "Entry_ID": entry_id,
            "Form": form,
            "Form_Latin": romani(form),
            "Script": "Cyrl" if has_cyrillic(form) else "Latn",
            "Source": ";".join(keys),
            "Source_Abbreviation": (f["source"] + " " + ", ".join(f["years"])) if f["source"] else "",
            "Editor_Note": nf(f["pre_note"]),
            "Source_Annotation": nf(f["annotation"]),
            "Source_Annotation_Latin": romani(f["annotation"]) if has_cyrillic(f["annotation"]) else "",
            "Source_Glosses": ";".join(nf(g) for g in f["glosses"]),
            "Source_Glosses_Latin": ";".join(russian(g) for g in f["glosses"]) if any(has_cyrillic(g) for g in f["glosses"]) else "",
            "Sense_Numbers": ";".join(f["senses"]),
            "Uncertain": "true" if f["uncertain"] else "false",
            "Same_Form_As_Previous": "true" if f.get("repeated") else "false",
        }
        atts.append(row); out.append(row)
    return out

n = 0
for e in D["entries"]:
    n += 1
    eid = f"e{n:04d}"
    ws = [s for s in e["senses"]]
    mean = nf(e["meaning"])
    entries.append({
        "ID": eid, "Language_ID": LANG, "Headword": nf(e["headword"]),
        "Paradigm": nf(e["paradigm"]), "Part_Of_Speech": nf(e["pos"]),
        "Main_Entry_ID": "", "Subentry_Type": "",
        "Meaning": mean, "Meaning_Latin": russian(mean),
        "Distribution": "; ".join(e["notes"]["distribution"]),
        "Derived_From": "; ".join(e["notes"]["derivation"]),
        "Composition": "; ".join(e["notes"]["composition"]),
        "Header_Notes": "; ".join(e["notes"]["other"]),
        "Etymology": nf(e["etymology"]), "Etymology_Latin": russian(nf(e["etymology"])) if e["etymology"] else "",
        "See_Also": ";".join(nf(x) for x in e["see_also"]),
        "Letter": e["letter"], "Book_Order": n,
    })
    for k, (num, desc) in enumerate(ws, 1):
        senses.append({"ID": f"{eid}-s{k}", "Entry_ID": eid, "Sense_Number": num,
                       "Description": nf(desc), "Description_Latin": russian(nf(desc))})
    fr = add_forms(eid, e["forms"])
    subs_web = []
    for j, s in enumerate(e["subentries"], 1):
        sid = f"{eid}-{j:02d}"
        sm = nf(s["meaning"])
        entries.append({
            "ID": sid, "Language_ID": LANG, "Headword": nf(s["headword"]), "Paradigm": "",
            "Part_Of_Speech": "", "Main_Entry_ID": eid, "Subentry_Type": s["label"],
            "Meaning": sm, "Meaning_Latin": russian(sm), "Distribution": "", "Derived_From": "",
            "Composition": "", "Header_Notes": "", "Etymology": "", "Etymology_Latin": "",
            "See_Also": ";".join(nf(x) for x in s["see_also"]), "Letter": s["letter"], "Book_Order": n,
        })
        if sm:
            senses.append({"ID": f"{sid}-s1", "Entry_ID": sid, "Sense_Number": "",
                           "Description": sm, "Description_Latin": russian(sm)})
        sfr = add_forms(sid, s["forms"])
        subs_web.append({"id": sid, "l": s["label"], "h": nf(s["headword"]), "m": sm, "ml": russian(sm),
                         "sa": [nf(x) for x in s["see_also"]],
                         "f": [[r["Form"], r["Form_Latin"], r["Source_Abbreviation"], r["Editor_Note"],
                                r["Source_Annotation"], r["Uncertain"] == "true"] for r in sfr]})
    web.append({"id": eid, "L": e["letter"], "h": nf(e["headword"]), "p": nf(e["paradigm"]), "pos": nf(e["pos"]),
                "m": mean, "ml": russian(mean),
                "n": "; ".join(e["notes"]["distribution"] + ["← " + x for x in e["notes"]["derivation"]]
                               + ["= " + x for x in e["notes"]["composition"]] + e["notes"]["other"]),
                "et": nf(e["etymology"]), "sa": [nf(x) for x in e["see_also"]],
                "f": [[r["Form"], r["Form_Latin"], r["Source_Abbreviation"], r["Editor_Note"],
                       r["Source_Annotation"], r["Uncertain"] == "true"] for r in fr],
                "s": subs_web})

def write(name, rows):
    with open(os.path.join(CLDF, name), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)

write("entries.csv", entries)
write("senses.csv", senses)
write("attestations.csv", atts)
write("languages.csv", [{"ID": LANG, "Name": "North-Eastern Romani (18th–19th-century sources)",
                         "Glottocode": "", "ISO639P3code": "rmy", "Macroarea": "Eurasia"}])

# ---- sources.bib ----
def bibesc(s):
    return s.replace("{", "\\{").replace("}", "\\}")

bib = []
bib.append("""@book{Kozhanov2025,
  author = {Кожанов, Кирилл А.},
  title = {Цыганский язык в источниках XVIII–XIX вв. (из архивов России и Литвы)},
  address = {Санкт-Петербург},
  publisher = {Маматов},
  year = {2025},
  isbn = {978-5-91076-297-2}
}
""")
SRC = json.load(open(os.path.join(os.path.dirname(__file__), "sources.json"), encoding="utf-8"))
def src_info(abbr, year):
    for v in SRC.values():
        if v["abbr"] == abbr and year in v["years"]:
            return v
    return None
for k in sorted(used_sources, key=lambda x: (used_sources[x][1], x)):
    abbr, year = used_sources[k]
    v = src_info(abbr, year)
    if v is None:
        bib.append(f"""@misc{{{k},
  title = {{“{abbr} {year}”: not in the list of sources of Kozhanov 2025, probably a misprint}},
  year = {{{year}}},
  note = {{Abbreviation in Kozhanov 2025: {abbr} {year}}}
}}
""")
        continue
    pubs = "; ".join(f"[{p['key']}] {p['reference']}" for p in v["publications"])
    fields = [f"  author = {{{bibesc(v['author'])}}}" if v["author"] else None,
              f"  title = {{{bibesc(v['description'][len(v['author']) + 2:] if v['author'] and v['description'].startswith(v['author'] + ', ') else v['description'])}}}",
              f"  year = {{{year}}}",
              f"  note = {{Abbreviation in Kozhanov 2025: {abbr} {year}" + (f". Published in: {bibesc(pubs)}" if pubs else "") + "}"]
    bib.append(f"@misc{{{k},\n" + ",\n".join(f for f in fields if f) + "\n}\n")
# archival sources as listed in the book
arch = [l.strip() for l in open(os.path.join(os.path.dirname(__file__), "archives.txt"), encoding="utf-8") if l.strip()]
cur = None; ai = 0
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
    else:
        cur = line
open(os.path.join(CLDF, "sources.bib"), "w", encoding="utf-8").write("\n".join(bib))

json.dump({"entries": web,
           "sources": {f"{a} {y}": k for k, (a, y) in used_sources.items()}},
          open(os.path.join(DOCS, "data.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print(len(entries), "entries/subentries;", len(senses), "senses;", len(atts), "attestations;", len(used_sources), "source-years")

# ---- search page ----
tpl = open(os.path.join(os.path.dirname(__file__), "index.template.html"), encoding="utf-8").read()
repo = os.environ.get("REPO", "burushona")
page = tpl.replace("__REPO__", repo)
open(os.path.join(DOCS, "index.html"), "w", encoding="utf-8").write(page)
# self-contained preview with the data embedded (for opening locally / as an artifact)
data = open(os.path.join(DOCS, "data.json"), encoding="utf-8").read().replace("</", "<\\/")
open(os.path.join(root, "preview.html"), "w", encoding="utf-8").write(page.replace("/*DATA*/null", data))
open(os.path.join(DOCS, ".nojekyll"), "w").write("")
