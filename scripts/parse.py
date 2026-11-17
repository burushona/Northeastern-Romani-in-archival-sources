"""Parse the Word index (paras.json from extract.py) into structured entries.

Formatting conventions used by the book:
  bold   = headwords (and cross-referenced headwords)
  italic = forms cited from the sources, and grammatical labels (POS, уменьш. ...)
"""
import json, re, sys, unicodedata

SRC_ABBR = [
    "Dow.-S.", "Добр.", "Патк.", "Григ.", "Narb.", "Пог.", "Gl.", "Пал.", "Поп.",
    "Гол.", "Бакм.", "Бpакм.", "Шт.", "Köp.", "Бард.", "Duhm.", "Лек.", "Ziel.",
    "Bor.", "Sowa", "Дор.", "Добр", "Патк", "Григ", "Narb",
]
SRC_RE = re.compile(
    r"(?<![\w\-])(" + "|".join(re.escape(a) for a in sorted(SRC_ABBR, key=len, reverse=True))
    + r")\s+(1[6-9]\d\d(?:\s*,\s*1[6-9]\d\d)*)"
)
# normalise typos in abbreviations (reported in qa report)
ABBR_FIX = {"Добр": "Добр.", "Патк": "Патк.", "Григ": "Григ.", "Narb": "Narb.", "Бpакм.": "Бакм."}

SUB_LABELS = ("уменьш.", "прич.", "нар.", "порядк.", "сравн.", "срав.", "деепр.", "отр.")
OPEN, CLOSE = "([«", ")]»"


class Chars:
    """A paragraph as a list of (char, bold, italic, depth) where depth counts ( [ « nesting."""

    def __init__(self, segs):
        self.c = []
        d = 0
        for text, b, it in segs:
            for ch in text:
                if ch in CLOSE:
                    d = max(0, d - 1)
                    self.c.append((ch, b, it, d))
                elif ch in OPEN:
                    self.c.append((ch, b, it, d))
                    d += 1
                else:
                    self.c.append((ch, b, it, d))

    def text(self, a=0, b=None):
        return "".join(x[0] for x in self.c[a:b])


def clean(s):
    s = unicodedata.normalize("NFC", s)
    s = s.replace("\xa0", " ").replace("\t", " ")
    return re.sub(r"\s+", " ", s).strip()


def runs(chars, a, b):
    """group chars[a:b] into runs of (text, bold, italic, depth_at_start)"""
    out = []
    for i in range(a, b):
        ch, bo, it, d = chars.c[i]
        if out and out[-1][1] == bo and out[-1][2] == it and not (it and ch == ";"):
            out[-1][0] += ch
        else:
            out.append([ch, bo, it, d, i])
    return out


def find_top(chars, ch_target, a=0, b=None, need_plain=True):
    b = len(chars.c) if b is None else b
    for i in range(a, b):
        ch, bo, it, d = chars.c[i]
        if ch == ch_target and d == 0 and (not need_plain or not it):
            return i
    return -1


def split_top(chars, sep, a, b):
    parts, start = [], a
    for i in range(a, b):
        ch, bo, it, d = chars.c[i]
        if ch == sep and d == 0 and not it:
            parts.append((start, i))
            start = i + 1
    parts.append((start, b))
    return parts


def bold_words(chars, a, b):
    out, cur = [], ""
    for i in range(a, b):
        ch, bo, it, d = chars.c[i]
        if bo:
            cur += ch
        elif cur:
            out.append(clean(cur)); cur = ""
    if cur:
        out.append(clean(cur))
    return [w.strip(" ,.;") for w in out if w.strip(" ,.;")]


# ---------- header ----------

