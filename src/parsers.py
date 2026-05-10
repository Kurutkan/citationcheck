"""
Belge ayrıştırıcı.

Desteklenen formatlar:
- .docx  (python-docx)
- .pdf   (pdfplumber)
- .txt   (düz metin)

parse_document(path) -> str
    Belgeden düz metin döndürür; DOCX için paragrafları satır sonuyla ayırır.
    """
from __future__ import annotations

from pathlib import Path


def parse_document(path: str | Path) -> str:
      """
          Belgeyi okuyup düz metin olarak döndür.

              Parameters
                  ----------
                      path : str | Path
                              Dosya yolu (.docx, .pdf veya .txt).

                                  Returns
                                      -------
                                          str
                                                  Belgenin tüm metni.

                                                      Raises
                                                          ------
                                                              ValueError
                                                                      Desteklenmeyen dosya uzantısı.
                                                                          FileNotFoundError
                                                                                  Dosya bulunamazsa.
                                                                                      """
      path = Path(path)
      if not path.exists():
                raise FileNotFoundError(f"Dosya bulunamadı: {path}")

      suffix = path.suffix.lower()

    if suffix == ".docx":
              return _parse_docx(path)
elif suffix == ".pdf":
          return _parse_pdf(path)
elif suffix in (".txt", ".md"):
          return path.read_text(encoding="utf-8", errors="replace")
else:
          raise ValueError(
                        f"Desteklenmeyen dosya uzantısı: '{suffix}'. "
                        "Kabul edilenler: .docx, .pdf, .txt"
          )


def _parse_docx(path: Path) -> str:
      """DOCX dosyasını paragraf bazlı düz metne çevir."""
      from docx import Document  # python-docx

    doc = Document(str(path))
    lines: list[str] = []

    for para in doc.paragraphs:
              text = para.text.strip()
              if text:
                            lines.append(text)

          return "\n".join(lines)


def _parse_pdf(path: Path) -> str:
      """PDF dosyasını sayfa bazlı düz metne çevir."""
      import pdfplumber

    pages: list[str] = []
    with pdfplumber.open(str(path)) as pdf:
              for page in pdf.pages:
                            text = page.extract_text()
                            if text:
                                              pages.append(text.strip())

                    return "\n".join(pages)
