"""
APA 7 biçim kontrol modülü.
 
Düz metinden tespit edilebilen yaygın ihlalleri işaretler:
  - APA 7 'et al.' kuralı (3+ yazarda ilk atıftan itibaren)
  - DOI URL formatı (https://doi.org/)
  - Alfabetik sıralama
  - & vs and tutarlılığı (parantez içi vs anlatımsal)
  - Yıl harf eki tutarlılığı (2020 vs 2020a)
  - Sayfa aralığı en-dash
  - Yazar baş harfi formatı
  - Referans noktalama bütünlüğü
 
DOCX-spesifik kontroller (docx_inspection geçildiğinde):
  - Asılı girinti (hanging indent)
  - Çift satır aralığı
  - Dergi adı italik
  - Cilt numarası italik
"""
from __future__ import annotations
 
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import List, Literal, Optional, TYPE_CHECKING
 
from .extractors import Citation, Reference
 
if TYPE_CHECKING:
    from .docx_inspector import DocxInspection, ParagraphFormatInfo
 
 
SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}
 
 
@dataclass
class FormatIssue:
    """Tek bir APA 7 biçim ihlali."""
    severity: Literal["error", "warning", "info"]
    category: str
    message: str
    location: str
    raw_excerpt: str
    suggestion: Optional[str] = None
 
 
# =============================================================================
# REFERENS LİSTESİ KONTROLLERİ
# =============================================================================
 
def check_alphabetical_sort(references: List[Reference]) -> List[FormatIssue]:
    """Referans listesi ilk yazar soyadına göre alfabetik olmalı."""
    issues: List[FormatIssue] = []
    for i in range(1, len(references)):
        prev = (references[i - 1].first_author_surname or "").lower()
        curr = (references[i].first_author_surname or "").lower()
        if prev and curr and prev > curr:
            issues.append(FormatIssue(
                severity="warning",
                category="Alfabetik Sıralama",
                message=(
                    f"Referans #{i + 1} alfabetik sıraya uymuyor: "
                    f"'{references[i].first_author_surname}' "
                    f"'{references[i - 1].first_author_surname}' sonrasında olmamalı."
                ),
                location=f"Referans #{i + 1}",
                raw_excerpt=references[i].raw[:120] + ("…" if len(references[i].raw) > 120 else ""),
                suggestion=(
                    f"'{references[i - 1].first_author_surname}' (#{i}) ve "
                    f"'{references[i].first_author_surname}' (#{i + 1}) yer değiştirmeli."
                ),
            ))
    return issues
 
 
_DOI_BARE = re.compile(r"\b10\.\d{4,9}/[^\s,;]+", re.IGNORECASE)
_DOI_OLD_PREFIX = re.compile(r"\bdoi:\s*10\.\d", re.IGNORECASE)
_DOI_DX = re.compile(r"https?://dx\.doi\.org/", re.IGNORECASE)
_DOI_GOOD = re.compile(r"https?://doi\.org/10\.", re.IGNORECASE)
 
 
def check_doi_format(ref: Reference, idx: int) -> List[FormatIssue]:
    """APA 7 DOI: tam URL — https://doi.org/10.xxxx/yyyy"""
    issues: List[FormatIssue] = []
    raw = ref.raw
 
    if _DOI_OLD_PREFIX.search(raw):
        issues.append(FormatIssue(
            severity="error",
            category="DOI Formatı",
            message="APA 7'de 'doi:' öneki kullanımı geçersiz.",
            location=f"Referans #{idx + 1}",
            raw_excerpt=raw[:120] + ("…" if len(raw) > 120 else ""),
            suggestion="'doi: 10.xxxx/yyyy' → 'https://doi.org/10.xxxx/yyyy'",
        ))
 
    if _DOI_DX.search(raw):
        issues.append(FormatIssue(
            severity="warning",
            category="DOI Formatı",
            message="APA 7: 'dx.doi.org' eski format, 'doi.org' kullanılmalı.",
            location=f"Referans #{idx + 1}",
            raw_excerpt=raw[:120] + ("…" if len(raw) > 120 else ""),
            suggestion="https://dx.doi.org/... → https://doi.org/...",
        ))
 
    # DOI çıplak halde: '10.1234/abc' var ama hiçbir doi.org URL'si yok
    if ref.doi and not _DOI_GOOD.search(raw) and not _DOI_OLD_PREFIX.search(raw) and not _DOI_DX.search(raw):
        issues.append(FormatIssue(
            severity="warning",
            category="DOI Formatı",
            message="APA 7: DOI tam URL formatında yazılmalı.",
            location=f"Referans #{idx + 1}",
            raw_excerpt=raw[:120] + ("…" if len(raw) > 120 else ""),
            suggestion=f"'{ref.doi}' → 'https://doi.org/{ref.doi}'",
        ))
 
    return issues
 
 
