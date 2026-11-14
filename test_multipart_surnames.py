"""
Çok parçalı soyadlar, soyad ekleri ve çok isimli yazarlar için regresyon testleri.

Kapsam: İspanyolca / Portekizce / Fransızca / Felemenkçe / Almanca soyad ekleri,
Türkçe çift soyadlar, 3-5 sözcüklü yazar adları, aksanlı harfler, esnek eşleştirme.
"""
from __future__ import annotations

import pytest

from src.cross_check import cross_check
from src.extractors import extract_in_text_citations, extract_references
from src.format_checker import _count_distinct_authors, check_alphabetical_sort, check_apa7_et_al
from src.names import fold, match_surnames, surname_tokens

TITLE = "Sağlık hizmetlerinde bir araştırma başlığı. Dergi Adı, 1(2), 3-14."


def _run(body: str, ref_lines: list[str]):
    refs = "\n".join(f"{line} {TITLE}" for line in ref_lines)
    citations = extract_in_text_citations(body)
    references = extract_references(refs)
    return citations, references, cross_check(citations, references)


# --- names.py ---------------------------------------------------------------

@pytest.mark.parametrize("raw,expected", [
    ("Gonçalves", "goncalves"), ("Şahin", "sahin"), ("IŞIK", "isik"),
    ("İnce", "ince"), ("Jørgensen", "jorgensen"), ("Núñez", "nunez"),
    ("Strauß", "strauss"), ("Łukasiewicz", "lukasiewicz"),
])
def test_fold(raw, expected):
    assert fold(raw) == expected


@pytest.mark.parametrize("raw,expected", [
    ("de Souza", ["souza"]), ("van der Berg", ["berg"]),
    ("De la Fuente", ["fuente"]), ("Castro e Silva", ["castro", "silva"]),
    ("Ortega y Gasset", ["ortega", "gasset"]), ("Bago d'Uva", ["bago", "uva"]),
    ("Demir-Yılmaz", ["demir", "yilmaz"]), ("Al-Farabi", ["farabi"]),
    ("O’Brien", ["obrien"]), ("Le", ["le"]),
])
def test_surname_tokens(raw, expected):
    assert surname_tokens(raw) == expected


@pytest.mark.parametrize("a,b,expected", [
    ("de Souza", "De Souza", "exact"),
    ("Souza", "de Souza", "exact"),
    ("González", "Gonzalez", "exact"),
    ("Demir Yılmaz", "Demir-Yılmaz", "exact"),
    ("Yılmaz", "Demir Yılmaz", "variant"),
    ("Márquez", "García Márquez", "variant"),
    ("LeBlanc", "Le Blanc", "variant"),
    ("Kurutkam", "Kurutkan", "typo"),
    ("Kaya", "Kara", None),          # kısa soyad: yazım hatası sayılmaz
    ("Yılmaz", "Yıldız", None),
    ("Demir", "Demirci", None),
    ("Smith", "Jones", None),
])
def test_match_surnames(a, b, expected):
    assert match_surnames(a, b) == expected


# --- Soyad ekleri (İspanyolca, Portekizce, Fransızca, Felemenkçe ...) -------

PARTICLE_CASES = [
    ("(de Souza, 2020)", "de Souza, A. B. (2020)."),
    ("de Souza (2020) bulmuştur", "de Souza, A. B. (2020)."),
    ("De Souza (2020) bulmuştur", "de Souza, A. B. (2020)."),
    ("(van der Berg & Müller, 2018)", "van der Berg, J., & Müller, K. (2018)."),
    ("(Dos Santos et al., 2021)", "dos Santos, M. A., Lima, P., & Rocha, T. (2021)."),
    ("De la Fuente (2015) göstermiştir", "de la Fuente, R. (2015)."),
    ("(de los Ríos, 2015)", "De Los Ríos, R. (2015)."),
    ("Gonçalves da Silva (2014) göstermiştir", "Gonçalves da Silva, P. (2014)."),
    ("(Le Blanc, 2013)", "LeBlanc, P. (2013)."),
    ("(Du Pont & Des Jardins, 2012)", "du Pont, A., & des Jardins, B. (2012)."),
    ("(von Neumann, 1944)", "Von Neumann, J. (1944)."),
    ("(Núñez, 2005)", "Nunez, A. (2005)."),
    ("(Al-Farabi, 2003)", "al-Farabi, M. (2003)."),
    ("(D’Angelo, 2012)", "D'Angelo, F. (2012)."),
]


