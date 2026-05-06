"""
APA Atıf Doğrulayıcı — Streamlit MVP arayüzü.

Çalıştırma:
    pip install -r requirements.txt
    streamlit run app.py
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from src.parsers import parse_document
from src.extractors import extract_in_text_citations, extract_references
from src.validators import validate_references_batch
from src.cross_check import cross_check
from src.format_checker import (
    check_apa_format,
    summarize_by_category,
    summarize_by_severity,
)
from src.track_changes_patcher import generate_track_changes_patch
from src.llm import (
    ANTHROPIC_AVAILABLE,
    LLMClient,
    LLMUnavailableError,
    is_reference_underparsed,
    llm_parse_reference,
    merge_llm_into_reference,
    should_assess_hallucination,
    assess_batch,
    assessment_label,
    recommendation_label,
    MODEL_PARSING,
    MODEL_REASONING,
)

# --- Sayfa konfigürasyonu ---
st.set_page_config(
    page_title="APA Atıf Doğrulayıcı",
    page_icon="📚",
    layout="wide",
)

st.title("📚 APA 7 Atıf Doğrulayıcı — MVP")
st.caption(
    "Metin içi atıf çıkarımı · Referans listesi ayrıştırma · "
    "Çapraz tutarlılık kontrolü · CrossRef veritabanı doğrulaması"
)

# --- Yan panel ---
with st.sidebar:
    st.header("⚙️ Ayarlar")

    enable_validation = st.checkbox(
        "Dış veritabanı doğrulamasını aç",
        value=True,
        help="Her referansı seçili akademik veritabanlarında arar.",
    )

    selected_providers = st.multiselect(
        "Doğrulama kaynakları (sıra önemlidir)",
        options=["crossref", "openalex"],
        default=["crossref", "openalex"],
        help=(
            "CrossRef: ~140M kayıt, DOI'li yayınlar için altın standart. "
            "OpenAlex: ~250M kayıt, açık erişim ve gri literatür kapsamı geniş. "
            "Sıralı çalışır: birinci provider 'verified' bulursa ikincisi atlanır."
        ),
    )

    polite_email_input = st.text_input(
        "Polite pool e-posta",
        value="",
        help=(
            "CrossRef ve OpenAlex'e e-posta verirseniz hızlı yanıt havuzuna girersiniz. "
            "Akademik kullanım için önerilir, kişisel veri saklanmaz. "
            "Boş bırakılırsa varsa sistem e-postası kullanılır."
        ),
    )

    # Fallback: kullanıcı girdisi > st.secrets["CROSSREF_EMAIL"] > yok
    _email_from_secrets = None
    try:
        _email_from_secrets = st.secrets.get("CROSSREF_EMAIL", None)
    except (FileNotFoundError, Exception):
        pass
    polite_email = polite_email_input or _email_from_secrets or ""

    max_refs_to_check = st.slider(
        "Maksimum referans sayısı",
        min_value=5,
        max_value=200,
        value=30,
        help="MVP'de hız için sınır. Tüm referanslar için yükseltin.",
    )

    request_delay = st.slider(
        "Referanslar arası gecikme (sn)",
        min_value=0.0,
        max_value=1.0,
        value=0.2,
        step=0.1,
    )

    st.divider()
    st.subheader("🧠 LLM Destekli Analiz")

    if not ANTHROPIC_AVAILABLE:
        st.caption(
            "⚠️ `anthropic` paketi yüklü değil. "
            "Etkinleştirmek için: `pip install anthropic pydantic`"
        )
        enable_llm = False
        api_key = None
        enable_llm_parsing = False
        enable_hallucination = False
    else:
        enable_llm = st.checkbox(
            "LLM destekli analizi aç",
            value=False,
            help=(
                "Claude API kullanarak (1) bozuk referansları yapısal alanlara "
                "ayrıştırır ve (2) doğrulanamayan referansların halüsinasyon "
                "(uydurma) olup olmadığını değerlendirir."
            ),
        )

        api_key = None
        enable_llm_parsing = False
        enable_hallucination = False

        if enable_llm:
            # API anahtarı kaynağı önceliği:
            #   1. Kullanıcı UI'dan girer (en yüksek öncelik — BYO key)
            #   2. st.secrets["ANTHROPIC_API_KEY"] (deployment owner ön-konfigürasyonu)
            #   3. ANTHROPIC_API_KEY ortam değişkeni (lokal geliştirme)
            secrets_key = None
            try:
                secrets_key = st.secrets.get("ANTHROPIC_API_KEY", None)
            except (FileNotFoundError, Exception):
                # secrets.toml yoksa veya başka bir hata varsa sessizce geç
                pass

            if secrets_key:
                st.caption(
                    "🔑 Sistem yöneticisi tarafından paylaşılan API anahtarı bulundu. "
                    "Kendi anahtarınızı kullanmak için aşağıya yapıştırın."
                )

            user_input_key = st.text_input(
                "Anthropic API anahtarı",
                type="password",
                value="",
                help=(
                    "API anahtarınız bu oturumda kullanılır, kalıcı saklanmaz. "
                    "Boş bırakırsanız varsa sistem anahtarı kullanılır. "
                    "Alternatif: ANTHROPIC_API_KEY ortam değişkeni."
                ),
            )

            # Etkin anahtar: kullanıcı girdisi > secrets > env
            api_key = user_input_key or secrets_key or None

            enable_llm_parsing = st.checkbox(
                "Bozuk referansları LLM ile ayrıştır",
                value=True,
                help=f"Eksik alanlı referanslar için. Model: {MODEL_PARSING}",
            )

            enable_hallucination = st.checkbox(
                "Halüsinasyon (uydurma) tespiti",
                value=True,
                help=(
                    f"CrossRef/OpenAlex'te bulunamayan referansları akademik "
                    f"forensik mantıkla değerlendirir. Model: {MODEL_REASONING}"
                ),
            )

    st.divider()
    st.markdown("**Desteklenen formatlar:** PDF, DOCX, TXT")
    st.markdown(
        "**Veritabanları:** "
        "[CrossRef](https://api.crossref.org) · "
        "[OpenAlex](https://api.openalex.org)"
    )

# --- Dosya yükleme ---
uploaded = st.file_uploader(
    "Bir akademik makale yükleyin",
    type=["pdf", "docx", "txt"],
    help="APA 7 formatında yazılmış makaleler en iyi sonucu verir.",
)

if uploaded is None:
    st.info("👆 Başlamak için bir makale yükleyin.")
    with st.expander("ℹ️ Bu MVP ne yapar, ne yapmaz?"):
        st.markdown(
            """
