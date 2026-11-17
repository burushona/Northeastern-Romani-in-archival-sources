"""Transliteration of Cyrillic text.

romani(): Cyrillic source forms -> Latin, Romanist conventions (č š ž x c, aspirates th kh ph čh,
          ʼ for palatalisation). Letter-based and reversible: е/я/ю/ё after a consonant give ʼe ʼa ʼu ʼo,
          elsewhere je ja ju jo (after hushing ч ш ж щ and Patkanov's g just e a u o); э gives e; ь gives ʼ; word-final/medial ъ is dropped; ѣ gives ě.
          Stress marks and other diacritics of the source are kept. In Cyrillic forms Latin g is
          Patkanov's letter for dž (gювли́ткас), Latin h marks aspiration (пhурдэно́).
russian(): Russian meanings -> scholarly (linguistic) transliteration:
          ж ž, х x, ц c, ч č, ш š, щ šč, ы y, э è, ю ju, я ja, ё ë, й j, ь ʹ, ъ ʺ, ѣ ě, і i, ѳ f, ѵ y.
"""
import re, unicodedata

PAL = "ʼ"  # U+02BC
CONS = set("бвгджзклмнпрстфхцчшщй") | set("bcdfghjklmnpqrstvwxzčšžłś")

RU = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "ë", "ж": "ž", "з": "z",
    "и": "i", "й": "j", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r",
    "с": "s", "т": "t", "у": "u", "ф": "f", "х": "x", "ц": "c", "ч": "č", "ш": "š", "щ": "šč",
    "ъ": "ʺ", "ы": "y", "ь": "ʹ", "э": "è", "ю": "ju", "я": "ja", "і": "i", "ѣ": "ě", "ѳ": "f",
    "ѵ": "y", "ў": "ŭ", "є": "je", "ї": "ji", "ґ": "g",
}

ROM_BASE = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "ж": "ž", "з": "z", "и": "i", "й": "j",
    "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t",
    "у": "u", "ф": "f", "х": "x", "ц": "c", "ч": "č", "ш": "š", "щ": "šč", "ы": "y", "э": "e",
    "і": "i", "ѣ": "ě", "ѳ": "f", "ѵ": "i", "ў": "ŭ", "ь": PAL, "ъ": "",
}
IOT = {"е": "e", "я": "a", "ю": "u", "ё": "o"}
DIGRAPH = {"тх": "th", "кх": "kh", "пх": "ph", "чх": "čh", "дж": "dž"}

HUSH = set("чшжщg")
CYR = re.compile(r"[Ѐ-ӿ]")


def has_cyrillic(s):
    return bool(CYR.search(s))


def _case(src, out):
    if src.isupper() and out:
        return out[0].upper() + out[1:]
    return out


def romani(s):
    if not has_cyrillic(s):
        return unicodedata.normalize("NFC", s)
    s = unicodedata.normalize("NFC", s)
    out = []
    prev_base = ""  # last base (non-combining) source letter, lower case
    i = 0
    while i < len(s):
        ch = s[i]
        lo = ch.lower()
        two = s[i:i + 2].lower()
        if two in DIGRAPH:
            out.append(_case(ch, DIGRAPH[two])); prev_base = two[1]; i += 2; continue
        if unicodedata.combining(ch):
            out.append(ch); i += 1; continue
        if lo in IOT:
            v = IOT[lo]
            if prev_base in HUSH:
                r = v  # palatality not distinctive after hushing consonants: чя -> ča, gю -> džu
            elif prev_base in CONS:
                r = PAL + v
            else:
                r = "j" + v
            out.append(_case(ch, r))
        elif lo in ROM_BASE:
            out.append(_case(ch, ROM_BASE[lo]))
        elif lo == "g":  # Patkanov's g = dž
            out.append(_case(ch, "dž"))
        else:
            out.append(ch)
        prev_base = lo if lo not in "ьъ" else lo
        i += 1
    r = unicodedata.normalize("NFC", "".join(out))
    return r


def russian(s):
    if not has_cyrillic(s):
        return s
    s = unicodedata.normalize("NFC", s)
    out = []
    for ch in s:
        lo = ch.lower()
        if lo in RU:
            out.append(_case(ch, RU[lo]))
        else:
            out.append(ch)
    return unicodedata.normalize("NFC", "".join(out))


if __name__ == "__main__":
    for w in ["адя́кэ", "адя́ке", "тэачакирэ́с", "адатхы́р", "чаорья́кэ", "gювли́ткас", "пhурдэно́",
              "балова́съ", "ачё́м-пэ", "Ягори́", "джуклоро́", "мангё́м", "вѣ́ко", "адат’рэ́", "яг", "бияндло́"]:
        print(w, "->", romani(w))
    for w in ["оставлять", "жёлудь", "Подлинно; обыкновенно", "щенокъ", "висѣлица", "этотъ, тотъ"]:
        print(w, "->", russian(w))
