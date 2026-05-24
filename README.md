# 📚 citationcheck — APA 7 Atıf Doğrulayıcı / Citation Checker

**Türkçe ve İngilizce akademik makalelerde metin içi atıfları, kaynakçayı ve yetim referansları kontrol eden; LLM destekli halüsinasyon (uydurma kaynak) tespiti yapan açık kaynak Streamlit uygulaması.**

*An open-source Streamlit application that validates in-text citations, cross-checks reference lists, detects orphan references, and uses LLM-powered hallucination detection in Turkish and English academic papers.*

---

## 🇹🇷 Türkçe

### Ne işe yarar?

PDF, DOCX veya TXT formatında akademik bir makale yüklediğinizde bu uygulama:

- **Metin içi atıfları çıkarır** — parantez içi (Smith, 2020) ve anlatımsal Smith (2020) atıflar dahil; çoklu atıflar (Smith, 2020; Jones, 2021) ayırır.
- **Türkçe ve İngilizce çalışır** — `vd.`, `ve ark.`, `ve diğerleri`, `et al.` varyantlarını destekler.
- **Referans listesini ayrıştırır** — yazar, yıl, başlık, DOI alanlarını çıkarır.
- **Çapraz tutarlılık kontrolü** — metinde atıfı geçen ama kaynakçada olmayan (eksik) ve kaynakçada olan ama metinde geçmeyen (yetim) referansları işaretler.
- **CrossRef + OpenAlex** ile çoklu kaynak doğrulaması yapar — DOI varsa direkt eşler, yoksa bibliyografik aramaya geçer.
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

### Anthropic API anahtarı (opsiyonel)

LLM destekli ayrıştırma ve halüsinasyon tespiti için bir Anthropic API anahtarı gerekir. Üç yolla verebilirsiniz:

1. **UI üzerinden** — sol panelden "LLM destekli analizi aç" → API anahtarınızı yapıştırın. Anahtar sadece o oturumda kullanılır, hiçbir yere kaydedilmez (BYO key).
2. **Ortam değişkeni** — `export ANTHROPIC_API_KEY=sk-ant-...` ardından Streamlit'i başlatın.
3. **`.streamlit/secrets.toml`** — proje kökünde `.streamlit/secrets.toml` dosyası oluşturun:
   ```toml
   ANTHROPIC_API_KEY = "sk-ant-..."
   CROSSREF_EMAIL = "you@example.com"  # opsiyonel, polite pool için
   ```

API anahtarı vermezseniz uygulama yine çalışır; sadece LLM özellikleri devre dışı kalır.

### Streamlit Cloud'a deploy

1. Bu repoyu GitHub hesabınıza forklayın (veya doğrudan kullanın).
2. [share.streamlit.io](https://share.streamlit.io) adresine GitHub ile girin.
3. "New app" → repo seçin, ana dosya: `app.py`, branch: `main`.
4. Advanced settings → Secrets bölümüne `ANTHROPIC_API_KEY = "..."` ekleyin (kullanıcılar kendi anahtarını da girebilir).
5. Deploy. Birkaç dakika içinde herkese açık bir URL'iniz olur.

---

## 🇬🇧 English

### What it does

Upload a PDF, DOCX, or TXT academic paper and this app will:

- **Extract in-text citations** — parenthetical (Smith, 2020) and narrative Smith (2020); splits multi-citations.
- **Bilingual support** — handles `et al.`, `vd.`, `ve ark.`, `ve diğerleri`.
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

### Anthropic API key (optional)

LLM-powered parsing and hallucination detection require an Anthropic API key. Three options:

1. **In the UI** — enable "LLM destekli analizi aç" in the sidebar and paste your key. It is used only for that session and never persisted (BYO key).
2. **Environment variable** — `export ANTHROPIC_API_KEY=sk-ant-...` then run Streamlit.
3. **`.streamlit/secrets.toml`** in the project root.

The app works without an API key; only LLM features will be disabled.

### Deploying to Streamlit Cloud

Fork the repo, connect at [share.streamlit.io](https://share.streamlit.io), select `app.py` as the entry point, optionally add `ANTHROPIC_API_KEY` in Secrets, deploy.

---

## 🏗️ Architecture

```
app.py                       # Streamlit UI
src/
  parsers.py                 # PDF/DOCX/TXT → (body, references)
  extractors.py              # Regex-based citation & reference extraction
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
