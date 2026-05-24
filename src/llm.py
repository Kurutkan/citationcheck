"""
LLM (Anthropic Claude) entegrasyonu — opsiyonel modül.

Bu modül anthropic paketi yoksa veya API anahtarı verilmediyse otomatik
olarak devre dışı kalır. app.py her zaman bu modülü import etmeye çalışır;
ANTHROPIC_AVAILABLE flag ile özellikleri devre dışı bırakabilir.
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Callable, List, Optional

from .extractors import Reference

logger = logging.getLogger(__name__)

try:
    import anthropic  # type: ignore
    ANTHROPIC_AVAILABLE = True
except ImportError:
    anthropic = None  # type: ignore
    ANTHROPIC_AVAILABLE = False

try:
    from pydantic import BaseModel, Field, ValidationError  # type: ignore
    PYDANTIC_AVAILABLE = True
except ImportError:
    PYDANTIC_AVAILABLE = False

    class BaseModel:  # type: ignore
        pass

    def Field(*a, **kw):  # type: ignore
        return None

    class ValidationError(Exception):  # type: ignore
        pass


# Model isimleri
MODEL_PARSING = "claude-haiku-4-5"
MODEL_REASONING = "claude-sonnet-4-5"


class LLMUnavailableError(RuntimeError):
    """anthropic paketi yok veya API anahtarı eksik/geçersiz."""


class ParsedReference(BaseModel):
    """LLM tarafından ayrıştırılmış referans yapısı."""
    authors: Optional[str] = Field(default=None)
    year: Optional[str] = Field(default=None)
    title: Optional[str] = Field(default=None)
    container: Optional[str] = Field(default=None)
    volume: Optional[str] = Field(default=None)
    issue: Optional[str] = Field(default=None)
    pages: Optional[str] = Field(default=None)
    doi: Optional[str] = Field(default=None)
    url: Optional[str] = Field(default=None)
    publisher: Optional[str] = Field(default=None)
    reference_type: Optional[str] = Field(default=None)
    has_ocr_errors: bool = Field(default=False)
    parsing_confidence: float = Field(default=0.0)


class HallucinationAssessment(BaseModel):
    """LLM forensik halüsinasyon değerlendirmesi."""
    assessment: str = Field(description="likely_genuine|uncertain|suspicious|likely_fabricated")
    confidence: float = Field(default=0.5)
    reasoning: str = Field(default="")
    indicators_for_fabrication: List[str] = Field(default_factory=list)
    indicators_for_genuineness: List[str] = Field(default_factory=list)
    possibly_real_alternative: Optional[str] = Field(default=None)
    recommendation: str = Field(description="accept|manual_verification|likely_remove|definitely_remove")


class LLMClient:
    """Anthropic API ince sarmalayıcı."""

    def __init__(self, api_key: Optional[str] = None):
        if not ANTHROPIC_AVAILABLE:
            raise LLMUnavailableError(
                "anthropic paketi yüklü değil. Kurulum: pip install anthropic pydantic"
            )
        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise LLMUnavailableError(
                "ANTHROPIC_API_KEY bulunamadı. UI dan girin veya ortam değişkeni ayarlayın."
            )
        self.client = anthropic.Anthropic(api_key=key)

    def complete_json(
        self,
        *,
        model: str,
        system: str,
        user: str,
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> dict:
        """JSON-yalın yanıt isteyen bir tamamlama yap, dict olarak döndür."""
        response = self.client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        text = "".join(
            block.text for block in response.content
            if getattr(block, "type", "") == "text"
        ).strip()
        return _extract_json(text)


def _extract_json(text: str) -> dict:
    """Modelin yanıtından ilk geçerli JSON objesini ayıkla."""
    pattern = r"```(?:json)?\s*(\{.*?\})\s*```"
    m = re.search(pattern, text, re.DOTALL)
    candidate = m.group(1) if m else None

    if not candidate:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError(f"JSON bulunamadı: {text[:200]}")
        candidate = text[start : end + 1]

    try:
        return json.loads(candidate)
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON parse hatası: {e} / kaynak: {candidate[:200]}")

_PARSE_SYSTEM = (
    "Sen akademik referans ayrıştırma uzmanısın. "
    "Verilen ham referans metnini (APA, IEEE, Chicago veya bozuk format olabilir) "
    "yapısal alanlara çevir. Türkçe ve İngilizce referansları desteklersin.\n\n"
    "Çıktın SADECE geçerli JSON olmalı. Alan bulunamıyorsa null bırak. "
    "OCR/dijital bozulma izleri varsa has_ocr_errors=true işaretle. "
    "parsing_confidence ile genel güvenini bildir (0.0-1.0)."
)

_PARSE_USER_TPL = (
    "Aşağıdaki referansı ayrıştır ve JSON olarak döndür:\n\n"
    "{raw}\n\n"
    "Beklenen alanlar: authors, year, title, container, volume, issue, "
    "pages, doi, url, publisher, reference_type "
    "(journal|book|chapter|conference|thesis|report|webpage), "
    "has_ocr_errors (bool), parsing_confidence (0.0-1.0)."
)


def is_reference_underparsed(ref: Reference) -> bool:
    """Eksik alanlı bir referans LLM e gönderilmeye değer mi?"""
    missing = 0
    if not ref.authors_raw:
        missing += 1
    if not ref.year:
        missing += 1
    if not ref.title:
        missing += 1
    return missing >= 2 or len((ref.raw or "").strip()) < 30


def llm_parse_reference(raw: str, client: "LLMClient") -> Optional[dict]:
    """Tek bir referansı LLM ile ayrıştır; başarısızsa None döner."""
    try:
        data = client.complete_json(
            model=MODEL_PARSING,
            system=_PARSE_SYSTEM,
            user=_PARSE_USER_TPL.format(raw=raw),
            max_tokens=600,
            temperature=0.0,
        )
        if data.get("doi"):
            data["doi"] = str(data["doi"]).strip().rstrip(".,;")
        if data.get("year"):
            data["year"] = str(data["year"])[:4]
        data.setdefault("has_ocr_errors", False)
        data.setdefault("parsing_confidence", 0.5)
        return data
    except Exception as exc:
        logger.warning("LLM parse hatası: %s", exc)
        return None


def merge_llm_into_reference(ref: Reference, parsed: dict) -> None:
    """LLM çıktısını Reference nesnesine birleştir."""
    if not ref.authors_raw and parsed.get("authors"):
        ref.authors_raw = parsed["authors"]
    if not ref.year and parsed.get("year"):
        ref.year = parsed["year"]
    if not ref.title and parsed.get("title"):
        ref.title = parsed["title"]
    if not ref.doi and parsed.get("doi"):
        ref.doi = parsed["doi"]
    ref.llm_parsed = True
    ref.llm_parse_data = parsed


_HALLUC_SYSTEM = (
    "Sen akademik referans forensik uzmanısın. Görevin: bir akademik referansın "
    "gerçek bir yayına ait olup olmadığını (yani uydurulup uydurulmadığını) "
    "değerlendirmek.\n\n"
    "Sahtelik ipuçları: var olmayan dergi+yazar+yıl üçlüsü, yapay-mükemmel başlıklar, "
    "tutarsız cilt/sayfa, geçersiz DOI.\n"
    "Gerçeklik ipuçları: Türkçe/yerel dergi, kitap, tez, eski yayın (öncesi 1990), "
    "bölgesel konferans, spesifik gerçekçi başlık.\n\n"
    "ÖNEMLİ: Bulunamamak tek başına uydurma KANITI DEĞİLDİR. Türkçe/yerel akademik "
    "üretim için ihtiyatlı ol.\n\n"
    "Çıktın SADECE geçerli JSON olmalı."
)

_HALLUC_USER_TPL = (
    "Aşağıdaki referansı değerlendir.\n\n"
    "REFERANS:\n{raw}\n\n"
    "AYRIŞTIRILMIŞ ALANLAR:\n"
    "- Yazarlar: {authors}\n"
    "- Yıl: {year}\n"
    "- Başlık: {title}\n"
    "- DOI: {doi}\n\n"
    "DOĞRULAMA DENEMELERİ:\n{attempts}\n\n"
    "JSON şeması: assessment (likely_genuine|uncertain|suspicious|likely_fabricated), "
    "confidence (0.0-1.0), reasoning, indicators_for_fabrication (list), "
    "indicators_for_genuineness (list), possibly_real_alternative (str|null), "
    "recommendation (accept|manual_verification|likely_remove|definitely_remove)."
)


def should_assess_hallucination(ref: Reference) -> bool:
    """Bu referans halüsinasyon kontrolüne aday mı?"""
    if ref.validation_status in ("verified",):
        return False
    if ref.validation_status in ("not_found", "low_confidence", "unchecked"):
        return True
    return False


def _format_attempts(ref: Reference) -> str:
    if not ref.validation_attempts:
        return "(deneme yok)"
    lines = []
    for a in ref.validation_attempts:
        score = a.get("score", 0)
        lines.append(f"- {a.get('provider')}: {a.get('status')} (skor: {score:.1f})")
    return "\n".join(lines)


def assess_hallucination(ref: Reference, client: "LLMClient") -> Optional[dict]:
    """Tek bir referansı halüsinasyon açısından değerlendir."""
    try:
        data = client.complete_json(
            model=MODEL_REASONING,
            system=_HALLUC_SYSTEM,
            user=_HALLUC_USER_TPL.format(
                raw=ref.raw,
                authors=ref.authors_raw or "—",
                year=ref.year or "—",
                title=ref.title or "—",
                doi=ref.doi or "—",
                attempts=_format_attempts(ref),
            ),
            max_tokens=800,
            temperature=0.0,
        )
        data.setdefault("assessment", "uncertain")
        data.setdefault("confidence", 0.5)
        data.setdefault("reasoning", "")
        data.setdefault("indicators_for_fabrication", [])
        data.setdefault("indicators_for_genuineness", [])
        data.setdefault("recommendation", "manual_verification")
        return data
    except Exception as exc:
        logger.warning("LLM halüsinasyon hatası: %s", exc)
        return None


def assess_batch(
    references: List[Reference],
    client: "LLMClient",
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
) -> List[Reference]:
    """Aday referansları işle; sonuçları in-place günceller."""
    total = len(references)
    for i, ref in enumerate(references):
        if progress_callback:
            label = (ref.raw[:60] + "…") if len(ref.raw) > 60 else ref.raw
            progress_callback(i, total, label)
        result = assess_hallucination(ref, client)
        if result:
            ref.hallucination_assessment = result
    if progress_callback:
        progress_callback(total, total, "bitti")
    return references


_ASSESSMENT_LABELS = {
    "likely_genuine": "🟢 Muhtemelen gerçek",
    "uncertain": "⚪ Belirsiz",
    "suspicious": "🟡 Şüpheli",
    "likely_fabricated": "🔴 Muhtemelen uydurma",
}

_RECOMMENDATION_LABELS = {
    "accept": "Kabul edilebilir",
    "manual_verification": "Manuel doğrulama önerilir",
    "likely_remove": "Çıkarılması önerilir",
    "definitely_remove": "Mutlaka çıkarılmalı",
}


def assessment_label(value: str) -> str:
    return _ASSESSMENT_LABELS.get(value, value)


def recommendation_label(value: str) -> str:
    return _RECOMMENDATION_LABELS.get(value, value)
