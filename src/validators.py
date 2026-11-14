"""
Referans doğrulama orkestratörü.

Birden fazla akademik veritabanı (provider) ile sıralı doğrulama yapar.

Strateji:
  1. İlk provider'da DOI veya bibliyografik arama
  2. Sonuç "verified" güveninde ise dur
  3. Aksi takdirde sıradaki provider'ı dene
  4. Hiçbiri tam emin değilse, en yüksek skorlu sonucu kaydet

Bu yaklaşımın değeri:
  - CrossRef DOI'siz ya da gri literatür için zayıftır → OpenAlex devreye girer
  - Tek provider'a bağımlı kalmamak doğrulama güvenilirliğini artırır
  - Yeni provider eklemek (Semantic Scholar, Scopus) sadece yeni dosya gerektirir
"""
from __future__ import annotations

import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, List, Optional, Sequence

try:
    from rapidfuzz import fuzz
except ImportError:  # rapidfuzz yoksa standart kütüphane ile yaklaşık eşdeğer
    from difflib import SequenceMatcher

    class fuzz:  # type: ignore[no-redef]
        @staticmethod
        def _ratio(a: str, b: str) -> float:
            return 100.0 * SequenceMatcher(None, a, b).ratio() if a or b else 0.0

        @staticmethod
        def token_set_ratio(a: str, b: str) -> float:
            ta, tb = set(a.lower().split()), set(b.lower().split())
            if not ta or not tb:
                return 0.0
            inter = " ".join(sorted(ta & tb))
            ra = (inter + " " + " ".join(sorted(ta - tb))).strip()
            rb = (inter + " " + " ".join(sorted(tb - ta))).strip()
            return max(fuzz._ratio(inter, ra), fuzz._ratio(inter, rb), fuzz._ratio(ra, rb))

from .extractors import Reference
from .names import fold, surname_tokens
from .providers import PROVIDERS, DEFAULT_ORDER

# Eşikler — kalibrasyon İP10'da yapılacak
VERIFIED_THRESHOLD = 85.0
LOW_CONFIDENCE_THRESHOLD = 65.0


def _candidate_text(candidate: dict) -> str:
    """Standart şemadan eşleştirme metni oluştur."""
    title = candidate.get("title", "") or ""
    authors = " ".join(candidate.get("authors", [])[:5])
    container = candidate.get("container", "") or ""
    return f"{title} {authors} {container}".strip()


def score_match(reference: Reference, candidate: dict) -> float:
    """
    Aday kaydın referansla benzerlik skoru (0-100).

    - token_set_ratio: kelime sırasından bağımsız bulanık eşleşme
    - yıl uyuşmazlığı varsa %30 ceza (yanlış pozitifleri törpüler)
    """
    ref_text = " ".join(filter(None, [reference.title, reference.authors_raw, reference.raw]))
    cand_text = _candidate_text(candidate)

    # Aksan ve büyük/küçük harf farkı skoru düşürmesin (Gonçalves ~ Goncalves)
    base = float(fuzz.token_set_ratio(_norm(ref_text), _norm(cand_text)))

    cand_year = candidate.get("year")
    if reference.year and cand_year and reference.year[:4] != cand_year[:4]:
        base *= 0.7

    # Başlık denetimi: aday başlığının anlamlı sözcüklerinin çoğu referansta geçmeli.
    # Yalnızca yazar + dergi adı tutan, başlığı farklı bir kayıt "doğrulandı" sayılmaz.
    coverage = title_coverage(reference, candidate)
    if coverage is not None and coverage < 0.5:
        base *= 0.6

    # İlk yazar denetimi: adayın ilk yazarının soyadı referans metninde geçmeli.
    if first_author_present(reference, candidate) is False:
        base *= 0.75

    return base


_WORD_RE = re.compile(r"[a-z0-9]+")
_STOP = frozenset(
    "the a an of and in on for to with by from at as is are its "
    "ve ile bir bu icin de da ile olarak uzerine "
    "el la los las de del y en un una e o do da dos das um uma em "
    "le les des du et un une der die das und".split()
)


def _norm(text: str) -> str:
    return " ".join(_WORD_RE.findall(fold(text or "")))


def title_coverage(reference: Reference, candidate: dict) -> Optional[float]:
    """Aday başlığındaki anlamlı sözcüklerin referans ham metninde geçme oranı (0-1).

    Aday başlığı çok kısaysa (2 anlamlı sözcükten az) None döner: karar verilemez.
    """
    cand_words = [w for w in _WORD_RE.findall(fold(candidate.get("title") or "")) if w not in _STOP and len(w) > 2]
    if len(cand_words) < 2:
        return None
    ref_words = set(_WORD_RE.findall(fold(reference.raw or "")))
    return sum(1 for w in cand_words if w in ref_words) / len(cand_words)


def first_author_present(reference: Reference, candidate: dict) -> Optional[bool]:
    """Adayın ilk yazarının soyadı referans metninde geçiyor mu? Yazar bilgisi yoksa None."""
    authors = candidate.get("authors") or []
    if not authors:
        return None
    first = authors[0]
    # CrossRef: "Soyad, Ad" | OpenAlex: "Ad Soyad"
    surname = first.split(",")[0] if "," in first else first.split()[-1] if first.split() else ""
    toks = surname_tokens(surname)
    if not toks:
        return None
    ref_words = set(_WORD_RE.findall(fold(reference.raw or "")))
    return any(t in ref_words for t in toks)