_PAGE_HYPHEN = re.compile(r"\b(\d+)\s*-\s*(\d+)\b")
_PAGE_ENDASH = re.compile(r"\b\d+\s*[–—]\s*\d+\b")
 
 
def check_page_range_format(ref: Reference, idx: int) -> List[FormatIssue]:
    """Sayfa aralığında en-dash (–) önerilir, sıradan tire (-) yerine."""
    # Yıl ve cilt-sayı kombinasyonlarını dışla: tipik sayfa kalıbı için
    # "1, 1-10" / "20(3), 123-145" gibi sayfa öncesi virgül + boşluk var
    page_pattern = re.search(r",\s*(?:pp?\.\s*)?(\d+\s*-\s*\d+)\b", ref.raw)
    if page_pattern and not _PAGE_ENDASH.search(ref.raw):
        return [FormatIssue(
            severity="info",
            category="Sayfa Aralığı",
            message="APA: sayfa aralığında en-dash (–) tercih edilir.",
            location=f"Referans #{idx + 1}",
            raw_excerpt=page_pattern.group(0),
            suggestion=f"'{page_pattern.group(1)}' → '"
                      f"{page_pattern.group(1).replace('-', '–')}'",
        )]
    return []
 
 
# Yazar baş harfi: "Smith, J. M." doğru; "Smith, JM." veya "Smith, J.M." hatalı
_AUTHOR_NO_SPACE = re.compile(r"[A-Z]\.[A-Z]\.")               # "J.M."
_AUTHOR_RUN_ON = re.compile(r",\s+[A-Z]{2,}\.")                # ", JM."
 
 
def check_author_format(ref: Reference, idx: int) -> List[FormatIssue]:
    """Yazar baş harfleri: 'J. M.' (nokta + boşluk + nokta)."""
    if not ref.authors_raw:
        return []
 
    issues: List[FormatIssue] = []
 
    if _AUTHOR_NO_SPACE.search(ref.authors_raw):
        issues.append(FormatIssue(
            severity="warning",
            category="Yazar Formatı",
            message="Baş harfler arasında boşluk olmalı: 'J.M.' yerine 'J. M.'",
            location=f"Referans #{idx + 1}",
            raw_excerpt=ref.authors_raw[:80],
            suggestion="'Smith, J.M.' → 'Smith, J. M.'",
        ))
 
    if _AUTHOR_RUN_ON.search(ref.authors_raw):
        issues.append(FormatIssue(
            severity="warning",
            category="Yazar Formatı",
            message="Baş harfler arasında nokta + boşluk olmalı: 'JM.' yerine 'J. M.'",
            location=f"Referans #{idx + 1}",
            raw_excerpt=ref.authors_raw[:80],
            suggestion="'Smith, JM.' → 'Smith, J. M.'",
        ))
 
    return issues
 
 
def check_reference_terminator(ref: Reference, idx: int) -> List[FormatIssue]:
    """Her referans nokta ile bitmeli (URL/DOI son geliyorsa nokta opsiyonel)."""
    raw = ref.raw.strip()
    if not raw:
        return []
    last_char = raw[-1]
    # URL ile bitiyorsa noktaya gerek yok (ama tavsiye edilir)
    ends_with_url = bool(re.search(r"https?://[^\s]+$", raw))
    if last_char not in ".)" and not ends_with_url:
        return [FormatIssue(
            severity="info",
            category="Noktalama",
            message="Referans nokta ile bitmiyor.",
            location=f"Referans #{idx + 1}",
            raw_excerpt=raw[-60:],
            suggestion="Sonuna '.' ekleyin.",
        )]
    return []
 
 
# =============================================================================
# METİN İÇİ ATIF KONTROLLERİ
# =============================================================================
 
