"""書誌情報の取得。APIキー不要の公開APIを使う。

- 論文: Crossref (DOIから) / OpenAlex (DOI・タイトル検索の補助)
- 本: openBD (ISBN、日本の出版物に強い) / Google Books (ISBNの補助)
取得できない場合は空 dict を返し、手入力にフォールバックする。
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
            }
    except Exception:
        pass
    try:
        data = _get_json("https://www.googleapis.com/books/v1/volumes?q=isbn:" + isbn)
        items = data.get("items", [])
        if items:
            v = items[0].get("volumeInfo", {})
            year = None
            if v.get("publishedDate"):
                year = int(str(v["publishedDate"])[:4])
            return {
                "title": v.get("title", ""),
                "authors": ", ".join(v.get("authors", [])),
                "year": year,
                "venue": v.get("publisher", ""),
                "isbn": isbn,
            }
    except Exception:
        pass
    return {}
