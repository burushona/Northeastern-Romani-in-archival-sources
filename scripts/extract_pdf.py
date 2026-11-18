"""Extract the word index from the published PDF into the same format as extract.py (paras.json),
keeping bold (Brygada Bold = headwords) and italic (Cambria Italic = forms) from the fonts.

usage: extract_pdf.py book.pdf first_page last_page hyphenated_words.txt out.json
(hyphenated_words.txt lists words that contain a real hyphen; it decides whether a hyphen at a line end is kept)
"""
import json, re, sys, unicodedata
import pdfplumber

pdf_path, first, last, hyph_file, out = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4], sys.argv[5]

LEFT = 56.7          # first line of an entry
INDENT = 73.7        # continuation lines and sub-paragraphs
SUB_LABELS = ("уменьш.", "прич.", "нар.", "порядк.", "сравн.", "срав.", "деепр.", "отр.")

word_hyph = set(unicodedata.normalize("NFC", l.strip()) for l in open(hyph_file, encoding="utf-8") if l.strip())


sys.path.insert(0, __import__("os").path.dirname(__file__))
from pdflines import style, page_lines


paras, cur = [], None
HY = []
right = 0
with pdfplumber.open(pdf_path) as pdf:
    all_lines = []
    for pno in range(first - 1, last):
        pl = page_lines(pdf.pages[pno])
        for L in pl:
            if re.fullmatch(r"\d{3}", L["text"].strip()):
                continue  # page number
            L["page"] = pno + 1
            all_lines.append(L)
    right = max(L["x1"] for L in all_lines)

    def flush():
        if cur and cur["items"]:
            segs = []
            for t, b, i in cur["items"]:
                if segs and segs[-1][1] == b and segs[-1][2] == i:
                    segs[-1][0] += t
                else:
                    segs.append([t, b, i])
            for s in segs:
                s[0] = unicodedata.normalize("NFC", s[0])
            paras.append({"i": len(paras), "style": cur["style"], "segs": segs, "page": cur["page"]})

    prev = None
    in_archive = False
    for L in all_lines:
        t = L["text"].strip()
        heading = (L["size"] > 10.5 and not re.fullmatch(r"\d{3}", t)) or t in ("Архивные источники", "Электронные базы данных")
        if heading:
            flush(); cur = {"style": "Heading 2", "items": list(L["items"]), "page": L["page"]}; flush(); cur = None; prev = None
            if t == "Архивные источники":
                in_archive = True
            continue
        if in_archive:
            # list of archives: one paragraph per line, except wrapped continuation lines (indented)
            if cur is not None and L["x0"] > INDENT + 15 and prev is not None:
                cur["items"].append((" ", False, False)); cur["items"] += list(L["items"])
            else:
                flush(); cur = {"style": "Normal", "items": list(L["items"]), "page": L["page"]}
            prev = L
            continue
        starts_entry = abs(L["x0"] - LEFT) < 3
        prev_short = prev is not None and prev["x1"] < right - 25
        def first_bold_after_label():
            # label (italic) followed directly by a bold headword, or by '?:' / ':'
            k = 0
            while k < len(L["items"]) and (L["items"][k][2] or L["items"][k][0] in " ."):
                k += 1
            rest = "".join(i[0] for i in L["items"][k:k + 3])
            return (k < len(L["items"]) and L["items"][k][1]) or re.match(r"\s*\??:", rest)
        sub_start = abs(L["x0"] - INDENT) < 3 and (
            t.startswith(("Этим.", "Этим:")) or
            (t.startswith(SUB_LABELS) and L["items"][0][2] and first_bold_after_label()) or
            (bool(re.match(r"^[^\s:]+-:", t)) and L["items"][0][1])
        )
        if cur is None or starts_entry or sub_start:
            flush()
            cur = {"style": "Normal", "items": ([("\t", False, False)] if not starts_entry else []) + list(L["items"]), "page": L["page"]}
        else:
            # join with the previous line: hyphenation or space
            last_txt = "".join(i[0] for i in cur["items"][-12:])
            if last_txt.endswith("-"):
                m1 = re.search(r"(\S+)-$", last_txt)
                m2 = re.match(r"(\S+)", L["text"])
                cand = (m1.group(1) if m1 else "") + "-" + (m2.group(1).rstrip(",;:)»") if m2 else "")
                keep = any(cand.rstrip(",;:)»") in w for w in word_hyph)
                HY.append((cand, keep))
                if not keep:
                    cur["items"].pop()  # soft hyphenation: drop the hyphen
                cur["items"] += list(L["items"])
            else:
                cur["items"].append((" ", cur["items"][-1][1] and L["items"][0][1], cur["items"][-1][2] and L["items"][0][2]))
                cur["items"] += list(L["items"])
        prev = L
    flush()

# drop the intro and everything after the index
start = next(i for i, p in enumerate(paras) if p["style"] == "Heading 2")
paras = paras[:start] + paras[start:]
json.dump(paras, open(out, "w"), ensure_ascii=False)
print(len(paras), "paragraphs; right margin", round(right, 1))