def parse_header(chars, a, b):
    """main-entry header: headword paradigm POS (…) (…) meaning"""
    rs = runs(chars, a, b)
    i = 0
    while i < len(rs) and not rs[i][1]:
        i += 1  # skip leading tab/space
    head = ""
    while i < len(rs) and (rs[i][1] or (head and rs[i][0].strip() == "" and i + 1 < len(rs) and rs[i + 1][1])):
        head += rs[i][0]; i += 1
    pre_par = ""
    # a bold ' -' at the end of the headword run is the start of the paradigm: "baránd -(’)á"
    if re.search(r"\s-$", head.rstrip()):
        head = head.rstrip()[:-1]; pre_par = "-"
        head = head.rstrip()
    # material glued to the bold headword without a space belongs to it: baripé(n), džind(l)|ó
    while head and not head[-1].isspace() and i < len(rs) and rs[i][0][:1] not in (" ", "\t", "") and not pre_par:
        m = re.match(r"\S+", rs[i][0])
        glue = m.group(0)
        if glue.startswith(("(←", "(=")) or (rs[i][2] and not head.endswith("(")):
            break
        head += glue
        if len(glue) == len(rs[i][0]):
            i += 1
        else:
            rs[i][0] = rs[i][0][len(glue):]
            rs[i][4] += len(glue)
            break
    paradigm = pre_par
    j = next((k for k in range(i, len(rs)) if rs[k][2] and rs[k][3] == 0 and rs[k][0].strip()), None)
    if j is not None and j > i:
        # everything up to the grammatical label: inflected forms, also "(реже bagél) bága", "(вин. lés)"
        paradigm = clean(pre_par + "".join(r[0] for r in rs[i:j]))
        i = j
    while i < len(rs) and not rs[i][2]:
        if rs[i][3] > 0 or rs[i][0].lstrip().startswith("("):
            break
        paradigm += rs[i][0]; i += 1
    pos = ""
    while i < len(rs) and (rs[i][2] or (pos and re.fullmatch(r"[\s.,]*", rs[i][0]))):
        pos += rs[i][0]; i += 1
    # a trailing '.' after POS sits in the next plain run
    rest_start = rs[i][4] if i < len(rs) else b
    rest = chars.text(rest_start, b)
    if pos and rest.startswith("."):
        pos += "."; rest = rest[1:]
    notes = {"distribution": [], "derivation": [], "composition": [], "other": []}
    rest = rest.strip()
    while rest.startswith("("):
        depth, j = 0, 0
        for j, ch in enumerate(rest):
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    break
        inner = clean(rest[1:j])
        if inner.startswith(("есть", "нет")):
            notes["distribution"].append(inner)
        elif inner.startswith("←"):
            notes["derivation"].append(clean(inner[1:]))
        elif inner.startswith("="):
            notes["composition"].append(clean(inner[1:]))
        else:
            notes["other"].append(inner)
        rest = rest[j + 1:].strip()
    return clean(head), clean(paradigm), clean(pos).strip(), notes, clean(rest)


def split_senses(meaning):
    meaning = meaning.strip().rstrip(":").strip()
    if not meaning:
        return []
    parts = re.split(r"(?:^|;\s*)(\d+)\.\s+", meaning)
    if len(parts) == 1:
        return [("", meaning)]
    out = []
    if parts[0].strip():
        out.append(("", parts[0].strip(" ;")))
    for k in range(1, len(parts), 2):
        out.append((parts[k], parts[k + 1].strip(" ;")))
    return out


# ---------- attestation chunks ----------

def parse_annotation(txt):
    """text a source gives after a form: «glosses», + «extra», (grammatical forms) …"""
    txt = clean(txt).strip(" ,;")
    glosses = []
    for m in re.finditer(r"(\+\s*)?«([^»]*)»", txt):
        glosses.append(("+ " if m.group(1) else "") + clean(m.group(2)))
    return txt, glosses


def parse_prenote(txt):
    txt = clean(txt).strip(" ,;")
    senses, uncertain = [], False
    m = re.search(r"\((\d+(?:\s*,\s*\d+)*)\)", txt)
    if m:
        senses = [s.strip() for s in m.group(1).split(",")]
        txt = clean(txt[:m.start()] + txt[m.end():])
    if "(?)" in txt:
        uncertain = True
        txt = clean(txt.replace("^(?)", "").replace("(?)", ""))
    return txt.strip(" ,;"), senses, uncertain


