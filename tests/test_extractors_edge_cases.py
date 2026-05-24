"""
Gerileme testleri: extractors.py ve cross_check.py kenar durumları.

Bu test dosyası, geçmiş PR'lerde (#1, #2, #3, #4) düzeltilen tüm
kenar durumlarının yeniden bozulmasını önlemek için yazılmıştır.

Çalıştırmak için:
    pytest tests/test_extractors_edge_cases.py -v

Gereksinimler: pytest (requirements.txt veya `pip install pytest`)
"""
from __future__ import annotations

import pytest

from src.extractors import (
    Citation,
    Reference,
    extract_in_text_citations,
    extract_references,
    _split_reference_entries,
)
from src.cross_check import cross_check


# ---------------------------------------------------------------------------
# 1) Citation.key — atıf tarafı normalizasyonu
# ---------------------------------------------------------------------------

class TestCitationKey:
    """Atıftan üretilen eşleştirme anahtarının doğru normalize edildiğini test eder."""

    def test_simple_surname(self):
        c = Citation(raw="(Smith, 2020)", authors="Smith", year="2020",
                     citation_type="parenthetical", position=0)
        assert c.key == "smith|2020"

    def test_curly_apostrophe_normalized(self):
        # U+2019 (right single quotation mark) düz ' ile aynı keye dönüşmeli
        c1 = Citation(raw="", authors="O’Donnell", year="2008",
                      citation_type="parenthetical", position=0)
        c2 = Citation(raw="", authors="O'Donnell", year="2008",
                      citation_type="parenthetical", position=0)
        assert c1.key == c2.key == "o'donnell|2008"

    def test_mc_prefix(self):
        c = Citation(raw="", authors="McIntyre", year="2006",
                     citation_type="parenthetical", position=0)
        assert c.key == "mcintyre|2006"

    def test_d_apostrophe_prefix(self):
        c = Citation(raw="", authors="Bago d’Uva", year="2009",
                     citation_type="parenthetical", position=0)
        assert c.key == "bago d'uva|2009"

    def test_van_lowercase_prefix(self):
        c = Citation(raw="", authors="van Doorslaer", year="2006",
                     citation_type="parenthetical", position=0)
        assert c.key == "van doorslaer|2006"

    def test_etal_stripped(self):
        c = Citation(raw="", authors="Smith et al.", year="2020",
                     citation_type="parenthetical", position=0)
        assert c.key == "smith|2020"

    def test_turkish_possessive_stripped(self):
        # Reason'ın → Reason
        c = Citation(raw="", authors="Reason’ın", year="2000",
                     citation_type="narrative", position=0)
        assert c.key == "reason|2000"

    def test_conjunction_word_boundary(self):
        # "and" kelime ortasında bölmemeli: Handastya bütün kalmalı
        c = Citation(raw="", authors="Handastya & Betti", year="2023",
                     citation_type="parenthetical", position=0)
        assert c.key == "handastya|2023"

# ---------------------------------------------------------------------------
# 2) Reference.key — kaynakça tarafı normalizasyonu (APA-aware)
# ---------------------------------------------------------------------------

