"""
DOCX biçim incelemesi.
 
Bu modül, python-docx kullanarak bir Word belgesinin biçimsel özelliklerini
çıkarır: paragraf girintileri, satır aralığı ve italik metin spanları.
 
Bu bilgiler düz metinden okunamadığı için DOCX-spesifik APA 7 kontrolleri
(asılı girinti, çift satır aralığı, dergi adı/cilt italikliği) bu modüle dayanır.
"""
from __future__ import annotations
 
import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
 
from .extractors import Reference
 
 
# --- Veri modelleri --------------------------------------------------------
 
 
@dataclass
class ItalicSpan:
    """Bir paragraf metni içinde italik biçimli bir aralık."""
    start: int   # paragraph.text içindeki konum (0-tabanlı)
    end: int     # exclusive
    text: str
 
 
@dataclass
class ParagraphFormatInfo:
    """Tek bir paragrafın biçim metaverileri."""
    text: str
    # Girintiler — punto cinsinden (None = miras alıyor / belirsiz)
    first_line_indent_pt: Optional[float] = None
    left_indent_pt: Optional[float] = None
    # Satır aralığı
    line_spacing: Optional[float] = None       # 1.0 = single, 2.0 = double
    line_spacing_rule: Optional[str] = None    # "DOUBLE", "MULTIPLE", "SINGLE"...
    # Italik spanlar
    italic_spans: List[ItalicSpan] = field(default_factory=list)
 
    @property
    def has_hanging_indent(self) -> bool:
        """
        APA 7 asılı girinti: ilk satır 0", sonraki satırlar 0.5".
        python-docx'te bu, first_line_indent < 0 ve left_indent > 0 olarak gelir.
        Örn: first_line_indent = -36 pt, left_indent = 36 pt.
        Eşik 10 pt: dokümanın "Hanging" stili kullanılmış olabilir.
        """
        if self.first_line_indent_pt is None:
            return False
        # Negatif first_line_indent + pozitif left_indent → asılı girinti
        return self.first_line_indent_pt < -5
 
    @property
    def is_double_spaced(self) -> bool:
        """APA 7: çift satır aralığı (2.0)."""
        if self.line_spacing_rule == "DOUBLE":
            return True
        if self.line_spacing is None:
            return False
        return abs(self.line_spacing - 2.0) < 0.05
 
 
@dataclass
class DocxInspection:
    """Tüm DOCX inceleme sonuçları."""
    body_paragraphs: List[ParagraphFormatInfo]
    reference_paragraphs: List[ParagraphFormatInfo]
    # Reference indeksinden reference_paragraphs indeksine eşleme
    reference_to_paragraph: dict = field(default_factory=dict)
 
 
# --- DOCX okuma ------------------------------------------------------------
 
 
_REFERENCE_HEADING_RE = re.compile(
    r"^\s*(references|reference list|kaynaklar|kaynakça|kaynakca|bibliography|works\s+cited)\s*$",
    re.IGNORECASE,
)
 
 
def _is_run_italic(run) -> bool:
    """
    Bir run'un italik olup olmadığını kontrol et — stil mirası dahil.
 
    python-docx'te run.italic üç değer alabilir:
      True  → açıkça italik
      False → açıkça düz
      None  → karakter stilinden miras al
    """
    if run.italic is True:
        return True
    if run.italic is False:
        return False
    # Miras: stil hiyerarşisinde italik tanımı var mı?
    style = getattr(run, "style", None)
    seen = set()
    while style is not None and id(style) not in seen:
        seen.add(id(style))
        font = getattr(style, "font", None)
        if font is not None:
            if font.italic is True:
                return True
            if font.italic is False:
                return False
        style = getattr(style, "base_style", None)
    return False
 
 
def _inspect_paragraph(p) -> ParagraphFormatInfo:
    """python-docx Paragraph nesnesini ParagraphFormatInfo'ya dönüştür."""
    pf = p.paragraph_format
 
    first_line_indent_pt = pf.first_line_indent.pt if pf.first_line_indent is not None else None
    left_indent_pt = pf.left_indent.pt if pf.left_indent is not None else None
 
    line_spacing = pf.line_spacing  # zaten float ya da None
    line_spacing_rule = None
    if pf.line_spacing_rule is not None:
        # WD_LINE_SPACING enum → string
        rule_str = str(pf.line_spacing_rule)
        # "DOUBLE (3)" → "DOUBLE"
        line_spacing_rule = rule_str.split()[0] if rule_str else None
 
    # Italik spanları topla
    italic_spans: List[ItalicSpan] = []
    pos = 0
    for run in p.runs:
        run_text = run.text or ""
        run_len = len(run_text)
        if run_len > 0 and _is_run_italic(run):
            italic_spans.append(ItalicSpan(start=pos, end=pos + run_len, text=run_text))
        pos += run_len
 
    return ParagraphFormatInfo(
        text=p.text,
        first_line_indent_pt=first_line_indent_pt,
        left_indent_pt=left_indent_pt,
        line_spacing=line_spacing,
        line_spacing_rule=line_spacing_rule,
        italic_spans=italic_spans,
    )
 
 