def parse_chunk(chars, a, b, problems, where):
    """one ';'-separated chunk of the attestation list -> list of form dicts"""
    forms = []
    items = []  # ("form", text, start) | ("between", start, end)
    rs = runs(chars, a, b)
    pos = a
    # merge italic runs split only by a hyphen/apostrophe/space (formatting breaks inside one form)
    merged = []
    for r in rs:
        if (len(merged) >= 2 and r[2] and r[3] == 0 and merged[-2][2] and merged[-2][3] == 0
                and not merged[-1][2] and re.fullmatch(r"\s*[-’ʼ']?\s*", merged[-1][0])
                and not merged[-2][0].rstrip().endswith(",")):
            merged[-2][0] += merged[-1][0] + r[0]
            merged.pop()
        else:
            merged.append(list(r))
    rs = merged
    for t, bo, it, d, start in rs:
        if it and d == 0 and t.strip(" ,;"):
            # italic at top level = cited form(s); commas separate forms
            if pos < start:
                items.append(("between", pos, start))
            for f in t.split(","):
                if f.strip():
                    items.append(("form", clean(f), start))
            pos = start + len(t)
    if pos < b:
        items.append(("between", pos, b))

    uncited = []
    pre = {"note": "", "senses": [], "uncertain": False}
    last_form = None

    def new_form(text):
        nonlocal pre
        f = {"form": text, "pre_note": pre["note"], "senses": pre["senses"],
             "uncertain": pre["uncertain"], "annotation": "", "glosses": [],
             "source": None, "years": []}
        if text.endswith("(?)"):
            f["uncertain"] = True
        pre = {"note": "", "senses": list(pre["senses"]) if pre["senses"] else [], "uncertain": False}
        return f

    prev_kind = "start"
    for it in items:
        if it[0] == "form":
            f = new_form(it[1])
            forms.append(f); uncited.append(f); last_form = f
            prev_kind = "form"
            continue
        s, e = it[1], it[2]
        txt = chars.text(s, e)
        if prev_kind == "note":
            prev_kind = "cite"
        # citations inside this stretch (only those at depth 0)
        cites = [m for m in SRC_RE.finditer(txt)
                 if chars.c[s + m.start()][3] == 0 and not chars.c[s + m.start()][2]]
        cursor = 0
        for m in cites:
            seg = txt[cursor:m.start()]
            if prev_kind == "form" and last_form is not None:
                # split at first top-level comma: before -> annotation of previous form
                ci = top_comma(chars, s + cursor, s + m.start())
                if ci is None:
                    post, prenote = seg, ""
                else:
                    post, prenote = txt[cursor:ci - s], txt[ci - s + 1:m.start()]
                add_annotation(last_form, post)
                if prenote.strip(" ,;"):
                    # e.g. "кирко́ Григ. 1851, ж. «табакъ» Григ. 1852": the note refers back to the same form
                    f = dict(last_form); f["annotation"] = ""; f["glosses"] = []; f["repeated"] = True
                    f["source"] = None; f["years"] = []
                    note, senses, unc = parse_prenote(re.sub(r"(\+\s*)?«[^»]*»|\([^)]*\)", "", prenote))
                    f["pre_note"] = note
                    add_annotation(f, prenote[len(prenote) - len(prenote.lstrip()):] if False else " ".join(re.findall(r"(?:\+\s*)?«[^»]*»|\([^)]*\)", prenote)))
                    forms.append(f); uncited.append(f)
            elif seg.strip(" ,;") and last_form is not None and prev_kind == "cite":
                # same form, further information from another source: "… Григ. 1851, + «овца» Григ. 1852"
                f = dict(last_form); f["annotation"] = ""; f["glosses"] = []; f["pre_note"] = ""
                f["source"] = None; f["years"] = []; f["repeated"] = True
                add_annotation(f, seg)
                forms.append(f); uncited.append(f)
            elif seg.strip(" ,;"):
                problems.append((where, "text before citation without a form: " + clean(seg)))
            abbr = ABBR_FIX.get(m.group(1), m.group(1))
            years = [y.strip() for y in m.group(2).split(",")]
            if not uncited:
                problems.append((where, f"citation without form: {abbr} {m.group(2)}"))
            for f in uncited:
                f["source"], f["years"] = abbr, years
            uncited = []
            cursor = m.end()
            prev_kind = "cite"
        seg = txt[cursor:]
        if prev_kind == "form" and last_form is not None:
            ci = top_comma(chars, s + cursor, e)
            if ci is None:
                # whole stretch belongs to the previous form unless it is clearly a pre-note
                add_annotation(last_form, seg)
            else:
                add_annotation(last_form, txt[cursor:ci - s])
                set_pre(pre, txt[ci - s + 1:])
        else:
            if prev_kind == "cite" and ";" in seg:
                pre["senses"] = []  # sense markers do not carry over a ';'
            set_pre(pre, seg)
        if cursor < len(txt) and txt[cursor:].strip(" ,;"):
            if prev_kind == "cite":
                prev_kind = "note"
    for f in uncited:
        problems.append((where, "form without source: " + f["form"]))
    return forms


def top_comma(chars, a, b):
    for i in range(a, b):
        ch, bo, it, d = chars.c[i]
        if ch in ",;" and d == 0 and not it:
            return i
    return None


def add_annotation(f, txt):
    raw, gl = parse_annotation(txt)
    if raw:
        f["annotation"] = clean((f["annotation"] + " " + raw))
        f["glosses"] += gl
        if "(?)" in raw:
            f["uncertain"] = True


def set_pre(pre, txt):
    note, senses, unc = parse_prenote(txt)
    if note:
        pre["note"] = clean(pre["note"] + " " + note)
    if senses:
        pre["senses"] = senses
    if unc:
        pre["uncertain"] = True