# 3+ yazarlı atıfta et al. olmadan virgüllü liste algılama
# Örn: "Sammer, Lykens, Singh, Mains, & Lackan, 2010" → 5 yazar, et al. yok
_ETAL = r"(?:et\s*al\.?|vd\.|ve\s*ark\.|ve\s*diğerleri)"
_AUTHOR_TOKEN = r"[A-ZÇĞİÖŞÜ][a-zçğıöşü]+(?:[\s\-'][A-ZÇĞİÖŞÜ][a-zçğıöşü]+)?"
 
 
def _count_distinct_authors(authors_text: str) -> int:
    """
    Yazar metnindeki tek tek yazarları kabaca say.
 
    "Sammer, Lykens, Singh, Mains, & Lackan" → 5
    "Smith & Jones" → 2
    "Smith et al." → ≥3 (et al. var; sayma)
    "Smith" → 1
    """
    cleaned = re.sub(_ETAL, "", authors_text, flags=re.IGNORECASE)
    # Yazar isimlerini yakala (aynı zamanda WHO gibi acronymlere izin ver)
    tokens = re.findall(_AUTHOR_TOKEN, cleaned)
    return len(tokens)
 
 
def check_apa7_et_al(citations: List[Citation]) -> List[FormatIssue]:
    """
    APA 7 KRİTİK KURAL: 3 ve daha fazla yazarda ilk atıftan itibaren 'et al.'
    kullanılmalı. APA 6'da ilk atıf tüm yazarları gerektiriyordu — bu artık geçersiz.
    """
    issues: List[FormatIssue] = []
    has_etal = re.compile(_ETAL, re.IGNORECASE)
 
    for c in citations:
        author_count = _count_distinct_authors(c.authors)
        if author_count >= 3 and not has_etal.search(c.authors):
            issues.append(FormatIssue(
                severity="error",
                category="APA 7 et al. Kuralı",
                message=(
                    "APA 7: 3 ve daha fazla yazarlı çalışmalarda ilk atıftan itibaren "
                    "'et al.' (veya Türkçede 'vd.') kullanılmalı. APA 6 kuralı geçersiz."
                ),
                location=f"Konum {c.position}",
                raw_excerpt=c.raw,
                suggestion=(
                    f"'{c.first_author_surname} et al., {c.year}' "
                    f"(İngilizce) veya '{c.first_author_surname} vd., {c.year}' (Türkçe)"
                ),
            ))
    return issues
 
 
def check_ampersand_usage(citations: List[Citation]) -> List[FormatIssue]:
    """
    APA 7: parantez içi atıfta '&', anlatımsal atıfta 'and' kullanılmalı.
    Türkçe 've' her iki yerde de yaygın kabul gördüğü için uyarmıyoruz.
    """
    issues: List[FormatIssue] = []
    has_and = re.compile(r"\band\b", re.IGNORECASE)
    has_amp = re.compile(r"&")
 
    for c in citations:
        if c.citation_type == "parenthetical" and has_and.search(c.authors):
            issues.append(FormatIssue(
                severity="warning",
                category="& vs and",
                message="Parantez içi atıfta '&' kullanılmalı, 'and' yerine.",
                location=f"Konum {c.position}",
                raw_excerpt=c.raw,
                suggestion="(A and B, 2020) → (A & B, 2020)",
            ))
        elif c.citation_type == "narrative" and has_amp.search(c.authors):
            issues.append(FormatIssue(
                severity="warning",
                category="& vs and",
                message="Anlatımsal atıfta 'and' kullanılmalı, '&' yerine.",
                location=f"Konum {c.position}",
                raw_excerpt=c.raw,
                suggestion="A & B (2020) → A and B (2020)",
            ))
    return issues
 
 
