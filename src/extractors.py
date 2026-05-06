"""
Atıf ve referans çıkarımı.
 
İki temel sınıf:
- Citation:  metin içi atıflar  (Smith, 2020) / Smith (2020) / (Yazar vd., 2020)
- Reference: kaynakçadaki tek bir bibliyografik kayıt
 
MVP düzeyinde regex tabanlı; gelişmiş sürümde LLM doğrulama eklenecek.
"""
from __future__ import annotations
 
import re
from dataclasses import dataclass, field
from typing import List, Optional
 
# --- Karakter sınıfları (Türkçe diakritikler dahil) ---
_UPPER = r"A-ZÇĞİÖŞÜ"
_LOWER = r"a-zçğıöşü"
 
# Tek bir yazar parçası: "Smith", "Van Dijk", "O'Brien", "Müller-Schmidt"
_AUTHOR = rf"[{_UPPER}][{_LOWER}]+(?:[\s\-'][{_UPPER}][{_LOWER}]+)?"
 
# Acronym yazar: WHO, OECD, FDA, NATO (3-6 büyük harf)
_ACRONYM = rf"[{_UPPER}]{{2,6}}"
 
# "et al." / "vd." / "ve ark." / "ve diğerleri" varyantları
_ETAL = r"(?:et\s*al\.?|vd\.|ve\s*ark\.|ve\s*diğerleri)"
 
# Bağlaçlar: & / and / ve
_CONJ = r"(?:&|and|ve)"
 
# Türkçe iyelik / ilgi ekleri yazara bitişebilir: Reason'ın, Smith'in, Vincent'a
_POSSESSIVE = rf"(?:'[{_LOWER}]+)?"
 
# Yazar listesi (parantez içi ATIF için):
#   "Smith"
#   "Smith & Jones"
#   "Smith and Jones"
#   "Smith et al."
#   "Sammer, Lykens, Singh, Mains, & Lackan"  (3+ yazar virgüllü)
#   "WHO" / "OECD"
_AUTHORS_PAREN = (
    rf"(?:"
    rf"{_AUTHOR}"
    rf"(?:\s*,\s*{_AUTHOR}){{0,8}}"            # virgüllü ek yazarlar
    rf"(?:\s*,?\s*{_CONJ}\s*{_AUTHOR})?"       # son yazar & ile bağlı
    rf"(?:\s*,?\s*{_ETAL})?"                   # et al. / vd. / ve diğerleri
    rf"|"
    rf"{_ACRONYM}"                             # WHO, OECD vb.
    rf")"
)
 
# Yazar listesi (anlatımsal ATIF için): yıl parantezden önceki yazar(lar)
_AUTHORS_NARRATIVE = (
    rf"(?:"
    rf"{_AUTHOR}{_POSSESSIVE}"
    rf"(?:\s*,\s*{_AUTHOR})*"
    rf"(?:\s*{_CONJ}\s*{_AUTHOR})?"
    rf"(?:\s+{_ETAL})?"
    rf"|"
    rf"{_ACRONYM}"
    rf")"
)
 
# Sayfa eki: , p. 5  /  , pp. 5-7  /  , s. 5  /  , ss. 5-7
_PAGE = r"(?:\s*,\s*(?:p\.|pp\.|s\.|ss\.)\s*[\d\-,\s]+)?"
 
# --- Atıf desenleri ---
 
# Parantez içi atıf
PAREN_CITATION = re.compile(
    rf"\((?P<authors>{_AUTHORS_PAREN})\s*,\s*(?P<year>\d{{4}}[a-z]?){_PAGE}\)",
    re.UNICODE,
)
 
# Anlatımsal atıf: Smith (2020), Smith ve Jones (2020), Reason'ın (2000)
NARRATIVE_CITATION = re.compile(
    rf"(?P<authors>{_AUTHORS_NARRATIVE})\s*\((?P<year>\d{{4}}[a-z]?){_PAGE}\)",
    re.UNICODE,
)
 