class TestReferenceKey:
    """Reference.first_author_surname ve Reference.key testleri."""

    def test_simple_apa(self):
        r = Reference(raw="", authors_raw="Smith, J.", year="2020")
        assert r.key == "smith|2020"

    def test_multi_word_surname_arenliu_qosaj(self):
        # PR #4: çok kelimeli soyad APA virgülünde bölünmemeli
        r = Reference(raw="", authors_raw="Arenliu Qosaj, F.", year="2018")
        assert r.key == "arenliu qosaj|2018"

    def test_multi_word_surname_ozgen_narci(self):
        r = Reference(raw="", authors_raw="Özgen Narcı, B.", year="2015")
        assert r.key == "özgen narcı|2015"

    def test_multi_word_surname_duc_thanh(self):
        r = Reference(raw="", authors_raw="Duc Thanh, N.", year="2021")
        assert r.key == "duc thanh|2021"

    def test_bago_d_uva_curly_apostrophe(self):
        # PR #3 + #4: hem apostrof normalize hem çok kelimeli soyad
        r = Reference(raw="", authors_raw="Bago d’Uva, T.", year="2009")
        assert r.key == "bago d'uva|2009"

    def test_o_donnell_curly_apostrophe(self):
        r = Reference(raw="", authors_raw="O’Donnell, O.", year="2008")
        assert r.key == "o'donnell|2008"

    def test_institutional_acronym_who(self):
        r = Reference(raw="", authors_raw="WHO", year="2025")
        assert r.key == "who|2025"

    def test_institutional_acronym_oecd(self):
        r = Reference(raw="", authors_raw="OECD", year="2024")
        assert r.key == "oecd|2024"

    def test_mixed_institutional_who_and_world_bank(self):
        # "WHO, & World Bank" → ilk yazar WHO
        r = Reference(raw="", authors_raw="WHO, & World Bank", year="2025")
        assert r.key == "who|2025"

    def test_mixed_institutional_oecd_and_european_commission(self):
        r = Reference(raw="", authors_raw="OECD, & European Commission", year="2024")
        assert r.key == "oecd|2024"

    def test_multiword_org_world_bank(self):
        r = Reference(raw="", authors_raw="World Bank", year="2020")
        assert r.key == "world bank|2020"

    def test_missing_year_returns_none(self):
        r = Reference(raw="", authors_raw="Smith, J.", year=None)
        assert r.key is None

    def test_missing_authors_returns_none(self):
        r = Reference(raw="", authors_raw=None, year="2020")
        assert r.key is None


# ---------------------------------------------------------------------------
# 3) extract_in_text_citations — metin içi atıf çıkarımı
# ---------------------------------------------------------------------------

class TestExtractInTextCitations:
    """Gerçek metin pasajlarından atıf çıkarımı testleri."""

    def test_simple_parenthetical(self):
        text = "Bu konu önemlidir (Smith, 2020)."
        cits = extract_in_text_citations(text)
        assert len(cits) == 1
        assert cits[0].key == "smith|2020"

    def test_narrative_citation(self):
        text = "Smith (2020) bunu vurgular."
        cits = extract_in_text_citations(text)
        assert len(cits) == 1
        assert cits[0].citation_type == "narrative"
        assert cits[0].key == "smith|2020"

    def test_o_donnell_et_al(self):
        text = "Bu sorun (O’Donnell et al., 2008) tarafından ele alınmıştır."
        cits = extract_in_text_citations(text)
        assert len(cits) == 1
        assert cits[0].key == "o'donnell|2008"

    def test_van_doorslaer(self):
        text = "Çalışma (van Doorslaer et al., 2006) bunu gösterir."
        cits = extract_in_text_citations(text)
        assert len(cits) == 1
        assert cits[0].key == "van doorslaer|2006"

    def test_bago_d_uva(self):
        text = "Sonuçlar (Bago d’Uva et al., 2009) ile uyumludur."
        cits = extract_in_text_citations(text)
        assert len(cits) == 1
        assert cits[0].key == "bago d'uva|2009"

    def test_handastya_not_split_on_and(self):
        # PR #2: "Handastya & Betti" → yazar "Handastya", "H" değil
        text = "Yöntem (Handastya & Betti, 2023) önerilmiştir."
        cits = extract_in_text_citations(text)
        assert len(cits) == 1
        assert cits[0].key == "handastya|2023"

    def test_nanda_not_split_on_and(self):
        text = "Çalışma (Nanda & Sharma, 2023) ile karşılaştırılır."
        cits = extract_in_text_citations(text)
        assert len(cits) == 1
        assert cits[0].key == "nanda|2023"

    def test_who_world_bank_acronym(self):
        text = "Rapor (WHO & World Bank, 2025) yayımlandı."
        cits = extract_in_text_citations(text)
        assert len(cits) == 1
        assert cits[0].key == "who|2025"

    def test_oecd_european_commission(self):
        text = "Veriler (OECD & European Commission, 2024) tarafından açıklanmıştır."
        cits = extract_in_text_citations(text)
        assert len(cits) == 1
        assert cits[0].key == "oecd|2024"

    def test_birincisi_stop_word_skipped(self):
        # PR #2: "Birincisi, Williams (1959)" → yazar "Williams", "Birincisi" değil
        text = "Birincisi, Williams (1959) önemli bir katkı sunmuştur."
        cits = extract_in_text_citations(text)
        assert len(cits) == 1
        assert cits[0].key == "williams|1959"

    def test_la_zadeh_not_captured(self):
        # PR #2: cümle parçası "la Zadeh" yanlış yakalanmamalı
        # ama Williams (1959) yakalanmalı
        text = "Açıklamada la Zadeh (1965) yazımı normal metin akışındadır. Williams (1959) önemlidir."
        cits = extract_in_text_citations(text)
        keys = {c.key for c in cits}
        assert "williams|1959" in keys
        # "la zadeh|1965" yakalanmamalı çünkü öncesinde "Açıklamada" sözcüğü var

    def test_multi_citation_semicolon(self):
        text = "Veriler (Smith, 2020; Jones, 2021) tarafından doğrulanmıştır."
        cits = extract_in_text_citations(text)
        assert len(cits) == 2
        keys = {c.key for c in cits}
        assert keys == {"smith|2020", "jones|2021"}


