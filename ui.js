/* citationcheck: arayüz. #ccx kökü altında çalışır; core.js sonrasında yüklenir. */
(function () {
  "use strict";
  var CC = CitationCheck, root = document.getElementById("ccx");
  if (!root) return;
  var PDFJS = "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.10.38/";
  var MAX_MB = 25, MAX_VALIDATE = 300;
  var lang = "en"; try { if (localStorage.getItem("ccx-lang") === "tr") lang = "tr"; } catch (e) {}
  var state = { result: null, tab: "cross", validated: false, busy: false };

  var T = {
    tr: {
      kicker: "Araç · Akademik yazım", title: "Atıf ve Kaynakça Denetleyici",
      lede: "Makalenizi yapıştırın ya da yükleyin. Metin içi atıflar ile kaynakça karşılaştırılır; eksik, yetim ve tutarsız yazılmış kaynaklar saniyeler içinde listelenir.",
      paste: "Makale metni (kaynakça dahil)", ph: "Metninizi buraya yapıştırın. Kaynakça bölümü kendi satırında “Kaynakça” ya da “References” başlığıyla başlamalıdır.",
      upload: "Dosya yükle (DOCX, PDF, TXT)", sample: "Örnek metin", analyze: "Denetle", clear: "Temizle",
      privacy: "Metniniz tarayıcınızdan çıkmaz; hiçbir sunucuya yüklenmez. Yalnızca “Veritabanında doğrula” düğmesine basarsanız kaynakça satırları CrossRef ve OpenAlex'e sorgu olarak gönderilir.",
      reading: "Dosya okunuyor…", tooBig: "Dosya çok büyük (en fazla " + MAX_MB + " MB).", badFile: "Dosya okunamadı. DOCX ya da TXT deneyin veya metni yapıştırın.",
      pdfFail: "PDF okunamadı. Taranmış (görüntü) PDF olabilir; DOCX yükleyin ya da metni yapıştırın.", noType: "Desteklenmeyen dosya türü. DOCX, PDF ya da TXT yükleyin.",
      empty: "Önce bir metin yapıştırın ya da dosya yükleyin.",
      noRefs: "Kaynakça bölümü bulunamadı. Kaynakçanın başına, kendi satırında “Kaynakça” ya da “References” başlığı ekleyin.",
      numeric: "Bu metin numaralı atıf sistemi (Vancouver / IEEE: [1], [2-4]) kullanıyor görünüyor. Bu araç yazar-tarih (APA) atıflarını denetler; numaralı atıflarda metin-kaynakça eşleştirmesi yapılmaz.",
      mCit: "Metin içi atıf", mRef: "Kaynak", mMiss: "Kaynakçada yok", mOrph: "Metinde atıf yok", mFuzzy: "Yazım tutarsız",
      tCross: "Çapraz kontrol", tCit: "Atıflar", tRef: "Kaynaklar", tFmt: "Biçim",
      hMiss: "Metinde var, kaynakçada yok", hOrph: "Kaynakçada var, metinde atıf yok", hFuzzy: "Eşleşti, ancak soyad yazımı tutarsız",
      okMiss: "Tüm atıfların kaynağı kaynakçada mevcut.", okOrph: "Tüm kaynaklara metinde atıf yapılmış.",
      fuzzyNote: "Bu atıflar kaynakçadaki kayıtla eşleştirildi, ancak soyad iki yerde farklı yazılmış. Metin ile kaynakçayı aynı biçime getirin.",
      variant: "farklı yazım", typo: "olası yazım hatası", inRefs: "kaynakçada",
      cRaw: "Atıf", cAuth: "Yazar(lar)", cYear: "Yıl", cType: "Tür", cMatch: "Kaynakçada", paren: "parantez içi", narr: "anlatımsal", yes: "var", no: "yok",
      rNo: "#", rRef: "Kaynak", rAuth: "İlk yazar", rYear: "Yıl", rCited: "Atıf", rStatus: "Veritabanı", rFound: "Bulunan kayıt",
      validate: "Veritabanında doğrula (CrossRef + OpenAlex)", validating: "Doğrulanıyor", validateNote: "Kaynakların gerçekten var olup olmadığını sorgular. Kaynakça satırları CrossRef ve OpenAlex'e gönderilir.",
      capped: "Yalnızca ilk " + MAX_VALIDATE + " kaynak doğrulandı.",
      s_verified: "Doğrulandı", s_low_confidence: "Düşük güven", s_not_found: "Bulunamadı", s_doi_mismatch: "DOI başka yayına ait", s_error: "Sorgulanamadı", s_unchecked: "-",
      vSum: "doğrulandı", vLow: "düşük güven", vNot: "bulunamadı", vDoi: "DOI uyuşmazlığı", vErr: "sorgulanamadı",
      doiWarn: "Dikkat: aşağıdaki kaynaklarda DOI gerçek, ancak başka bir yayına ait. Uydurma kaynaklarda sık görülür.",
      notFoundWarn: "“Bulunamadı” kaynağın uydurma olduğunu kanıtlamaz: kitaplar, tezler, raporlar ve Türkçe dergilerin bir bölümü bu veritabanlarında yer almaz. Bu kaynakları elle kontrol edin.",
      f_etal: "APA 7: üç ve daha fazla yazarlı kaynakta ilk atıftan itibaren “et al.” (Türkçede “vd.”) kullanılır.",
      f_alpha: "Kaynakça alfabetik sırada değil: “{a}”, “{b}” kaydından önce gelmeli.",
      f_doi: "DOI biçimi: APA 7'de DOI “https://doi.org/…” biçiminde yazılır.", f_noyear: "Bu kaynakta yıl bulunamadı.",
      f_dup: "Aynı kaynak iki kez listelenmiş görünüyor (#{a} ve #{b}).", okFmt: "Biçim sorunu saptanmadı.",
      csvCit: "Atıfları indir (CSV)", csvRef: "Kaynakları indir (CSV)", none: "Kayıt yok.",
      limits: "Sınırlar: yazar-tarih (APA) atıfları denetlenir; yalnızca ilk yazar karşılaştırılır; taranmış PDF'lerde metin okunamaz.",
      credit: "Hazırlayan: Prof. Dr. Mehmet Nurullah Kurutkan, Düzce Üniversitesi İşletme Fakültesi Sağlık Yönetimi Bölümü", source: "Açık kaynak kod"
    },
    en: {
      kicker: "Tool · Academic writing", title: "Citation and Reference Checker",
      lede: "Paste or upload your manuscript. In-text citations are compared with the reference list; missing, uncited and inconsistently spelled sources are listed in seconds.",
      paste: "Manuscript text (including the reference list)", ph: "Paste your text here. The reference list must start with a “References” heading on its own line.",
      upload: "Upload a file (DOCX, PDF, TXT)", sample: "Sample text", analyze: "Check", clear: "Clear",
      privacy: "Your text never leaves your browser; nothing is uploaded to a server. Only if you press “Verify in databases” are the reference lines sent to CrossRef and OpenAlex as queries.",
      reading: "Reading file…", tooBig: "File too large (max " + MAX_MB + " MB).", badFile: "The file could not be read. Try DOCX or TXT, or paste the text.",
      pdfFail: "The PDF could not be read. It may be a scanned (image) PDF; upload a DOCX or paste the text.", noType: "Unsupported file type. Upload DOCX, PDF or TXT.",
      empty: "Paste some text or upload a file first.",
      noRefs: "No reference list found. Add a “References” heading on its own line above the list.",
      numeric: "This text appears to use a numbered citation system (Vancouver / IEEE: [1], [2-4]). This tool checks author-date (APA) citations; numbered citations are not matched against the list.",
      mCit: "In-text citations", mRef: "References", mMiss: "Missing from list", mOrph: "Never cited", mFuzzy: "Spelled differently",
      tCross: "Cross-check", tCit: "Citations", tRef: "References", tFmt: "Format",
      hMiss: "Cited in the text, missing from the reference list", hOrph: "In the reference list, never cited", hFuzzy: "Matched, but the surname is spelled differently",
      okMiss: "Every citation has an entry in the reference list.", okOrph: "Every reference is cited in the text.",
      fuzzyNote: "These citations were matched to a reference, but the surname is written differently in the two places. Make the text and the list consistent.",
      variant: "different spelling", typo: "possible typo", inRefs: "in the list",
      cRaw: "Citation", cAuth: "Author(s)", cYear: "Year", cType: "Type", cMatch: "In list", paren: "parenthetical", narr: "narrative", yes: "yes", no: "no",
      rNo: "#", rRef: "Reference", rAuth: "First author", rYear: "Year", rCited: "Cited", rStatus: "Database", rFound: "Record found",
      validate: "Verify in databases (CrossRef + OpenAlex)", validating: "Verifying", validateNote: "Checks whether each source really exists. Reference lines are sent to CrossRef and OpenAlex.",
      capped: "Only the first " + MAX_VALIDATE + " references were verified.",
      s_verified: "Verified", s_low_confidence: "Low confidence", s_not_found: "Not found", s_doi_mismatch: "DOI belongs to another work", s_error: "Could not query", s_unchecked: "-",
      vSum: "verified", vLow: "low confidence", vNot: "not found", vDoi: "DOI mismatch", vErr: "could not query",
      doiWarn: "Warning: in the references below the DOI is real but belongs to a different publication. This is common in fabricated references.",
      notFoundWarn: "“Not found” does not prove a source is fabricated: books, theses, reports and many non-English journals are not in these databases. Check these sources by hand.",
      f_etal: "APA 7: with three or more authors, use “et al.” from the first citation.",
      f_alpha: "The list is not in alphabetical order: “{a}” should come before “{b}”.",
      f_doi: "DOI format: APA 7 writes DOIs as “https://doi.org/…”.", f_noyear: "No year found in this reference.",
      f_dup: "The same source appears to be listed twice (#{a} and #{b}).", okFmt: "No format problems found.",
      csvCit: "Download citations (CSV)", csvRef: "Download references (CSV)", none: "No records.",
      limits: "Limits: author-date (APA) citations only; only the first author is compared; text cannot be read from scanned PDFs.",
      credit: "Prepared by Prof. Dr. Mehmet Nurullah Kurutkan, Düzce University, Faculty of Business, Department of Health Management", source: "Open source code"
    }
  };
  function t(k, vars) {
    var s = (T[lang] && T[lang][k]) || T.en[k] || k;
    if (vars) Object.keys(vars).forEach(function (v) { s = s.split("{" + v + "}").join(vars[v]); });
    return s;
  }
  var SAMPLE = "Sağlıkta eşitsizlik uzun süredir çalışılmaktadır (de Souza, 2020). García Márquez (2019) farklı bir sonuç bulmuştur. " +
    "Benzer bulgular (van der Berg & Müller, 2018) ve (Dos Santos et al., 2021) tarafından da bildirilmiştir. " +
    "Demir Yılmaz (2022) hemşireleri incelemiştir. Ancak Şahin (2017) buna karşı çıkar. Kaya (2023) çift soyadlı yazara tek soyadla atıf yapmaktadır. " +
    "Bazı kaynaklar ise listede yoktur (Uydurma, 2021).\n\nKaynakça\n" +
    "Aksoy Kaya, Z. (2023). Hemşirelikte iş yükü ve bakım kalitesi. Sağlık Yönetimi Dergisi, 5(1), 10-22.\n" +
    "Demir-Yılmaz, A. (2022). Hemşirelerde tükenmişlik ve dayanıklılık. Hemşirelik Araştırmaları Dergisi, 8(3), 44-58.\n" +
    "de Souza, A. B. (2020). Desigualdades em saúde no Brasil. Revista de Saúde Pública, 54(2), 30-41.\n" +
    "dos Santos, M. A., Lima, P., & Rocha, T. (2021). Acesso aos serviços de saúde. Cadernos de Saúde Pública, 37(4), 1-12.\n" +
    "García Márquez, G. (2019). Calidad de la atención hospitalaria. Gaceta Sanitaria, 33(5), 400-410.\n" +
    "Öztürk, C. (2015). Hasta güvenliği kültürü. Sağlıkta Kalite Dergisi, 2(1), 1-9.\n" +
    "Şahin, M. (2017). Sağlık politikalarında dönüşüm. Sağlık Politikaları Dergisi, 3(2), 15-27.\n" +
    "van der Berg, J., & Müller, K. (2018). Patient safety in Dutch hospitals. BMJ Quality and Safety, 27(6), 500-509.";

  function h(tag, attrs, kids) {
    var el = document.createElement(tag);
    if (attrs) Object.keys(attrs).forEach(function (k) {
      var v = attrs[k];
      if (v === null || v === undefined || v === false) return;
      if (k === "class") el.className = v; else if (k === "text") el.textContent = v;
      else if (k.slice(0, 2) === "on") el.addEventListener(k.slice(2), v); else el.setAttribute(k, v === true ? "" : v);
    });
    (kids || []).forEach(function (c) { if (c) el.appendChild(typeof c === "string" ? document.createTextNode(c) : c); });
    return el;
  }
  function clear(el) { while (el.firstChild) el.removeChild(el.firstChild); return el; }

  // ---------- İskelet ----------
  var ta, msg, out, fileInput, analyzeBtn;
  function build() {
    clear(root);
    ta = h("textarea", { id: "ccx-text", rows: "12", spellcheck: "false", placeholder: t("ph"), "aria-label": t("paste") });
    if (state.keepText) ta.value = state.keepText;
    fileInput = h("input", { type: "file", id: "ccx-file", accept: ".docx,.pdf,.txt,.md", class: "ccx-hide", onchange: onFile });
    analyzeBtn = h("button", { type: "button", class: "ccx-btn ccx-primary", text: t("analyze"), onclick: run });
    msg = h("div", { class: "ccx-msg", role: "status", "aria-live": "polite" });
    out = h("div", { class: "ccx-out" });
    root.appendChild(h("header", { class: "ccx-hero" }, [
      h("div", { class: "ccx-top" }, [h("span", { class: "ccx-kicker", text: t("kicker") }),
        h("div", { class: "ccx-lang", role: "group", "aria-label": "Language" }, ["en", "tr"].map(function (l) {
          return h("button", { type: "button", "aria-pressed": String(l === lang), text: l.toUpperCase(), onclick: function () { setLang(l); } });
        }))]),
      h("h2", { class: "ccx-title", text: t("title") }), h("p", { class: "ccx-lede", text: t("lede") })
    ]));
    root.appendChild(h("section", { class: "ccx-card" }, [
      h("label", { class: "ccx-label", for: "ccx-text", text: t("paste") }), ta,
      h("div", { class: "ccx-actions" }, [analyzeBtn,
        h("label", { class: "ccx-btn", for: "ccx-file", tabindex: "0", text: t("upload"), onkeydown: function (e) { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); fileInput.click(); } } }), fileInput,
        h("button", { type: "button", class: "ccx-btn ccx-ghost", text: t("sample"), onclick: function () { ta.value = SAMPLE; run(); } }),
        h("button", { type: "button", class: "ccx-btn ccx-ghost", text: t("clear"), onclick: function () { ta.value = ""; state.result = null; clear(out); clear(msg); ta.focus(); } })]),
      h("p", { class: "ccx-privacy", text: t("privacy") }), msg
    ]));
    root.appendChild(out);
    root.appendChild(h("footer", { class: "ccx-foot" }, [h("p", { text: t("limits") }),
      h("p", {}, [t("credit") + " · ", h("a", { href: "https://github.com/Kurutkan/citationcheck", target: "_blank", rel: "noopener", text: t("source") })])]));
    if (state.result) render();
  }
  function setLang(l) { lang = l; try { localStorage.setItem("ccx-lang", l); } catch (e) {} state.keepText = ta ? ta.value : ""; build(); }
  function say(text, kind) { clear(msg); if (text) msg.appendChild(h("p", { class: "ccx-note ccx-" + (kind || "info"), text: text })); }

  // ---------- Dosya okuma ----------
  async function pdfToText(buffer) {
    var lib = await import(PDFJS + "pdf.min.mjs");
    lib.GlobalWorkerOptions.workerSrc = PDFJS + "pdf.worker.min.mjs";
    var doc = await lib.getDocument({ data: buffer }).promise, pages = [];
    for (var p = 1; p <= doc.numPages; p++) {
      var content = await (await doc.getPage(p)).getTextContent(), text = "", lastY = null;
      content.items.forEach(function (it) {
        if (typeof it.str !== "string") return;
        var y = it.transform ? it.transform[5] : null;
        if (lastY !== null && y !== null && Math.abs(y - lastY) > 2 && text && text.slice(-1) !== "\n") text += "\n";
        text += it.str;
        if (it.hasEOL) text += "\n";
        if (y !== null) lastY = y;
      });
      pages.push(text.split("\n").filter(function (ln) { return !/^\s*\d{1,4}\s*$/.test(ln); }).join("\n"));
    }
    return pages.join("\n");
  }
  async function onFile() {
    var f = fileInput.files && fileInput.files[0];
    if (!f) return;
    fileInput.value = "";
    if (f.size > MAX_MB * 1024 * 1024) return say(t("tooBig"), "bad");
    var ext = (f.name.split(".").pop() || "").toLowerCase();
    say(t("reading"), "info");
    try {
      var text;
      if (ext === "txt" || ext === "md") text = await f.text();
      else if (ext === "docx") text = await CC.docxToText(await f.arrayBuffer());
      else if (ext === "pdf") { try { text = await pdfToText(await f.arrayBuffer()); } catch (e) { return say(t("pdfFail"), "bad"); } if (!text || text.replace(/\s/g, "").length < 200) return say(t("pdfFail"), "bad"); }
      else return say(t("noType"), "bad");
      ta.value = text;
      run();
    } catch (e) { say(t("badFile"), "bad"); }
  }

  // ---------- Çözümleme ----------
  function run() {
    var text = ta.value;
    if (!text || !text.trim()) return say(t("empty"), "bad");
    state.result = CC.analyze(text); state.validated = false; state.tab = "cross";
    say("");
    render();
    out.scrollIntoView({ behavior: "smooth", block: "start" });
  }
  function metric(n, label, tone) { return h("div", { class: "ccx-metric" + (tone ? " ccx-" + tone : "") }, [h("b", { text: String(n) }), h("span", { text: label })]); }
  function isCited(ref) { return state.result.cross.orphans.indexOf(ref) < 0; }
  function isMatched(c) { return !state.result.cross.missing.some(function (m) { return m.key === c.key; }); }

  function render() {
    var r = state.result, x = r.cross;
    clear(out);
    if (!r.refsText) out.appendChild(h("p", { class: "ccx-note ccx-bad", text: t("noRefs") }));
    if (r.numericStyle) out.appendChild(h("p", { class: "ccx-note ccx-warn", text: t("numeric") }));
    out.appendChild(h("div", { class: "ccx-metrics" }, [metric(r.citations.length, t("mCit")), metric(r.references.length, t("mRef")),
      metric(x.missing.length, t("mMiss"), x.missing.length ? "bad" : "ok"), metric(x.orphans.length, t("mOrph"), x.orphans.length ? "warn" : "ok"),
      metric(x.fuzzy.length, t("mFuzzy"), x.fuzzy.length ? "warn" : "ok")]));
    if (r.references.length) out.appendChild(h("div", { class: "ccx-bar ccx-vtop" }, [h("button", { type: "button", class: "ccx-btn ccx-primary", text: t("validate"), disabled: state.busy, onclick: function () { state.tab = "ref"; state.autoValidate = true; render(); } }), h("span", { class: "ccx-sub", text: t("validateNote") })]));
    var tabs = [["cross", t("tCross"), x.missing.length + x.orphans.length + x.fuzzy.length], ["cit", t("tCit"), r.citations.length],
      ["ref", t("tRef"), r.references.length], ["fmt", t("tFmt"), r.format.length]];
    out.appendChild(h("div", { class: "ccx-tabs", role: "tablist" }, tabs.map(function (tb) {
      return h("button", { type: "button", role: "tab", "aria-selected": String(state.tab === tb[0]), onclick: function () { state.tab = tb[0]; render(); } },
        [tb[1] + " ", h("span", { class: "ccx-count", text: String(tb[2]) })]);
    })));
    var panel = h("div", { class: "ccx-panel", role: "tabpanel" });
    ({ cross: panelCross, cit: panelCit, ref: panelRef, fmt: panelFmt })[state.tab](panel);
    out.appendChild(panel);
  }
  function list(title, items, okText, tone, fn) {
    var box = h("div", { class: "ccx-list" }, [h("h3", { text: title + " (" + items.length + ")" })]);
    if (!items.length) box.appendChild(h("p", { class: "ccx-note ccx-ok", text: okText }));
    else box.appendChild(h("ul", {}, items.map(function (it) { return h("li", { class: "ccx-" + tone }, fn(it)); })));
    return box;
  }
  function panelCross(p) {
    var x = state.result.cross;
    p.appendChild(h("div", { class: "ccx-two" }, [
      list(t("hMiss"), x.missing, t("okMiss"), "bad", function (c) { return [h("code", { text: c.raw }), h("small", { text: c.surname + " · " + c.year })]; }),
      list(t("hOrph"), x.orphans, t("okOrph"), "warn", function (r) { return [h("span", { text: r.raw.length > 170 ? r.raw.slice(0, 170) + "…" : r.raw })]; })]));
    if (x.fuzzy.length) {
      var b = list(t("hFuzzy"), x.fuzzy, "", "info", function (f) {
        return [h("code", { text: f.citation.raw }), h("small", { text: "↔ " + t("inRefs") + ": " + f.reference.surname + " (" + f.reference.year + ") · " + t(f.kind) })];
      });
      b.insertBefore(h("p", { class: "ccx-sub", text: t("fuzzyNote") }), b.children[1]);
      p.appendChild(b);
    }
  }
  function table(heads, rows) {
    return h("div", { class: "ccx-scroll" }, [h("table", {}, [h("thead", {}, [h("tr", {}, heads.map(function (x) { return h("th", { scope: "col", text: x }); }))]),
      h("tbody", {}, rows.map(function (cells) { return h("tr", {}, cells.map(function (c) { return typeof c === "string" ? h("td", { text: c }) : h("td", {}, [c]); })); }))])]);
  }
  function download(name, rows) {
    var a = h("a", { href: URL.createObjectURL(new Blob([CC.toCsv(rows)], { type: "text/csv;charset=utf-8" })), download: name });
    document.body.appendChild(a); a.click(); setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 500);
  }
  function pill(text, tone) { return h("span", { class: "ccx-pill ccx-" + tone, text: text }); }
  function panelCit(p) {
    var cs = state.result.citations;
    if (!cs.length) return p.appendChild(h("p", { class: "ccx-note ccx-info", text: t("none") }));
    p.appendChild(h("div", { class: "ccx-bar" }, [h("button", { type: "button", class: "ccx-btn ccx-ghost", text: t("csvCit"), onclick: function () {
      download("citations.csv", [[t("cRaw"), t("cAuth"), t("cYear"), t("cType"), t("cMatch")]].concat(cs.map(function (c) { return [c.raw, c.authors, c.year, c.type, isMatched(c) ? t("yes") : t("no")]; })));
    } })]));
    p.appendChild(table([t("cRaw"), t("cAuth"), t("cYear"), t("cType"), t("cMatch")], cs.map(function (c) {
      return [c.raw, c.authors, c.year, c.type === "narrative" ? t("narr") : t("paren"), isMatched(c) ? pill(t("yes"), "ok") : pill(t("no"), "bad")];
    })));
  }
  var TONE = { verified: "ok", low_confidence: "warn", not_found: "bad", doi_mismatch: "bad", error: "info", unchecked: "info" };
  function panelRef(p) {
    var rs = state.result.references;
    if (!rs.length) return p.appendChild(h("p", { class: "ccx-note ccx-info", text: t("none") }));
    var prog = h("div", { class: "ccx-progress", hidden: true }, [h("div", {})]);
    var vbtn = h("button", { type: "button", class: "ccx-btn ccx-primary", text: t("validate"), disabled: state.busy, onclick: function () { validate(vbtn, prog); } });
    p.appendChild(h("div", { class: "ccx-bar" }, [vbtn, h("button", { type: "button", class: "ccx-btn ccx-ghost", text: t("csvRef"), onclick: function () {
      download("references.csv", [[t("rNo"), t("rRef"), t("rAuth"), t("rYear"), "DOI", t("rCited"), t("rStatus"), t("rFound"), "URL"]].concat(rs.map(function (r) {
        return [r.index, r.raw, r.surname, r.year, r.doi, isCited(r) ? t("yes") : t("no"), t("s_" + r.status), r.match ? r.match.title : "", r.match ? r.match.url : ""];
      })));
    } })]));
    p.appendChild(h("p", { class: "ccx-sub", text: t("validateNote") })); p.appendChild(prog); if (state.autoValidate) { state.autoValidate = false; validate(vbtn, prog); }
    if (state.validated) {
      var n = function (s) { return rs.filter(function (r) { return r.status === s; }).length; };
      p.appendChild(h("div", { class: "ccx-metrics ccx-small" }, [metric(n("verified"), t("vSum"), "ok"), metric(n("low_confidence"), t("vLow"), "warn"),
        metric(n("not_found"), t("vNot"), n("not_found") ? "bad" : "ok"), metric(n("doi_mismatch"), t("vDoi"), n("doi_mismatch") ? "bad" : "ok")].concat(n("error") ? [metric(n("error"), t("vErr"))] : [])));
      if (n("doi_mismatch")) p.appendChild(h("p", { class: "ccx-note ccx-bad", text: t("doiWarn") }));
      if (n("not_found")) p.appendChild(h("p", { class: "ccx-note ccx-info", text: t("notFoundWarn") }));
      if (rs.length > MAX_VALIDATE) p.appendChild(h("p", { class: "ccx-note ccx-info", text: t("capped") }));
    }
    p.appendChild(table([t("rNo"), t("rRef"), t("rAuth"), t("rYear"), t("rCited"), t("rStatus"), t("rFound")], rs.map(function (r) {
      var found = "";
      if (r.match && r.status !== "not_found") found = r.match.url ? h("a", { href: r.match.url, target: "_blank", rel: "noopener", text: (r.match.title || r.match.url).slice(0, 110) }) : (r.match.title || "").slice(0, 110);
      return [String(r.index), r.raw.length > 220 ? r.raw.slice(0, 220) + "…" : r.raw, r.surname || "", r.year || "", isCited(r) ? pill(t("yes"), "ok") : pill(t("no"), "warn"),
        r.status === "unchecked" ? "-" : pill(t("s_" + r.status), TONE[r.status]), found];
    })));
  }
  function panelFmt(p) {
    var fs = state.result.format;
    if (!fs.length) return p.appendChild(h("p", { class: "ccx-note ccx-ok", text: t("okFmt") }));
    p.appendChild(h("ul", { class: "ccx-fmt" }, fs.map(function (f) {
      return h("li", {}, [h("strong", { text: t("f_" + f.code, { a: f.a || "", b: f.b || "" }) }), h("code", { text: f.excerpt })]);
    })));
  }

  // ---------- Veritabanı doğrulaması ----------
  var cache = new Map();
  async function fetchJson(url) {
    if (cache.has(url)) return cache.get(url);
    for (var attempt = 0; attempt < 2; attempt++) {
      var ctl = new AbortController(), timer = setTimeout(function () { ctl.abort(); }, 15000);
      try {
        var res = await fetch(url, { signal: ctl.signal, headers: { Accept: "application/json" } });
        clearTimeout(timer);
        if ((res.status === 429 || res.status >= 500) && attempt === 0) { await new Promise(function (ok) { setTimeout(ok, 1500); }); continue; }
        var out2 = { status: res.status, data: res.ok ? await res.json() : null };
        if (res.ok || res.status === 404) cache.set(url, out2);
        return out2;
      } catch (e) { clearTimeout(timer); if (attempt === 1) throw e; }
    }
    throw new Error("net");
  }
  async function validate(btn, prog) {
    if (state.busy) return;
    state.busy = true; btn.disabled = true; prog.hidden = false;
    var rs = state.result.references.slice(0, MAX_VALIDATE), bar = prog.firstChild, label = t("validating");
    try {
      await CC.validateAll(rs, fetchJson, function (d, n) { bar.style.width = Math.round(100 * d / n) + "%"; btn.textContent = label + " " + d + " / " + n; }, 4);
    } finally { state.busy = false; state.validated = true; if (state.tab === "ref") render(); }
  }

  build();
})();