# Çoklu atıf ayırıcı: (Smith, 2020; Jones, 2021)
_MULTI_SPLIT = re.compile(r"\s*;\s*")
_MULTI_INNER = re.compile(
    rf"(?P<authors>{_AUTHORS_PAREN})\s*,\s*(?P<year>\d{{4}}[a-z]?)",
    re.UNICODE,
)
 
# --- Referans listesi desenleri ---
DOI_PATTERN = re.compile(r"\b10\.\d{4,9}/[^\s,;]+", re.IGNORECASE)
YEAR_IN_PARENS = re.compile(r"\((\d{4}[a-z]?)\)")
YEAR_BARE = re.compile(r"\b(19|20)\d{2}[a-z]?\b")
 
 
@dataclass
class Citation:
    """Metin içi tek bir atıf."""
    raw: str
    authors: str
    year: str
    citation_type: str  # "parenthetical" | "narrative"
    position: int       # karakter ofseti (gövde metni içinde)
 
    @property
    def first_author_surname(self) -> str:
        """Eşleştirme için ilk yazarın soyadı (ham, lower-case değil)."""
        # "Smith & Jones" / "Smith et al." / "Smith and Jones" / "Smith, Jones, & Brown"
        cleaned = re.sub(_ETAL, "", self.authors).strip()
        # Türkçe iyelik ekini at: Reason'ın → Reason
        cleaned = re.sub(rf"'[{_LOWER}]+", "", cleaned)
        first = re.split(rf"\s*{_CONJ}\s*|\s*,\s*", cleaned)[0]
        return first.strip()
 
    @property
    def key(self) -> str:
        """Çapraz eşleştirme anahtarı: 'soyad|yıl' (lower-case)."""
        return f"{self.first_author_surname.lower()}|{self.year}"
 
 
@dataclass
class Reference:
    """Kaynakçadaki tek bir bibliyografik kayıt."""
    raw: str
    authors_raw: Optional[str] = None
    year: Optional[str] = None
    title: Optional[str] = None
    doi: Optional[str] = None
 
    # Doğrulama alanları (provider-bağımsız)
    validation_match: Optional[dict] = None     # Normalize edilmiş aday kayıt
    validation_score: float = 0.0
    validation_status: str = "unchecked"        # verified | low_confidence | not_found | unchecked
    validation_provider: Optional[str] = None   # "crossref" | "openalex" | ...
    validation_attempts: List[dict] = field(default_factory=list)
 
    # LLM alanları
    llm_parsed: bool = False                    # LLM ile yeniden ayrıştırıldı mı
    llm_parse_data: Optional[dict] = None       # ParsedReference içeriği (sözlük)
    hallucination_assessment: Optional[dict] = None  # HallucinationAssessment içeriği
 
    @property
    def first_author_surname(self) -> Optional[str]:
        if not self.authors_raw:
            return None
        # APA formatı: "Smith, J., & Jones, K." → ilk virgüle kadar olan
        first = re.split(r"\s*,\s*|\s*&\s*|\s+and\s+", self.authors_raw)[0]
        return first.strip(" .")
 
    @property
    def key(self) -> Optional[str]:
        sn = self.first_author_surname
        if not sn or not self.year:
            return None
        return f"{sn.lower()}|{self.year}"
 
 
# --- Çıkarım fonksiyonları ---
 
