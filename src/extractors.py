"""
Atıf ve referans çıkarımı.

İki temel sınıf:
- Citation: metin içi atıflar (Smith, 2020) / Smith (2020) / (Yazar vd., 2020)
- Reference: kaynakçadaki tek bir bibliyografik kayıt

MVP düzeyinde regex tabanlı; gelişmiş sürümde LLM doğrulama eklenecek.

NOT: Bu sürüm aşağıdaki kenar durumlarını düzeltir:
- Mc/Mac/O'/d'/D' önekli soyadlar (O'Donnell, McIntyre, d'Uva, Bago d'Uva)
- Curly/typographic apostroflar (U+2019, U+2018, U+02BC)
- Lowercase soyad ön ekleri parantez içi atıflarda (van, von, de, del, ...)
- Çok kelimeli kurumsal yazarlar (World Bank, European Commission, ...)
- Karma kurumsal listeler (WHO & World Bank, OECD & European Commission)
- Türkçe söylem belirteçlerinin yanlış yazar olarak yakalanması (Birincisi, Ayrıca, ...)
- PDF/Word kaynaklı non-breaking ve dar boşluklar
- "and"/"ve" bağlaçlarının kelime ortasında eşleşmesinin engellenmesi (Handastya, Nanda, ...)
- Anlatımsal atıflarda yazardan önce sözcük olmamasını zorunlu kılma (la Zadeh yanlış yakalaması)
- APA-aware kaynakça entry bölme ve yıl-temelli birleştirme
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional

# --- Karakter sınıfları (Türkçe diakritikler dahil) ---
_UPPER = r"A-ZÇĞİÖŞÜ"
_LOWER = r"a-zçğıöşü"

# Tüm apostrof türleri: düz ', sağ tek tırnak ’, sol tek tırnak ‘, modifier letter apostrophe ʼ, prime ʹ
_APOS = r"['\u2019\u2018\u02BC\u02B9]"

# Lowercase soyad ön ekleri: van, von, de, del, della, di, da, du, le, la, el, al, bin, ibn, ten, ter, der, den, af, av, of
_PREFIX_LOWER = r"(?:van|von|de|del|della|di|da|du|le|la|el|al|bin|ibn|ten|ter|der|den|af|av|of)"

# Tek bir yazar "çekirdek" parçası: Mc/Mac/O'/D'/d'/L'/l' önekleri + büyük harf + küçük harfler
_AUTHOR_CORE = rf"(?:Mc|Mac|D{_APOS}|d{_APOS}|O{_APOS}|L{_APOS}|l{_APOS})?[{_UPPER}][{_LOWER}]+"

# Bir yazar parçası: isteğe bağlı lowercase ön ek (van, de, ...) + çekirdek
_AUTHOR_PART = rf"(?:{_PREFIX_LOWER}\s+)?{_AUTHOR_CORE}"

# Tam yazar (çok parçalı): "Smith", "Van Dijk", "O'Brien", "Müller-Schmidt", "Bago d'Uva"
_AUTHOR = rf"{_AUTHOR_PART}(?:[\s\-]{_AUTHOR_PART}){{0,3}}"

# Anlatımsal atıflarda lowercase prefix İSTEMEYEN katı yazar (yan-cümle "la Zadeh" yanlış yakalamasını önler)
_AUTHOR_STRICT = rf"{_AUTHOR_CORE}(?:[\s\-]{_AUTHOR_CORE}){{0,3}}"

# Kısaltma yazar (acronym): WHO, OECD, FDA, NATO, UNESCO (2-8 büyük harf)
_ACRONYM = rf"[{_UPPER}]{{2,8}}"

# Çok kelimeli kurumsal yazar: "World Bank", "European Commission", "United Nations"
_ORG_MULTIWORD = rf"[{_UPPER}][{_LOWER}]+(?:\s+(?:{_PREFIX_LOWER}\s+)?[{_UPPER}][{_LOWER}]+){{1,4}}"

# Genel kurumsal yazar (acronym veya çok kelimeli)
_ORG = rf"(?:{_ACRONYM}|{_ORG_MULTIWORD})"

# Bir "isim veya kurum"
_NAME_OR_ORG = rf"(?:{_AUTHOR}|{_ORG})"

# Whitespace karakter sınıfı: normal boşluk + non-breaking + narrow no-break + thin space
_WS = r"[\s\u00A0\u202F\u2009]"

# "et al." / "vd." / "ve ark." / "ve diğerleri" varyantları
_ETAL = rf"(?:et{_WS}*al\.?|vd\.?|ve{_WS}*ark\.?|ve{_WS}*diğerleri)"

# Bağlaçlar: & / and / ve — \b ile kelime sınırı zorunlu (Handastya, Nanda, Sandford gibi soyadların bölünmesini engeller)
_CONJ = r"(?:&|\band\b|\bve\b)"

# Türkçe iyelik / ilgi ekleri yazara bitişebilir: Reason'ın, Smith'in, Vincent'a
_POSSESSIVE = rf"(?:{_APOS}[{_LOWER}]+)?"

# Yazar listesi (parantez içi ATIF için):
_AUTHORS_PAREN = (
    rf"(?:"
    rf"{_NAME_OR_ORG}"
    rf"(?:\s*,\s*{_NAME_OR_ORG}){{0,15}}"
    rf"(?:\s*,?\s*{_CONJ}\s*{_NAME_OR_ORG})?"
    rf"(?:\s*,?\s*{_ETAL})?"
    rf")"
)

# Yazar listesi (anlatımsal ATIF için): yıl parantezden önceki yazar(lar)
# NOT: Anlatımsal yazar STRICT — lowercase prefix YOK; "la Zadeh (1965)" cümle parçası olarak yanlış yakalanmasın
_AUTHORS_NARRATIVE = (
    rf"(?:"
    rf"{_AUTHOR_STRICT}{_POSSESSIVE}"
    rf"(?:\s*,\s*{_AUTHOR_STRICT})*"
    rf"(?:\s*{_CONJ}\s*{_AUTHOR_STRICT})?"
    rf"(?:\s+{_ETAL})?"
    rf"|"
    rf"{_ORG}"
    rf")"
)

# Sayfa eki: , p. 5 / , pp. 5-7 / , s. 5 / , ss. 5-7
_PAGE = r"(?:\s*,\s*(?:p\.|pp\.|s\.|ss\.)\s*[\d\-,\s]+)?"

# --- Atıf desenleri ---

# Parantez içi atıf
PAREN_CITATION = re.compile(
    rf"\((?P<authors>{_AUTHORS_PAREN})\s*,\s*(?P<year>\d{{4}}[a-z]?){_PAGE}\)",
    re.UNICODE,
)

# Anlatımsal atıf: Smith (2020), Smith ve Jones (2020), Reason'ın (2000)
# Lookbehind: yazardan önce harf olmamalı — "metin la Zadeh (1965)" gibi yanlış yakalamayı engeller
NARRATIVE_CITATION = re.compile(
    rf"(?<![{_LOWER}{_UPPER}])"
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

# Yazar olamayacak Türkçe / İngilizce söylem belirteçleri ve genel sözcükler
_NON_AUTHOR_WORDS = {
    "Birincisi", "İkincisi", "Üçüncüsü", "Dördüncüsü", "Beşincisi",
    "Altıncısı", "Yedincisi", "Sekizincisi",
    "Ayrıca", "Ancak", "Fakat", "Lakin", "Yani", "Çünkü", "Öyleyse",
    "Örneğin", "Mesela", "Şekil", "Tablo", "Bölüm", "Kısım", "Madde",
    "Figure", "Table", "Section", "Chapter", "Part", "Appendix",
    "Bu", "Şu", "Bunun", "Şunun", "Bunlar", "Şunlar",
    "Sonuç", "Sonuçta", "Özet", "Genel",
}

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
        cleaned = re.sub(_ETAL, "", self.authors, flags=re.UNICODE).strip()
        # Türkçe iyelik / ilgi ekini at — yalnızca apostrof + KÜÇÜK HARF + KELİME SONU
        cleaned = re.sub(
            rf"{_APOS}(?:ın|in|un|ün|nın|nin|nun|nün|a|e|ya|ye|da|de|ta|te|den|dan|ki|s)\b",
            "",
            cleaned,
            flags=re.UNICODE,
        )
        # Bağlaçta ve virgülde böl — _CONJ artık word-boundary korumalı (Handastya bölünmez)
        first = re.split(rf"\s+{_CONJ}\s+|\s*,\s*", cleaned, maxsplit=1)[0]
        return first.strip()

    @property
    def key(self) -> str:
        """Çapraz eşleştirme anahtarı: 'soyad|yıl' (lower-case, apostrof normalize)."""
        sn = self.first_author_surname
        sn = re.sub(_APOS, "'", sn)
        return f"{sn.lower()}|{self.year}"

@dataclass
class Reference:
    """Kaynakçadaki tek bir bibliyografik kayıt."""
    raw: str
    authors_raw: Optional[str] = None
    year: Optional[str] = None
    title: Optional[str] = None
    doi: Optional[str] = None

    validation_match: Optional[dict] = None
    validation_score: float = 0.0
    validation_status: str = "unchecked"
    validation_provider: Optional[str] = None
    validation_attempts: List[dict] = field(default_factory=list)

    llm_parsed: bool = False
    llm_parse_data: Optional[dict] = None
    hallucination_assessment: Optional[dict] = None

    @property
    def first_author_surname(self) -> Optional[str]:
        if not self.authors_raw:
            return None
        # APA: "O'Donnell, O., van Doorslaer, E., & ..." → ilk virgül soyaddan sonra gelir,
        # baş harf ve "." içeren parçalardan kaçınmak için: 
        # Sadece "ad" gibi parçaları (X.X. veya X.) atla; gerçek soyada kadar yürü
        text = self.authors_raw.strip()
        # İlk virgüle kadar olan kısım soyaddır (APA kuralı)
        first = re.split(r"\s*,\s*|\s*&\s*|\s+and\s+", text)[0]
        return first.strip(" .")

    @property
    def key(self) -> Optional[str]:
        sn = self.first_author_surname
        if not sn or not self.year:
            return None
        sn = re.sub(_APOS, "'", sn)
        return f"{sn.lower()}|{self.year}"

# --- Yardımcılar ---

def _normalize_whitespace(text: str) -> str:
    """PDF/Word kaynaklı garip whitespace karakterlerini temizler."""
    text = text.replace("\u00AD", "")  # soft hyphen
    text = re.sub(r"[\u00A0\u202F\u2009\u200A]", " ", text)
    text = re.sub(r"([a-zçğıöşüA-ZÇĞİÖŞÜ])-\n([a-zçğıöşüA-ZÇĞİÖŞÜ])", r"\1\2", text, flags=re.UNICODE)
    text = re.sub(r"(?<=[a-zçğıöşü,])\n(?=[a-zçğıöşü])", " ", text, flags=re.UNICODE)
    return text

# --- Çıkarım fonksiyonları ---

PAREN_BLOCK = re.compile(r"\(([^()]*\b\d{4}[a-z]?\b[^()]*)\)", re.UNICODE)

def extract_in_text_citations(body: str) -> List[Citation]:
    """Metin gövdesinden tüm metin içi atıfları çıkar."""
    body = _normalize_whitespace(body)

    citations: List[Citation] = []
    matched_spans: List[tuple] = []

    for block in PAREN_BLOCK.finditer(body):
        inner = block.group(1)
        block_start = block.start()
        matched_spans.append((block.start(), block.end()))

        parts_inner = _MULTI_SPLIT.split(inner)

        for part in parts_inner:
            im = _MULTI_INNER.search(part.strip())
            if not im:
                continue
            citations.append(
                Citation(
                    raw=f"({part.strip()})" if len(parts_inner) > 1 else block.group(0),
                    authors=im.group("authors").strip(),
                    year=im.group("year"),
                    citation_type="parenthetical",
                    position=block_start,
                )
            )

    for m in NARRATIVE_CITATION.finditer(body):
        if any(s <= m.start() < e for s, e in matched_spans):
            continue
        if m.start() > 0 and body[m.start() - 1] == "(":
            continue

        authors_str = m.group("authors").strip()
        first_token = re.split(r"[\s,]+", authors_str)[0]
        if first_token in _NON_AUTHOR_WORDS:
            if "," in authors_str:
                remainder = authors_str.split(",", 1)[1].strip()
                if remainder:
                    authors_str = remainder
                else:
                    continue
            else:
                continue

        citations.append(
            Citation(
                raw=m.group(0),
                authors=authors_str,
                year=m.group("year"),
                citation_type="narrative",
                position=m.start(),
            )
        )

    citations.sort(key=lambda c: c.position)
    return citations

def _split_reference_entries(refs_text: str) -> List[str]:
    """
    Kaynakça metnini ayrı kayıtlara böl. APA-aware:
    - Önce çift yeni satıra göre dener.
    - Olmazsa "satır başı + Soyad, X." kalıbına göre böler (X. = baş harf).
    - Sonra yıl içermeyen parçaları bir önceki entry'ye birleştirir
      (hanging indent kaybı yaşamış PDF'ler için).
    """
    refs_text = refs_text.strip()
    if not refs_text:
        return []

    # Strateji 1: çift yeni satır
    blocks = re.split(r"\n\s*\n", refs_text)
    if len(blocks) > 3:
        candidates = [b.replace("\n", " ").strip() for b in blocks if len(b.strip()) > 20]
    else:
        # Strateji 2: APA-aware — satır başında "Soyad, X." kalıbına göre böl
        # Soyad: opsiyonel lowercase prefix + büyük harf + (harf|apostrof|tire)+
        # Ardından virgül + boşluk + büyük harf + nokta (baş harf)
        pattern = (
            rf"\n(?=(?:{_PREFIX_LOWER}\s+)?"
            rf"(?:Mc|Mac|D{_APOS}|d{_APOS}|O{_APOS}|L{_APOS}|l{_APOS})?"
            rf"[{_UPPER}][{_LOWER}{_UPPER}\-]*{_APOS}?[{_LOWER}{_UPPER}\-]+"
            rf"\s*,\s*[{_UPPER}]\.)"
        )
        lines = re.split(pattern, refs_text, flags=re.UNICODE)
        candidates = [l.replace("\n", " ").strip() for l in lines if len(l.strip()) > 20]

    # Birleştirme: yıl içermeyen parçaları bir önceki entry'ye ekle
    merged: List[str] = []
    year_re = re.compile(r"\(\d{4}[a-z]?\)|\b(?:19|20)\d{2}\b")
    for c in candidates:
        if not year_re.search(c) and merged:
            merged[-1] = merged[-1] + " " + c
        else:
            merged.append(c)
    return merged

def extract_references(refs_text: str) -> List[Reference]:
    """Kaynakça metnini Reference nesnelerine ayır."""
    if not refs_text or not refs_text.strip():
        return []

    entries = _split_reference_entries(refs_text)
    references: List[Reference] = []

    for entry in entries:
        ref = Reference(raw=entry)

        doi_match = DOI_PATTERN.search(entry)
        if doi_match:
            ref.doi = doi_match.group(0).rstrip(".,;)")

        ym = YEAR_IN_PARENS.search(entry)
        if ym:
            ref.year = ym.group(1)
            ref.authors_raw = entry[: ym.start()].strip().rstrip(".,")
            after = entry[ym.end():].strip().lstrip(".").strip()
            tm = re.match(r"([^.]+)\.", after)
            if tm:
                ref.title = tm.group(1).strip()
        else:
            ym2 = YEAR_BARE.search(entry)
            if ym2:
                ref.year = ym2.group(0)
                # Yıl bulunduysa yazar = yıldan önceki kısım
                ref.authors_raw = entry[: ym2.start()].strip().rstrip(".,")

        references.append(ref)

    return references