@pytest.mark.parametrize("body,ref", PARTICLE_CASES)
def test_particle_surnames_match(body, ref):
    citations, references, res = _run(body, [ref])
    assert len(citations) == 1 and len(references) == 1
    assert res.missing_in_references == []
    assert res.orphan_references == []


# --- Çift / çoklu soyad -----------------------------------------------------

DOUBLE_CASES = [
    ("García Márquez (2019) bulmuştur", "García Márquez, G. (2019)."),
    ("(García Márquez, 2019)", "García Márquez, G. (2019)."),
    ("(Márquez, 2019)", "García Márquez, G. (2019)."),
    ("(González-Pérez y López, 2016)", "González-Pérez, J., & López, M. (2016)."),
    ("Castro e Silva (2006) çalışması", "Castro e Silva, L. (2006)."),
    ("(Silva e Santos, 2001)", "Silva, A., & Santos, B. (2001)."),
    ("(Ortega y Gasset, 1930)", "Ortega y Gasset, J. (1930)."),
    ("(Peña Nieto, 2008)", "Peña Nieto, E. (2008)."),
    ("Demir Yılmaz (2022) incelemiştir", "Demir-Yılmaz, A. (2022)."),
    ("Öztürk-Kaya (2021) incelemiştir", "Öztürk Kaya, F. (2021)."),
    ("Kaya (2023) incelemiştir", "Aksoy Kaya, Z. (2023)."),
    ("(Aksoy Kaya, 2023)", "Kaya, Z. (2023)."),
    ("(Çelik Aydın Demirtaş, 2007)", "Çelik Aydın Demirtaş, N. (2007)."),
    ("Karaca Yılmaz Öztürk Demir (2013) göstermiştir", "Karaca Yılmaz Öztürk Demir, S. (2013)."),
    ("(Mendes de Almeida Santos, 2012)", "Mendes de Almeida Santos, R. (2012)."),
    ("(García Márquez, 1967)", "García Márquez, Gabriel (1967)."),
]


@pytest.mark.parametrize("body,ref", DOUBLE_CASES)
def test_double_surnames_match(body, ref):
    citations, references, res = _run(body, [ref])
    assert len(citations) == 1 and len(references) == 1
    assert res.missing_in_references == []
    assert res.orphan_references == []


def test_inconsistent_spelling_is_reported():
    _, _, res = _run("Kaya (2023) incelemiştir.", ["Aksoy Kaya, Z. (2023)."])
    assert [f.kind for f in res.fuzzy_matches] == ["variant"]
    _, _, res = _run("(Kurutkam, 2021).", ["Kurutkan, M. N. (2021)."])
    assert [f.kind for f in res.fuzzy_matches] == ["typo"]
    _, _, res = _run("(de Souza, 2020).", ["De Souza, A. (2020)."])
    assert res.fuzzy_matches == []


def test_exact_match_preferred_over_variant():
    """Listede hem 'Kaya' hem 'Aksoy Kaya' varsa 'Kaya (2023)' yalnızca birincisine bağlanır."""
    _, _, res = _run("Kaya (2023) incelemiştir.", ["Aksoy Kaya, Z. (2023).", "Kaya, B. (2023)."])
    assert res.missing_in_references == []
    assert [r.first_author_surname for r in res.orphan_references] == ["Aksoy Kaya"]


# --- Gerçek eksik ve yetim kayıtlar hâlâ yakalanmalı -------------------------