# Çoklu atıf yakalama: parantez içinde en az bir yıl bulunan blok
# Örn: (Smith, 2020; Jones, 2021)  veya  (Greenfield & Braithwaite, 2008; Brubakk, ..., 2015)
PAREN_BLOCK = re.compile(r"\(([^()]*\b\d{4}[a-z]?\b[^()]*)\)", re.UNICODE)
 
 
def extract_in_text_citations(body: str) -> List[Citation]:
    """Metin gövdesinden tüm metin içi atıfları çıkar."""
    citations: List[Citation] = []
    matched_spans: List[tuple] = []  # (start, end) parantez içi atıflarınki
 
    # 1) Parantez bloklarını yakala — sonra içini parçala
    for block in PAREN_BLOCK.finditer(body):
        inner = block.group(1)
        block_start = block.start()
        matched_spans.append((block.start(), block.end()))
 
        # Noktalı virgülle ayrılmış parçalar
        parts = _MULTI_SPLIT.split(inner)
        any_match = False
 
        for part in parts:
            im = _MULTI_INNER.search(part.strip())
            if not im:
                continue
            any_match = True
            # Parantez içinde sayfa eki olabilir; rawı parça olarak göster
            citations.append(
                Citation(
                    raw=f"({part.strip()})" if len(parts) > 1 else block.group(0),
                    authors=im.group("authors").strip(),
                    year=im.group("year"),
                    citation_type="parenthetical",
                    position=block_start,
                )
            )
 
        # Hiçbir parçada yazar+yıl eşleşmediyse bu blok muhtemelen atıf değil
        # (örn. "(2020)" sadece yıl, ya da "(N=403)") — atla
 
    # 2) Anlatımsal atıflar — parantez bloklarıyla çakışmasın
    for m in NARRATIVE_CITATION.finditer(body):
        # Parantez bloklarının içine düşüyorsa atla
        if any(s <= m.start() < e for s, e in matched_spans):
            continue
        # Hemen önündeki "(" varsa bu zaten parantez içi olarak görüldü
        if m.start() > 0 and body[m.start() - 1] == "(":
            continue
        citations.append(
            Citation(
                raw=m.group(0),
                authors=m.group("authors").strip(),
                year=m.group("year"),
                citation_type="narrative",
                position=m.start(),
            )
        )
 
    citations.sort(key=lambda c: c.position)
    return citations
 
 
def _split_reference_entries(refs_text: str) -> List[str]:
    """
    Kaynakça metnini ayrı kayıtlara böl.
 
    APA referansları çoğunlukla yeni satırla başlar ve büyük harfle açılır.
    Asılı girinti (hanging indent) PDF dönüşümünde bozulabilir; bu nedenle
    iki strateji denenir:
      1. Boş satıra göre böl
      2. Yeni satır + büyük harfle başlayan satırlara göre böl
    """
    refs_text = refs_text.strip()
    if not refs_text:
        return []
 
    # Strateji 1: çift yeni satır
    blocks = re.split(r"\n\s*\n", refs_text)
    if len(blocks) > 3:  # makul sayıda kayıt
        return [b.replace("\n", " ").strip() for b in blocks if len(b.strip()) > 20]
 
    # Strateji 2: tek satır + büyük harf başlangıç
    lines = re.split(rf"\n(?=[{_UPPER}])", refs_text)
    return [l.replace("\n", " ").strip() for l in lines if len(l.strip()) > 20]
 
 
def extract_references(refs_text: str) -> List[Reference]:
    """Kaynakça metnini Reference nesnelerine ayır."""
    if not refs_text or not refs_text.strip():
        return []
 
    entries = _split_reference_entries(refs_text)
    references: List[Reference] = []
 
    for entry in entries:
        ref = Reference(raw=entry)
 
        # DOI
        doi_match = DOI_PATTERN.search(entry)
        if doi_match:
            ref.doi = doi_match.group(0).rstrip(".,;)")
 
        # Yıl: önce parantez içi, sonra çıplak
        ym = YEAR_IN_PARENS.search(entry)
        if ym:
            ref.year = ym.group(1)
            # Yazar = yıldan önce
            ref.authors_raw = entry[: ym.start()].strip().rstrip(".,")
            # Başlık = yıldan sonraki ilk cümle (kabaca)
            after = entry[ym.end():].strip().lstrip(".").strip()
            tm = re.match(r"([^.]+)\.", after)
            if tm:
                ref.title = tm.group(1).strip()
        else:
            ym2 = YEAR_BARE.search(entry)
            if ym2:
                ref.year = ym2.group(0)
 
        references.append(ref)
 
    return references
 
