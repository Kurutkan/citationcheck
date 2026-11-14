// JS çekirdeği testleri. Çalıştırma: node web/test_core.mjs
// 1) Python sürümüyle eşlik: fixtures.json içindeki her belge için aynı sonuç
// 2) Veritabanı doğrulaması: sahte fetch ile DOI uyuşmazlığı, doğrulama, ağ hatası
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
const dir = path.dirname(fileURLToPath(import.meta.url));
const CC = new Function(fs.readFileSync(path.join(dir, "core.js"), "utf8") + "\nreturn CitationCheck;")();
const fx = JSON.parse(fs.readFileSync(path.join(dir, "fixtures.json"), "utf8"));
let pass = 0, fail = 0;
const eq = (label, got, want) => {
  const g = JSON.stringify(got), w = JSON.stringify(want);
  if (g === w) pass++; else { fail++; console.log("BAŞARISIZ:", label, "\n   beklenen:", w, "\n   bulunan: ", g); }
};
fx.docs.forEach((d, i) => {
  const a = CC.analyze(d.text), tag = `belge ${i + 1} (${d.text.slice(0, 40).replace(/\n/g, " ")})`;
  eq(tag + " atıflar", a.citations.map(c => [c.surname, c.year, c.type]), d.citations);
  eq(tag + " kaynaklar", a.references.map(r => [r.surname, r.year, r.doi]), d.references);
  eq(tag + " eksik", a.cross.missing.map(c => [c.surname, c.year]), d.missing);
  eq(tag + " yetim", a.cross.orphans.map(r => [r.surname, r.year]), d.orphans);
  eq(tag + " esnek", a.cross.fuzzy.map(f => [f.citation.surname, f.reference.surname, f.kind]), d.fuzzy);
  eq(tag + " eşleşen", a.cross.matchedCount, d.matched);
  eq(tag + " numaralı", a.numericStyle, d.numeric);
});
fx.names.forEach(n => {
  eq(`soyad ${n.a} ~ ${n.b}`, CC.matchSurnames(n.a, n.b), n.match);
  eq(`fold ${n.a}`, CC.fold(n.a), n.fa);
  eq(`parçalar ${n.a}`, CC.surnameTokens(n.a), n.ta);
});
fx.counts.forEach(([s, n]) => eq(`yazar sayısı ${s}`, CC.countAuthors(s), n));

// --- Doğrulama ---
const REAL = { title: ["Patient safety culture in Turkish hospitals: a cross-sectional study"],
  author: [{ family: "Kurutkan", given: "Mehmet Nurullah" }, { family: "Demir", given: "Ayşe" }],
  published: { "date-parts": [[2020]] }, "container-title": ["Journal of Patient Safety"], DOI: "10.1000/real" };
const genuine = "Kurutkan, M. N., & Demir, A. (2020). Patient safety culture in Turkish hospitals: A cross-sectional study. Journal of Patient Safety, 16(2), 1-9.";
const fake = "Özkaya, B., & Arslan, T. (2020). Yapay zekâ destekli karar sistemlerinin hemşire memnuniyetine etkisi. Hemşirelik Bilimleri Dergisi, 4(1), 22-31.";
const one = raw => CC.extractReferences(raw + "\n" + raw.replace("2020", "2021"))[0];
const net = handlers => async url => {
  for (const [frag, res] of handlers) if (url.includes(frag)) { if (res === "throw") throw new Error("ağ"); return res; }
  return { status: 404, data: null };
};
const empty = { status: 200, data: { message: { items: [] }, results: [] } };

let r = await CC.validateReference(one(genuine + " https://doi.org/10.1000/real"), net([["works/10.1000", { status: 200, data: { message: REAL } }]]));
eq("DOI aynı yayına ait -> doğrulandı", r.status, "verified");
r = await CC.validateReference(one(fake + " https://doi.org/10.1000/real"),
  net([["works/10.1000", { status: 200, data: { message: REAL } }], ["query.bibliographic", empty], ["openalex", empty]]));
