"""
Çapraz tutarlılık kontrolü.

Metin içi atıfları (Citation) ile referans listesini (Reference) karşılaştırır:

- Metin içinde atıfı geçen ama referans listesinde olmayan kaynaklar
  → missing_in_references
- Referans listesinde olan ama metin içinde hiç atıf yapılmayan kaynaklar
  → orphan_references

cross_check(citations, references) -> CrossCheckResult

Not: Eşleştirme anahtarı (key) artık doğrudan Citation.key ve Reference.key
property'leri üzerinden alınır. Bu sayede curly apostroflar (U+2019, U+2018)
ve diğer normalizasyonlar tek bir yerden (extractors.py) yönetilir.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional

from .extractors import Citation, Reference, _APOS, _UPPER, _LOWER
from .names import match_surnames

@dataclass
class FuzzyMatch:
    """Birebir olmayan, ama aynı kaynağı gösterdiği anlaşılan atıf-referans çifti."""
    citation: Citation
    reference: Reference
    kind: str  # "variant" (farklı yazım / eksik soyad) | "typo" (olası yazım hatası)


@dataclass
class CrossCheckResult:
    """Çapraz kontrol sonuçları."""
    # Metinde geçen ama referanslarda bulunmayan atıflar
    missing_in_references: List[Citation] = field(default_factory=list)
    # Referanslarda olan ama metinde geçmeyen kaynaklar ("yetim" referans)
    orphan_references: List[Reference] = field(default_factory=list)
    # Eşleşen (tutarlı) atıf-referans sayısı
    matched_count: int = 0
    # Esnek eşleşmeler: eşleşti sayılır, ancak yazım tutarsızlığı olarak raporlanır
    fuzzy_matches: List[FuzzyMatch] = field(default_factory=list)


_YEAR_ALIASES = {
    "t.y.": "n.d.", "t. y.": "n.d.", "n. d.": "n.d.",
    "baskıda": "in press", "basımda": "in press", "yayımlanmak üzere": "in press",
}


def _norm_year(year: Optional[str]) -> str:
    """'t.y.' = 'n.d.', 'baskıda' = 'in press'."""
    y = re.sub(r"\s+", " ", (year or "").strip().lower())
    return _YEAR_ALIASES.get(y, y)


def _year_base(year: Optional[str]) -> str:
    y = _norm_year(year)
    return y[:4] if y[:4].isdigit() else y


def cross_check(
    citations: List[Citation],
    references: List[Reference],
) -> CrossCheckResult:
    """
    Metin içi atıfları referans listesiyle karşılaştır.

    Eşleştirme mantığı (yıl aynı olmak koşuluyla, sırayla):
    1. Birebir: soyadın ayırt edici parçaları aynı. Ekler (de, da, van der ...),
       aksanlar, tire/boşluk ve büyük-küçük harf farkı dikkate alınmaz.
    2. Varyant: bir tarafın soyad parçaları diğerinin alt kümesi
       ("Yılmaz" ~ "Demir Yılmaz", "Márquez" ~ "García Márquez") ya da
       bitişik/ayrı yazım ("LeBlanc" ~ "Le Blanc").
    3. Yazım hatası: tek harflik fark.
    Birebir eşleşme varsa esnek eşleşmeye bakılmaz; böylece "Kaya (2023)" atfı,
    listede hem "Kaya" hem "Aksoy Kaya" varken yanlış kayda bağlanmaz.
    """
    ref_info = []  # (ref, soyad, yıl)
    for ref in references:
        surname, year = _ref_surname_year(ref)
        ref_info.append((ref, surname, year))

    cited_refs: set[int] = set()
    missing: List[Citation] = []
    fuzzy: List[FuzzyMatch] = []
    matched_keys: set[str] = set()
    seen: dict[str, bool] = {}
    seen_fuzzy: set[tuple] = set()

    for cit in citations:
        k = cit.key
        if not k:
            continue
        surname = cit.first_author_surname
        hits: dict[str, list[int]] = {"exact": [], "variant": [], "typo": []}
        for idx, (ref, r_surname, r_year) in enumerate(ref_info):
            if not r_surname or not r_year:
                continue
            if _norm_year(r_year) != _norm_year(cit.year):
                # "2020a" atfı "2020" kaydıyla (ve tersi) yalnızca esnek eşleşir
                if _year_base(r_year) != _year_base(cit.year):
                    continue
                level = match_surnames(surname, r_surname)
                if level:
                    hits["variant" if level == "exact" else level].append(idx)
                continue
            level = match_surnames(surname, r_surname)
            if level:
                hits[level].append(idx)

        chosen_level = next((lv for lv in ("exact", "variant", "typo") if hits[lv]), None)
        if chosen_level is None:
            if k not in seen:
                missing.append(cit)
                seen[k] = False
            continue

        seen[k] = True
        matched_keys.add(k)
        for idx in hits[chosen_level]:
            cited_refs.add(idx)
            if chosen_level != "exact":
                fk = (k, idx)
                if fk not in seen_fuzzy:
                    seen_fuzzy.add(fk)
                    fuzzy.append(FuzzyMatch(cit, ref_info[idx][0], chosen_level))

    orphans = [
        ref for idx, (ref, r_surname, r_year) in enumerate(ref_info)
        if r_surname and r_year and idx not in cited_refs
    ]

    return CrossCheckResult(
        missing_in_references=missing,
        orphan_references=orphans,
        matched_count=len(matched_keys),
        fuzzy_matches=fuzzy,
    )


def _ref_surname_year(ref: Reference) -> tuple[Optional[str], Optional[str]]:
    """Referansın (ilk yazar soyadı, yıl) ikilisi; yazar ayrıştırılamadıysa ham metinden türet."""
    if not ref.year:
        return None, None
    surname = ref.first_author_surname
    if not surname:
        m = re.search(rf"[{_UPPER}][{_LOWER}]+", ref.raw or "")
        surname = m.group(0) if m else None
    return surname, ref.year


def _ref_key(ref: Reference) -> Optional[str]:
    """Geriye dönük uyumluluk: 'soyadı|yıl' anahtarı."""
    if ref.key:
        return ref.key
    surname, year = _ref_surname_year(ref)
    if not surname or not year:
        return None
    return f"{re.sub(_APOS, chr(39), surname).lower()}|{year[:4]}"
