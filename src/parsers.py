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
    r"kaynak(?:ça|ca|lar)|kaynaklar\s*ve\s*ek(?:ler)?)"
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
    """DOCX dosyasını paragraf bazlı düz metne çevir."""
    from docx import Document  # python-docx

    doc = Document(str(path))
    lines: list[str] = []
    for para in doc.paragraphs:
        t = para.text.strip()
        if t:
            lines.append(t)
    return "\n".join(lines)


def _parse_pdf(path: Path) -> str:
    """PDF dosyasını sayfa bazlı düz metne çevir."""
    import pdfplumber

    pages: list[str] = []
    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                pages.append(t.strip())
    return "\n".join(pages)
