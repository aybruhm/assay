from html.parser import HTMLParser
from urllib.parse import parse_qs, unquote, urlparse

from planner.research.models import SearchHit

_SKIP_TAGS = {"head", "script", "style", "noscript", "svg", "template"}
_BLOCK_TAGS = {
    "p",
    "div",
    "section",
    "article",
    "header",
    "footer",
    "li",
    "br",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "tr",
    "td",
    "th",
}


class _TextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _SKIP_TAGS:
            self._skip_depth += 1
        elif tag in _BLOCK_TAGS:
            self.parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1
        elif tag in _BLOCK_TAGS:
            self.parts.append(" ")

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            self.parts.append(data)


class _TitleParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.parts.append(data)


class _SearchParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self.snippets: list[str] = []
        self._in_link = False
        self._in_snippet = False
        self._href = ""
        self._link_parts: list[str] = []
        self._snippet_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        classes = (attributes.get("class") or "").split()
        if tag == "a" and "result__a" in classes:
            self._in_link = True
            self._href = attributes.get("href") or ""
            self._link_parts = []
            self._in_snippet = False
        elif "result__snippet" in classes:
            self._in_snippet = True
            self._snippet_parts = []
            self._in_link = False

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._in_link:
            title = " ".join("".join(self._link_parts).split())
            if title and self._href:
                self.links.append((title, self._href))
            self._in_link = False
        if self._in_snippet and tag in {"a", "div", "span"}:
            snippet = " ".join("".join(self._snippet_parts).split())
            if snippet:
                self.snippets.append(snippet)
            self._in_snippet = False

    def handle_data(self, data: str) -> None:
        if self._in_link:
            self._link_parts.append(data)
        if self._in_snippet:
            self._snippet_parts.append(data)


def extract_title(html_text: str) -> str:
    parser = _TitleParser()
    parser.feed(html_text)
    return " ".join("".join(parser.parts).split())


def extract_text(html_text: str, max_chars: int = 8000) -> str:
    parser = _TextParser()
    parser.feed(html_text)
    text = " ".join("".join(parser.parts).split())
    return text[:max_chars]


def decode_result_url(href: str) -> str:
    if href.startswith("//"):
        href = f"https:{href}"
    parsed = urlparse(href)
    if parsed.netloc.endswith("duckduckgo.com") and parsed.path.startswith("/l/"):
        values = parse_qs(parsed.query).get("uddg")
        if values:
            return unquote(values[0])
    return href


def parse_search_results(html_text: str, max_results: int) -> list[SearchHit]:
    parser = _SearchParser()
    parser.feed(html_text)
    hits: list[SearchHit] = []
    for index, (title, href) in enumerate(parser.links[:max_results]):
        snippet = parser.snippets[index] if index < len(parser.snippets) else ""
        hits.append(
            SearchHit(
                title=title,
                url=decode_result_url(href),
                snippet=snippet,
            )
        )
    return hits