def doi_record_matches(reference: Reference, candidate: dict) -> bool:
    """DOI'nin gösterdiği kayıt gerçekten bu referans mı?

    Gerçek bir DOI'yi başka bir (uydurma) kaynağa yapıştırmak, yapay zekâ ile
    üretilmiş kaynakçalarda sık görülür. Bu yüzden DOI'nin çözülmesi tek başına
    yeterli sayılmaz; başlık ya da ilk yazar da tutmalıdır.
    """
    coverage = title_coverage(reference, candidate)
    author_ok = first_author_present(reference, candidate)
    if coverage is None:
        return author_ok is not False
    if coverage >= 0.6:
        return True
    if coverage >= 0.4 and author_ok:
        return True
    return False


def _classify(score: float) -> str:
    if score >= VERIFIED_THRESHOLD:
        return "verified"
    if score >= LOW_CONFIDENCE_THRESHOLD:
        return "low_confidence"
    return "not_found"


def validate_with_provider(
    reference: Reference,
    provider_name: str,
    email: Optional[str] = None,
) -> dict:
    """
    Tek bir provider ile doğrulama dener.

    Döndürür:
        {
            "provider": str,
            "status":   str,    # verified | low_confidence | not_found
            "score":    float,
            "match":    dict | None,
        }
    """
    if provider_name not in PROVIDERS:
        return {"provider": provider_name, "status": "not_found", "score": 0.0, "match": None}

    provider = PROVIDERS[provider_name]

    # 1. DOI varsa: kayıt çözülmeli VE referansla uyuşmalı
    if reference.doi:
        match = provider.search_by_doi(reference.doi, email)
        if match:
            if doi_record_matches(reference, match):
                return {
                    "provider": provider_name,
                    "status": "verified",
                    "score": 100.0,
                    "match": match,
                }
            return {
                "provider": provider_name,
                "status": "doi_mismatch",
                "score": score_match(reference, match),
                "match": match,
            }

    # 2. Bibliyografik arama
    candidates = provider.search_by_bibliographic(reference.raw, email, rows=3)
    if not candidates:
        return {"provider": provider_name, "status": "not_found", "score": 0.0, "match": None}

    best, best_score = None, 0.0
    for c in candidates:
        s = score_match(reference, c)
        if s > best_score:
            best, best_score = c, s

    return {
        "provider": provider_name,
        "status": _classify(best_score),
        "score": best_score,
        "match": best,
    }


def validate_reference(
    reference: Reference,
    providers: Optional[Sequence[str]] = None,
    email: Optional[str] = None,
) -> Reference:
    """
    Referansı sıralı providerlarda doğrula.

    İlk "verified" sonuç bulununca durur. Hiçbiri verified değilse, tüm
    provider'ları dener ve en yüksek skorlu olanı seçer.

    Reference nesnesini in-place günceller.
    """
    order = list(providers) if providers else list(DEFAULT_ORDER)

    attempts: List[dict] = []
    best: Optional[dict] = None

    for provider_name in order:
        result = validate_with_provider(reference, provider_name, email)
        attempts.append({
            "provider": result["provider"],
            "status": result["status"],
            "score": result["score"],
        })

        # Erken çıkış: yüksek güvenli sonuç bulundu
        if result["status"] == "verified":
            best = result
            break

        # DOI başka bir yayına aitse bu bulgu korunur; ancak başka bir kaynakta
        # referansın kendisi doğrulanırsa (yanlış yazılmış DOI) "verified" kazanır.
        if best is not None and best["status"] == "doi_mismatch":
            continue
        if best is None or result["status"] == "doi_mismatch" or result["score"] > best["score"]:
            best = result

    if best is None:
        reference.validation_status = "not_found"
        reference.validation_score = 0.0
        reference.validation_match = None
        reference.validation_provider = None
    else:
        reference.validation_status = best["status"]
        reference.validation_score = best["score"]
        reference.validation_match = best["match"]
        reference.validation_provider = best["provider"] if best["match"] else None

    reference.validation_attempts = attempts
    return reference


def validate_references_batch(
    references: List[Reference],
    providers: Optional[Sequence[str]] = None,
    email: Optional[str] = None,
    delay: float = 0.0,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    max_workers: int = 4,
) -> List[Reference]:
    """
    Tüm referansları doğrula.

    Sorgular `max_workers` iş parçacığıyla paralel yürür (ağ beklemesi baskın
    olduğu için 100+ kaynaklı listelerde süre belirgin kısalır). `delay` > 0
    verilirse gönderimler arasında beklenir (polite pool). `progress_callback`
    her zaman çağıran iş parçacığından tetiklenir (Streamlit için gerekli).
    """
    total = len(references)
    if total == 0:
        return references

    if max_workers <= 1:
        for i, ref in enumerate(references):
            validate_reference(ref, providers=providers, email=email)
            if delay > 0:
                time.sleep(delay)
            if progress_callback:
                progress_callback(i + 1, total)
        return references

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = []
        for ref in references:
            futures.append(pool.submit(validate_reference, ref, providers, email))
            if delay > 0:
                time.sleep(delay / max_workers)
        done = 0
        for fut in as_completed(futures):
            try:
                fut.result()
            except Exception:
                pass  # tek bir kaynaktaki hata tüm doğrulamayı durdurmasın
            done += 1
            if progress_callback:
                progress_callback(done, total)
    return references