# ---------------------------------------------------------------------------
# 4) _split_reference_entries — kaynakça bölme
# ---------------------------------------------------------------------------

class TestSplitReferenceEntries:
    """Kaynakça metnini ayrı kayıtlara bölme testleri (PR #4)."""

    def test_basic_apa_entries(self):
        text = (
            "Smith, J. (2020). Title one. Journal A, 1, 1.\n"
            "Jones, R. (2021). Title two. Journal B, 2, 2."
        )
        entries = _split_reference_entries(text)
        assert len(entries) == 2

    def test_multiword_surname_split(self):
        # PR #4: çok kelimeli soyad satır başı tanınmalı
        text = (
            "Arenliu Qosaj, F. (2018). Health title. Journal X, 1.\n"
            "Özgen Narcı, B. (2015). Another title. Journal Y, 2."
        )
        entries = _split_reference_entries(text)
        assert len(entries) == 2

    def test_institutional_split(self):
        # PR #4: WHO ile başlayan kayıt yeni entry olarak tanınmalı
        text = (
            "Smith, J. (2020). Title. Journal A.\n"
            "WHO, & World Bank. (2025). Global report. Geneva."
        )
        entries = _split_reference_entries(text)
        assert len(entries) == 2


# ---------------------------------------------------------------------------
# 5) extract_references — Reference nesnesi üretimi
# ---------------------------------------------------------------------------

class TestExtractReferences:
    """Reference nesnesi üretimi testleri."""

    def test_year_extracted(self):
        text = "Smith, J. (2020). Title. Journal."
        refs = extract_references(text)
        assert len(refs) == 1
        assert refs[0].year == "2020"

    def test_authors_raw_extracted(self):
        text = "Smith, J. (2020). Title. Journal."
        refs = extract_references(text)
        assert "Smith" in refs[0].authors_raw

    def test_doi_extracted(self):
        text = "Smith, J. (2020). Title. Journal. https://doi.org/10.1234/abc.efg"
        refs = extract_references(text)
        assert refs[0].doi == "10.1234/abc.efg"


# ---------------------------------------------------------------------------
# 6) cross_check — entegrasyon testleri (uçtan uca)
# ---------------------------------------------------------------------------

