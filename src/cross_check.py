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

from .extractors import Citation, Reference, _APOS

@dataclass
class CrossCheckResult:
    """Çapraz kontrol sonuçları."""
    # Metinde geçen ama referanslarda bulunmayan atıflar
    missing_in_references: List[Citation] = field(default_factory=list)
    # Referanslarda olan ama metinde geçmeyen kaynaklar ("yetim" referans)
    orphan_references: List[Reference] = field(default_factory=list)
    # Eşleşen (tutarlı) atıf-referans sayısı
    matched_count: int = 0

def cross_check(
    citations: List[Citation],
    references: List[Reference],
) -> CrossCheckResult:
    """
    Metin içi atıfları referans listesiyle karşılaştır.

    Eşleştirme mantığı:
    - Her Citation için key = "soyadı|yıl" (lower-case, apostrof normalize)
    - Her Reference için key = "soyadı|yıl" (lower-case, apostrof normalize)
    - Tam anahtar eşleşmesi aranır (MVP düzeyinde yeterli)
    """
    ref_keys: set[str] = set()
    for ref in references:
        k = _ref_key(ref)
        if k:
            ref_keys.add(k)

    cit_keys: set[str] = set()
    for cit in citations:
        if cit.key:
            cit_keys.add(cit.key)

    missing_in_references: List[Citation] = []
    seen_cit: set[str] = set()
    for cit in citations:
        k = cit.key
        if k and k not in ref_keys and k not in seen_cit:
            missing_in_references.append(cit)
            seen_cit.add(k)

    orphan_references: List[Reference] = []
    for ref in references:
        k = _ref_key(ref)
        if k and k not in cit_keys:
            orphan_references.append(ref)

    matched_count = len(cit_keys & ref_keys)

    return CrossCheckResult(
        missing_in_references=missing_in_references,
        orphan_references=orphan_references,
        matched_count=matched_count,
    )

def _ref_key(ref: Reference) -> Optional[str]:
    """
    Referans için eşleştirme anahtarı üret: 'soyadı|yıl' (lower-case).

    Öncelikle Reference.key property'sini kullanır — orada apostrof normalizasyonu
    (curly → düz) ve lower-case dönüşümü zaten yapılır. Reference.key None dönerse
    (yıl/yazar eksikse) fallback olarak ref.raw'dan bir soyad türetir.
    """
    # 1) Öncelikli yol: Reference.key property — extractors.py ile aynı normalizasyon
    primary = ref.key
    if primary:
        return primary

    # 2) Fallback: yıl varsa ama yazar yoksa, ham metinden soyad türetmeye çalış
    if not ref.year:
        return None

    m = re.search(r"[A-ZÇĞİÖŞÜ][a-zçğıöşü]+", ref.raw or "")
    if not m:
        return None
    surname = m.group(0)
    # Apostrof normalizasyonu (Reference.key ile tutarlı olmak için)
    surname = re.sub(_APOS, "'", surname)
    return f"{surname.lower()}|{ref.year[:4]}"
