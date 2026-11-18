"""Shared PDF helpers: read the lines of a page with bold/italic and diacritics in the right place."""
import re, unicodedata


def style(fontname):
    f = fontname.split("+")[-1].lower()
    return ("bold" in f or "-bo" in f or f.endswith("bd")) and "montserrat" not in f, ("italic" in f or "-it" in f or "oblique" in f)


def page_lines(page):
    H = page.height
    chars = [c for c in page.chars if c["text"]]
    prev = None
    for c in chars:
        c["base"] = H - c["matrix"][5]
        if unicodedata.combining(c["text"][0]):
            c["owner"] = prev   # a combining mark follows its letter in the content stream
        else:
            prev = c   # baseline from the text matrix (font bboxes are unreliable)
    lines = []
    for c in sorted([c for c in chars if c["size"] > 6.5], key=lambda c: c["base"]):
        if lines and c["base"] - lines[-1]["base0"] < 2.5:
            lines[-1]["chars"].append(c)
        else:
            lines.append({"base0": c["base"], "chars": [c]})
    for c in chars:
        if c["size"] <= 6.5:  # superscripts
            min(lines, key=lambda L: abs(L["base0"] - c["base"]))["chars"].append(c)
    for L in lines:
        L["bottom"] = L["base0"]
    out = []
    for L in sorted(lines, key=lambda L: L["bottom"]):
        base = sorted([c for c in L["chars"] if not unicodedata.combining(c["text"][0])], key=lambda c: c["x0"])
        while base and base[0]["text"] == " ":
            base.pop(0)
        marks = [c for c in L["chars"] if unicodedata.combining(c["text"][0])]
        if not [b for b in base if b["text"] != " "]:
            continue
        attach = {id(b): [] for b in base}
        for m in marks:
            cx = (m["x0"] + m["x1"]) / 2
            # base char whose span contains the mark's centre, else nearest to the left
            owner = m.get("owner")
            if owner is None or id(owner) not in attach:
                cand = [b for b in base if b["x0"] < m["x0"] - 0.05 and b["text"] != " "] or base[:1]
                owner = cand[-1]
            attach[id(owner)].append(m)
        items, prev = [], None
        cells, lastx1 = [], None   # column cells: a new cell starts after a gap wider than ~1.5 em
        for b in base:
            sz = b["size"]
            if b["text"] != " " and (lastx1 is None or b["x0"] - lastx1 > 1.5 * sz):
                cells.append({"x0": b["x0"], "start": len(items)})
            if b["text"] == " ":
                if items and items[-1][0] != " ":
                    items.append((" ", items[-1][1], items[-1][2]))
                prev = b
                continue
            if prev is not None and prev["text"] != " " and b["x0"] - prev["x1"] > 0.25 * sz and items and items[-1][0] != " ":
                items.append((" ", items[-1][1], items[-1][2]))
            bo, it = style(b["fontname"])
            txt = b["text"]
            if b["size"] <= 6.5 and txt == "?":
                txt = "(?)"  # superscript question mark = morphologically unclear form
            elif b["size"] <= 6.5 and txt.isdigit():
                txt = txt.translate(str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹"))  # homonym number
            items.append((txt, bo, it, b["size"]))
            for m in attach[id(b)]:
                items.append((m["text"], bo, it, b["size"]))
            prev = b
            lastx1 = b["x1"]
        if not base:
            continue
        while items and items[-1][0] == " ":
            items.pop()
        nb = [b for b in base if b["text"] != " "]
        for k, c in enumerate(cells):
            end = cells[k + 1]["start"] if k + 1 < len(cells) else len(items)
            c["items"] = [i for i in items[c["start"]:end]]
            while c["items"] and c["items"][-1][0] == " ":
                c["items"].pop()
        sizes = items
        items = [i[:3] for i in items]
        out.append({"x0": nb[0]["x0"], "x1": nb[-1]["x1"], "items": items, "cells": cells,
                    "size": max(c["size"] for c in nb),
                    "text": "".join(i[0] for i in items)})
    return out


