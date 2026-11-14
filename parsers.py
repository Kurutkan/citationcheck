"""
Belge ayrıştırıcı.

Desteklenen formatlar:
  - .docx  (python-docx)
  - .pdf   (pdfplumber)
  - .txt   (düz metin)

Ana giriş:
    parse_document(path) -> tuple[str, str]
        (body, references_section) ikilisi döndürür.
        - body: kaynakça bölümünden önceki metin (gövde)
        - references_section: "References / Kaynakça / Bibliography" başlığından
          sonraki metin (bulunmadıysa boş string)

Bu ikili dönüş, atıf ve referans çıkarımının birbirine karışmamasını sağlar.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Tuple


# Kaynakça başlığı varyantları (TR + EN). Çok dilli kabul için geniş tutuldu.
_REF_HEADING_RE = re.compile(
    r"(?im)^[\s\*#>0-9\.\)\-]*"
    r"(references?|reference\s*list|works\s+cited|bibliography|"
    r"kaynak(?:ça|ca|lar)|kaynaklar\s*ve\s*ek(?:ler)?|"
    # İspanyolca, Portekizce, Fransızca, İtalyanca, Almanca
    r"referencias(?:\s+bibliogr[aá]ficas)?|refer[eê]ncias(?:\s+bibliogr[aá]ficas)?|"
    r"bibliograf[ií]a|obras\s+citadas|r[eé]f[eé]rences(?:\s+bibliographiques)?|"
    r"bibliographie|riferimenti(?:\s+bibliografici)?|literatur(?:verzeichnis)?)"
    r"\s*[:\.]?\s*$"
)


def parse_document(path: str | Path) -> Tuple[str, str]:
    """
    Belgeyi okuyup (gövde, kaynakça_bölümü) ikilisi olarak döndür.

    Parameters
    ----------
    path : str | Path
        Dosya yolu (.docx, .pdf, .txt veya .md).

    Returns
    -------
    tuple[str, str]
        (body, references_section). Kaynakça başlığı bulunamazsa
        references_section = "" döner ve tüm metin body içinde kalır.

    Raises
    ------
    FileNotFoundError
        Dosya yoksa.
    ValueError
        Desteklenmeyen uzantı.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Dosya bulunamadı: {path}")

    suffix = path.suffix.lower()
    if suffix == ".docx":
        text = _parse_docx(path)
    elif suffix == ".pdf":
        text = _parse_pdf(path)
    elif suffix in (".txt", ".md"):
        text = path.read_text(encoding="utf-8", errors="replace")
    else:
        raise ValueError(
            f"Desteklenmeyen dosya uzantısı: '{suffix}'. "
            "Kabul edilenler: .docx, .pdf, .txt, .md"
        )

    return split_body_and_references(text)


def split_body_and_references(text: str) -> Tuple[str, str]:
    """
    Düz metni gövde ve kaynakça bölümüne ayır.

    Strateji:
    1. Satır bazında "References / Kaynakça / Bibliography" başlığı ara
       (sadece kendi başına bir satırda olan; gövde içinde geçen "references"
       kelimesi yanıltıcı olmasın diye).
    2. En SON eşleşmeyi kullan - bazı makalelerde "References" kelimesi
       önce metin içinde geçebilir; gerçek kaynakça başlığı sonda olur.
    3. Hiç eşleşme yoksa (body=tüm metin, refs="") döndür.
    """
    if not text:
        return "", ""

    matches = list(_REF_HEADING_RE.finditer(text))
    if not matches:
        return text, ""

    last = matches[-1]
    body = text[: last.start()].rstrip()
    refs_section = text[last.end():].lstrip()
    return body, refs_section


def _parse_docx(path: Path) -> str:
    """DOCX dosyasını düz metne çevir.

    Gövde paragrafları ve tablolar belgedeki sırayla okunur (tablo hücrelerindeki
    atıflar kaybolmaz); dipnot ve sonnotlar gövdenin sonuna, kaynakça başlığından
    önce eklenir.
    """
    from docx import Document  # python-docx
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    doc = Document(str(path))
    lines: list[str] = []

    def _add_table(tbl) -> None:
        seen: set[int] = set()
        for row in tbl.rows:
            for cell in row.cells:
                if id(cell._tc) in seen:  # birleştirilmiş hücreler tekrar etmesin
                    continue
                seen.add(id(cell._tc))
                for para in cell.paragraphs:
                    t = para.text.strip()
                    if t:
                        lines.append(t)
                for inner in cell.tables:
                    _add_table(inner)

    for child in doc.element.body.iterchildren():
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            t = Paragraph(child, doc).text.strip()
            if t:
                lines.append(t)
        elif tag == "tbl":
            _add_table(Table(child, doc))

    notes = _docx_notes(doc)
    if notes:
        # Notları son kaynakça başlığından önce yerleştir ki gövde sayılsınlar
        idx = None
        for k in range(len(lines) - 1, -1, -1):
            if _REF_HEADING_RE.match(lines[k]):
                idx = k
                break
        if idx is None:
            lines.extend(notes)
        else:
            lines[idx:idx] = notes
    return "\n".join(lines)


def _docx_notes(doc) -> list[str]:
    """Dipnot ve sonnot metinleri (varsa)."""
    W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    out: list[str] = []
    try:
        for rel in doc.part.rels.values():
            if rel.is_external:
                continue
            if not (rel.reltype.endswith("/footnotes") or rel.reltype.endswith("/endnotes")):
                continue
            from lxml import etree
            root = etree.fromstring(rel.target_part.blob)
            for note in root:
                if note.get(f"{W}type") in ("separator", "continuationSeparator", "continuationNotice"):
                    continue
                for para in note.iter(f"{W}p"):
                    t = "".join(node.text or "" for node in para.iter(f"{W}t")).strip()
                    if t:
                        out.append(t)
    except Exception:
        return out
    return out


def _parse_pdf(path: Path) -> str:
    """PDF dosyasını sayfa bazlı düz metne çevir."""
    import pdfplumber

    pages: list[str] = []
    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                # Yalnızca sayfa numarasından oluşan satırları at
                kept = [ln for ln in t.split("\n") if not re.fullmatch(r"\s*\d{1,4}\s*", ln)]
                pages.append("\n".join(kept).strip())
    return "\n".join(pages)
