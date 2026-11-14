"""
Doğrulama (DOI denetimi, paralel çalışma) ve kenar durumları için testler:
tarihsiz / baskıda atıflar, ikincil atıflar, numaralı sistem tespiti, DOCX tabloları.
Ağ erişimi gerekmez; veritabanı sağlayıcıları taklit edilir.
"""
from __future__ import annotations

import pytest

from src import validators
from src.cross_check import cross_check
from src.extractors import (
    Reference, detect_numeric_style, extract_in_text_citations, extract_references,
)
from src.parsers import parse_document

TITLE = "Sağlık hizmetlerinde bir araştırma başlığı. Dergi Adı, 1(2), 3-14."


def _run(body, ref_lines):
    citations = extract_in_text_citations(body)
    references = extract_references("\n".join(f"{l} {TITLE}" for l in ref_lines))
    return citations, references, cross_check(citations, references)


# --- Tarihsiz ve baskıda -----------------------------------------------------

@pytest.mark.parametrize("body,ref", [
    ("(Yılmaz, t.y.)", "Yılmaz, A. (t.y.)."),
    ("(Yılmaz, t.y.)", "Yılmaz, A. (n.d.)."),
    ("Smith (n.d.) argues", "Smith, J. (n.d.)."),
    ("(Demir Yılmaz, baskıda)", "Demir-Yılmaz, A. (in press)."),
    ("(de Souza, in press)", "de Souza, A. (in press)."),
    ("(World Health Organization, 2020)", "World Health Organization. (2020, March 5)."),
])
def test_undated_and_in_press(body, ref):
    citations, references, res = _run(body, [ref])
    assert len(citations) == 1 and len(references) == 1
    assert res.missing_in_references == [] and res.orphan_references == []


# --- İkincil atıf ------------------------------------------------------------

@pytest.mark.parametrize("body", [
    "(Smith, 1990, as cited in Jones, 2020)",
    "(Smith, 1990; akt. Jones, 2020)",
    "(Smith, 1990, akt. Jones, 2020)",
    "Smith (1990, as cited in Jones, 2020) argued",
    "(Smith, 1990, citado en Jones, 2020)",
    "(akt. Jones, 2020)",
])
def test_secondary_citation_uses_cited_source_only(body):
    citations, _, res = _run(body, ["Jones, B. (2020)."])
    assert [c.first_author_surname for c in citations] == ["Jones"]
    assert res.missing_in_references == [] and res.orphan_references == []


# --- Numaralı sistem ---------------------------------------------------------

def test_numeric_style_detection():
    numeric = "Bulgular [1] ve [2, 3] ile uyumludur [4-6]. Ayrıca [7] ve [8]."
    assert detect_numeric_style(numeric, 0) is True
    apa = "Bulgular (Smith, 2020) ve (Jones, 2021) ile uyumludur [1]."
    assert detect_numeric_style(apa, 2) is False


# --- DOCX: tablolar ----------------------------------------------------------

def test_docx_table_cells_are_read(tmp_path):
    docx = pytest.importorskip("docx")
    doc = docx.Document()
    doc.add_paragraph("Giriş paragrafı (Yılmaz, 2020).")
    table = doc.add_table(rows=1, cols=2)
    table.cell(0, 0).text = "Kaynak"
    table.cell(0, 1).text = "Tablodaki atıf (de Souza, 2019)"
    doc.add_paragraph("Kaynakça")
    doc.add_paragraph(f"de Souza, A. (2019). {TITLE}")
    doc.add_paragraph(f"Yılmaz, A. (2020). {TITLE}")
    path = tmp_path / "ornek.docx"
    doc.save(str(path))

    body, refs = parse_document(path)
    citations = extract_in_text_citations(body)
    assert sorted(c.first_author_surname for c in citations) == ["Yılmaz", "de Souza"]
    res = cross_check(citations, extract_references(refs))
    assert res.missing_in_references == [] and res.orphan_references == []


# --- Veritabanı doğrulaması --------------------------------------------------

