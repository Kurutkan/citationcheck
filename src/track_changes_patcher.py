"""
Word Track Changes ile otomatik düzeltme yaması üretimi.
 
Bu modül DOCX dosyasını alır, tespit edilen biçim sorunlarından otomatik olarak
düzeltilebilenleri Word Track Changes (`<w:ins>` + `<w:del>`) olarak işaretler
ve yeni bir DOCX üretir. Kullanıcı Word'de açıp her değişikliği "Kabul Et / Reddet"
ile inceleyebilir.
 
Otomatik uygulanan düzeltmeler:
  1. Sayfa aralığı: hyphen → en-dash  (156-165 → 156–165)
  2. APA 6 → APA 7 et al. sadeleştirme  (Smith, Jones, Brown, & Black → Smith et al.)
  3. DOI formatı  (doi:10.xxx → https://doi.org/10.xxx)
 
Manuel inceleme gerektirenler (özet sayfada listelenir):
  - İtalik (dergi adı, cilt numarası)
  - Asılı girinti
  - Çift satır aralığı
 
Word OOXML referansı:
  https://learn.microsoft.com/en-us/dotnet/api/documentformat.openxml.wordprocessing
"""
from __future__ import annotations
 
import re
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional, Tuple
 
from docx import Document
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor
from lxml import etree
 
from .extractors import Citation, Reference
from .docx_inspector import DocxInspection
from .format_checker import FormatIssue
 
 
PATCH_AUTHOR = "APA Doğrulayıcı"
 
 
# =============================================================================
# Veri modelleri
# =============================================================================
 
@dataclass
class TextSubstitution:
    """Track changes ile uygulanacak tek bir metin değiştirme."""
    paragraph_xml: object        # lxml Element: hangi paragraf
    old_text: str
    new_text: str
    category: str                # "Sayfa Aralığı" | "APA 7 et al." | "DOI Formatı"
    description: str             # İnsan-okur açıklama
 
 
@dataclass
class PatchResult:
    """generate_track_changes_patch dönüş tipi."""
    output_path: str
    applied_count: int = 0
    failed_count: int = 0
    fixes_by_category: dict = field(default_factory=dict)
    manual_review: List[FormatIssue] = field(default_factory=list)
 
 
# =============================================================================
# Otomatik düzeltme tespiti
# =============================================================================
 
def _detect_page_range_fixes(
    references: List[Reference],
    inspection: DocxInspection,
    para_index_in_doc: dict,
) -> List[TextSubstitution]:
    """Sayfa aralıklarındaki hyphen'leri en-dash önerisine dönüştür."""
    fixes: List[TextSubstitution] = []
    pattern = re.compile(r",\s*(?:pp?\.\s*)?(\d+)-(\d+)\b")
 
    for ref_idx, ref in enumerate(references):
        para_idx = inspection.reference_to_paragraph.get(ref_idx)
        if para_idx is None:
            continue
        para_xml = para_index_in_doc.get(para_idx)
        if para_xml is None:
            continue
 
        for m in pattern.finditer(ref.raw):
            old_pages = f"{m.group(1)}-{m.group(2)}"
            new_pages = f"{m.group(1)}–{m.group(2)}"  # en-dash
            fixes.append(TextSubstitution(
                paragraph_xml=para_xml,
                old_text=old_pages,
                new_text=new_pages,
                category="Sayfa Aralığı",
                description=f"APA en-dash: {old_pages} → {new_pages}",
            ))
 
    return fixes
 
 
