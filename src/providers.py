"""
Akademik veritabani saglayicilari (providers).
"""
from __future__ import annotations
import logging
from typing import Optional
import requests

logger = logging.getLogger(__name__)
_TIMEOUT = 10


def _headers(email=None):
    ua = "citationcheck/1.0 (academic reference validator)"
    if email:
        ua += f" mailto:{email}"
    return {"User-Agent": ua}


def _safe_get(url, params, email=None):
    try:
        resp = requests.get(url, params=params, headers=_headers(email), timeout=_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        logger.debug("Provider HTTP hatasi (%s): %s", url, exc)
        return None


class CrossRefProvider:
    BASE = "https://api.crossref.org"

    def search_by_doi(self, doi, email=None):
        data = _safe_get(f"{self.BASE}/works/{doi.strip()}", {}, email)
        if not data:
            return None
        return self._normalize(data.get("message", {}))

    def search_by_bibliographic(self, query, email=None, rows=3):
        params = {
            "query.bibliographic": query,
            "rows": rows,
            "select": "title,author,published,container-title,DOI,URL",
        }
        data = _safe_get(f"{self.BASE}/works", params, email)
        if not data:
            return []
        return [self._normalize(i) for i in data.get("message", {}).get("items", []) if i]

    @staticmethod
    def _normalize(item):
        titles = item.get("title") or []
        title = titles[0] if titles else ""
        authors_raw = item.get("author") or []
        authors = []
        for a in authors_raw:
            family = a.get("family", "")
            given = a.get("given", "")
            if family:
                authors.append(f"{family}, {given}".strip(", "))
        pub = item.get("published") or item.get("published-print") or {}
        date_parts = pub.get("date-parts", [[]])
        year = str(date_parts[0][0]) if date_parts and date_parts[0] else None
        containers = item.get("container-title") or []
        container = containers[0] if containers else None
        doi = item.get("DOI") or None
        url = item.get("URL") or (f"https://doi.org/{doi}" if doi else None)
        return {
            "title": title, "authors": authors, "year": year,
            "container": container, "doi": doi, "url": url, "source": "crossref",
        }


class OpenAlexProvider:
    BASE = "https://api.openalex.org"

    def search_by_doi(self, doi, email=None):
        doi_clean = doi.strip()
        for prefix in ("https://doi.org/", "http://dx.doi.org/"):
            if doi_clean.startswith(prefix):
                doi_clean = doi_clean[len(prefix):]
        params = {"filter": f"doi:{doi_clean}", "per_page": 1}
        if email:
            params["mailto"] = email
        data = _safe_get(f"{self.BASE}/works", params, email)
        if not data:
            return None
        results = data.get("results", [])
        return self._normalize(results[0]) if results else None

    def search_by_bibliographic(self, query, email=None, rows=3):
        params = {"search": query, "per_page": rows}
        if email:
            params["mailto"] = email
        data = _safe_get(f"{self.BASE}/works", params, email)
        if not data:
            return []
        return [self._normalize(r) for r in data.get("results", []) if r]

    @staticmethod
    def _normalize(item):
        title = item.get("title") or ""
        authorships = item.get("authorships") or []
        authors = [
            a.get("author", {}).get("display_name", "")
            for a in authorships
            if a.get("author", {}).get("display_name")
        ]
        year = item.get("publication_year")
        year = str(year) if year else None
        primary_location = item.get("primary_location") or {}
        source = primary_location.get("source") or {}
        container = source.get("display_name") or None
        doi_raw = item.get("doi") or None
        doi = doi_raw
        if doi and doi.startswith("https://doi.org/"):
            doi = doi[len("https://doi.org/"):]
        return {
            "title": title, "authors": authors, "year": year,
            "container": container, "doi": doi, "url": doi_raw, "source": "openalex",
        }


PROVIDERS = {
    "crossref": CrossRefProvider(),
    "openalex": OpenAlexProvider(),
}

DEFAULT_ORDER = ["crossref", "openalex"]
