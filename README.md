# 📚 citationcheck — APA 7 Atıf Doğrulayıcı / Citation Checker

**Türkçe ve İngilizce akademik makalelerde metin içi atıfları, kaynakçayı ve yetim referansları kontrol eden; LLM destekli halüsinasyon (uydurma kaynak) tespiti yapan açık kaynak Streamlit uygulaması.**

*An open-source Streamlit application that validates in-text citations, cross-checks reference lists, detects orphan references, and uses LLM-powered hallucination detection in Turkish and English academic papers.*

---

## 🇹🇷 Türkçe

### Ne işe yarar?

PDF, DOCX veya TXT formatında akademik bir makale yüklediğinizde bu uygulama:

- **Metin içi atıfları çıkarır** — parantez içi (Smith, 2020) ve anlatımsal Smith (2020) atıflar dahil; çoklu atıflar (Smith, 2020; Jones, 2021) ayırır.
- **Türkçe ve İngilizce çalışır** — `vd.`, `ve ark.`, `ve diğerleri`, `et al.` varyantlarını destekler.
- **Çok parçalı soyadları tanır** — soyad ekleri (`de`, `da`, `dos`, `del`, `de la`, `van der`, `von`, `al-`), çift soyadlar (`Demir Yılmaz`, `Demir-Yılmaz`, `García Márquez`, `Castro e Silva`), 3-5 sözcüklü yazar adları ve aksanlı harfler (`ñ`, `ã`, `ç`, `ø`). Atıf tek soyadla, kaynakça çift soyadla yazılmışsa eşleştirir ve yazım tutarsızlığı olarak bildirir.
- **Referans listesini ayrıştırır** — yazar, yıl, başlık, DOI alanlarını çıkarır.
- **Çapraz tutarlılık kontrolü** — metinde atıfı geçen ama kaynakçada olmayan (eksik) ve kaynakçada olan ama metinde geçmeyen (yetim) referansları işaretler.
- **CrossRef + OpenAlex** ile çoklu kaynak doğrulaması yapar — DOI varsa kaydı getirir ve başlık/yazarla karşılaştırır (gerçek DOI başka bir yayına aitse `doi_mismatch` olarak işaretler), yoksa bibliyografik aramaya geçer.
- **APA 7 biçim kontrolü** — `et al.` kuralı, `&` vs `and`, alfabetik sıra, DOI formatı, sayfa aralığı en-dash, yazar baş harfleri ve daha fazlası.
- **DOCX biçim kontrolü** — asılı girinti, çift satır aralığı, dergi adı + cilt italikliği kontrolü.
- **🧠 LLM destekli (opsiyonel):**
  - Bozuk / OCR'lı referansları Claude Haiku ile yapısal alanlara ayrıştırır.
  - Doğrulanamayan referansların halüsinasyon olup olmadığını Claude Sonnet ile akademik forensik mantıkla değerlendirir.
- **Word Track Changes** — DOCX yüklediyseniz otomatik düzeltmeleri Word'ün İncele sekmesinden kabul/reddedebileceğiniz şekilde yamalı bir DOCX üretir.
- **CSV dışa aktarımı** — atıflar ve referans doğrulama sonuçlarını indirebilirsiniz.

### Neden önemli?

Yapay zekâyla yazılmış akademik metinlerde uydurma kaynak (hallucinated citation) yaygın bir sorun. Bu uygulama, kaynakların gerçekten var olup olmadığını ücretsiz veritabanlarına (CrossRef, OpenAlex) sorarak ve LLM ile forensik analiz yaparak doğrular. Türkçe ve yerel akademik üretimi yanlış yere "uydurma" olarak işaretlememek için model özel olarak ihtiyatlı kalibre edilmiştir.

### Yerel kurulum

```bash
git clone https://github.com/Kurutkan/citationcheck.git
cd citationcheck
pip install -r requirements.txt
streamlit run app.py
```

Tarayıcı otomatik olarak `http://localhost:8501` adresinde açılır.

### Anthropic API anahtarı (opsiyonel, yalnızca kendi anahtarınız)

LLM destekli ayrıştırma ve halüsinasyon tespiti için bir Anthropic API anahtarı gerekir. Anahtar **yalnızca arayüzden** girilir: sol panelden "LLM destekli analizi aç" → kendi anahtarınızı yapıştırın. Anahtar sadece o oturumda kullanılır, hiçbir yere kaydedilmez.

Paylaşılan bir sunucu anahtarı **yoktur**: uygulama `secrets.toml` ya da `ANTHROPIC_API_KEY` ortam değişkenindeki anahtarı bilinçli olarak okumaz. Böylece herkese açık bir kurulumda maliyet uygulama sahibine yazılmaz. Anahtar girilmezse LLM özellikleri kapalı kalır, diğer tüm denetimler çalışır.

İsteğe bağlı olarak `.streamlit/secrets.toml` içine yalnızca `CROSSREF_EMAIL = "you@example.com"` yazabilirsiniz (hızlı yanıt havuzu için; gizli bilgi değildir).

### Gizlilik

Yüklenen dosya yalnızca işlem süresince geçici olarak diske yazılır ve iş biter bitmez silinir. En fazla 25 MB dosya kabul edilir.