class TestCrossCheckIntegration:
    """Atıf + referans + cross_check uçtan uca testleri."""

    def test_o_donnell_curly_apostrophe_matches(self):
        # PR #3: atıf curly, referans curly — eşleşmeli
        body = "Bu konu (O’Donnell et al., 2008) tarafından ele alınmıştır."
        refs_text = "O’Donnell, O., van Doorslaer, E., Wagstaff, A., & Lindelow, M. (2008). Analyzing Health Equity. World Bank."
        cits = extract_in_text_citations(body)
        refs = extract_references(refs_text)
        result = cross_check(cits, refs)
        assert result.matched_count == 1
        assert len(result.missing_in_references) == 0

    def test_bago_d_uva_matches(self):
        body = "Çalışma (Bago d’Uva et al., 2009) sonuçlarını destekler."
        refs_text = "Bago d’Uva, T., Jones, A. M., & van Doorslaer, E. (2009). Measurement of horizontal inequity. Health Economics."
        cits = extract_in_text_citations(body)
        refs = extract_references(refs_text)
        result = cross_check(cits, refs)
        assert result.matched_count == 1
        assert len(result.missing_in_references) == 0

    def test_arenliu_qosaj_matches(self):
        body = "Veriler (Arenliu Qosaj et al., 2018) bunu doğrular."
        refs_text = "Arenliu Qosaj, F., Tahirukaj, A., & Berisha, V. (2018). Health systems in Kosovo. Lancet."
        cits = extract_in_text_citations(body)
        refs = extract_references(refs_text)
        result = cross_check(cits, refs)
        assert result.matched_count == 1
        assert len(result.missing_in_references) == 0

    def test_ozgen_narci_matches(self):
        body = "Çalışma (Özgen Narcı et al., 2015) sonuçlarını destekler."
        refs_text = "Özgen Narcı, B., Şahin, İ., & Yıldırım, H. H. (2015). Catastrophic health expenditures in Turkey. Health Policy."
        cits = extract_in_text_citations(body)
        refs = extract_references(refs_text)
        result = cross_check(cits, refs)
        assert result.matched_count == 1
        assert len(result.missing_in_references) == 0

    def test_who_world_bank_matches(self):
        body = "Rapor (WHO & World Bank, 2025) yayımlandı."
        refs_text = "WHO, & World Bank. (2025). Tracking universal health coverage: 2025 global monitoring report. Geneva."
        cits = extract_in_text_citations(body)
        refs = extract_references(refs_text)
        result = cross_check(cits, refs)
        assert result.matched_count == 1
        assert len(result.missing_in_references) == 0

    def test_oecd_european_commission_matches(self):
        body = "Veriler (OECD & European Commission, 2024) tarafından açıklanmıştır."
        refs_text = "OECD, & European Commission. (2024). Health at a Glance: Europe 2024. OECD Publishing."
        cits = extract_in_text_citations(body)
        refs = extract_references(refs_text)
        result = cross_check(cits, refs)
        assert result.matched_count == 1
        assert len(result.missing_in_references) == 0

    def test_handastya_betti_matches(self):
        body = "Yöntem (Handastya & Betti, 2023) önerilmiştir."
        refs_text = "Handastya, N., & Betti, G. (2023). The Double Fuzzy Set Approach to Multidimensional Poverty Measurement. Social Indicators Research."
        cits = extract_in_text_citations(body)
        refs = extract_references(refs_text)
        result = cross_check(cits, refs)
        assert result.matched_count == 1
        assert len(result.missing_in_references) == 0

    def test_birincisi_williams_matches(self):
        body = "Birincisi, Williams (1959) önemli katkıdır."
        refs_text = "Williams, B. (1959). Health and welfare. Journal of Social Policy."
        cits = extract_in_text_citations(body)
        refs = extract_references(refs_text)
        result = cross_check(cits, refs)
        assert result.matched_count == 1
        assert len(result.missing_in_references) == 0

    def test_unmatched_citation_detected(self):
        # Atıfta var, kaynakçada yok — missing_in_references'te olmalı
        body = "Bu (Unknown, 2099) bilinmeyendir."
        refs_text = "Smith, J. (2020). Title. Journal."
        cits = extract_in_text_citations(body)
        refs = extract_references(refs_text)
        result = cross_check(cits, refs)
        assert len(result.missing_in_references) == 1
        assert result.missing_in_references[0].key == "unknown|2099"

    def test_orphan_reference_detected(self):
        # Kaynakçada var, atıfta yok — orphan_references'te olmalı
        body = "Genel bir cümle, atıf yok."
        refs_text = "Smith, J. (2020). Title. Journal."
        cits = extract_in_text_citations(body)
        refs = extract_references(refs_text)
        result = cross_check(cits, refs)
        assert len(result.orphan_references) == 1