def check_year_suffix_consistency(citations: List[Citation]) -> List[FormatIssue]:
    """
    Aynı yazar+yıl kombinasyonu birden fazla atıfta hem 'a/b' ekiyle hem eksiz
    kullanılıyorsa tutarsızlık vardır.
 
    Tipik kalıp:
      - Doğru: 'Smith (2020a)' ve 'Smith (2020b)' (iki farklı esere)
      - Yanlış: 'Smith (2020)' ve 'Smith (2020a)' aynı çalışmada karışık
    """
    issues: List[FormatIssue] = []
 
    # Yazar + bare year ile grupla
    groups: dict[str, List[Citation]] = defaultdict(list)
    for c in citations:
        if not c.year:
            continue
        bare_year_match = re.match(r"\d{4}", c.year)
        if not bare_year_match:
            continue
        bare_year = bare_year_match.group(0)
        key = f"{c.first_author_surname.lower()}|{bare_year}"
        groups[key].append(c)
 
    for key, group in groups.items():
        if len(group) < 2:
            continue
        bare = [c for c in group if not re.search(r"[a-z]$", c.year)]
        suffixed = [c for c in group if re.search(r"[a-z]$", c.year)]
        if bare and suffixed:
            surname, year = key.split("|")
            issues.append(FormatIssue(
                severity="warning",
                category="Yıl Harf Eki",
                message=(
                    f"'{group[0].first_author_surname}' yazarın {year} yılı için "
                    f"hem ekli hem eksiz atıf kullanımı tutarsız "
                    f"(bare: {len(bare)}, suffixed: {len(suffixed)})."
                ),
                location="Birden fazla konum",
                raw_excerpt=" / ".join(c.raw for c in group[:3]),
                suggestion=(
                    "Aynı yazar+yıl farklı eserlere atıfsa tüm atıflar 'a/b/c' ekiyle "
                    "tutarlı olmalı. Aynı esere ise hiçbiri ek almamalı."
                ),
            ))
 
    return issues
 
 
# =============================================================================
# DOCX-SPESİFİK KONTROLLER (paragraf biçimi + italik)
# =============================================================================
 
def check_docx_hanging_indent(
    ref: Reference, idx: int, para: "ParagraphFormatInfo"
) -> List[FormatIssue]:
    """APA 7: kaynakça paragrafı asılı girintili olmalı."""
    if para.has_hanging_indent:
        return []
    return [FormatIssue(
        severity="warning",
        category="Asılı Girinti (DOCX)",
        message="APA 7: kaynakça paragrafında asılı girinti bulunmuyor.",
        location=f"Referans #{idx + 1}",
        raw_excerpt=para.text[:120] + ("…" if len(para.text) > 120 else ""),
        suggestion=(
            "Word: Paragraf > Girinti > Özel: 'Asılı' (0.5\" / 1.27 cm). "
            "Tüm referanslarda toplu uygulayın."
        ),
    )]
 
 
def check_docx_journal_italic(
    ref: Reference, idx: int, para: "ParagraphFormatInfo"
) -> List[FormatIssue]:
    """APA 7: dergi adı italik olmalı (referans listesinde)."""
    from .docx_inspector import find_journal_volume_positions, is_span_italic
 
    jv = find_journal_volume_positions(para.text)
    if not jv:
        return []  # Dergi-cilt deseni bulunamadı (kitap/rapor vb. olabilir)
 
    j_start, j_end, _, _ = jv
    journal_text = para.text[j_start:j_end].strip()
    if not journal_text:
        return []
 
    if is_span_italic(j_start, j_end, para.italic_spans):
        return []
 
    return [FormatIssue(
        severity="error",
        category="Italik (DOCX)",
        message=f"Dergi adı italik olmalı: '{journal_text}'",
        location=f"Referans #{idx + 1}",
        raw_excerpt=para.text[max(0, j_start - 20):min(len(para.text), j_end + 20)],
        suggestion="Dergi adını seçip Ctrl+I (Cmd+I) ile italik yapın.",
    )]
 
 
def check_docx_volume_italic(
    ref: Reference, idx: int, para: "ParagraphFormatInfo"
) -> List[FormatIssue]:
    """APA 7: cilt numarası italik olmalı (sayı/issue italik DEĞİL)."""
    from .docx_inspector import find_journal_volume_positions, is_span_italic
 
    jv = find_journal_volume_positions(para.text)
    if not jv:
        return []
 
    _, _, v_start, v_end = jv
    volume_text = para.text[v_start:v_end]
 
    if is_span_italic(v_start, v_end, para.italic_spans):
        return []
 
    return [FormatIssue(
        severity="warning",
        category="Italik (DOCX)",
        message=f"Cilt numarası italik olmalı: '{volume_text}' (sayı/issue italik OLMAYACAK).",
        location=f"Referans #{idx + 1}",
        raw_excerpt=para.text[max(0, v_start - 10):min(len(para.text), v_end + 10)],
        suggestion="Sadece cilt numarasını seçip Ctrl+I (Cmd+I) ile italik yapın.",
    )]
 
 