### Tarayıcıda çalışan sürüm (web/)

`web/citationcheck.html` tek dosyalık, sunucusuz bir sürümdür: metin, DOCX ve PDF tarayıcıda işlenir, belge hiçbir sunucuya gönderilmez. Yalnızca kaynakça satırları CrossRef ve OpenAlex'e sorgu olarak iletilir. API anahtarı gerektirmez. LLM özellikleri ve Word Track Changes bu sürümde yoktur. Testler: `node web/test_core.mjs`.

### Streamlit Cloud'a deploy

1. Bu repoyu GitHub hesabınıza forklayın (veya doğrudan kullanın).
2. [share.streamlit.io](https://share.streamlit.io) adresine GitHub ile girin.
3. "New app" → repo seçin, ana dosya: `app.py`, branch: `main`.
4. Deploy. Birkaç dakika içinde herkese açık bir URL'iniz olur.

---

## 🇬🇧 English

### What it does

Upload a PDF, DOCX, or TXT academic paper and this app will:

- **Extract in-text citations** — parenthetical (Smith, 2020) and narrative Smith (2020); splits multi-citations.
- **Bilingual support** — handles `et al.`, `vd.`, `ve ark.`, `ve diğerleri`.
- **Multi-part surnames** — particles (`de`, `da`, `dos`, `del`, `de la`, `van der`, `von`, `al-`), double surnames (`García Márquez`, `Castro e Silva`, `Demir-Yılmaz`), 3-5 word author names and accented letters. A citation using one surname is matched to a double-surname reference and reported as a spelling inconsistency.
- **Parse the reference list** into author/year/title/DOI.
- **Cross-check consistency** — flags citations missing from references and orphan references (in bibliography but never cited).
- **Validate against CrossRef + OpenAlex** — DOI lookup first, then bibliographic search with fuzzy matching.
- **APA 7 format checks** — `et al.` rule, `&` vs `and`, alphabetical order, DOI format, page range en-dash, author initials.
- **DOCX format inspection** — hanging indent, double spacing, journal/volume italics.
- **🧠 LLM-powered (optional):**
  - Re-parse broken / OCR-damaged references with Claude Haiku.
  - Detect hallucinated (fabricated) references with Claude Sonnet using academic forensic reasoning.
- **Word Track Changes patch** — generates a DOCX with tracked corrections you can accept/reject in Word.
- **CSV export** of citations and validation results.

### Quick start

```bash
git clone https://github.com/Kurutkan/citationcheck.git
cd citationcheck
pip install -r requirements.txt
streamlit run app.py
```

### Anthropic API key (optional, bring your own)

LLM-powered parsing and hallucination detection require an Anthropic API key, entered **only in the UI** (sidebar → "LLM destekli analizi aç"). It is used for that session and never persisted. There is **no shared server key**: the app deliberately ignores `secrets.toml` and the `ANTHROPIC_API_KEY` environment variable, so a public deployment cannot run up costs for its owner. Without a key, only the LLM features are disabled.

### Privacy

Uploaded files are written to disk only for the duration of processing and deleted immediately. Maximum upload size is 25 MB.

### Browser-only version (web/)

`web/citationcheck.html` is a single-file, serverless build: text, DOCX and PDF are processed in the browser and the document is never uploaded. Only reference lines are sent to CrossRef and OpenAlex as queries. No API key needed. LLM features and Word Track Changes are not included. Tests: `node web/test_core.mjs`.

### Deploying to Streamlit Cloud

Fork the repo, connect at [share.streamlit.io](https://share.streamlit.io), select `app.py` as the entry point, deploy.

---

## 🏗️ Architecture

```
app.py                       # Streamlit UI
src/
  parsers.py                 # PDF/DOCX/TXT → (body, references)
  extractors.py              # Regex-based citation & reference extraction
  names.py                   # Surname normalisation and flexible matching
  cross_check.py             # Citation ↔ reference matching
  providers.py               # CrossRef + OpenAlex API wrappers
  validators.py              # Multi-provider validation orchestrator
  format_checker.py          # APA 7 format rules
  docx_inspector.py          # DOCX formatting metadata (italics, indent)
  track_changes_patcher.py   # Word Track Changes DOCX generator
  llm.py                     # Optional Anthropic Claude integration
```

## 🤝 Katkı / Contributing

PR'lar, sorun bildirimleri ve özellik istekleri memnuniyetle karşılanır. Issues sekmesinden başlayın.

## 📜 Lisans / License

MIT License — bu proje ilmin zekâtı niyetiyle ücretsiz ve açık kaynak olarak yayınlanmıştır. Akademik dürüstlüğe katkı sunmak için herkes tarafından kullanılabilir, değiştirilebilir ve dağıtılabilir.

*This project is released as open source in the spirit of giving knowledge freely. Everyone is welcome to use, modify, and redistribute it to contribute to academic integrity.*

## 🙏 Teşekkür / Acknowledgments

- [CrossRef](https://api.crossref.org) — ~140M academic records
- [OpenAlex](https://api.openalex.org) — ~250M open metadata records
- [Anthropic](https://www.anthropic.com) — Claude models for LLM features
- [Streamlit](https://streamlit.io) — UI framework
