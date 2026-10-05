"""Extraction of metadata from SOL (OJS) pages.

Every function here takes an already parsed page and returns plain data;
nothing in this module touches the network.
"""

from __future__ import annotations

from bs4 import BeautifulSoup, Tag

from .models import ArticleRef, Author, IssueRef, Paper

# <meta name="..."> tags that map directly onto a Paper attribute.
_SIMPLE_META_FIELDS = {
    "DC.Language": "language",
    "DC.Type.articleType": "section",
    "DC.Title": "title",
    "DC.Title.Alternative": "title_alt",
    "DC.Identifier.DOI": "doi",
    "DC.Date.created": "pub_date",
    "citation_date": "pub_date",
    "citation_firstpage": "first_page",
    "citation_lastpage": "last_page",
    "citation_pdf_url": "pdf_url",
}

# xml:lang of a DC.Description tag -> Paper attribute.
_ABSTRACT_FIELDS = {"en": "abstract", "pt": "abstract_alt"}

NO_PAGES = "no page number"


def _last_path_segment(url: str) -> str:
    return url.rstrip("/").split("/")[-1]


def _text(tag: Tag | None) -> str:
    return tag.get_text().strip() if tag else ""


# ---------------------------------------------------------------------------
# Archive page (list of issues)
# ---------------------------------------------------------------------------

def parse_archive(soup: BeautifulSoup) -> list[IssueRef]:
    """Returns the issues listed on an archive page."""
    issues = []
    for summary in soup.find_all("div", class_="obj_issue_summary"):
        published = _text(summary.find("span", class_="value"))
        for link in summary.find_all("a", class_="title"):
            url = link["href"]
            issues.append(IssueRef(_last_path_segment(url), url, published))
    return issues


def parse_next_archive_page(soup: BeautifulSoup) -> str | None:
    """Returns the URL of the next archive page, if the archive is paginated."""
    pagination = soup.find("div", class_="cmp_pagination")
    link = pagination.find("a", class_="next") if pagination else None
    return link["href"] if link else None


# ---------------------------------------------------------------------------
# Issue page (list of articles)
# ---------------------------------------------------------------------------

def parse_issue_date(soup: BeautifulSoup) -> str:
    published = soup.find("div", class_="published")
    return _text(published.find("span", class_="value")) if published else ""


def parse_issue_articles(soup: BeautifulSoup) -> list[ArticleRef]:
    """Returns the articles listed on an issue page."""
    articles = []
    for summary in soup.find_all("div", class_="obj_article_summary"):
        title = summary.find("div", class_="title")
        link = title.find("a") if title else None
        if not link:
            continue
        pages = _text(summary.find("div", class_="pages")) or NO_PAGES
        articles.append(ArticleRef(_last_path_segment(link["href"]), pages))
    return articles


# ---------------------------------------------------------------------------
# Article page
# ---------------------------------------------------------------------------

def parse_article(soup: BeautifulSoup, article_id: str, pages: str = "") -> Paper:
    """Builds a :class:`Paper` from an article page."""
    paper = Paper(id=article_id, pages=pages.strip())
    _read_meta_tags(soup, paper)
    _assign_orcids(soup, paper.authors)
    paper.keywords = _parse_keywords(soup)
    paper.references = _parse_references(soup)
    return paper


def _read_meta_tags(soup: BeautifulSoup, paper: Paper) -> None:
    for tag in soup.find_all("meta"):
        name = tag.get("name")
        content = tag.get("content", "").strip()

        if name in _SIMPLE_META_FIELDS:
            setattr(paper, _SIMPLE_META_FIELDS[name], content)
        elif name == "DC.Description":
            field = _ABSTRACT_FIELDS.get(tag.get("xml:lang"))
            if field:
                setattr(paper, field, content)
        elif name == "citation_author":
            paper.authors.append(Author(name=content))
        elif name == "citation_author_institution" and paper.authors:
            # The institution tag follows the tag of the author it belongs to.
            paper.authors[-1].affiliation = content


def _assign_orcids(soup: BeautifulSoup, authors: list[Author]) -> None:
    """Fills in ORCIDs from the visible author list, matched by position."""
    main_entry = soup.find("div", class_="main_entry")
    author_list = main_entry.find("ul", class_="authors") if main_entry else None
    if not author_list:
        return
    for author, item in zip(authors, author_list.find_all("li")):
        orcid = item.find("span", class_="orcid")
        author.orcid = _text(orcid.find("a")) if orcid else ""


def _parse_keywords(soup: BeautifulSoup) -> list[str]:
    item = soup.find("div", class_="item keywords")
    value = _text(item.find("span", class_="value")) if item else ""
    return [kwd.strip() for kwd in value.split(",") if kwd.strip()]


def _parse_references(soup: BeautifulSoup) -> list[str]:
    item = soup.find("div", class_="item references")
    value = item.find("div", class_="value") if item else None
    if not value:
        return []
    lines = (line.replace("[link]", "").strip() for line in value.text.splitlines())
    return [line for line in lines if line]