def _detect_doi_fixes(
    references: List[Reference],
    inspection: DocxInspection,
    para_index_in_doc: dict,
) -> List[TextSubstitution]:
    """'doi:10.xxx' → 'https://doi.org/10.xxx'."""
    fixes: List[TextSubstitution] = []
    pattern = re.compile(r"\bdoi:\s*(10\.\S+)", re.IGNORECASE)
 
    for ref_idx, ref in enumerate(references):
        para_idx = inspection.reference_to_paragraph.get(ref_idx)
        if para_idx is None:
            continue
        para_xml = para_index_in_doc.get(para_idx)
        if para_xml is None:
            continue
 
        for m in pattern.finditer(ref.raw):
            old = m.group(0)
            doi_clean = m.group(1).rstrip(".,;)")
            new = f"https://doi.org/{doi_clean}"
            fixes.append(TextSubstitution(
                paragraph_xml=para_xml,
                old_text=old,
                new_text=new,
                category="DOI Formatı",
                description=f"DOI URL: {old} → {new}",
            ))
 
    return fixes
 
 
_ETAL_RE = re.compile(r"(?:et\s*al\.?|vd\.|ve\s*ark\.|ve\s*diğerleri)", re.IGNORECASE)
_AUTHOR_TOKEN_RE = re.compile(
    r"[A-ZÇĞİÖŞÜ][a-zçğıöşü]+(?:[\s\-'][A-ZÇĞİÖŞÜ][a-zçğıöşü]+)?"
)
 
 
def _suggest_etal_replacement(citation_raw: str, first_surname: str, year: str, is_turkish: bool) -> Optional[str]:
    """
    APA 6 stili çoklu atıfı APA 7 et al. formatına çevir.
 
    Örnek:
      (Sammer, Lykens, Singh, Mains, & Lackan, 2010) → (Sammer et al., 2010)
      Kurutkan, Usta, Orhan ve Bingöl (2014) → Kurutkan vd. (2014)
    """
    etal_word = "vd." if is_turkish else "et al."
 
    # Parantez içi: (Authors, Year) → (Surname et al., Year)
    if citation_raw.startswith("(") and citation_raw.endswith(")"):
        return f"({first_surname} {etal_word}, {year})"
 
    # Anlatımsal: Authors (Year) → Surname et al. (Year)
    if "(" in citation_raw and citation_raw.endswith(")"):
        return f"{first_surname} {etal_word} ({year})"
 
    return None
 
 
def _detect_etal_fixes(
    citations: List[Citation],
    body_paragraphs_xml: List[object],
    body_text_full: str,
) -> List[TextSubstitution]:
    """
    APA 6 → APA 7 et al. sadeleştirmesi.
 
    Hangi paragrafa ait olduğunu bulmak için: atıf raw metni gövde paragraflarında
    aranır; bulunduğunda o paragraf XML'i hedef olarak kullanılır.
    """
    fixes: List[TextSubstitution] = []
    seen_old_texts: set = set()
 
    for c in citations:
        # 3+ yazar var mı?
        cleaned = _ETAL_RE.sub("", c.authors)
        author_count = len(_AUTHOR_TOKEN_RE.findall(cleaned))
        if author_count < 3:
            continue
        # Zaten et al. var mı?
        if _ETAL_RE.search(c.authors):
            continue
 
        # Türkçe varyant mı? (Türkçe "ve" varlığı + Latin alfabe Türkçe karakter)
        is_turkish = bool(re.search(r"\bve\b|ç|ğ|ı|ö|ş|ü", c.authors))
 
        replacement = _suggest_etal_replacement(
            c.raw, c.first_author_surname, c.year, is_turkish
        )
        if not replacement:
            continue
        if c.raw in seen_old_texts:
            continue
        seen_old_texts.add(c.raw)
 
        # Hangi paragrafta? Atıf metnini gövde paragraflarında ara
        target_para = None
        for p_xml in body_paragraphs_xml:
            p_text = _paragraph_text(p_xml)
            if c.raw in p_text:
                target_para = p_xml
                break
 
        if target_para is None:
            continue  # Paragrafta bulunamadı (eşleştirme başarısız)
 
        fixes.append(TextSubstitution(
            paragraph_xml=target_para,
            old_text=c.raw,
            new_text=replacement,
            category="APA 7 et al.",
            description=f"APA 6 → APA 7: '{c.raw}' → '{replacement}'",
        ))
 
    return fixes
 
 