eq("gerçek DOI, uydurma kaynak -> doi_mismatch", r.status, "doi_mismatch");
r = await CC.validateReference(one(genuine), net([["query.bibliographic", { status: 200, data: { message: { items: [REAL] } } }]]));
eq("arama: aynı başlık -> doğrulandı", r.status, "verified");
const other = { ...REAL, title: ["Nurse staffing and mortality in intensive care units of public hospitals"] };
r = await CC.validateReference(one(genuine), net([["query.bibliographic", { status: 200, data: { message: { items: [other] } } }], ["openalex", empty]]));
eq("arama: farklı başlık -> doğrulanmadı", r.status !== "verified", true);
r = await CC.validateReference(one(fake), net([["query.bibliographic", empty], ["openalex", empty]]));
eq("hiçbir yerde yok -> bulunamadı", r.status, "not_found");
r = await CC.validateReference(one(fake), net([["crossref", "throw"], ["openalex", "throw"]]));
eq("ağ hatası 'bulunamadı' sayılmaz", r.status, "error");
r = await CC.validateReference(one(genuine + " https://doi.org/10.1000/yanlis"),
  net([["works/10.1000", { status: 404, data: null }], ["query.bibliographic", { status: 200, data: { message: { items: [REAL] } } }]]));
eq("yanlış yazılmış DOI, gerçek kaynak -> doğrulandı", r.status, "verified");
r = await CC.validateReference(one(genuine), net([["query.bibliographic", empty],
  ["openalex", { status: 200, data: { results: [{ title: REAL.title[0], publication_year: 2020, authorships: [{ author: { display_name: "Mehmet Nurullah Kurutkan" } }] }] } }]]));
eq("OpenAlex yedeği -> doğrulandı", [r.status, r.provider], ["verified", "openalex"]);
const many = CC.extractReferences(Array.from({ length: 12 }, (_, i) => `Yazar${i}, A. (2020). Bambaşka bir başlık numara ${i}. Dergi Adı, 1(2), 3-4.`).join("\n"));
const seen = [];
await CC.validateAll(many, net([["query.bibliographic", empty], ["openalex", empty]]), (d, t) => seen.push([d, t]), 4);
eq("toplu doğrulama ilerleme", [seen.length, seen.at(-1)], [12, [12, 12]]);
eq("toplu doğrulama durumlar", many.every(x => x.status === "not_found"), true);

// --- Biçim ve çeşitli ---
const a = CC.analyze("(García Márquez, López Obrador, & Peña Nieto, 2011) ve (Çelik Aydın Demirtaş, 2007).\n\nKaynakça\n" +
  "Şahin, A. (2020). Başlık bir iki üç dört. Dergi, 1, 1-2. doi:10.1000/x\nÇelik, B. (2019). Başlık bir iki üç dört. Dergi, 1, 1-2.\nÇelik, B. (2019). Başlık bir iki üç dört. Dergi, 1, 1-2.");
eq("biçim kodları", a.format.map(f => f.code).sort(), ["alpha", "doi", "dup", "etal"]);
eq("csv kaçış", CC.toCsv([["a", 'b"c', "d,e"]]), '﻿a,"b""c","d,e"');
const big = ("Bu çalışmada (Yılmaz, 2020) ve García Márquez (2019) ile de Souza vd. (2018) incelenmiştir. ").repeat(4000);
const t0 = Date.now(); const nBig = CC.extractCitations(big).length; const ms = Date.now() - t0;
eq("uzun metin atıf sayısı", nBig, 12000);
console.log(`uzun metin (${Math.round(big.length / 1000)} bin karakter): ${ms} ms`);

// --- DOCX okuma (harici kütüphane yok; tablo hücreleri dahil) ---
{
  const sample = path.join(dir, "samples", "ornek.docx");
  if (fs.existsSync(sample)) {
    const buf = fs.readFileSync(sample);
    const text = await CC.docxToText(buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength));
    const d = CC.analyze(text);
    eq("docx atıflar", d.citations.map(c => c.surname).sort(), ["García Márquez", "Yılmaz", "de Souza"]);
    eq("docx kaynak sayısı", d.references.length, 3);
    eq("docx eksik/yetim", [d.cross.missing.length, d.cross.orphans.length], [0, 0]);
    eq("docx XML kaçışları", text.includes("& García") && text.includes("<test>"), true);
  }
}

console.log(`\n${pass} geçti, ${fail} başarısız`);
process.exit(fail ? 1 : 0);
