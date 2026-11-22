"""書誌情報の取得・検索。APIキー不要の公開APIを使う。

- 論文: OpenAlex（タイトル検索・DOI） / Crossref（DOI）
- 本: Google Books（タイトル検索・ISBN、表紙画像あり） / openBD（ISBN、日本の出版物に強い）
取得できない場合は空を返し、手入力にフォールバックする。
"""
import json
import os
import urllib.parse
import urllib.request

TIMEOUT = 10

# 任意のAPIキー（無くても動くが、共有IP等で無償枠を使い切った場合に自分の枠を使える）
OPENALEX_API_KEY = os.environ.get("OPENALEX_API_KEY", "")
GOOGLE_BOOKS_API_KEY = os.environ.get("GOOGLE_BOOKS_API_KEY", "")
UA = {"User-Agent": "labnote (personal research log)"}


def _get_json(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


# ---- 論文 ----

def _openalex_work(w):
    authors = []
    for a in w.get("authorships", []):
        name = a.get("author", {}).get("display_name", "")
        if name:
            authors.append(name)
    venue = ""
    loc = w.get("primary_location") or {}
    if loc.get("source"):
        venue = loc["source"].get("display_name", "")
    doi = w.get("doi") or ""
    if doi.startswith("https://doi.org/"):
        doi = doi[len("https://doi.org/"):]
    return {
        "title": w.get("title", ""),
        "authors": ", ".join(authors),
        "year": w.get("publication_year"),
        "venue": venue,
        "doi": doi,
        "url": w.get("id", ""),
    }


def _crossref_work(m):
    authors = []
    for a in m.get("author", []):
        name = " ".join(x for x in [a.get("given", ""), a.get("family", "")] if x)
        if name:
            authors.append(name)
    year = None
    for key in ("published-print", "published-online", "issued"):
        parts = m.get(key, {}).get("date-parts", [])
        if parts and parts[0]:
            year = parts[0][0]
            break
    return {
        "title": (m.get("title") or [""])[0],
        "authors": ", ".join(authors),
        "year": year,
        "venue": (m.get("container-title") or [""])[0],
        "doi": m.get("DOI", ""),
        "url": m.get("URL", ""),
    }


def search_papers(query, limit=10):
    """論文をタイトル検索し、候補のリストを返す（OpenAlex→Crossrefの順に試す）。"""
    try:
        url = ("https://api.openalex.org/works?search=" +
               urllib.parse.quote(query) + f"&per-page={limit}")
        if OPENALEX_API_KEY:
            url += "&api_key=" + urllib.parse.quote(OPENALEX_API_KEY)
        data = _get_json(url)
        results = [_openalex_work(w) for w in data.get("results", [])]
        if results:
            return results
    except Exception:
        pass
    try:
        url = ("https://api.crossref.org/works?query.bibliographic=" +
               urllib.parse.quote(query) + f"&rows={limit}")
        data = _get_json(url)
        return [_crossref_work(m) for m in data.get("message", {}).get("items", [])]
    except Exception:
        return []


def lookup_doi(doi):
    """CrossrefでDOIから論文の書誌情報を引く。"""
    try:
        data = _get_json("https://api.crossref.org/works/" +
                         urllib.parse.quote(doi, safe=""))
        m = data.get("message", {})
        authors = []
        for a in m.get("author", []):
            name = " ".join(x for x in [a.get("given", ""), a.get("family", "")] if x)
            if name:
                authors.append(name)
        year = None
        for key in ("published-print", "published-online", "issued"):
            parts = m.get(key, {}).get("date-parts", [])
            if parts and parts[0]:
                year = parts[0][0]
                break
        return {
            "title": (m.get("title") or [""])[0],
            "authors": ", ".join(authors),
            "year": year,
            "venue": (m.get("container-title") or [""])[0],
            "doi": m.get("DOI", doi),
            "url": m.get("URL", ""),
        }
    except Exception:
        return {}


# ---- 本 ----

def _google_book(item):
    v = item.get("volumeInfo", {})
    isbn = ""
    for ident in v.get("industryIdentifiers", []):
        if ident.get("type") in ("ISBN_13", "ISBN_10"):
            isbn = ident.get("identifier", "")
            if ident.get("type") == "ISBN_13":
                break
    cover = ""
    links = v.get("imageLinks", {})
    if links:
        cover = links.get("thumbnail") or links.get("smallThumbnail") or ""
        cover = cover.replace("http://", "https://")
    year = None
    if v.get("publishedDate"):
        try:
            year = int(str(v["publishedDate"])[:4])
        except ValueError:
            year = None
    return {
        "title": v.get("title", ""),
        "authors": ", ".join(v.get("authors", [])),
        "year": year,
        "venue": v.get("publisher", ""),
        "isbn": isbn,
        "url": v.get("infoLink", ""),
        "cover_url": cover,
    }


def search_books(query, limit=10):
    """本をタイトル検索し、候補のリストを返す。

    Google Books（表紙画像つき）を優先し、無償枠の上限などで取得できない場合は
    国立国会図書館サーチ（NDL Search、表紙画像なし）にフォールバックする。
    """
    try:
        url = ("https://www.googleapis.com/books/v1/volumes?q=" +
               urllib.parse.quote("intitle:" + query) + f"&maxResults={limit}")
        if GOOGLE_BOOKS_API_KEY:
            url += "&key=" + urllib.parse.quote(GOOGLE_BOOKS_API_KEY)
        data = _get_json(url)
        results = [_google_book(it) for it in data.get("items", [])]
        if results:
            return results
    except Exception:
        pass
    return _search_books_ndl(query, limit)


def _search_books_ndl(query, limit=10):
    """NDL Search の OpenSearch API でタイトル検索する（表紙画像は返らない）。"""
    import xml.etree.ElementTree as ET
    url = ("https://ndlsearch.ndl.go.jp/api/opensearch?title=" +
           urllib.parse.quote(query) + f"&cnt={limit}")
    DC = "{http://purl.org/dc/elements/1.1/}"
    DCT = "{http://purl.org/dc/terms/}"
    XSI = "{http://www.w3.org/2001/XMLSchema-instance}type"
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            xml_text = resp.read().decode("utf-8")
        root = ET.fromstring(xml_text)
        results = []
        for item in root.iter("item"):
            def first(tag):
                e = item.find(tag)
                return (e.text or "") if e is not None else ""
            def all_texts(tag):
                return [e.text or "" for e in item.findall(tag)]
            isbn = ""
            for ident in item.findall(f"{DC}identifier"):
                if ident.get(XSI, "").endswith("ISBN"):
                    isbn = (ident.text or "").replace("-", "")
                    break
            year = None
            issued = first(f"{DCT}issued")
            if issued:
                try:
                    year = int(issued[:4])
                except ValueError:
                    year = None
            title = first(f"{DC}title")
            if title:
                results.append({
                    "title": title,
                    "authors": ", ".join(all_texts(f"{DC}creator")),
                    "year": year,
                    "venue": first(f"{DC}publisher"),
                    "isbn": isbn,
                    "url": first("link"),
                    "cover_url": "",
                })
        return results
    except Exception:
        return []
