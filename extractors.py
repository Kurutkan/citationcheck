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
- Kaynakça tarafında çok kelimeli soyad ve kurumsal yazar tespiti (Arenliu Qosaj, Özgen Narcı, Bago d'Uva, WHO & World Bank, ...)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional

# --- Karakter sınıfları (Türkçe diakritikler dahil) ---
# Türkçe ile birlikte İspanyolca, Portekizce, Fransızca, Almanca, İskandinav,
# Orta/Doğu Avrupa ve Vietnamca harfleri kapsar (á é í ñ ã õ ç â ê ô ü ø å ł č ...).
def _latin_letters(want_upper: bool) -> str:
    chars = []
    for start, end in ((0x00C0, 0x0250), (0x1E00, 0x1F00)):
        for cp in range(start, end):
            ch = chr(cp)
            if ch in "\u00D7\u00F7":
                continue
            if want_upper and ch.isupper():
                chars.append(ch)
            elif not want_upper and ch.islower():
                chars.append(ch)
    return "".join(chars)

_UPPER = "A-Z" + _latin_letters(True)
_LOWER = "a-z" + _latin_letters(False)

# Tüm apostrof türleri
_APOS = r"['\u2019\u2018\u02BC\u02B9]"

# Lowercase soyad ön ekleri
_PREFIX_LOWER = (
    r"(?:van|von|vom|zu|zum|zur|der|den|het|ten|ter|te|"
    r"de|del|della|dello|dei|degli|delle|di|da|das|do|dos|du|des|"
    r"le|la|las|los|lo|el|al|bin|ibn|ben|af|av|of)"
)
# Art arda gelen ekler: "van der", "de la", "de los" ...
_PREFIXES = rf"(?:{_PREFIX_LOWER}\s+){{1,3}}"

# Tire türleri (çift soyad: Demir-Yılmaz, González‑Pérez)
_HYPH = r"\-\u2010\u2011"

# Tek bir yazar "çekirdek" parçası
# Önekler: Mc, Mac, D', O', L', N', M', al-, el-. İç büyük harf: DeSouza, LeBlanc.
_CORE_PREFIX = rf"(?:Mc|Mac|[DdOoLlNnMm]{_APOS}|al[{_HYPH}]|el[{_HYPH}])"
_AUTHOR_CORE = rf"{_CORE_PREFIX}?[{_UPPER}][{_LOWER}]+(?:[{_UPPER}][{_LOWER}]+)?"

# Bir yazar parçası: isteğe bağlı lowercase ön ek + çekirdek
_AUTHOR_PART = rf"(?:{_PREFIXES})?{_AUTHOR_CORE}"

# Tam yazar (çok parçalı)
_AUTHOR = rf"{_AUTHOR_PART}(?:[\s{_HYPH}]{_AUTHOR_PART}){{0,4}}"

# Anlatımsal atıflarda lowercase prefix İSTEMEYEN katı yazar
# Baştaki ek alınmaz ("la Zadeh" yanlış yakalaması), ama soyadın İÇİNDEKİ ekler
# alınır: "Gonçalves da Silva (2014)", "García de la Torre (2019)".
_AUTHOR_STRICT = rf"{_AUTHOR_CORE}(?:[\s{_HYPH}](?:{_PREFIXES})?{_AUTHOR_CORE}){{0,4}}"

# Kısaltma yazar (acronym): WHO, OECD, FDA, NATO, UNESCO
_ACRONYM = rf"[{_UPPER}]{{2,8}}"

# Çok kelimeli kurumsal yazar
_ORG_MULTIWORD = rf"[{_UPPER}][{_LOWER}]+(?:\s+(?:{_PREFIXES})?[{_UPPER}][{_LOWER}]+){{1,4}}"

# Genel kurumsal yazar
_ORG = rf"(?:{_ACRONYM}|{_ORG_MULTIWORD})"

# Bir "isim veya kurum"
_NAME_OR_ORG = rf"(?:{_AUTHOR}|{_ORG})"

# Whitespace karakter sınıfı
_WS = r"[\s\u00A0\u202F\u2009]"

# "et al." / "vd." / "ve ark." / "ve diğerleri" varyantları
_ETAL = rf"(?:et{_WS}*al\.?|vd\.?|ve{_WS}*ark\.?|ve{_WS}*diğerleri)"

# Bağlaçlar
_CONJ = r"(?:&|\band\b|\bve\b|\by\b|\be\b|\bet\b|\bund\b)"

# Türkçe iyelik / ilgi ekleri
_POSSESSIVE = rf"(?:{_APOS}[{_LOWER}]+)?"

# Yazar listesi (parantez içi ATIF için)
_AUTHORS_PAREN = (
    rf"(?:"
    rf"{_NAME_OR_ORG}"
    rf"(?:\s*,\s*{_NAME_OR_ORG}){{0,15}}"
    rf"(?:\s*,?\s*{_CONJ}\s*{_NAME_OR_ORG})?"
    rf"(?:\s*,?\s*{_ETAL})?"
    rf")"
)

# Yazar listesi (anlatımsal ATIF için)
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

# Yıl: 2020 / 2020a / t.y. / n.d. / baskıda / in press
_YEAR = r"(?:\d{4}[a-z]?|n\.\s?d\.|t\.\s?y\.|in\s+press|baskıda|basımda|yayımlanmak\s+üzere)"

# İkincil atıf belirteçleri: yalnızca belirteçten SONRAKİ kaynak kaynakçada yer alır
_SECONDARY = re.compile(
    r"\b(?:as\s+cited\s+in|cited\s+in|as\s+quoted\s+in|akt(?:aran)?\s*[.:]?|"
    r"citado\s+(?:en|em|por)|apud|cité\s+(?:par|dans)|zitiert\s+nach)\s+",
    re.IGNORECASE | re.UNICODE,
)

# Sayfa eki
_PAGE = r"(?:\s*,\s*(?:p\.|pp\.|s\.|ss\.|para\.|paras\.)\s*[\d\-\u2013,\s]+)?"

# --- Atıf desenleri ---
PAREN_CITATION = re.compile(
    rf"\((?P<authors>{_AUTHORS_PAREN})\s*,\s*(?P<year>{_YEAR}){_PAGE}\)",
    re.UNICODE,
)

NARRATIVE_CITATION = re.compile(
    rf"(?<![{_LOWER}{_UPPER}])"
    rf"(?P<authors>{_AUTHORS_NARRATIVE})\s*\((?P<year>{_YEAR}){_PAGE}\)",
    re.UNICODE,
)

_MULTI_SPLIT = re.compile(r"\s*;\s*")
_MULTI_INNER = re.compile(
    rf"(?P<authors>{_AUTHORS_PAREN})\s*,\s*(?P<year>{_YEAR})",
    re.UNICODE,
)

# --- Referans listesi desenleri ---
DOI_PATTERN = re.compile(r"\b10\.\d{4,9}/[^\s,;]+", re.IGNORECASE)
# "(2020)", "(2020a)", "(2020, March 5)", "(t.y.)", "(n.d.)", "(baskıda)", "(in press)"
YEAR_IN_PARENS = re.compile(
    rf"\(({_YEAR})(?:\s*,[^()]{{0,40}})?\)", re.UNICODE | re.IGNORECASE
)
YEAR_BARE = re.compile(r"\b(19|20)\d{2}[a-z]?\b")

# Yazar olamayacak Türkçe / İngilizce söylem belirteçleri
_NON_AUTHOR_WORDS = {
    "Birincisi", "İkincisi", "Üçüncüsü", "Dördüncüsü", "Beşincisi",
    "Altıncısı", "Yedincisi", "Sekizincisi",
    "Ayrıca", "Ancak", "Fakat", "Lakin", "Yani", "Çünkü", "Öyleyse",
    "Örneğin", "Mesela", "Şekil", "Tablo", "Bölüm", "Kısım", "Madde",
    "Figure", "Table", "Section", "Chapter", "Part", "Appendix",
    "Bu", "Şu", "Bunun", "Şunun", "Bunlar", "Şunlar",
    "Sonuç", "Sonuçta", "Özet", "Genel",
    "Nitekim", "Dolayısıyla", "Böylece", "Özellikle", "Benzer", "Oysa",
    "Sonra", "Önce", "Daha", "Diğer", "Yine", "Hatta", "Zira", "Buna",
    "Öte", "Aynı", "Bununla", "Halbuki", "Kısaca", "Özetle", "Bkz", "Örn",
    "However", "Moreover", "Furthermore", "Additionally", "Similarly",
    "Likewise", "Thus", "Therefore", "Hence", "Also", "Indeed", "Notably",
    "Recently", "Later", "Earlier", "Subsequently", "Conversely", "Meanwhile",
    "While", "Although", "Whereas", "Since", "Because", "Both", "See",
    "Following", "Unlike", "Like", "Then", "Yet", "Still", "Finally",
    "First", "Second", "Third", "In", "As", "And", "But", "Per", "Cf",
}

@dataclass
class Citation:
    """Metin içi tek bir atıf."""
    raw: str
    authors: str
    year: str
    citation_type: str
    position: int

    @property
    def first_author_surname(self) -> str:
        """Eşleştirme için ilk yazarın soyadı."""
        cleaned = re.sub(_ETAL, "", self.authors, flags=re.UNICODE).strip()
        cleaned = re.sub(
            rf"{_APOS}(?:ın|in|un|ün|nın|nin|nun|nün|a|e|ya|ye|da|de|ta|te|den|dan|ki|s)\b",
            "",
            cleaned,
            flags=re.UNICODE,
        )
        first = re.split(rf"\s+{_CONJ}\s+|\s*,\s*", cleaned, maxsplit=1)[0]
        return first.strip()

    @property
    def key(self) -> str:
        """Çapraz eşleştirme anahtarı: 'soyad|yıl'."""
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
        """
        APA-aware kaynakça yazar tespiti.

        Tanır:
        - "Soyad, A." → "Soyad" (klasik APA)
        - "İki Kelimeli Soyad, A." → "İki Kelimeli Soyad" (Arenliu Qosaj, Özgen Narcı)
        - "Bago d'Uva, T." → "Bago d'Uva" (apostroflu çok kelimeli)
        - "WHO" / "OECD" → kurumsal akronim
        - "World Bank" / "European Commission" → çok kelimeli kurumsal
        - "WHO, & World Bank" / "OECD, & European Commission" → ilk yazar akronim
        """
        if not self.authors_raw:
            return None
        text = self.authors_raw.strip()
        # İlk yazar bloğunu al: &, "and", ";" ile böl (virgül APA'da soyad/ad ayırıcısı)
        first_block = re.split(r"\s*&\s*|\s+and\s+|\s+ve\s+|;", text, maxsplit=1)[0].strip()
        # Sondaki virgülü temizle ("WHO, " → "WHO")
        first_block = first_block.rstrip(",. ").strip()
        # 1) APA kalıbı: "Soyad(lar), A." — virgülden sonra baş harf gelirse soyad sol taraf
        m = re.match(
            rf"^((?:{_PREFIXES})?{_AUTHOR_CORE}"
            rf"(?:[\s{_HYPH}](?:(?:{_PREFIXES})|(?:[ye]\s+))?{_AUTHOR_CORE}){{0,4}})"
            rf"\s*,\s*[{_UPPER}]\.",
            first_block,
            flags=re.UNICODE,
        )
        if m:
            return m.group(1).strip()
        # 2) Kurumsal yazar (akronim veya çok kelimeli)
        m_org = re.match(rf"^({_ORG})(?:\s*[,(.]|\s*$)", first_block, flags=re.UNICODE)
        if m_org:
            return m_org.group(1).strip()
        # 3) Fallback: virgülden önceki kısım
        return first_block.split(",")[0].strip(" .")

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
    text = text.replace("\u00AD", "")
    text = re.sub(r"[\u00A0\u202F\u2009\u200A]", " ", text)
    text = re.sub(rf"([{_LOWER}{_UPPER}])-\n([{_LOWER}{_UPPER}])", r"\1\2", text, flags=re.UNICODE)
    text = re.sub(rf"(?<=[{_LOWER},])\n(?=[{_LOWER}])", " ", text, flags=re.UNICODE)
    return text

# --- Çıkarım fonksiyonları ---

PAREN_BLOCK = re.compile(
    rf"\(([^()]*(?:\b\d{{4}}[a-z]?\b|n\.\s?d\.|t\.\s?y\.|in\s+press|baskıda|basımda)[^()]*)\)",
    re.UNICODE,
)

_NUMERIC_CITATION = re.compile(r"\[\d{1,3}(?:\s*[,\-\u2013]\s*\d{1,3})*\]")


def detect_numeric_style(body: str, author_date_count: int = 0) -> bool:
    """Belge numaralı atıf sistemi (Vancouver / IEEE) kullanıyor mu?"""
    numeric = len(_NUMERIC_CITATION.findall(body or ""))
    return numeric >= 5 and numeric > 2 * author_date_count

def extract_in_text_citations(body: str) -> List[Citation]:
    """Metin gövdesinden tüm metin içi atıfları çıkar."""
    body = _normalize_whitespace(body)

    citations: List[Citation] = []
    matched_spans: List[tuple] = []

    for block in PAREN_BLOCK.finditer(body):
        inner = block.group(1)
        block_start = block.start()
        matched_spans.append((block.start(), block.end()))

        # İkincil atıf: "(Smith, 1990, as cited in Jones, 2020)", "(Smith, 1990; akt. Jones, 2020)"
        # APA'ya göre kaynakçada yalnızca okunan kaynak (Jones) bulunur.
        sec = None
        for sec in _SECONDARY.finditer(inner):
            pass
        if sec is not None:
            inner = inner[sec.end():]

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
        # Cümle başındaki söylem belirteçlerini ayıkla ("Ancak Şahin (2017)",
        # "However, Smith (2009)"); geriye yazar kalmazsa atıf sayılmaz.
        while True:
            parts = re.split(r"[\s,]+", authors_str, maxsplit=1)
            if parts[0] not in _NON_AUTHOR_WORDS:
                break
            authors_str = parts[1].strip() if len(parts) > 1 else ""
            if not authors_str:
                break
        if not authors_str or not re.match(rf"[{_UPPER}]|{_CORE_PREFIX}", authors_str):
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
    - Olmazsa "satır başı + Soyad, X." kalıbına göre böler.
      Çok kelimeli soyadlar (Arenliu Qosaj, Özgen Narcı) ve kurumsal yazarlar (WHO, OECD) da tanınır.
    - Sonra yıl içermeyen parçaları bir önceki entry'ye birleştirir.
    """
    refs_text = refs_text.strip()
    if not refs_text:
        return []

    blocks = re.split(r"\n\s*\n", refs_text)
    raw_lines = [l.strip() for l in refs_text.split("\n") if len(l.strip()) > 20]
    line_year = re.compile(r"\(\d{4}[a-z]?\)|\((?:n\.d\.|t\.y\.)\)")
    if len(blocks) > 3:
        candidates = [b.replace("\n", " ").strip() for b in blocks if len(b.strip()) > 20]
    elif len(raw_lines) >= 2 and sum(bool(line_year.search(l[:300])) for l in raw_lines) >= 0.85 * len(raw_lines):
        # DOCX / TXT: her satır (paragraf) zaten tek bir kaynak. Yazar adı açık
        # yazılmış ("García Márquez, Gabriel (1967)") kayıtlar da böylece ayrılır.
        candidates = raw_lines
    else:
        # Çok kelimeli soyad + APA virgül-baş-harf VEYA kurumsal akronim ile başlayan satır
        word = (
            rf"{_CORE_PREFIX}?"
            rf"[{_UPPER}][{_LOWER}{_UPPER}{_HYPH}]*{_APOS}?[{_LOWER}{_UPPER}{_HYPH}]+"
        )
        author_start = (
            rf"(?:{_PREFIXES})?{word}"
            rf"(?:\s+(?:(?:{_PREFIXES})|(?:[ye]\s+))?{word}){{0,4}}"
            rf"\s*,\s*[{_UPPER}]\."
        )
        org_start = rf"{_ACRONYM}(?:\s*[,(&]|\s+[{_UPPER}])"
        pattern = rf"\n(?={author_start}|{org_start})"
        lines = re.split(pattern, refs_text, flags=re.UNICODE)
        candidates = [l.replace("\n", " ").strip() for l in lines if len(l.strip()) > 20]

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
            ref.year = re.sub(r"\s+", " ", ym.group(1))
            ref.authors_raw = entry[: ym.start()].strip().rstrip(".,")
            after = entry[ym.end():].strip().lstrip(".").strip()
            tm = re.match(r"([^.]+)\.", after)
            if tm:
                ref.title = tm.group(1).strip()
        else:
            ym2 = YEAR_BARE.search(entry)
            if ym2:
                ref.year = ym2.group(0)
                ref.authors_raw = entry[: ym2.start()].strip().rstrip(".,")

        references.append(ref)

    return references
