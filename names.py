"""
Soyad normalizasyonu ve esnek eşleştirme.

Amaç: metin içi atıftaki soyad ile kaynakçadaki soyadın yazımı farklı olsa bile
aynı kişiyi gösterdiğini anlamak. Kapsanan durumlar:

- Soyad ekleri (partiküller): de, da, do, dos, das, del, de la, van der, von,
  di, du, le, la, al-, el-, bin, ibn ...  ("de Souza" = "De Souza" = "Souza")
- Çift / çoklu soyad: "Demir Yılmaz" = "Demir-Yılmaz"; yalnızca bir soyadla
  yapılan atıf ("Yılmaz") çift soyadlı kayıtla ("Demir Yılmaz") eşleşir
- İspanyolca / Portekizce çift soyad: "García Márquez", "Castro e Silva",
  "Ortega y Gasset"
- Aksan ve harf farkları: "González" = "Gonzalez", "Şahin" = "Sahin",
  "Jørgensen" = "Jorgensen", "Müller" = "Muller"
- Bitişik / ayrı yazım: "LeBlanc" = "Le Blanc", "McDonald" = "Mc Donald"
- Apostrof türleri: "O'Brien" = "O’Brien" = "OBrien"
- Tek harflik yazım hatası: "Kurutkan" ~ "Kurutkam" (uyarı ile eşleşir)
"""
from __future__ import annotations

import re
import unicodedata
from typing import List, Optional

# Aksan ayrıştırması (NFKD) ile çözülemeyen harfler
_SPECIAL_FOLD = {
    "ı": "i", "İ": "i", "ß": "ss", "ø": "o", "Ø": "o", "ł": "l", "Ł": "l",
    "đ": "d", "Đ": "d", "ð": "d", "Ð": "d", "þ": "th", "Þ": "th",
    "æ": "ae", "Æ": "ae", "œ": "oe", "Œ": "oe", "ħ": "h", "Ħ": "h",
}

# Soyadın ayırt edici olmayan parçaları (katlanmış, küçük harf)
PARTICLES = frozenset({
    # Romans dilleri
    "de", "del", "della", "dello", "dei", "degli", "delle", "di", "da", "das",
    "do", "dos", "du", "des", "d", "la", "le", "les", "lo", "los", "las", "l",
    "y", "e", "i",
    # Cermen dilleri
    "van", "von", "vom", "zu", "zum", "zur", "der", "den", "het", "ten", "ter",
    "te", "af", "av", "of",
    # Arapça kökenli
    "al", "el", "bin", "ibn", "ben", "bint", "abu", "ebu",
})

_APOS_CHARS = "'’‘ʼʹ`´"
_SPLIT_RE = re.compile(r"[\s\-‐‑‒–—.,]+")


def fold(text: str) -> str:
    """Aksanları ve büyük/küçük harf farkını gider: 'Gonçalves' -> 'goncalves'."""
    if not text:
        return ""
    out = []
    for ch in text:
        out.append(_SPECIAL_FOLD.get(ch, ch))
    s = unicodedata.normalize("NFKD", "".join(out))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.lower()


def all_tokens(surname: str) -> List[str]:
    """Soyadı parçalarına ayır (partiküller dahil), apostrofları kaldır."""
    s = fold(surname)
    for ch in _APOS_CHARS:
        # "d'Uva" -> "d uva": partikül ayrı parça olur ve sonra elenir
        s = re.sub(rf"\b([dl]){re.escape(ch)}", r"\1 ", s)
        s = s.replace(ch, "")
    return [t for t in _SPLIT_RE.split(s) if t]


def surname_tokens(surname: str) -> List[str]:
    """Ayırt edici soyad parçaları: partiküller atılır.

    Soyad yalnızca partiküllerden oluşuyorsa (ör. Vietnamca "Le", "Do")
    parçalar olduğu gibi bırakılır.
    """
    toks = all_tokens(surname)
    core = [t for t in toks if t not in PARTICLES]
    return core or toks


def _edit_distance_le1(a: str, b: str) -> bool:
    """İki dizgi arasındaki düzenleme mesafesi en çok 1 mi?"""
    if a == b:
        return True
    la, lb = len(a), len(b)
    if abs(la - lb) > 1:
        return False
    if la > lb:
        a, b, la, lb = b, a, lb, la
    i = j = diff = 0
    while i < la and j < lb:
        if a[i] == b[j]:
            i += 1
            j += 1
            continue
        diff += 1
        if diff > 1:
            return False
        if la == lb:
            i += 1
        j += 1
    return True


def match_surnames(a: Optional[str], b: Optional[str]) -> Optional[str]:
    """İki soyadı karşılaştır.

    Döndürür:
      "exact"   : ayırt edici parçalar birebir aynı
      "variant" : aynı kişi, farklı yazım (eksik soyad, tire, bitişik yazım,
                  fazladan sözcük)
      "typo"    : tek harflik fark (olası yazım hatası)
      None      : eşleşme yok
    """
    if not a or not b:
        return None
    ta, tb = surname_tokens(a), surname_tokens(b)
    if not ta or not tb:
        return None
    if ta == tb:
        return "exact"

    sa, sb = set(ta), set(tb)
    if sa == sb or sa <= sb or sb <= sa:
        return "variant"

    # Bitişik / ayrı yazım: "LeBlanc" ~ "Le Blanc", "Demiryılmaz" ~ "Demir Yılmaz"
    ja, jb = "".join(all_tokens(a)), "".join(all_tokens(b))
    if ja == jb or "".join(ta) == "".join(tb):
        return "variant"

    # Tek harflik yazım hatası (kısa soyadlarda yanlış eşleşmeyi önlemek için >= 5 harf)
    ca, cb = "".join(ta), "".join(tb)
    if min(len(ca), len(cb)) >= 5 and _edit_distance_le1(ca, cb):
        return "typo"
    if len(ta) == len(tb) and len(ta) > 1:
        diffs = [(x, y) for x, y in zip(ta, tb) if x != y]
        if len(diffs) == 1:
            x, y = diffs[0]
            if min(len(x), len(y)) >= 5 and _edit_distance_le1(x, y):
                return "typo"
    return None


def sort_key(surname: Optional[str]) -> str:
    """Alfabetik sıra denetimi için anahtar (APA: partikül soyadın parçasıdır)."""
    return "".join(all_tokens(surname or ""))
