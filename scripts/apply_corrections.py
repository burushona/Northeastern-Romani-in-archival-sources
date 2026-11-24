"""Apply scripts/corrections.tsv (corrections of misprints in the book) to the paragraphs extracted from the PDF.
Unchanged characters keep their formatting; inserted characters are set in roman.

usage: apply_corrections.py paras.json corrections.tsv out.json
"""
import csv, difflib, json, sys, unicodedata

paras = json.load(open(sys.argv[1], encoding="utf-8"))
rows = list(csv.DictReader(open(sys.argv[2], encoding="utf-8"), delimiter="\t"))
nfc = lambda s: unicodedata.normalize("NFC", s)

for p in paras:
    for s in p["segs"]:
        s[0] = nfc(s[0])

for r in rows:
    printed, corrected = nfc(r["printed"]), nfc(r["corrected"])
    hits = []
    for p in paras:
        chars = [(c, s[1], s[2]) for s in p["segs"] for c in s[0]]
        text = "".join(c[0] for c in chars)
        i = text.find(printed)
        if i == -1:
            continue
        hits.append(p["i"])
        new = chars[:i]
        old = chars[i:i + len(printed)]
        for op, a1, a2, b1, b2 in difflib.SequenceMatcher(None, printed, corrected, autojunk=False).get_opcodes():
            if op == "equal":
                new += old[a1:a2]
            elif op == "replace" and a2 - a1 == b2 - b1:
                new += [(corrected[b1 + k], old[a1 + k][1], old[a1 + k][2]) for k in range(b2 - b1)]
            else:
                new += [(c, False, False) for c in corrected[b1:b2]]
        new += chars[i + len(printed):]
        segs = []
        for c, b, it in new:
            if segs and segs[-1][1] == b and segs[-1][2] == it:
                segs[-1][0] += c
            else:
                segs.append([c, b, it])
        p["segs"] = segs
        p.setdefault("corrections", []).append(r["note"])
    if len(hits) != 1:
        sys.exit(f"correction for {r['entry']} matched {len(hits)} paragraphs (must be exactly 1): {printed}")

json.dump(paras, open(sys.argv[3], "w", encoding="utf-8"), ensure_ascii=False)
print(len(rows), "corrections applied")