def check_docx_line_spacing(
    inspection: "DocxInspection",
) -> List[FormatIssue]:
    """
    APA 7: tüm metin çift satır aralığı (2.0).
 
    Strateji: gövde + kaynakçadaki anlamlı paragrafların büyük çoğunluğu çift
    satır aralığında değilse tek bir belge-geneli uyarı çıkar.
    """
    paragraphs = list(inspection.body_paragraphs) + list(inspection.reference_paragraphs)
    relevant = [p for p in paragraphs if len((p.text or "").strip()) >= 50]
    if len(relevant) < 3:
        return []  # Yeterli veri yok
 
    not_double = [p for p in relevant if not p.is_double_spaced]
    if len(not_double) <= len(relevant) * 0.5:
        return []  # Çoğu paragraf çift satır aralığında
 
    # Çoğunluk problemli — tek özet uyarı
    sample = next((p.text for p in not_double if p.text), "")
    return [FormatIssue(
        severity="warning",
        category="Satır Aralığı (DOCX)",
        message=(
            f"APA 7: tüm metin çift satır aralığında olmalı (2.0). "
            f"İncelenen {len(relevant)} paragrafın {len(not_double)}'i çift değil."
        ),
        location="Belge geneli",
        raw_excerpt=(sample[:80] + "…") if len(sample) > 80 else sample,
        suggestion="Word: Tümünü seç (Ctrl+A) > Satır Aralığı: 2.0",
    )]
 
 
# =============================================================================
# ANA ORKESTRATÖR
# =============================================================================
 
def check_apa_format(
    citations: List[Citation],
    references: List[Reference],
    docx_inspection: Optional["DocxInspection"] = None,
) -> List[FormatIssue]:
    """
    Tüm APA 7 biçim kontrollerini çalıştır.
 
    `docx_inspection` geçilirse DOCX-spesifik kontroller (italik, girinti,
    satır aralığı) da eklenir. Düz metin (PDF/TXT) için None geçilir.
    """
    issues: List[FormatIssue] = []
 
    # === Düz metin kontrolleri ===
    issues.extend(check_alphabetical_sort(references))
    for i, ref in enumerate(references):
        issues.extend(check_doi_format(ref, i))
        issues.extend(check_page_range_format(ref, i))
        issues.extend(check_author_format(ref, i))
        issues.extend(check_reference_terminator(ref, i))
 
    issues.extend(check_apa7_et_al(citations))
    issues.extend(check_ampersand_usage(citations))
    issues.extend(check_year_suffix_consistency(citations))
 
    # === DOCX-spesifik kontroller ===
    if docx_inspection is not None:
        issues.extend(check_docx_line_spacing(docx_inspection))
 
        # Her referans için: ilgili paragrafı bul ve kontrolleri uygula
        for ref_idx, para_idx in docx_inspection.reference_to_paragraph.items():
            if not (0 <= ref_idx < len(references)):
                continue
            if not (0 <= para_idx < len(docx_inspection.reference_paragraphs)):
                continue
            ref = references[ref_idx]
            para = docx_inspection.reference_paragraphs[para_idx]
            issues.extend(check_docx_hanging_indent(ref, ref_idx, para))
            issues.extend(check_docx_journal_italic(ref, ref_idx, para))
            issues.extend(check_docx_volume_italic(ref, ref_idx, para))
 
    # Severity sırasına göre sırala (errors → warnings → infos)
    issues.sort(key=lambda i: (SEVERITY_ORDER.get(i.severity, 99), i.category))
 
    return issues
 
 
def summarize_by_category(issues: List[FormatIssue]) -> dict[str, int]:
    """Kategori başına sorun sayısı."""
    counts: dict[str, int] = defaultdict(int)
    for issue in issues:
        counts[issue.category] += 1
    return dict(counts)
 
 
def summarize_by_severity(issues: List[FormatIssue]) -> dict[str, int]:
    """Severity başına sorun sayısı."""
    counts: dict[str, int] = defaultdict(int)
    for issue in issues:
        counts[issue.severity] += 1
    return dict(counts)
 
