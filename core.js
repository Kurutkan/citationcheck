/* citationcheck: tarayıcı çekirdeği (DOM kullanmaz; Node ile test edilebilir).
   Python sürümündeki src/extractors.py, names.py, cross_check.py, parsers.py ve
   validators.py mantığının JavaScript karşılığıdır. */
var CitationCheck = (function () {
  "use strict";

  // ---------- Harf sınıfları ve yapı taşları ----------
  var U = "\\p{Lu}", L = "\\p{Ll}";
  var APOS = "['\\u2019\\u2018\\u02BC\\u02B9]";
  var WB0 = "(?<![\\p{L}\\p{N}_])", WB1 = "(?![\\p{L}\\p{N}_])";
  var PREFIX_LOWER = "(?:van|von|vom|zu|zum|zur|der|den|het|ten|ter|te|" +
    "de|del|della|dello|dei|degli|delle|di|da|das|do|dos|du|des|" +
    "le|la|las|los|lo|el|al|bin|ibn|ben|af|av|of)";
  var PREFIXES = "(?:" + PREFIX_LOWER + "\\s+){1,3}";
  var HYPH = "\\-\\u2010\\u2011";
  var CORE_PREFIX = "(?:Mc|Mac|[DdOoLlNnMm]" + APOS + "|al[" + HYPH + "]|el[" + HYPH + "])";
  var AUTHOR_CORE = CORE_PREFIX + "?" + U + L + "+(?:" + U + L + "+)?";
  var AUTHOR_PART = "(?:" + PREFIXES + ")?" + AUTHOR_CORE;
  var AUTHOR = AUTHOR_PART + "(?:[\\s" + HYPH + "]" + AUTHOR_PART + "){0,4}";
  var AUTHOR_STRICT = AUTHOR_CORE + "(?:[\\s" + HYPH + "](?:" + PREFIXES + ")?" + AUTHOR_CORE + "){0,4}";
  var ACRONYM = U + "{2,8}";
  var ORG_MULTI = U + L + "+(?:\\s+(?:" + PREFIXES + ")?" + U + L + "+){1,4}";
  var ORG = "(?:" + ACRONYM + "|" + ORG_MULTI + ")";
  var NAME_OR_ORG = "(?:" + AUTHOR + "|" + ORG + ")";
  var ETAL = "(?:et\\s*al\\.?|vd\\.?|ve\\s*ark\\.?|ve\\s*diğerleri)";
  var CONJ = "(?:&|" + ["and", "ve", "y", "e", "et", "und"].map(function (w) { return WB0 + w + WB1; }).join("|") + ")";
  var POSSESSIVE = "(?:" + APOS + L + "+)?";
  var AUTHORS_PAREN = "(?:" + NAME_OR_ORG + "(?:\\s*,\\s*" + NAME_OR_ORG + "){0,15}" +
    "(?:\\s*,?\\s*" + CONJ + "\\s*" + NAME_OR_ORG + ")?(?:\\s*,?\\s*" + ETAL + ")?)";
  var AUTHORS_NARR = "(?:" + AUTHOR_STRICT + POSSESSIVE + "(?:\\s*,\\s*" + AUTHOR_STRICT + ")*" +
    "(?:\\s*" + CONJ + "\\s*" + AUTHOR_STRICT + ")?(?:\\s+" + ETAL + ")?|" + ORG + ")";
  var YEAR = "(?:\\d{4}[a-z]?|n\\.\\s?d\\.|t\\.\\s?y\\.|in\\s+press|baskıda|basımda|yayımlanmak\\s+üzere)";
  var PAGE = "(?:\\s*,\\s*(?:p\\.|pp\\.|s\\.|ss\\.|para\\.|paras\\.)\\s*[\\d\\-\\u2013,\\s]+)?";

  var NARRATIVE = new RegExp("(?<![\\p{L}])(?<authors>" + AUTHORS_NARR + ")\\s*\\((?<year>" + YEAR + ")" + PAGE + "\\)", "gu");
  var MULTI_INNER = new RegExp("(?<authors>" + AUTHORS_PAREN + ")\\s*,\\s*(?<year>" + YEAR + ")", "u");
  var PAREN_BLOCK = new RegExp("\\(([^()]*(?:" + WB0 + "\\d{4}[a-z]?" + WB1 +
    "|n\\.\\s?d\\.|t\\.\\s?y\\.|in\\s+press|baskıda|basımda)[^()]*)\\)", "gu");
  var SECONDARY = new RegExp(WB0 + "(?:as\\s+cited\\s+in|cited\\s+in|as\\s+quoted\\s+in|akt(?:aran)?\\s*[.:]?|" +
    "citado\\s+(?:en|em|por)|apud|cité\\s+(?:par|dans)|zitiert\\s+nach)\\s+", "giu");
  var NUMERIC = /\[\d{1,3}(?:\s*[,\-\u{2013}]\s*\d{1,3})*\]/gu;
  var DOI_RE = /10\.\d{4,9}\/[^\s,;]+/i;
  var YEAR_IN_PARENS = new RegExp("\\((" + YEAR + ")(?:\\s*,[^()]{0,40})?\\)", "iu");
  var YEAR_BARE = /(?<!\d)(?:19|20)\d{2}[a-z]?(?![\p{L}\d])/u;
  var ETAL_RE = new RegExp(ETAL, "gu");
  var ETAL_TEST = new RegExp(ETAL, "iu");
  var POSS_RE = new RegExp(APOS + "(?:ın|in|un|ün|nın|nin|nun|nün|a|e|ya|ye|da|de|ta|te|den|dan|ki|s)" + WB1, "gu");
  var FIRST_SPLIT = new RegExp("\\s+" + CONJ + "\\s+|\\s*,\\s*", "u");
  var APOS_G = new RegExp(APOS, "gu");

  var NON_AUTHOR = new Set(("Birincisi İkincisi Üçüncüsü Dördüncüsü Beşincisi Altıncısı Yedincisi Sekizincisi " +
    "Ayrıca Ancak Fakat Lakin Yani Çünkü Öyleyse Örneğin Mesela Şekil Tablo Bölüm Kısım Madde " +
    "Figure Table Section Chapter Part Appendix Bu Şu Bunun Şunun Bunlar Şunlar Sonuç Sonuçta Özet Genel " +
    "Nitekim Dolayısıyla Böylece Özellikle Benzer Oysa Sonra Önce Daha Diğer Yine Hatta Zira Buna " +
    "Öte Aynı Bununla Halbuki Kısaca Özetle Bkz Örn " +
    "However Moreover Furthermore Additionally Similarly Likewise Thus Therefore Hence Also Indeed Notably " +
    "Recently Later Earlier Subsequently Conversely Meanwhile While Although Whereas Since Because Both See " +
    "Following Unlike Like Then Yet Still Finally First Second Third In As And But Per Cf").split(" "));

  // ---------- Soyad normalizasyonu (names.py) ----------
  var SPECIAL = { "ı": "i", "İ": "i", "ß": "ss", "ø": "o", "Ø": "o", "ł": "l", "Ł": "l", "đ": "d", "Đ": "d",
    "ð": "d", "Ð": "d", "þ": "th", "Þ": "th", "æ": "ae", "Æ": "ae", "œ": "oe", "Œ": "oe", "ħ": "h", "Ħ": "h" };
  var PARTICLES = new Set(("de del della dello dei degli delle di da das do dos du des d la le les lo los las l y e i " +
    "van von vom zu zum zur der den het ten ter te af av of al el bin ibn ben bint abu ebu").split(" "));

  function fold(text) {
    if (!text) return "";
    var s = "";
    for (var ch of text) s += (SPECIAL[ch] !== undefined ? SPECIAL[ch] : ch);
    return s.normalize("NFKD").replace(/\p{M}/gu, "").toLowerCase();
  }
  function allTokens(surname) {
    var s = fold(surname);
    s = s.replace(/(?<![a-z0-9])([dl])['\u{2019}\u{2018}\u{2BC}\u{2B9}`\xB4]/gu, "$1 ");
    s = s.replace(/['\u{2019}\u{2018}\u{2BC}\u{2B9}`\xB4]/gu, "");
    return s.split(/[\s\-\u{2010}-\u{2014}.,]+/u).filter(Boolean);
  }
  function surnameTokens(surname) {
    var toks = allTokens(surname);
    var core = toks.filter(function (t) { return !PARTICLES.has(t); });
    return core.length ? core : toks;
  }
  function editLe1(a, b) {
    if (a === b) return true;
    if (Math.abs(a.length - b.length) > 1) return false;
    if (a.length > b.length) { var t = a; a = b; b = t; }
    var i = 0, j = 0, diff = 0;
    while (i < a.length && j < b.length) {
      if (a[i] === b[j]) { i++; j++; continue; }
      if (++diff > 1) return false;
      if (a.length === b.length) i++;
      j++;
    }
    return true;
  }
  function matchSurnames(a, b) {
    if (!a || !b) return null;
    var ta = surnameTokens(a), tb = surnameTokens(b);
    if (!ta.length || !tb.length) return null;
    if (ta.join(" ") === tb.join(" ")) return "exact";
    var sa = new Set(ta), sb = new Set(tb);
    var aInB = ta.every(function (t) { return sb.has(t); }), bInA = tb.every(function (t) { return sa.has(t); });
    if (aInB || bInA) return "variant";
    if (allTokens(a).join("") === allTokens(b).join("") || ta.join("") === tb.join("")) return "variant";
    var ca = ta.join(""), cb = tb.join("");
    if (Math.min(ca.length, cb.length) >= 5 && editLe1(ca, cb)) return "typo";
    if (ta.length === tb.length && ta.length > 1) {
      var diffs = [];
      for (var i = 0; i < ta.length; i++) if (ta[i] !== tb[i]) diffs.push([ta[i], tb[i]]);
      if (diffs.length === 1 && Math.min(diffs[0][0].length, diffs[0][1].length) >= 5 && editLe1(diffs[0][0], diffs[0][1])) return "typo";
    }
    return null;
  }
  function sortKey(surname) { return allTokens(surname || "").join(""); }

  // ---------- Metin hazırlığı ----------
  function normalizeWhitespace(text) {
    text = text.replace(/\r\n?/g, "\n").replace(/\xAD/g, "").replace(/[^\S\r\n\t]/g, " ");
    text = text.replace(/(\p{L})-\n(\p{L})/gu, "$1$2");
    text = text.replace(/(?<=[\p{Ll},])\n(?=\p{Ll})/gu, " ");
    return text;
  }

  var HEADING = new RegExp("^[\\s*#>0-9.)\\-]*(references?|reference\\s*list|works\\s+cited|bibliography|" +
    "kaynak(?:ça|ca|lar)|kaynaklar\\s*ve\\s*ek(?:ler)?|referencias(?:\\s+bibliogr[aá]ficas)?|" +
    "refer[eê]ncias(?:\\s+bibliogr[aá]ficas)?|bibliograf[ií]a|obras\\s+citadas|" +
    "r[eé]f[eé]rences(?:\\s+bibliographiques)?|bibliographie|riferimenti(?:\\s+bibliografici)?|" +
    "literatur(?:verzeichnis)?)[ \\t]*[:.]?[ \\t]*$", "gimu");

  function splitBodyAndReferences(text) {
    if (!text) return { body: "", refs: "" };
    text = text.replace(/\r\n?/g, "\n");
    var last = null, m;
    HEADING.lastIndex = 0;
    while ((m = HEADING.exec(text)) !== null) { last = m; if (m[0].length === 0) HEADING.lastIndex++; }
    if (!last) return { body: text, refs: "" };
    return { body: text.slice(0, last.index).replace(/\s+$/, ""), refs: text.slice(last.index + last[0].length).replace(/^\s+/, "") };
  }

  // ---------- Atıf çıkarımı ----------
  function citationSurname(authors) {
    var cleaned = authors.replace(ETAL_RE, "").trim().replace(POSS_RE, "");
    return cleaned.split(FIRST_SPLIT)[0].trim();
  }
  function makeCitation(raw, authors, year, type, position) {
    var surname = citationSurname(authors);
    return { raw: raw, authors: authors, year: year.replace(/\s+/g, " "), type: type, position: position,
      surname: surname, key: surname.replace(APOS_G, "'").toLowerCase() + "|" + year };
  }
  var STARTS_NAME = new RegExp("^(?:" + U + "|" + CORE_PREFIX + ")", "u");

  function extractCitations(body) {
    body = normalizeWhitespace(body || "");
    var out = [], spans = [], block, m;
    PAREN_BLOCK.lastIndex = 0;
    while ((block = PAREN_BLOCK.exec(body)) !== null) {
      var inner = block[1];
      spans.push([block.index, block.index + block[0].length]);
      var sec = null, s;
      SECONDARY.lastIndex = 0;
      while ((s = SECONDARY.exec(inner)) !== null) sec = s;
      if (sec) inner = inner.slice(sec.index + sec[0].length);
      var parts = inner.split(/\s*;\s*/);
      for (var p = 0; p < parts.length; p++) {
        var part = parts[p].trim();
        var im = MULTI_INNER.exec(part);
        if (!im) continue;
        out.push(makeCitation(parts.length > 1 ? "(" + part + ")" : block[0], im.groups.authors.trim(), im.groups.year, "parenthetical", block.index));
      }
    }
    NARRATIVE.lastIndex = 0;
    while ((m = NARRATIVE.exec(body)) !== null) {
      var start = m.index;
      if (spans.some(function (sp) { return sp[0] <= start && start < sp[1]; })) continue;
      if (start > 0 && body[start - 1] === "(") continue;
      var authors = m.groups.authors.trim();
      for (;;) {
        var mm = /^([^\s,]+)[\s,]*([\s\S]*)$/.exec(authors);
        if (!mm || !NON_AUTHOR.has(mm[1])) break;
        authors = mm[2].trim();
        if (!authors) break;
      }
      if (!authors || !STARTS_NAME.test(authors)) continue;
      out.push(makeCitation(m[0], authors, m.groups.year, "narrative", start));
    }
    out.sort(function (a, b) { return a.position - b.position; });
    return out;
  }

  function detectNumericStyle(body, authorDateCount) {
    var n = ((body || "").match(NUMERIC) || []).length;
    return n >= 5 && n > 2 * (authorDateCount || 0);
  }

  // ---------- Kaynakça ----------
  var WORD = CORE_PREFIX + "?" + U + "[" + L + U + HYPH + "]*" + APOS + "?[" + L + U + HYPH + "]+";
  var AUTHOR_START = "(?:" + PREFIXES + ")?" + WORD + "(?:\\s+(?:(?:" + PREFIXES + ")|(?:[ye]\\s+))?" + WORD + "){0,4}\\s*,\\s*" + U + "\\.";
  var ORG_START = ACRONYM + "(?:\\s*[,(&]|\\s+" + U + ")";
  var ENTRY_SPLIT = new RegExp("\\n(?=" + AUTHOR_START + "|" + ORG_START + ")", "u");
  var LINE_YEAR = /\(\d{4}[a-z]?\)|\((?:n\.d\.|t\.y\.)\)/;
  var ANY_YEAR = /\(\d{4}[a-z]?\)|(?<![\p{L}\d])(?:19|20)\d{2}(?![\p{L}\d])/u;
  var REF_APA = new RegExp("^((?:" + PREFIXES + ")?" + AUTHOR_CORE + "(?:[\\s" + HYPH + "](?:(?:" + PREFIXES + ")|(?:[ye]\\s+))?" +
    AUTHOR_CORE + "){0,4})\\s*,\\s*" + U + "\\.", "u");
  var REF_ORG = new RegExp("^(" + ORG + ")(?:\\s*[,(.]|\\s*$)", "u");

  function splitReferenceEntries(refsText) {
    refsText = (refsText || "").replace(/\r\n?/g, "\n").trim();
    if (!refsText) return [];
    var blocks = refsText.split(/\n\s*\n/);
    var rawLines = refsText.split("\n").map(function (l) { return l.trim(); }).filter(function (l) { return l.length > 20; });
    var candidates;
    var clean = function (x) { return x.replace(/\n/g, " ").trim(); };
    if (blocks.length > 3) {
      candidates = blocks.filter(function (b) { return b.trim().length > 20; }).map(clean);
    } else if (rawLines.length >= 2 && rawLines.filter(function (l) { return LINE_YEAR.test(l.slice(0, 300)); }).length >= 0.85 * rawLines.length) {
      candidates = rawLines;
    } else {
      candidates = refsText.split(ENTRY_SPLIT).filter(function (l) { return l.trim().length > 20; }).map(clean);
    }
    var merged = [];
    candidates.forEach(function (c) {
      if (!ANY_YEAR.test(c) && merged.length) merged[merged.length - 1] += " " + c; else merged.push(c);
    });
    return merged;
  }

  function referenceSurname(authorsRaw) {
    if (!authorsRaw) return null;
    var first = authorsRaw.trim().split(/\s*&\s*|\s+and\s+|\s+ve\s+|;/)[0].trim().replace(/[,. ]+$/, "").trim();
    var m = REF_APA.exec(first);
    if (m) return m[1].trim();
    m = REF_ORG.exec(first);
    if (m) return m[1].trim();
    return first.split(",")[0].replace(/^[ .]+|[ .]+$/g, "");
  }

  function extractReferences(refsText) {
    return splitReferenceEntries(refsText).map(function (entry, idx) {
      var ref = { index: idx + 1, raw: entry, authorsRaw: null, year: null, title: null, doi: null, surname: null,
        status: "unchecked", score: 0, match: null, provider: null };
      var d = DOI_RE.exec(entry);
      if (d) ref.doi = d[0].replace(/[.,;)\]]+$/, "");
      var ym = YEAR_IN_PARENS.exec(entry);
      if (ym) {
        ref.year = ym[1].replace(/\s+/g, " ");
        ref.authorsRaw = entry.slice(0, ym.index).trim().replace(/[.,]+$/, "");
        var after = entry.slice(ym.index + ym[0].length).trim().replace(/^\.+/, "").trim();
        var tm = /^([^.]+)\./.exec(after);
        if (tm) ref.title = tm[1].trim();
      } else {
        var y2 = YEAR_BARE.exec(entry);
        if (y2) { ref.year = y2[0]; ref.authorsRaw = entry.slice(0, y2.index).trim().replace(/[.,]+$/, ""); }
      }
      ref.surname = referenceSurname(ref.authorsRaw);
      if (!ref.surname && ref.year) {
        var fm = new RegExp(U + L + "+", "u").exec(entry);
        ref.surname = fm ? fm[0] : null;
      }
      return ref;
    });
  }

  // ---------- Çapraz kontrol ----------
  var YEAR_ALIASES = { "t.y.": "n.d.", "t. y.": "n.d.", "n. d.": "n.d.", "baskıda": "in press", "basımda": "in press", "yayımlanmak üzere": "in press" };
  function normYear(y) { y = (y || "").trim().toLowerCase().replace(/\s+/g, " "); return YEAR_ALIASES[y] || y; }
  function yearBase(y) { y = normYear(y); return /^\d{4}/.test(y) ? y.slice(0, 4) : y; }

  function crossCheck(citations, references) {
    var cited = new Set(), missing = [], fuzzy = [], matchedKeys = new Set(), seen = new Set(), seenFuzzy = new Set();
    citations.forEach(function (cit) {
      if (!cit.key) return;
      var hits = { exact: [], variant: [], typo: [] };
      references.forEach(function (ref, idx) {
        if (!ref.surname || !ref.year) return;
        var level;
        if (normYear(ref.year) !== normYear(cit.year)) {
          if (yearBase(ref.year) !== yearBase(cit.year)) return;
          level = matchSurnames(cit.surname, ref.surname);
          if (level) hits[level === "exact" ? "variant" : level].push(idx);
          return;
        }
        level = matchSurnames(cit.surname, ref.surname);
        if (level) hits[level].push(idx);
      });
      var chosen = hits.exact.length ? "exact" : hits.variant.length ? "variant" : hits.typo.length ? "typo" : null;
      if (!chosen) { if (!seen.has(cit.key)) { missing.push(cit); seen.add(cit.key); } return; }
      seen.add(cit.key); matchedKeys.add(cit.key);
      hits[chosen].forEach(function (idx) {
        cited.add(idx);
        if (chosen !== "exact") {
          var fk = cit.key + "#" + idx;
          if (!seenFuzzy.has(fk)) { seenFuzzy.add(fk); fuzzy.push({ citation: cit, reference: references[idx], kind: chosen }); }
        }
      });
    });
    var orphans = references.filter(function (ref, idx) { return ref.surname && ref.year && !cited.has(idx); });
    return { missing: missing, orphans: orphans, matchedCount: matchedKeys.size, fuzzy: fuzzy };
  }

  // ---------- APA biçim denetimleri ----------
  var COUNT_SPLIT = /\s*,\s*(?:(?:&|and|ve|y|e|et|und)\s+)?|\s+(?:&|and|ve|y|e|et|und)\s+/u;
  function countAuthors(authors) {
    return authors.replace(ETAL_RE, "").split(COUNT_SPLIT).filter(function (p) { return p && /[\p{L}\p{N}]/u.test(p); }).length;
  }
  function checkFormat(citations, references) {
    var issues = [], seenEtal = new Set();
    citations.forEach(function (c) {
      if (countAuthors(c.authors) >= 3 && !ETAL_TEST.test(c.authors) && !seenEtal.has(c.raw)) {
        seenEtal.add(c.raw);
        issues.push({ code: "etal", excerpt: c.raw, a: c.surname, b: c.year });
      }
    });
    for (var i = 1; i < references.length; i++) {
      var prev = sortKey(references[i - 1].surname), cur = sortKey(references[i].surname);
      if (prev && cur && prev > cur) issues.push({ code: "alpha", excerpt: references[i].raw.slice(0, 120), a: references[i].surname, b: references[i - 1].surname });
    }
    var seenRef = new Map();
    references.forEach(function (r) {
      if (/\bdoi:\s*10\.\d/i.test(r.raw) || /https?:\/\/dx\.doi\.org\//i.test(r.raw) || (r.doi && !/https?:\/\/doi\.org\/10\./i.test(r.raw)))
        issues.push({ code: "doi", excerpt: r.raw.slice(0, 120), a: r.doi || "" });
      if (!r.year) issues.push({ code: "noyear", excerpt: r.raw.slice(0, 120) });
      if (r.surname && r.year) {
        var k = surnameTokens(r.surname).join(" ") + "|" + normYear(r.year) + "|" + fold(r.title || "").slice(0, 40);
        if (seenRef.has(k)) issues.push({ code: "dup", excerpt: r.raw.slice(0, 120), a: String(seenRef.get(k)), b: String(r.index) });
        else seenRef.set(k, r.index);
      }
    });
    return issues;
  }

  // ---------- Veritabanı doğrulaması ----------
  var STOP = new Set(("the a an of and in on for to with by from at as is are its ve ile bir bu icin de da olarak uzerine " +
    "el la los las del y en un una e o do dos das um uma em le les des du et une der die das und").split(" "));
  function words(text) { return fold(text || "").match(/[a-z0-9]+/g) || []; }
  function titleCoverage(ref, cand) {
    var cw = words(cand.title).filter(function (w) { return !STOP.has(w) && w.length > 2; });
    if (cw.length < 2) return null;
    var rw = new Set(words(ref.raw));
    return cw.filter(function (w) { return rw.has(w); }).length / cw.length;
  }
  function firstAuthorPresent(ref, cand) {
    var authors = cand.authors || [];
    if (!authors.length) return null;
    var first = authors[0], parts = first.trim().split(/\s+/);
    var surname = first.indexOf(",") >= 0 ? first.split(",")[0] : parts[parts.length - 1] || "";
    var toks = surnameTokens(surname);
    if (!toks.length) return null;
    var rw = new Set(words(ref.raw));
    return toks.some(function (t) { return rw.has(t); });
  }
  function doiRecordMatches(ref, cand) {
    var cov = titleCoverage(ref, cand), au = firstAuthorPresent(ref, cand);
    if (cov === null) return au !== false;
    if (cov >= 0.6) return true;
    return cov >= 0.4 && au === true;
  }
  function scoreCandidate(ref, cand) {
    var cov = titleCoverage(ref, cand), au = firstAuthorPresent(ref, cand);
    var yearOk = !ref.year || !cand.year || ref.year.slice(0, 4) === String(cand.year).slice(0, 4);
    var score = 100 * (0.7 * (cov === null ? 0.5 : cov) + 0.18 * (au === false ? 0 : 1) + 0.12 * (yearOk ? 1 : 0));
    var status = "not_found";
    if (cov !== null && cov >= 0.8 && au !== false && yearOk) status = "verified";
    else if (cov !== null && cov >= 0.5 && (au !== false || yearOk)) status = "low_confidence";
    else if (cov === null && au === true && yearOk) status = "low_confidence";
    return { score: Math.round(score * 10) / 10, status: status };
  }
  function cleanDoi(doi) {
    return (doi || "").trim().replace(/^(?:https?:\/\/(?:dx\.)?doi\.org\/|doi:\s*)/i, "").replace(/[.,;)\]]+$/, "");
  }
  function normCrossref(it) {
    var pub = it.published || it["published-print"] || it["published-online"] || it.issued || {};
    var dp = (pub["date-parts"] || [[]])[0] || [];
    return { title: (it.title || [""])[0] || "", year: dp[0] ? String(dp[0]) : null, doi: it.DOI || null,
      container: (it["container-title"] || [null])[0], source: "crossref",
      authors: (it.author || []).filter(function (a) { return a.family; }).map(function (a) { return a.family + (a.given ? ", " + a.given : ""); }),
      url: it.URL || (it.DOI ? "https://doi.org/" + it.DOI : null) };
  }
  function normOpenAlex(it) {
    var doi = it.doi || null;
    return { title: it.title || it.display_name || "", year: it.publication_year ? String(it.publication_year) : null,
      doi: doi ? doi.replace(/^https?:\/\/doi\.org\//i, "") : null, source: "openalex",
      container: (((it.primary_location || {}).source) || {}).display_name || null,
      authors: (it.authorships || []).map(function (a) { return (a.author || {}).display_name; }).filter(Boolean), url: doi || it.id || null };
  }

  /* fetchJson(url) -> Promise<{status:number, data:object|null}>; ağ hatasında reddeder. */
  async function validateReference(ref, fetchJson) {
    var best = null, errors = 0, mismatch = null;
    var consider = function (cand, provider) {
      var r = scoreCandidate(ref, cand);
      if (!best || r.score > best.score) best = { status: r.status, score: r.score, match: cand, provider: provider };
    };
    if (ref.doi) {
      try {
        var res = await fetchJson("https://api.crossref.org/works/" + encodeURIComponent(cleanDoi(ref.doi)).replace(/%2F/gi, "/"));
        if (res.status === 200 && res.data && res.data.message) {
          var c = normCrossref(res.data.message);
          if (doiRecordMatches(ref, c)) return { status: "verified", score: 100, match: c, provider: "crossref" };
          mismatch = { status: "doi_mismatch", score: scoreCandidate(ref, c).score, match: c, provider: "crossref" };
        } else if (res.status === 404) {
          ref.doiUnresolved = true;
        }
      } catch (e) { errors++; }
    }
    var q = encodeURIComponent(ref.raw.slice(0, 400));
    var providers = [
      ["crossref", "https://api.crossref.org/works?rows=3&select=title,author,published,issued,container-title,DOI,URL&query.bibliographic=" + q,
        function (d) { return ((d.message || {}).items || []).map(normCrossref); }],
      ["openalex", "https://api.openalex.org/works?per_page=3&search=" + encodeURIComponent(((ref.title || ref.raw).replace(/[^\p{L}\p{N}\s]/gu, " ")).slice(0, 250)),
        function (d) { return (d.results || []).map(normOpenAlex); }]
    ];
    for (var i = 0; i < providers.length; i++) {
      try {
        var r2 = await fetchJson(providers[i][1]);
        if (r2.status !== 200 || !r2.data) { if (r2.status !== 404) errors++; continue; }
        providers[i][2](r2.data).forEach(function (cand) { consider(cand, providers[i][0]); });
        if (best && best.status === "verified") break;
      } catch (e) { errors++; }
    }
    if (best && best.status === "verified") return best;       // DOI yanlış yazılmış, kaynak gerçek
    if (mismatch) return mismatch;
    if (best && best.status !== "not_found") return best;
    if (errors >= providers.length) return { status: "error", score: 0, match: null, provider: null };
    return { status: "not_found", score: best ? best.score : 0, match: best ? best.match : null, provider: null };
  }

  async function validateAll(references, fetchJson, onProgress, concurrency) {
    var next = 0, done = 0, total = references.length;
    async function worker() {
      while (next < total) {
        var ref = references[next++];
        var r;
        try { r = await validateReference(ref, fetchJson); } catch (e) { r = { status: "error", score: 0, match: null, provider: null }; }
        ref.status = r.status; ref.score = r.score; ref.match = r.match; ref.provider = r.provider;
        done++;
        if (onProgress) onProgress(done, total);
      }
    }
    var ws = [];
    for (var i = 0; i < Math.min(concurrency || 4, total); i++) ws.push(worker());
    await Promise.all(ws);
    return references;
  }

  function analyze(text) {
    var parts = splitBodyAndReferences(text);
    var citations = extractCitations(parts.body);
    var references = extractReferences(parts.refs);
    return { body: parts.body, refsText: parts.refs, citations: citations, references: references,
      cross: crossCheck(citations, references), format: checkFormat(citations, references),
      numericStyle: detectNumericStyle(parts.body, citations.length) };
  }

  function toCsv(rows) {
    return String.fromCharCode(0xFEFF) + rows.map(function (r) {
      return r.map(function (v) { v = v === null || v === undefined ? "" : String(v); return /[",\n;]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v; }).join(",");
    }).join("\r\n");
  }

  return { fold: fold, surnameTokens: surnameTokens, matchSurnames: matchSurnames, sortKey: sortKey,
    splitBodyAndReferences: splitBodyAndReferences, extractCitations: extractCitations, extractReferences: extractReferences,
    crossCheck: crossCheck, checkFormat: checkFormat, countAuthors: countAuthors, detectNumericStyle: detectNumericStyle,
    titleCoverage: titleCoverage, firstAuthorPresent: firstAuthorPresent, doiRecordMatches: doiRecordMatches,
    scoreCandidate: scoreCandidate, validateReference: validateReference, validateAll: validateAll, cleanDoi: cleanDoi,
    analyze: analyze, toCsv: toCsv };
})();

/* ---------- Dosya okuma (DOCX: harici kütüphane gerekmez) ---------- */
CitationCheck.docxXmlToText = function (xml) {
  "use strict";
  var out = [], re = /<w:p[\s>][\s\S]*?<\/w:p>/g, m;
  var decode = function (s) {
    // Not: kaynakta HTML varlığı (entity) yazılmaz; x26 = "ve" işareti. WordPress'in
    // kaydederken yaptığı karakter dönüşümlerinden etkilenmemek için.
    return s.replace(/\x26lt;/g, "<").replace(/\x26gt;/g, ">").replace(/\x26quot;/g, '"').replace(/\x26apos;/g, "'")
      .replace(/\x26#(\d+);/g, function (_, n) { return String.fromCodePoint(+n); })
      .replace(/\x26#x([0-9a-f]+);/gi, function (_, n) { return String.fromCodePoint(parseInt(n, 16)); }).replace(/\x26amp;/g, "\x26");
  };
  while ((m = re.exec(xml)) !== null) {
    var t = "", tok, tre = /<w:t(?:\s[^>]*)?>([\s\S]*?)<\/w:t>|<w:tab\s*\/>|<w:br\s*\/>|<w:cr\s*\/>|<w:noBreakHyphen\s*\/>/g;
    while ((tok = tre.exec(m[0])) !== null) {
      if (tok[1] !== undefined) t += decode(tok[1]);
      else if (tok[0].indexOf("w:tab") > 0) t += "\t";
      else if (tok[0].indexOf("Hyphen") > 0) t += "-";
      else t += " ";
    }
    t = t.trim();
    if (t) out.push(t);
  }
  return out;
};

CitationCheck.readZipEntries = async function (buffer, wanted) {
  "use strict";
  var dv = new DataView(buffer), u8 = new Uint8Array(buffer), n = u8.length, eocd = -1;
  for (var i = n - 22; i >= Math.max(0, n - 65557); i--) if (dv.getUint32(i, true) === 0x06054b50) { eocd = i; break; }
  if (eocd < 0) throw new Error("zip");
  var count = dv.getUint16(eocd + 10, true), off = dv.getUint32(eocd + 16, true), res = {}, td = new TextDecoder("utf-8");
  for (var k = 0; k < count; k++) {
    if (dv.getUint32(off, true) !== 0x02014b50) break;
    var method = dv.getUint16(off + 10, true), csize = dv.getUint32(off + 20, true);
    var nl = dv.getUint16(off + 28, true), el = dv.getUint16(off + 30, true), cl = dv.getUint16(off + 32, true), lho = dv.getUint32(off + 42, true);
    var name = td.decode(u8.subarray(off + 46, off + 46 + nl));
    if (wanted.indexOf(name) >= 0) {
      var lnl = dv.getUint16(lho + 26, true), lel = dv.getUint16(lho + 28, true), start = lho + 30 + lnl + lel;
      var data = u8.subarray(start, start + csize);
      if (method === 8) {
        var stream = new Blob([data]).stream().pipeThrough(new DecompressionStream("deflate-raw"));
        data = new Uint8Array(await new Response(stream).arrayBuffer());
      } else if (method !== 0) throw new Error("zip-method");
      res[name] = td.decode(data);
    }
    off += 46 + nl + el + cl;
  }
  return res;
};

CitationCheck.docxToText = async function (buffer) {
  "use strict";
  var files = await CitationCheck.readZipEntries(buffer, ["word/document.xml", "word/footnotes.xml", "word/endnotes.xml"]);
  if (!files["word/document.xml"]) throw new Error("docx");
  var lines = CitationCheck.docxXmlToText(files["word/document.xml"]), notes = [];
  ["word/footnotes.xml", "word/endnotes.xml"].forEach(function (f) { if (files[f]) notes = notes.concat(CitationCheck.docxXmlToText(files[f])); });
  if (notes.length) {
    var at = -1;
    for (var i = lines.length - 1; i >= 0; i--) if (CitationCheck.splitBodyAndReferences("x\n" + lines[i] + "\ny").refs === "y") { at = i; break; }
    if (at < 0) lines = lines.concat(notes); else lines = lines.slice(0, at).concat(notes, lines.slice(at));
  }
  return lines.join("\n");
};