# =============================================================================
# XML manipülasyon yardımcıları
# =============================================================================
 
def _now_iso() -> str:
    """Track changes için ISO 8601 UTC zaman damgası."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
 
 
def _paragraph_text(p_xml) -> str:
    """Bir paragraf XML elementinin tüm metnini birleştir."""
    parts = []
    for t in p_xml.iter(qn("w:t")):
        parts.append(t.text or "")
    for t in p_xml.iter(qn("w:delText")):
        # Silinmiş metni saymıyoruz; bu zaten kabul edilmiş bir change.
        # Ham metin için ekliyoruz ama gerçekte görünür değil.
        pass
    return "".join(parts)
 
 
class _ChangeIdGenerator:
    """w:id değerleri tüm belge boyunca benzersiz olmalı."""
    def __init__(self, start: int = 1000):
        self._next = start
 
    def next(self) -> str:
        n = self._next
        self._next += 1
        return str(n)
 
 
def _make_del_element(text: str, change_id: str, run_props: Optional[object]) -> object:
    """<w:del id=… author=… date=…><w:r>[<rPr/>]<w:delText>...</w:delText></w:r></w:del>"""
    del_elem = etree.Element(qn("w:del"))
    del_elem.set(qn("w:id"), change_id)
    del_elem.set(qn("w:author"), PATCH_AUTHOR)
    del_elem.set(qn("w:date"), _now_iso())
 
    r = etree.SubElement(del_elem, qn("w:r"))
    if run_props is not None:
        r.append(deepcopy(run_props))
 
    delText = etree.SubElement(r, qn("w:delText"))
    delText.set(qn("xml:space"), "preserve")
    delText.text = text
 
    return del_elem
 
 
def _make_ins_element(text: str, change_id: str, run_props: Optional[object]) -> object:
    """<w:ins id=… author=… date=…><w:r>[<rPr/>]<w:t>...</w:t></w:r></w:ins>"""
    ins_elem = etree.Element(qn("w:ins"))
    ins_elem.set(qn("w:id"), change_id)
    ins_elem.set(qn("w:author"), PATCH_AUTHOR)
    ins_elem.set(qn("w:date"), _now_iso())
 
    r = etree.SubElement(ins_elem, qn("w:r"))
    if run_props is not None:
        r.append(deepcopy(run_props))
 
    t = etree.SubElement(r, qn("w:t"))
    t.set(qn("xml:space"), "preserve")
    t.text = text
 
    return ins_elem
 
 
def _apply_substitution(sub: TextSubstitution, id_gen: _ChangeIdGenerator) -> bool:
    """
    Tek bir paragraf XML'ine track changes uygula.
 
    Algoritma:
      1. Paragrafın run'larını sırayla dolaş, sub.old_text'in başlangıç pozisyonunu bul
      2. Eğer old_text TEK BİR run'ın içine sığıyorsa:
         a. Run'ı üçe böl: [öncesi] + [değişen kısım] + [sonrası]
         b. Değişen kısmı w:del + w:ins çiftiyle değiştir
      3. Birden fazla run'a yayılmışsa atla (kapsam dışı)
    """
    p_xml = sub.paragraph_xml
    full_text = _paragraph_text(p_xml)
 
    pos = full_text.find(sub.old_text)
    if pos == -1:
        return False
 
    target_len = len(sub.old_text)
 
    # Run'ları gez ve old_text'in tek bir run'ın içinde olduğunu bul
    current = 0
    target_t = None      # Hedef <w:t>
    target_r = None      # Hedef <w:r>
    offset_in_t = None
 
    # XPath yerine doğrudan iter çünkü sıralama önemli
    for r in p_xml.iter(qn("w:r")):
        # del/ins içindeki run'ları atla — onlar zaten tracked
        if r.getparent().tag in (qn("w:del"), qn("w:ins")):
            continue
 
        for t in r.findall(qn("w:t")):
            t_text = t.text or ""
            t_len = len(t_text)
 
            if current <= pos and pos + target_len <= current + t_len:
                # Tam olarak bu <w:t> içinde
                target_t = t
                target_r = r
                offset_in_t = pos - current
                break
 
            current += t_len
        if target_t is not None:
            break
 
    if target_t is None:
        return False  # Birden fazla t/run'a yayılmış, kapsam dışı
 
    t_text = target_t.text or ""
    text_before = t_text[:offset_in_t]
    text_after = t_text[offset_in_t + target_len:]
 
    # Hedef run'ın özelliklerini koru
    rPr = target_r.find(qn("w:rPr"))
 
    # Adım 1: target_t'yi text_before olarak güncelle (boşsa sonra silinecek)
    target_t.text = text_before
    target_t.set(qn("xml:space"), "preserve")
 
    # Adım 2: del + ins elementlerini target_r'den HEMEN SONRA ekle
    parent = target_r.getparent()
    target_r_idx = list(parent).index(target_r)
 
    del_elem = _make_del_element(sub.old_text, id_gen.next(), rPr)
    ins_elem = _make_ins_element(sub.new_text, id_gen.next(), rPr)
 
    parent.insert(target_r_idx + 1, del_elem)
    parent.insert(target_r_idx + 2, ins_elem)
    insertion_idx = target_r_idx + 3
 
    # Adım 3: text_after varsa yeni bir run ekle (target_r'in özelliklerini koruyarak)
    if text_after:
        new_r = deepcopy(target_r)
        # Sadece <w:t>'yi text_after'a ayarla, ek elementleri temizle
        for t_to_remove in new_r.findall(qn("w:t")):
            new_r.remove(t_to_remove)
        new_t = etree.SubElement(new_r, qn("w:t"))
        new_t.set(qn("xml:space"), "preserve")
        new_t.text = text_after
        parent.insert(insertion_idx, new_r)
 
    # Adım 4: Eğer text_before boşsa, şimdi boş olan target_r'yi temizle
    if not text_before:
        # target_r'da başka <w:t> var mı? (genelde 1 tane olur)
        remaining_t = target_r.findall(qn("w:t"))
        if all((t.text or "") == "" for t in remaining_t):
            # Tamamı boş, target_r'yi kaldır
            parent.remove(target_r)
 
    return True
 
 
# =============================================================================
# Manuel inceleme listesi için kategoriler
# =============================================================================
 
# Bu kategoriler otomatik düzeltilemediği için manual_review listesine girer
_MANUAL_REVIEW_CATEGORIES = {
    "Italik (DOCX)",
    "Asılı Girinti (DOCX)",
    "Satır Aralığı (DOCX)",
    "Alfabetik Sıralama",       # paragraf sırası değiştirmek track changes ile karmaşık
    "Yazar Formatı",            # belirsiz pozisyonlama
    "Yıl Harf Eki",             # belge bağlamında manuel karar
    "& vs and",                 # manuel daha güvenli (yanlış yerde değiştirebilir)
    "Noktalama",                # özel bağlam
}
 
 
# =============================================================================
# Özet sayfası ekleme
# =============================================================================
 
def _add_summary_page(doc, applied: List[TextSubstitution], manual: List[FormatIssue]) -> None:
    """Belgenin BAŞINA özet bilgilendirme sayfası ekle."""
 
    # Yeni paragrafları başa eklemek için referans = ilk mevcut paragraf
    body = doc.element.body
    first_para = body.find(qn("w:p"))
 
    def _make_paragraph(text: str, *, bold: bool = False, size: int = 11, color: Optional[str] = None) -> object:
        p = etree.Element(qn("w:p"))
        r = etree.SubElement(p, qn("w:r"))
        rPr = etree.SubElement(r, qn("w:rPr"))
        if bold:
            etree.SubElement(rPr, qn("w:b"))
        sz = etree.SubElement(rPr, qn("w:sz"))
        sz.set(qn("w:val"), str(size * 2))  # OOXML half-points
        if color:
            col = etree.SubElement(rPr, qn("w:color"))
            col.set(qn("w:val"), color)
        t = etree.SubElement(r, qn("w:t"))
        t.set(qn("xml:space"), "preserve")
        t.text = text
        return p
 
    paragraphs_to_add = []
 
    paragraphs_to_add.append(_make_paragraph(
        "📋 APA Doğrulayıcı — Düzeltme Yaması", bold=True, size=14, color="2F5496"
    ))
    paragraphs_to_add.append(_make_paragraph(
        f"Otomatik uygulanan değişiklik sayısı: {len(applied)}", size=11
    ))
    paragraphs_to_add.append(_make_paragraph(
        "Aşağıdaki tracked changes'leri tek tek inceleyip Word'ün "
        "İncele > Kabul Et / Reddet menüsünden onaylayın.",
        size=10,
    ))
    paragraphs_to_add.append(_make_paragraph("", size=10))  # boş satır
 
    if applied:
        paragraphs_to_add.append(_make_paragraph(
            "✅ Otomatik Uygulanan Düzeltmeler:", bold=True, size=12, color="00833F"
        ))
 
        # Kategoriye göre grupla
        by_cat: dict = {}
        for sub in applied:
            by_cat.setdefault(sub.category, []).append(sub)
 
        for cat, subs in by_cat.items():
            paragraphs_to_add.append(_make_paragraph(
                f"  • {cat}: {len(subs)} değişiklik", size=10
            ))
 
    paragraphs_to_add.append(_make_paragraph("", size=10))
 
    if manual:
        paragraphs_to_add.append(_make_paragraph(
            "⚠️ Manuel İnceleme Gereken Sorunlar:", bold=True, size=12, color="C45911"
        ))
        paragraphs_to_add.append(_make_paragraph(
            "Aşağıdaki sorunlar otomatik düzeltilemedi (italik, girinti, satır aralığı, "
            "alfabetik sıra gibi). Word'de manuel olarak düzeltin:",
            size=10,
        ))
 
        # Severity'ye göre sırala
        sev_order = {"error": 0, "warning": 1, "info": 2}
        sorted_manual = sorted(manual, key=lambda i: sev_order.get(i.severity, 99))
 
        for issue in sorted_manual[:30]:  # En fazla 30
            icon = {"error": "🔴", "warning": "🟡", "info": "🔵"}[issue.severity]
            paragraphs_to_add.append(_make_paragraph(
                f"  {icon} [{issue.category}] {issue.location}: {issue.message}",
                size=10,
            ))
            if issue.suggestion:
                paragraphs_to_add.append(_make_paragraph(
                    f"     ✓ Öneri: {issue.suggestion}",
                    size=9, color="595959",
                ))
 
        if len(manual) > 30:
            paragraphs_to_add.append(_make_paragraph(
                f"  ... ve {len(manual) - 30} sorun daha (uygulamanın sekmesinde tüm liste).",
                size=10, color="595959",
            ))
 
    paragraphs_to_add.append(_make_paragraph("", size=10))
    paragraphs_to_add.append(_make_paragraph(
        "─" * 70, size=10, color="BFBFBF"
    ))
    paragraphs_to_add.append(_make_paragraph(
        f"Yama tarihi: {datetime.now().strftime('%Y-%m-%d %H:%M')} · "
        f"APA Doğrulayıcı v0.6",
        size=9, color="808080",
    ))
    paragraphs_to_add.append(_make_paragraph("", size=10))
 
    # Tüm paragrafları belgenin başına ekle
    # addprevious her seferinde first_para'nın hemen öncesine eklediği için
    # forward iteration ile doğal sıra korunur (her yeni paragraf öncekinden sonra gelir)
    for p in paragraphs_to_add:
        if first_para is not None:
            first_para.addprevious(p)
        else:
            body.append(p)
 
 
# =============================================================================
# Ana orkestratör
# =============================================================================
 
def generate_track_changes_patch(
    input_docx_path: str,
    output_docx_path: str,
    citations: List[Citation],
    references: List[Reference],
    inspection: DocxInspection,
    format_issues: List[FormatIssue],
    add_summary: bool = True,
) -> PatchResult:
    """
    Bir DOCX dosyasından tracked changes'lı yamalı bir DOCX üretir.
 
    Otomatik uygulanan: page range, et al., DOI.
    Manuel inceleme listesi (özet sayfada): italik, girinti, satır aralığı, vs.
    """
    doc = Document(input_docx_path)
 
    # Paragrafları indeksle: hem ham XML elementi hem konum
    all_paragraphs = list(doc.paragraphs)
    all_p_xml = [p._element for p in all_paragraphs]
 
    # Referans paragrafları için: docx_inspector eşleştirmesi sırayla index üzerinden
    # Ama burada all_p_xml içinde gerçek indeksini bulmalıyız.
    # docx_inspector body+ref ayrımı yaptığı için orada paragraph_index'lerini
    # kaybettik. Tekrar gövde/referans bölmesi yap.
    ref_heading_idx = None
    ref_heading_re = re.compile(
        r"^\s*(references|reference list|kaynaklar|kaynakça|kaynakca|bibliography|works\s+cited)\s*$",
        re.IGNORECASE,
    )
    for i, p in enumerate(all_paragraphs):
        if ref_heading_re.match(p.text or ""):
            ref_heading_idx = i
            break
 
    body_paragraphs_xml: List[object] = []
    ref_paragraphs_xml: List[object] = []
    if ref_heading_idx is not None:
        body_paragraphs_xml = all_p_xml[:ref_heading_idx]
        # Referans bölümünden sonra boş olmayanlar (inspector ile aynı filtre)
        for p in all_paragraphs[ref_heading_idx + 1:]:
            if (p.text or "").strip():
                ref_paragraphs_xml.append(p._element)
    else:
        body_paragraphs_xml = list(all_p_xml)
 
    # docx_inspector'ün reference_to_paragraph haritası ile eşleştir
    # Bu harita: ref_idx → ref_paragraphs_xml içindeki indeks
    para_index_in_doc = {
        ref_para_idx: ref_paragraphs_xml[ref_para_idx]
        for ref_para_idx in range(len(ref_paragraphs_xml))
    }
 
    # Otomatik düzeltmeleri tespit et
    body_text_full = "\n".join(p.text for p in all_paragraphs)
    fixes: List[TextSubstitution] = []
    fixes.extend(_detect_page_range_fixes(references, inspection, para_index_in_doc))
    fixes.extend(_detect_doi_fixes(references, inspection, para_index_in_doc))
    fixes.extend(_detect_etal_fixes(citations, body_paragraphs_xml, body_text_full))
 
    # Uygula
    id_gen = _ChangeIdGenerator(start=1000)
    applied: List[TextSubstitution] = []
    failed_count = 0
    for sub in fixes:
        if _apply_substitution(sub, id_gen):
            applied.append(sub)
        else:
            failed_count += 1
 
    # Manuel inceleme listesi
    manual = [i for i in format_issues if i.category in _MANUAL_REVIEW_CATEGORIES]
 
    # Özet sayfa
    if add_summary:
        _add_summary_page(doc, applied, manual)
 
    # Kaydet
    doc.save(output_docx_path)
 
    # Kategoriye göre özet
    fixes_by_category: dict = {}
    for sub in applied:
        fixes_by_category[sub.category] = fixes_by_category.get(sub.category, 0) + 1
 
    return PatchResult(
        output_path=output_docx_path,
        applied_count=len(applied),
        failed_count=failed_count,
        fixes_by_category=fixes_by_category,
        manual_review=manual,
    )
 