def _match_references_to_paragraphs(
    references: List[Reference],
    ref_paragraphs: List[ParagraphFormatInfo],
) -> dict:
    """
    Her Reference nesnesini DOCX paragrafına en yüksek kelime örtüşmesiyle eşleştir.
 
    Her paragraf en fazla bir referansa atanır (1-1 eşleşme).
    Eşik: en az 5 ortak anlamlı kelime.
    """
    matches: dict = {}
    used_paragraphs: set = set()
 
    def _significant_words(text: str) -> set:
        # Çok kısa kelimeleri ele
        return {w.lower() for w in re.findall(r"\w{4,}", text)}
 
    for ref_idx, ref in enumerate(references):
        ref_words = _significant_words(ref.raw)
        if not ref_words:
            continue
 
        best_idx, best_overlap = None, 0
        for para_idx, para in enumerate(ref_paragraphs):
            if para_idx in used_paragraphs:
                continue
            para_words = _significant_words(para.text)
            overlap = len(ref_words & para_words)
            if overlap > best_overlap:
                best_overlap, best_idx = overlap, para_idx
 
        if best_idx is not None and best_overlap >= 5:
            matches[ref_idx] = best_idx
            used_paragraphs.add(best_idx)
 
    return matches
 
 
def inspect_docx(path: str, references: List[Reference]) -> Optional[DocxInspection]:
    """
    DOCX dosyasını biçim metaverileriyle birlikte oku.
 
    Sadece .docx dosyaları için anlamlıdır. Hata durumunda None döner —
    çağıran tarafta DOCX-spesifik kontrolleri atlamak için.
    """
    try:
        from docx import Document
    except ImportError:
        return None
 
    try:
        doc = Document(path)
    except Exception:
        return None
 
    all_paragraphs = list(doc.paragraphs)
    if not all_paragraphs:
        return DocxInspection(body_paragraphs=[], reference_paragraphs=[])
 
    # Referans bölümünün başlangıcını bul
    ref_start = None
    for i, p in enumerate(all_paragraphs):
        if _REFERENCE_HEADING_RE.match(p.text or ""):
            ref_start = i
            break
 
    if ref_start is None:
        # Referans başlığı yok; tümü gövde sayılır
        return DocxInspection(
            body_paragraphs=[_inspect_paragraph(p) for p in all_paragraphs],
            reference_paragraphs=[],
            reference_to_paragraph={},
        )
 
    body_paragraphs = [_inspect_paragraph(p) for p in all_paragraphs[:ref_start]]
    # Referans bölümünden sonra boş olmayan paragrafları al
    ref_paragraphs_raw = [p for p in all_paragraphs[ref_start + 1:] if (p.text or "").strip()]
    reference_paragraphs = [_inspect_paragraph(p) for p in ref_paragraphs_raw]
 
    ref_to_para = _match_references_to_paragraphs(references, reference_paragraphs)
 
    return DocxInspection(
        body_paragraphs=body_paragraphs,
        reference_paragraphs=reference_paragraphs,
        reference_to_paragraph=ref_to_para,
    )
 
 
# --- Yardımcı: dergi adı + cilt konumlarını yakala -------------------------
 
 
_JOURNAL_VOLUME_RE = re.compile(
    r"[.?!]\s+"                      # Başlık sonu: nokta, soru işareti veya ünlem + boşluk
    r"([^.?!]+?),\s+"                # Dergi adı (cümle sonu içermez), virgül
    r"(\d+)"                         # Cilt
    r"(?:\(\s*\d+(?:\s*-\s*\d+)?\s*\))?"  # Opsiyonel sayı (issue)
    r"\s*,\s*"
    r"\d"                            # Sayfa numarasının başı
)
 
 
def find_journal_volume_positions(text: str) -> Optional[Tuple[int, int, int, int]]:
    """
    Bir referans metninde dergi adı ve cilt numarasının konumlarını bul.
 
    APA 7 deseni:  Yazarlar. (Yıl). Başlık. Dergi Adı, Cilt(Sayı), sayfa-aralığı.
 
    Geri dönüş:
        (journal_start, journal_end, volume_start, volume_end)
        ya da bulunamazsa None.
    """
    m = _JOURNAL_VOLUME_RE.search(text)
    if not m:
        return None
    return (m.start(1), m.end(1), m.start(2), m.end(2))
 
 
def is_span_italic(start: int, end: int, italic_spans: List[ItalicSpan]) -> bool:
    """
    [start, end) aralığı tamamen herhangi bir italik span tarafından kapsanıyor mu?
 
    Tam kapsama gerekiyor — kısmi italik (örn. derginin sadece bir kelimesi)
    yetersiz sayılır.
    """
    for span in italic_spans:
        if span.start <= start and span.end >= end:
            return True
    return False
 