REAL = {
    "title": "Patient safety culture in Turkish hospitals: a cross-sectional study",
    "authors": ["Kurutkan, Mehmet Nurullah", "Demir, Ayşe"],
    "year": "2020", "container": "Journal of Patient Safety", "doi": "10.1000/real", "url": None,
    "source": "fake",
}


class FakeProvider:
    def __init__(self, by_doi=None, by_search=None):
        self.by_doi, self.by_search, self.calls = by_doi, by_search or [], 0

    def search_by_doi(self, doi, email=None):
        self.calls += 1
        return self.by_doi

    def search_by_bibliographic(self, query, email=None, rows=3):
        self.calls += 1
        return self.by_search


def _ref(raw):
    return extract_references(raw + "\n" + raw.replace("2020", "2021"))[0]


def test_doi_pointing_to_same_work_is_verified(monkeypatch):
    monkeypatch.setitem(validators.PROVIDERS, "fake", FakeProvider(by_doi=REAL))
    ref = _ref(
        "Kurutkan, M. N., & Demir, A. (2020). Patient safety culture in Turkish hospitals: "
        "A cross-sectional study. Journal of Patient Safety, 16(2), 1-9. https://doi.org/10.1000/real"
    )
    validators.validate_reference(ref, providers=["fake"])
    assert ref.validation_status == "verified"


def test_real_doi_on_fabricated_reference_is_flagged(monkeypatch):
    """Gerçek bir DOI, başka (uydurma) bir kaynağa yapıştırılmışsa 'doğrulandı' sayılmaz."""
    monkeypatch.setitem(validators.PROVIDERS, "fake", FakeProvider(by_doi=REAL))
    ref = _ref(
        "Özkaya, B., & Arslan, T. (2020). Yapay zekâ destekli karar sistemlerinin hemşire "
        "memnuniyetine etkisi. Hemşirelik Bilimleri Dergisi, 4(1), 22-31. https://doi.org/10.1000/real"
    )
    validators.validate_reference(ref, providers=["fake"])
    assert ref.validation_status == "doi_mismatch"
    assert ref.validation_match["title"].startswith("Patient safety culture")


def test_search_hit_with_different_title_is_not_verified(monkeypatch):
    other = dict(REAL, title="Nurse staffing and mortality in intensive care units of public hospitals")
    monkeypatch.setitem(validators.PROVIDERS, "fake", FakeProvider(by_search=[other]))
    ref = _ref(
        "Kurutkan, M. N., & Demir, A. (2020). Patient safety culture in Turkish hospitals: "
        "A cross-sectional study. Journal of Patient Safety, 16(2), 1-9."
    )
    validators.validate_reference(ref, providers=["fake"])
    assert ref.validation_status != "verified"


def test_search_hit_with_same_title_is_verified(monkeypatch):
    monkeypatch.setitem(validators.PROVIDERS, "fake", FakeProvider(by_search=[REAL]))
    ref = _ref(
        "Kurutkan, M. N., & Demir, A. (2020). Patient safety culture in Turkish hospitals: "
        "A cross-sectional study. Journal of Patient Safety, 16(2), 1-9."
    )
    validators.validate_reference(ref, providers=["fake"])
    assert ref.validation_status == "verified"


def test_batch_validation_runs_in_parallel_and_reports_progress(monkeypatch):
    monkeypatch.setitem(validators.PROVIDERS, "fake", FakeProvider(by_search=[REAL]))
    refs = [Reference(raw=f"Yazar{i}, A. (2020). Başlık {i}. Dergi.", year="2020") for i in range(12)]
    seen = []
    validators.validate_references_batch(
        refs, providers=["fake"], progress_callback=lambda d, t: seen.append((d, t)), max_workers=4,
    )
    assert seen[-1] == (12, 12) and len(seen) == 12
    assert all(r.validation_status != "unchecked" for r in refs)


def test_llm_client_never_reads_a_shared_key(monkeypatch):
    from src import llm
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-ortak-anahtar")
    monkeypatch.setattr(llm, "ANTHROPIC_AVAILABLE", True)
    with pytest.raises(llm.LLMUnavailableError):
        llm.LLMClient(api_key=None)
