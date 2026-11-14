"""web/ kaynaklarından iki çıktı üretir:
  citationcheck.html      : tek dosyalık, bağımsız sayfa (yerelde ya da herhangi bir sunucuda açılır)
  wordpress-blocks.html   : healthtopic.org sayfasına konacak Gutenberg "Özel HTML" blokları
Kullanım: python web/build.py"""
import pathlib, re
here = pathlib.Path(__file__).resolve().parent
css = (here / "style.css").read_text(encoding="utf-8").strip()
js = (here / "core.js").read_text(encoding="utf-8") + "\n" + (here / "ui.js").read_text(encoding="utf-8")
assert "</script" not in js.lower()
import re as _re
assert not _re.search(r"&(?:#\d+|#x[0-9a-fA-F]+|[a-zA-Z]+);", js), "kaynakta HTML varlığı olmamalı"

standalone = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Citation and Reference Checker | citationcheck</title>
<style>body{{margin:0;padding:24px 12px;background:#E3EAF5}}
{css}</style>
</head>
<body>
<div id="ccx"><noscript>Bu araç JavaScript gerektirir.</noscript></div>
<script>
{js}
</script>
</body>
</html>
"""
(here / "citationcheck.html").write_text(standalone, encoding="utf-8")

# WordPress: "&" karakteri kaydedilirken "&#038;" olabildiği için kaynak, düz metin
# parçaları halinde saklanır ve küçük bir yükleyici tarafından birleştirilip çalıştırılır.
# (healthtopic.org'daki diğer etkileşimli modüllerle aynı yöntem.)
# Sayfa boyutunu küçültmek için: satır başı boşlukları, boş satırlar ve satır başında
# başlayan yorumlar atılır (kodda çok satırlı dizgi yoktur, bu yüzden güvenlidir).
slim = re.sub(r"(?m)^[ \t]*/\*[\s\S]*?\*/[ \t]*\n", "", js)
slim = "\n".join(l.strip() for l in slim.split("\n") if l.strip() and not l.strip().startswith("//"))
chunks, cur = [], ""
for line in slim.split("\n"):
    if len(cur) + len(line) > 11000 and cur:
        chunks.append(cur); cur = ""
    cur += line + "\n"
if cur: chunks.append(cur)
assert "".join(chunks) == slim + "\n"
parts = [f'<!-- wp:html -->\n<style>\n{css}\n</style>\n<div id="ccx"><noscript>Bu araç JavaScript gerektirir. This tool needs JavaScript.</noscript></div>\n<!-- /wp:html -->']
for c in chunks:
    parts.append(f'<!-- wp:html -->\n<script type="text/plain" data-ccx-src>\n{c}</script>\n<!-- /wp:html -->')
loader = ('(function(){var s="",A=String.fromCharCode(38);document.querySelectorAll("script[data-ccx-src]").forEach(function(e){s+=e.textContent;});'
          's=s.split(A+"#038;").join(A).split(A+"amp;").join(A);(new Function(s))();})();')
parts.append(f'<!-- wp:html -->\n<script><!--\n{loader}\n//--></script>\n<!-- /wp:html -->')
(here / "wordpress-blocks.html").write_text("\n\n".join(parts) + "\n", encoding="utf-8")
print("citationcheck.html", len(standalone), "| wordpress-blocks.html", sum(map(len, parts)), "|", len(chunks), "parça")