def test_true_missing_and_orphan_still_detected():
    body = "(de Souza, 2020) ve (Uydurma, 2021). Yılmaz (2019) ise farklıdır."
    _, _, res = _run(body, ["de Souza, A. (2020).", "Yetim, Y. (2001).", "Yılmaz, A. (2018)."])
    assert sorted(c.first_author_surname for c in res.missing_in_references) == ["Uydurma", "Yılmaz"]
    assert sorted(r.first_author_surname for r in res.orphan_references) == ["Yetim", "Yılmaz"]


def test_year_mismatch_is_not_matched():
    _, _, res = _run("(García Márquez, 2019).", ["García Márquez, G. (1967)."])
    assert len(res.missing_in_references) == 1 and len(res.orphan_references) == 1


# --- Cümle başı sözcükleri ---------------------------------------------------

@pytest.mark.parametrize("body,surname", [
    ("Ancak Şahin (2017) karşı çıkar.", "Şahin"),
    ("However, Smith (2009) disagreed.", "Smith"),
    ("Nitekim Demir Yılmaz (2022) aynı sonuca varmıştır.", "Demir Yılmaz"),
    ("Bu çalışmada da Yılmaz (2020) benzer sonuç bulmuştur.", "Yılmaz"),
])
def test_sentence_initial_words_are_stripped(body, surname):
    citations = extract_in_text_citations(body)
    assert [c.first_author_surname for c in citations] == [surname]


def test_non_citations_are_ignored():
    assert extract_in_text_citations("Tablo 3 (2020) ve Şekil 2 (2019). In 2020 (n = 45) patients.") == []


# --- Kaynakça bölme ----------------------------------------------------------

def test_reference_list_with_accents_is_split_per_entry():
    lines = [c[1] for c in PARTICLE_CASES + DOUBLE_CASES]
    refs = "\n".join(f"{line} {TITLE}" for line in lines)
    assert len(extract_references(refs)) == len(lines)


def test_wrapped_reference_lines_are_split_on_author_start():
    refs = (
        "de Souza, A. B. (2020). Uzun bir başlık ki satır sonunda\nbölünmüş durumda. Revista, 1(2), 3-4.\n"
        "García Márquez, G. (2019). İkinci uzun başlık ki yine satır\nsonunda bölünmüş. Revista, 5(6), 7-8.\n"
        "van der Berg, J., & Müller, K. (2018). Üçüncü başlık da\naynı şekilde. Tijdschrift, 9, 1-2."
    )
    assert [r.first_author_surname for r in extract_references(refs)] == [
        "de Souza", "García Márquez", "van der Berg",
    ]


# --- APA denetimleri ---------------------------------------------------------

@pytest.mark.parametrize("authors,count", [
    ("Çelik Aydın Demirtaş", 1),
    ("Gonçalves da Silva", 1),
    ("Karaca Yılmaz Öztürk Demir", 1),
    ("García Márquez & Peña Nieto", 2),
    ("Smith, Jones, & Lackan", 3),
    ("Sammer, Lykens, Singh, Mains, & Lackan", 5),
    ("Yılmaz ve Kaya", 2),
    ("Smith et al.", 1),
])
def test_author_count_ignores_number_of_name_words(authors, count):
    assert _count_distinct_authors(authors) == count


def test_et_al_rule_not_triggered_by_multiword_single_author():
    citations = extract_in_text_citations(
        "(Çelik Aydın Demirtaş, 2007) ve (Mendes de Almeida Santos, 2012)."
    )
    assert check_apa7_et_al(citations) == []


def test_alphabetical_sort_uses_folded_letters():
    refs = extract_references("\n".join(f"{l} {TITLE}" for l in [
        "Çelik, A. (2020).", "Demir, B. (2019).", "Öztürk, C. (2018).", "Şahin, D. (2017).", "Zengin, E. (2016).",
    ]))
    assert check_alphabetical_sort(refs) == []