**Yapar (mevcut sürümde):**
- PDF / DOCX / TXT belgeleri ayrıştırır
- Metin içi APA atıflarını yakalar (parantez içi + anlatımsal)
- Çoklu atıfları ayırır: `(Smith, 2020; Jones, 2021)`
- Türkçe ve İngilizce çalışır (`vd.`, `ve ark.`, `ve diğerleri`, `et al.`)
- Referans listesini parçalara ayırır (yazar / yıl / başlık / DOI)
- Metin ↔ kaynakça tutarlılığını denetler
- **CrossRef + OpenAlex** çoklu kaynak ile her referansı doğrular
- **🧠 LLM destekli (opsiyonel):**
  - Bozuk / OCR'lı referansları yapısal alanlara ayrıştırır (Claude Haiku)
  - Doğrulanamayan referansların **halüsinasyon (uydurma)** olup olmadığını
    akademik forensik mantıkla değerlendirir (Claude Sonnet)
  - Yapay zekâyla yazılmış makalelerdeki sahte referansları tespit etmek için kritik

**Henüz yapmaz (sonraki iş paketlerinde):**
- APA 7 biçim hatalarının ayrıntılı raporlanması (italik, noktalama, sıralama)
- LLM destekli "regex'in kaçırdığı atıfları yakala" özelliği
- Semantic Scholar / Google Scholar yedek doğrulama
- PDF üstüne renkli işaretleme ve Word Track Changes ile düzeltme önerisi
- BibTeX / RIS dışa aktarımı
"""
        )
    st.stop()

# --- İşlem akışı ---
with tempfile.NamedTemporaryFile(delete=False, suffix=Path(uploaded.name).suffix) as tmp:
    tmp.write(uploaded.read())
    tmp_path = tmp.name

try:
    with st.spinner("📄 Belge okunuyor ve bölümlere ayrılıyor..."):
        body, refs_section = parse_document(tmp_path)
except Exception as e:
    st.error(f"Belge okunamadı: {e}")
    st.stop()

if not refs_section:
    st.warning(
        "⚠️ Referans bölümü tespit edilemedi. "
        "Başlık (References / Kaynakça / Bibliography) makalede bulunamadı veya farklı yazılmış olabilir."
    )

with st.spinner("🔍 Metin içi atıflar çıkarılıyor..."):
    citations = extract_in_text_citations(body)

with st.spinner("📑 Referans listesi ayrıştırılıyor..."):
    references = extract_references(refs_section)

# --- LLM destekli referans ayrıştırma (eksik alanları doldur) ---
llm_client = None
if enable_llm and api_key:
    try:
        llm_client = LLMClient(api_key=api_key)
    except LLMUnavailableError as e:
        st.error(f"LLM istemcisi başlatılamadı: {e}")
        llm_client = None

if llm_client and enable_llm_parsing and references:
    underparsed = [r for r in references if is_reference_underparsed(r)]
    if underparsed:
        st.info(
            f"🧠 {len(underparsed)} referansta eksik alan tespit edildi. "
            f"LLM ({MODEL_PARSING}) ile yeniden ayrıştırılıyor..."
        )
        bar = st.progress(0.0, text="Başlıyor...")
        for i, ref in enumerate(underparsed):
            parsed = llm_parse_reference(ref.raw, llm_client)
            if parsed:
                merge_llm_into_reference(ref, parsed)
            bar.progress((i + 1) / len(underparsed), text=f"{i+1}/{len(underparsed)}")
        bar.empty()
        recovered = sum(1 for r in underparsed if r.llm_parsed)
        st.success(f"✓ {recovered}/{len(underparsed)} referansta alanlar tamamlandı.")

cross_result = cross_check(citations, references)

# --- DOCX biçim incelemesi (sadece .docx için) ---
docx_inspection = None
if Path(uploaded.name).suffix.lower() == ".docx":
    from src.docx_inspector import inspect_docx
    with st.spinner("📐 DOCX biçim metaverileri okunuyor (italik, girinti, satır aralığı)..."):
        docx_inspection = inspect_docx(tmp_path, references)

# --- APA 7 biçim kontrolü (DOCX inspection varsa onu da kullanır) ---
format_issues = check_apa_format(citations, references, docx_inspection)

# --- Özet metrikleri ---
st.divider()
st.subheader("📊 Özet")
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Metin içi atıf", len(citations))
c2.metric("Referans sayısı", len(references))
c3.metric(
    "Eksik referans",
    len(cross_result.missing_in_references),
    help="Metinde atıf var, kaynakçada karşılığı yok",
)
c4.metric(
    "Yetim referans",
    len(cross_result.orphan_references),
    help="Kaynakçada var, metinde atıf yok",
)

# Biçim sorunları özeti
fmt_severity = summarize_by_severity(format_issues)
fmt_total = len(format_issues)
fmt_errors = fmt_severity.get("error", 0)
c5.metric(
    "Biçim sorunu",
    f"{fmt_total}",
    delta=f"{fmt_errors} hata" if fmt_errors else None,
    delta_color="inverse" if fmt_errors else "off",
    help="APA 7 biçim ihlalleri (detay için 📝 sekmesi)",
)

# --- Çoklu provider doğrulaması (opsiyonel) ---
if enable_validation and selected_providers and references:
    st.divider()
    st.subheader("🌐 Veritabanı Doğrulaması")

    refs_to_check = references[:max_refs_to_check]
    if len(references) > max_refs_to_check:
        st.caption(
            f"Hız için ilk {max_refs_to_check} referans denetleniyor. "
            f"Tümü için sol panelden limiti yükseltin."
        )

    st.caption(
        f"Sıralı denenen kaynaklar: **{' → '.join(selected_providers)}**. "
        "Birinci provider yüksek güvenle eşleşme bulursa ikincisi atlanır."
    )

    progress_bar = st.progress(0.0, text="Başlatılıyor...")

    def _update_progress(done: int, total: int) -> None:
        progress_bar.progress(done / total, text=f"{done} / {total} referans doğrulandı")

    validate_references_batch(
        refs_to_check,
        providers=selected_providers,
        email=polite_email or None,
        delay=request_delay,
        progress_callback=_update_progress,
    )
    progress_bar.empty()

    verified = sum(1 for r in refs_to_check if r.validation_status == "verified")
    low = sum(1 for r in refs_to_check if r.validation_status == "low_confidence")
    notfound = sum(1 for r in refs_to_check if r.validation_status == "not_found")

    v1, v2, v3, v4 = st.columns(4)
    v1.metric("✅ Doğrulandı", verified)
    v2.metric("⚠️ Düşük güven", low)
    v3.metric("❌ Bulunamadı", notfound)

    # Provider katkısı: hangi kaynak kaç kez başarılı oldu
    provider_hits = {}
    for r in refs_to_check:
        if r.validation_status == "verified" and r.validation_provider:
            provider_hits[r.validation_provider] = provider_hits.get(r.validation_provider, 0) + 1
    if provider_hits:
        v4.metric(
            "Kaynak katkısı",
            " · ".join(f"{p}: {n}" for p, n in provider_hits.items()),
        )

# --- LLM destekli halüsinasyon tespiti ---
if llm_client and enable_hallucination and references:
    candidates = [r for r in references if should_assess_hallucination(r)]
    if candidates:
        st.divider()
        st.subheader("🚨 Halüsinasyon Tespiti")
        st.caption(
            f"Doğrulanamayan / düşük güvenli **{len(candidates)} referans** "
            f"akademik forensik mantıkla değerlendiriliyor (model: {MODEL_REASONING})..."
        )
        h_bar = st.progress(0.0, text="Başlıyor...")

        def _h_progress(done, total, label):
            h_bar.progress(done / total, text=f"{done}/{total} — {label}")

        assess_batch(candidates, llm_client, progress_callback=_h_progress)
        h_bar.empty()

        # Özet metrikler
        counts = {"likely_genuine": 0, "uncertain": 0, "suspicious": 0, "likely_fabricated": 0}
        for r in candidates:
            if r.hallucination_assessment:
                counts[r.hallucination_assessment["assessment"]] = (
                    counts.get(r.hallucination_assessment["assessment"], 0) + 1
                )

        h1, h2, h3, h4 = st.columns(4)
        h1.metric("🟢 Muhtemelen gerçek", counts.get("likely_genuine", 0))
        h2.metric("⚪ Belirsiz", counts.get("uncertain", 0))
        h3.metric("🟡 Şüpheli", counts.get("suspicious", 0))
        h4.metric("🔴 Muhtemelen uydurma", counts.get("likely_fabricated", 0))

# --- Sekmeler ---
st.divider()
tab_cit, tab_ref, tab_cross, tab_fmt, tab_hall, tab_dl = st.tabs(
    ["🔍 Metin İçi Atıflar", "📑 Referanslar", "🔗 Çapraz Kontrol",
     "📝 APA 7 Biçim", "🚨 Halüsinasyon", "📥 İndir"]
)

with tab_cit:
    if citations:
        df_cit = pd.DataFrame(
            [
                {
                    "Atıf": c.raw,
                    "Yazar(lar)": c.authors,
                    "Yıl": c.year,
                    "Tip": c.citation_type,
                    "Konum": c.position,
                    "Anahtar": c.key,
                }
                for c in citations
            ]
        )
        st.dataframe(df_cit, use_container_width=True, hide_index=True)
    else:
        st.info("Metin içi atıf bulunamadı.")

with tab_ref:
    if references:
        rows = []
        for r in references:
            rows.append(
                {
                    "Referans": r.raw[:140] + ("…" if len(r.raw) > 140 else ""),
                    "Yazar(lar)": r.authors_raw,
                    "Yıl": r.year,
                    "Başlık (algılanan)": r.title,
                    "DOI": r.doi,
                    "Durum": r.validation_status,
                    "Kaynak": r.validation_provider or "-",
                    "Skor": round(r.validation_score, 1) if r.validation_score else None,
                }
            )
        df_ref = pd.DataFrame(rows)

        def _color_status(val: str) -> str:
            colors = {
                "verified": "background-color: #d4edda",
                "low_confidence": "background-color: #fff3cd",
                "not_found": "background-color: #f8d7da",
            }
            return colors.get(val, "")

        st.dataframe(
            df_ref.style.map(_color_status, subset=["Durum"]),
            use_container_width=True,
            hide_index=True,
        )

        # Provider denemeleri için detay
        with st.expander("🔬 Provider deneme detayları (her referansın hangi kaynaklarda nasıl skorladığı)"):
            attempt_rows = []
            for i, r in enumerate(references):
                if not r.validation_attempts:
                    continue
                for a in r.validation_attempts:
                    attempt_rows.append({
                        "#": i + 1,
                        "Referans": r.raw[:80] + "…" if len(r.raw) > 80 else r.raw,
                        "Provider": a.get("provider"),
                        "Durum": a.get("status"),
                        "Skor": round(a.get("score", 0), 1),
                    })
            if attempt_rows:
                st.dataframe(pd.DataFrame(attempt_rows), use_container_width=True, hide_index=True)
            else:
                st.info("Henüz provider denemesi yapılmadı (doğrulama kapalı olabilir).")
    else:
        st.info("Referans listesi ayrıştırılamadı.")

with tab_cross:
    sub1, sub2 = st.columns(2)

    with sub1:
        st.markdown("#### ❌ Metinde var, kaynakçada yok")
        if cross_result.missing_in_references:
            for c in cross_result.missing_in_references:
                st.error(
                    f"`{c.raw}` — yazar: **{c.first_author_surname}**, yıl: **{c.year}**"
                )
        else:
            st.success("Tüm metin içi atıfların referansı mevcut. ✓")

    with sub2:
        st.markdown("#### ⚠️ Kaynakçada var, metinde atıf yok")
        if cross_result.orphan_references:
            for r in cross_result.orphan_references:
                preview = r.raw[:120] + ("…" if len(r.raw) > 120 else "")
                st.warning(preview)
        else:
            st.success("Tüm referanslar metinde kullanılmış. ✓")

with tab_fmt:
    if not format_issues:
        st.success("✓ APA 7 biçim sorunu tespit edilmedi.")
    else:
        # Üst özet
        sev_counts = summarize_by_severity(format_issues)
        cat_counts = summarize_by_category(format_issues)

        f1, f2, f3, f4 = st.columns(4)
        f1.metric("Toplam", len(format_issues))
        f2.metric("🔴 Hata", sev_counts.get("error", 0))
        f3.metric("🟡 Uyarı", sev_counts.get("warning", 0))
        f4.metric("🔵 Bilgi", sev_counts.get("info", 0))

        st.caption(
            "**Hata** (error): Q1 dergi gönderiminde reddedilebilecek kritik ihlaller. "
            "**Uyarı** (warning): tutarlılık veya format eksiklikleri. "
            "**Bilgi** (info): tarz tercihi önerileri (örn. en-dash)."
        )

        # Kategoriye göre grupla
        from collections import defaultdict
        grouped = defaultdict(list)
        for issue in format_issues:
            grouped[issue.category].append(issue)

        # Her kategori için expander
        # Severity önceliğine göre sırala
        sev_order = {"error": 0, "warning": 1, "info": 2}
        sorted_categories = sorted(
            grouped.keys(),
            key=lambda cat: (
                min(sev_order.get(i.severity, 99) for i in grouped[cat]),
                -len(grouped[cat]),
            ),
        )

        for category in sorted_categories:
            issues_in_cat = grouped[category]
            # Kategorideki en yüksek severity
            top_sev = min(issues_in_cat, key=lambda i: sev_order.get(i.severity, 99)).severity
            sev_icon = {"error": "🔴", "warning": "🟡", "info": "🔵"}[top_sev]

            with st.expander(
                f"{sev_icon} **{category}** — {len(issues_in_cat)} sorun",
                expanded=(top_sev == "error"),
            ):
                for issue in issues_in_cat:
                    issue_icon = {"error": "🔴", "warning": "🟡", "info": "🔵"}[issue.severity]

                    if issue.severity == "error":
                        container = st.error
                    elif issue.severity == "warning":
                        container = st.warning
                    else:
                        container = st.info

                    container(
                        f"**{issue_icon} {issue.location}** — {issue.message}\n\n"
                        f"📝 `{issue.raw_excerpt}`"
                        + (f"\n\n✅ **Öneri:** {issue.suggestion}" if issue.suggestion else "")
                    )

with tab_hall:
    assessed = [r for r in references if r.hallucination_assessment]
    if not assessed:
        if not enable_llm or not llm_client:
            st.info(
                "ℹ️ Halüsinasyon tespiti kapalı. Sol panelden "
                "**LLM destekli analizi** ve **Halüsinasyon tespitini** etkinleştirin."
            )
        elif not enable_hallucination:
            st.info("ℹ️ Halüsinasyon tespiti onay kutusu kapalı.")
        else:
            st.success(
                "✓ Doğrulanamayan referans kalmadı — halüsinasyon kontrolü gerekmedi."
            )
    else:
        st.caption(
            f"**{len(assessed)} referans** akademik forensik mantıkla değerlendirildi. "
            "Önemli: Veritabanında bulunamamak tek başına uydurma kanıtı DEĞİLDİR. "
            "Model bölgesel/Türkçe/kitap referansları için duyarlı kalibrelendi."
        )

        # Risk derecesine göre sırala: likely_fabricated > suspicious > uncertain > likely_genuine
        order = {"likely_fabricated": 0, "suspicious": 1, "uncertain": 2, "likely_genuine": 3}
        sorted_assessed = sorted(
            assessed,
            key=lambda r: order.get(r.hallucination_assessment["assessment"], 99),
        )

        for r in sorted_assessed:
            ha = r.hallucination_assessment
            label = assessment_label(ha["assessment"])

            # Renk seçimi: en riskli olanlar error/warning kutusunda
            if ha["assessment"] == "likely_fabricated":
                container_fn = st.error
            elif ha["assessment"] == "suspicious":
                container_fn = st.warning
            elif ha["assessment"] == "uncertain":
                container_fn = st.info
            else:
                container_fn = st.success

            with st.container(border=True):
                col_a, col_b = st.columns([3, 1])
                col_a.markdown(f"**{label}**")
                col_b.markdown(
                    f"_{recommendation_label(ha['recommendation'])}_  "
                    f"(güven: {ha['confidence']:.0%})"
                )
                container_fn(r.raw[:200] + ("…" if len(r.raw) > 200 else ""))

                st.markdown(f"**Gerekçe:** {ha['reasoning']}")

                cols = st.columns(2)
                if ha["indicators_for_fabrication"]:
                    cols[0].markdown("**Sahtelik işaretleri:**")
                    for ind in ha["indicators_for_fabrication"]:
                        cols[0].markdown(f"- {ind}")
                if ha["indicators_for_genuineness"]:
                    cols[1].markdown("**Gerçeklik işaretleri:**")
                    for ind in ha["indicators_for_genuineness"]:
                        cols[1].markdown(f"- {ind}")

                if ha.get("possibly_real_alternative"):
                    st.markdown(
                        f"**Olası gerçek karşılığı:** {ha['possibly_real_alternative']}"
                    )

with tab_dl:
    st.markdown("Sonuçları CSV olarak indir:")
    col_a, col_b = st.columns(2)

    if citations:
        df_cit_export = pd.DataFrame(
            [
                {
                    "raw": c.raw,
                    "authors": c.authors,
                    "year": c.year,
                    "type": c.citation_type,
                    "position": c.position,
                    "key": c.key,
                }
                for c in citations
            ]
        )
        col_a.download_button(
            "📥 Atıflar (CSV)",
            data=df_cit_export.to_csv(index=False).encode("utf-8-sig"),
            file_name="atiflar.csv",
            mime="text/csv",
        )

    if references:
        df_ref_export = pd.DataFrame(
            [
                {
                    "raw": r.raw,
                    "authors": r.authors_raw,
                    "year": r.year,
                    "title": r.title,
                    "doi": r.doi,
                    "validation_status": r.validation_status,
                    "validation_score": r.validation_score,
                    "validation_provider": r.validation_provider,
                    "matched_title": (r.validation_match or {}).get("title"),
                    "matched_doi": (r.validation_match or {}).get("doi"),
                    "matched_year": (r.validation_match or {}).get("year"),
                    "llm_parsed": r.llm_parsed,
                    "llm_parse_confidence": (r.llm_parse_data or {}).get("parsing_confidence"),
                    "llm_has_ocr_errors": (r.llm_parse_data or {}).get("has_ocr_errors"),
                    "halluc_assessment": (r.hallucination_assessment or {}).get("assessment"),
                    "halluc_confidence": (r.hallucination_assessment or {}).get("confidence"),
                    "halluc_recommendation": (r.hallucination_assessment or {}).get("recommendation"),
                    "halluc_reasoning": (r.hallucination_assessment or {}).get("reasoning"),
                }
                for r in references
            ]
        )
        col_b.download_button(
            "📥 Referanslar (CSV)",
            data=df_ref_export.to_csv(index=False).encode("utf-8-sig"),
            file_name="referanslar.csv",
            mime="text/csv",
        )

    # --- Track Changes Patch Üretimi (sadece DOCX yüklenmişse) ---
    st.divider()
    st.markdown("### 📝 Word Track Changes ile Otomatik Düzeltme")

    if docx_inspection is None:
        st.info(
            "Track Changes yaması üretmek için **DOCX** formatında belge yükleyin. "
            "Şu anki belge `.{}` formatında.".format(Path(uploaded.name).suffix.lstrip(".").lower())
        )
    else:
        # Otomatik düzeltilebilir kategoriler için ön sayım
        from src.track_changes_patcher import _MANUAL_REVIEW_CATEGORIES

        auto_categories = {"Sayfa Aralığı", "APA 7 et al. Kuralı", "DOI Formatı"}
        auto_count = sum(1 for i in format_issues if i.category in auto_categories)
        manual_count = sum(1 for i in format_issues if i.category in _MANUAL_REVIEW_CATEGORIES)

        col_x, col_y, col_z = st.columns(3)
        col_x.metric("✅ Otomatik düzeltilebilir", auto_count)
        col_y.metric("⚠️ Manuel inceleme", manual_count)
        col_z.metric("Toplam tespit", len(format_issues))

        st.markdown(
            "Bu özellik DOCX dosyanızdan **Track Changes işaretli yamalı bir kopya** üretir. "
            "Word'de açıp her değişikliği **İncele > Kabul Et / Reddet** menüsünden onaylayabilirsiniz. "
            "Otomatik uygulanmayan sorunlar (italik, girinti, satır aralığı, alfabetik sıra) "
            "yamalı belgenin başında özet sayfa olarak listelenir."
        )

        if st.button("🛠️ Track Changes Yaması Üret", type="primary", use_container_width=True):
            output_path = tempfile.NamedTemporaryFile(
                delete=False, suffix=".docx", prefix="patched_"
            ).name

            with st.spinner("📝 Word Track Changes yaması oluşturuluyor..."):
                try:
                    patch_result = generate_track_changes_patch(
                        input_docx_path=tmp_path,
                        output_docx_path=output_path,
                        citations=citations,
                        references=references,
                        inspection=docx_inspection,
                        format_issues=format_issues,
                    )
                except Exception as e:
                    st.error(f"Yama üretilemedi: {e}")
                    st.stop()

            st.success(
                f"✓ {patch_result.applied_count} değişiklik uygulandı, "
                f"{patch_result.failed_count} başarısız."
            )

            if patch_result.fixes_by_category:
                st.markdown("**Uygulanan düzeltmeler:**")
                for cat, count in patch_result.fixes_by_category.items():
                    st.markdown(f"- {cat}: **{count}** değişiklik")

            # İndirme butonu
            with open(output_path, "rb") as f:
                st.download_button(
                    "📥 Yamalı DOCX'i İndir (Track Changes ile)",
                    data=f.read(),
                    file_name=f"patched_{Path(uploaded.name).stem}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True,
                )

            st.caption(
                "💡 İpucu: Word'de açtıktan sonra üst şeritte **İncele** sekmesinden "
                "**Tüm Değişiklikleri Göster** seçeneğini etkinleştirin."
            )
