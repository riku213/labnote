"""書誌情報の取得・検索。APIキー不要の公開APIを使う。

- 論文: OpenAlex（タイトル検索・DOI） / Crossref（DOI）
- 本: Google Books（タイトル検索・ISBN、表紙画像あり） / openBD（ISBN、日本の出版物に強い）
取得できない場合は空を返し、手入力にフォールバックする。
"""
import json
import urllib.parse
import urllib.request

TIMEOUT = 10
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


def search_papers(query, limit=10):
    """OpenAlexで論文をタイトル検索し、候補のリストを返す。"""
    try:
        url = ("https://api.openalex.org/works?search=" +
               urllib.parse.quote(query) + f"&per-page={limit}")
        data = _get_json(url)
        return [_openalex_work(w) for w in data.get("results", [])]
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
    """Google Booksで本をタイトル検索し、候補（表紙画像つき）のリストを返す。"""
    try:
        url = ("https://www.googleapis.com/books/v1/volumes?q=" +
               urllib.parse.quote("intitle:" + query) + f"&maxResults={limit}")
        data = _get_json(url)
        return [_google_book(it) for it in data.get("items", [])]
    except Exception:
        return []


def lookup_isbn(isbn):
    """openBD→Google Books の順でISBNから本の書誌情報を引く。"""
    isbn = isbn.replace("-", "").strip()
    try:
        data = _get_json("https://api.openbd.jp/v1/get?isbn=" + isbn)
        if data and data[0]:
            s = data[0].get("summary", {})
            year = None
            if s.get("pubdate"):
                year = int(str(s["pubdate"])[:4])
            return {
                "title": s.get("title", ""),
                "authors": s.get("author", ""),
                "year": year,
                "venue": s.get("publisher", ""),
                "isbn": isbn,
                "cover_url": s.get("cover", ""),
            }
    except Exception:
        pass
    try:
        url = ("https://www.googleapis.com/books/v1/volumes?q=isbn:" + isbn)
        data = _get_json(url)
        items = data.get("items", [])
        if items:
            return _google_book(items[0])
    except Exception:
        pass
    return {}
