"""Python çekirdeğinin çıktılarından JS eşlik (parity) testleri için fixtures.json üretir.
Kullanım: python web/make_fixtures.py   (depo kökünden)"""
import json, pathlib, re, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from src.cross_check import cross_check
from src.extractors import extract_in_text_citations, extract_references, detect_numeric_style
from src.format_checker import _count_distinct_authors
from src.names import fold, match_surnames, surname_tokens
from src.parsers import split_body_and_references
from tests.test_multipart_surnames import PARTICLE_CASES, DOUBLE_CASES, TITLE

docs = []
def add(body, ref_lines, with_title=True):
    refs = "\n".join(f"{l} {TITLE}" if with_title else l for l in ref_lines)
    docs.append(f"{body}\n\nKaynakça\n{refs}")

for body, ref in PARTICLE_CASES + DOUBLE_CASES:
    add(body, [ref])
for body, ref in [
    ("(Yılmaz, t.y.)", "Yılmaz, A. (n.d.)."), ("Smith (n.d.) argues", "Smith, J. (n.d.)."),
    ("(Demir Yılmaz, baskıda)", "Demir-Yılmaz, A. (in press)."),
    ("(World Health Organization, 2020)", "World Health Organization. (2020, March 5)."),
    ("(Smith, 1990, as cited in Jones, 2020)", "Jones, B. (2020)."), ("(Smith, 1990; akt. Jones, 2020)", "Jones, B. (2020)."),
    ("Smith (1990, as cited in Jones, 2020) argued", "Jones, B. (2020)."),
    ("Ancak Şahin (2017) karşı çıkar.", "Şahin, M. (2017)."), ("However, Smith (2009) disagreed.", "Smith, J. (2009)."),
    ("Kaya (2023) incelemiştir.", "Aksoy Kaya, Z. (2023)."), ("(Kurutkam, 2021).", "Kurutkan, M. N. (2021)."),
    ("Tablo 3 (2020) ve Şekil 2 (2019). In 2020 (n = 45) patients.", "Yetim, Y. (2001)."),
    ("(García Márquez, 2019).", "García Márquez, G. (1967)."),
    ("(Smith, 2020a; Jones & Lee, 2019, p. 12; WHO, 2021)", "Smith, J. (2020a)."),
    ("Yılmaz'ın (2019) ve Yılmaz ve Kaya (2020); (Yılmaz vd., 2018).", "Yılmaz, A. (2019)."),
]:
    add(body, [ref])
add("Kaya (2023) incelemiştir.", ["Aksoy Kaya, Z. (2023).", "Kaya, B. (2023)."])
add("(de Souza, 2020) ve (Uydurma, 2021). Yılmaz (2019) ise farklıdır.", ["de Souza, A. (2020).", "Yetim, Y. (2001).", "Yılmaz, A. (2018)."])
for sample in sorted((pathlib.Path(__file__).resolve().parent / "samples").glob("*.txt")):
    docs.append(sample.read_text(encoding="utf-8"))
docs.append(
    "Giriş (de Souza, 2020).\n\nReferencias\n"
    "de Souza, A. B. (2020). Uzun bir başlık ki satır sonunda\nbölünmüş durumda. Revista, 1(2), 3-4.\n"
    "García Márquez, G. (2019). İkinci uzun başlık ki yine satır\nsonunda bölünmüş. Revista, 5(6), 7-8.\n"
    "van der Berg, J., & Müller, K. (2018). Üçüncü başlık da\naynı şekilde. Tijdschrift, 9, 1-2. https://doi.org/10.1000/abc.def")

out = {"docs": [], "names": [], "counts": []}
for text in docs:
    body, refs = split_body_and_references(text)
    cits = extract_in_text_citations(body); rs = extract_references(refs); res = cross_check(cits, rs)
    out["docs"].append({
        "text": text,
        "citations": [[c.first_author_surname, c.year, c.citation_type] for c in cits],
        "references": [[r.first_author_surname, r.year, r.doi] for r in rs],
        "missing": [[c.first_author_surname, c.year] for c in res.missing_in_references],
        "orphans": [[r.first_author_surname, r.year] for r in res.orphan_references],
        "fuzzy": [[f.citation.first_author_surname, f.reference.first_author_surname, f.kind] for f in res.fuzzy_matches],
        "matched": res.matched_count,
        "numeric": detect_numeric_style(body, len(cits)),
    })
pairs = [("de Souza", "De Souza"), ("Souza", "de Souza"), ("González", "Gonzalez"), ("Demir Yılmaz", "Demir-Yılmaz"),
         ("Yılmaz", "Demir Yılmaz"), ("Márquez", "García Márquez"), ("LeBlanc", "Le Blanc"), ("Kurutkam", "Kurutkan"),
         ("Kaya", "Kara"), ("Yılmaz", "Yıldız"), ("Demir", "Demirci"), ("Smith", "Jones"), ("O’Brien", "OBrien"),
         ("Bago d'Uva", "d’Uva"), ("IŞIK", "Işık"), ("İnce", "Ince"), ("Strauß", "Strauss"), ("Jørgensen", "Jorgensen"),
         ("al-Farabi", "Farabi"), ("Le", "Le"), ("Castro e Silva", "Silva")]
for a, b in pairs:
    out["names"].append({"a": a, "b": b, "match": match_surnames(a, b), "fa": fold(a), "ta": surname_tokens(a)})
for s in ["Çelik Aydın Demirtaş", "Gonçalves da Silva", "García Márquez & Peña Nieto", "Smith, Jones, & Lackan",
          "Sammer, Lykens, Singh, Mains, & Lackan", "Yılmaz ve Kaya", "Smith et al."]:
    out["counts"].append([s, _count_distinct_authors(s)])
p = pathlib.Path(__file__).resolve().parent / "fixtures.json"
p.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print(len(out["docs"]), "belge,", len(out["names"]), "soyad çifti")
