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
 
import time
from typing import Callable, List, Optional, Sequence
 
from rapidfuzz import fuzz
 
from .extractors import Reference
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
 
    base = float(fuzz.token_set_ratio(ref_text, cand_text))
 
    cand_year = candidate.get("year")
    if reference.year and cand_year and reference.year[:4] != cand_year[:4]:
        base *= 0.7
 
    return base
 
 
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
 
    # 1. DOI varsa doğrudan eşleştirme
    if reference.doi:
        match = provider.search_by_doi(reference.doi, email)
        if match:
            return {
                "provider": provider_name,
                "status": "verified",
                "score": 100.0,
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
 
        if best is None or result["score"] > best["score"]:
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
    delay: float = 0.2,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> List[Reference]:
    """
    Tüm referansları sırayla doğrula.
 
    `delay`: bir referansın tüm provider sorguları arasında değil,
    farklı referanslar arasında uygulanır (polite pool için).
    """
    total = len(references)
    for i, ref in enumerate(references):
        validate_reference(ref, providers=providers, email=email)
        if delay > 0:
            time.sleep(delay)
        if progress_callback:
            progress_callback(i + 1, total)
    return references
 
