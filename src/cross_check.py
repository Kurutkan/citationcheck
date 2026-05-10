"""
Çapraz tutarlılık kontrolü.

Metin içi atıfları (Citation) ile referans listesini (Reference) karşılaştırır:

- Metin içinde atıfı geçen ama referans listesinde olmayan kaynaklar
- Referans listesinde olan ama metin içinde hiç atıf yapılmayan kaynaklar

cross_check(citations, references) -> CrossCheckResult
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from .extractors import Citation, Reference


@dataclass
class CrossCheckResult:
    """Çapraz kontrol sonuçları."""
    # Metinde geçen ama referanslarda bulunmayan atıflar
    cited_not_in_references: List[Citation] = field(default_factory=list)
    # Referanslarda olan ama metinde geçmeyen kaynaklar
    in_references_not_cited: List[Reference] = field(default_factory=list)
    # Eşleşen (tutarlı) atıf sayısı
    matched_count: int = 0


def cross_check(
    citations: List[Citation],
    references: List[Reference],
) -> CrossCheckResult:
    """
    Metin içi atıfları referans listesiyle karşılaştır.

    Eşleştirme mantığı:
      - Her Citation için `key` = "soyadı|yıl" (lower-case)
      - Her Reference için `key` = "soyadı|yıl" (lower-case)
      - Fuzzy eşleştirme kullanılmaz; tam anahtar eşleşmesi aranır
        (yeterli çoğu durumda, MVP düzeyi)

    Parameters
    ----------
    citations  : Metin içi atıf listesi
    references : Referans listesi

    Returns
    -------
    CrossCheckResult
    """
    # Referans anahtarları seti
    ref_keys: set[str] = set()
    for ref in references:
        key = _ref_key(ref)
        if key:
            ref_keys.add(key)

    # Citation anahtarları seti (tekrarlananları saymıyoruz)
    cit_keys: set[str] = set()
    for cit in citations:
        cit_keys.add(cit.key)

    # Metinde geçen ama referanslarda olmayan
    cited_not_in_references: List[Citation] = []
    seen_cit: set[str] = set()
    for cit in citations:
        k = cit.key
        if k not in ref_keys and k not in seen_cit:
            cited_not_in_references.append(cit)
            seen_cit.add(k)

    # Referanslarda olan ama metinde geçmeyen
    in_references_not_cited: List[Reference] = []
    for ref in references:
        k = _ref_key(ref)
        if k and k not in cit_keys:
            in_references_not_cited.append(ref)

    matched_count = len(cit_keys & ref_keys)

    return CrossCheckResult(
        cited_not_in_references=cited_not_in_references,
        in_references_not_cited=in_references_not_cited,
        matched_count=matched_count,
    )


def _ref_key(ref: Reference) -> str | None:
    """
    Referans için eşleştirme anahtarı üret: 'soyadı|yıl'.
    """
    if not ref.year:
        return None

    authors_raw = (ref.authors_raw or "").strip()
    if not authors_raw:
        # Ham metinden ilk büyük harf kelimeyi al (kaba fallback)
        import re
        m = re.search(r"[A-ZÇĞİÖŞÜ][a-zçğıöşü]+", ref.raw or "")
        surname = m.group(0) if m else ""
    else:
        # "Smith, J." → "Smith" / "Smith & Jones" → "Smith"
        import re
        # İlk virgül veya & veya "and"/"ve" öncesindeki kısım
        first = re.split(r"[,&]|\band\b|\bve\b", authors_raw)[0].strip()
        # Parantez, nokta vb. temizle
        surname = re.sub(r"[^\w\s\-'ÇĞİÖŞÜçğıöşü]", "", first).strip()

    return f"{surname.lower()}|{ref.year[:4]}"