def parse_body(chars, a, b, problems, where):
    """the whole attestation list is one stream: each citation closes all forms since the previous one"""
    see_also, extra_meaning = [], ""
    # cross-references: 'см. также …' at top level runs to the end of the paragraph
    txt = chars.text(a, b)
    for m in re.finditer(r"см\. также", txt):
        i = a + m.start()
        if chars.c[i][3] == 0 and not chars.c[i][2]:
            see_also = bold_words(chars, i, b) or [clean(txt[m.start():])]
            b = i
            break
    # a meaning given inside the body before the first form ("субст. ж. ‘сундук’: …")
    ci = find_top(chars, ":", a, b)
    if ci != -1 and not any(chars.c[x][2] for x in range(a, ci) if chars.c[x][3] == 0 and chars.c[x][0].strip()):
        extra_meaning = clean(chars.text(a, ci))
        a = ci + 1
    forms = parse_chunk(chars, a, b, problems, where)
    return forms, see_also, extra_meaning


# ---------- driver ----------

def main(src, dst):
    P = json.load(open(src))
    entries, problems = [], []
    letter = None
    current = None
    in_index = False
    archive = []
    for p in P:
        full = "".join(s[0] for s in p["segs"])
        t = clean(full)
        if t.startswith("Архивные источники"):
            in_index = "archive"; continue
        if in_index == "archive":
            if t.startswith("Электронные базы данных"):
                archive.append(t); continue
            archive.append(t); continue
        if p["style"].startswith("Heading 2"):
            letter = t; in_index = True; continue
        if in_index == "archive":
            archive.append(t); continue
        if not in_index or not t:
            continue
        # a citation set in italics by mistake ("длу́го м. Патк. 1900" all italic): make it roman again
        segs = []
        for text, b, it in p["segs"]:
            m = SRC_RE.search(text) if it else None
            if m:
                pre = text[:m.start()]
                g = re.search(r"\s(?:м|ж|с)\.\s*$", pre)
                cut = g.start() if g else len(pre.rstrip())
                segs += [[text[:cut], b, True], [text[cut:], b, False]]
            else:
                segs.append([text, b, it])
        ch = Chars(segs)
        where = t[:60]
        if t.startswith(("Этим.", "Этим:")):
            if current is None:
                problems.append((where, "etymology without entry")); continue
            current["etymology"] = clean(re.sub(r"^Этим\.?:?", "", t))
            continue
        colon = find_top(ch, ":")
        # leading label?
        first_plain = next((x for x in ch.c if x[0].strip()), None)
        is_label = first_plain is not None and first_plain[2] and t.startswith(SUB_LABELS)
        hb = bold_words(ch, 0, colon if colon != -1 else len(ch.c))
        is_prefix = not is_label and bool(re.match(r"^[^\s:]+-:", t))
        if is_prefix and not (hb and hb[0].endswith("-")):
            hb = [t.split(":")[0]]
        if is_label or is_prefix:
            if current is None:
                problems.append((where, "subentry without main entry")); continue
            header = clean(ch.text(0, colon)) if colon != -1 else t
            label = ""
            if is_label:
                for L in SUB_LABELS:
                    if header.startswith(L):
                        label = L; break
            head = hb[0] if hb else header[len(label):].strip()
            if label == "" and head.endswith("-"):
                head = head.replace(" ", "")
            head = head or "?"
            # meaning in subentry header (rare): text after the bold headword
            after = header[len(label):].strip()
            after = after[len(head):].strip() if after.startswith(head) else ""
            body_forms, see, extra = parse_body(ch, colon + 1, len(ch.c), problems, where) if colon != -1 else ([], [], "")
            sub = {"type": "subentry", "label": label or "prefix", "headword": head,
                   "meaning": clean(" ".join(x for x in (after, extra) if x)),
                   "forms": body_forms, "see_also": see, "letter": letter, "para": p["i"]}
            current["subentries"].append(sub)
            continue
        # main entry
        if colon == -1:
            hdr_end = len(ch.c)
        else:
            hdr_end = colon
        head, paradigm, pos, notes, meaning = parse_header(ch, 0, hdr_end)
        if not head:
            problems.append((where, "paragraph not recognised as entry")); continue
        forms, see, extra = parse_body(ch, colon + 1, len(ch.c), problems, where) if colon != -1 else ([], [], "")
        if extra:
            meaning = clean(meaning + " " + extra)
        # crossrefs at the end of meaning (no attestations) e.g. "… ; см. также X"
        current = {"type": "entry", "headword": head, "paradigm": paradigm, "pos": pos,
                   "notes": notes, "meaning": meaning, "senses": split_senses(meaning),
                   "forms": forms, "see_also": see, "etymology": "", "subentries": [],
                   "letter": letter, "para": p["i"], "raw": t}
        entries.append(current)
    json.dump({"entries": entries, "problems": problems, "archive": archive},
              open(dst, "w"), ensure_ascii=False, indent=1)
    nf = sum(len(e["forms"]) + sum(len(s["forms"]) for s in e["subentries"]) for e in entries)
    print(f"entries {len(entries)}, subentries {sum(len(e['subentries']) for e in entries)}, forms {nf}, problems {len(problems)}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
