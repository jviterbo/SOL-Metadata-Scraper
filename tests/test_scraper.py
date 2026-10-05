"""Offline tests: the HTTP client is replaced by canned OJS-like pages."""

import csv

from bs4 import BeautifulSoup

from sol_scraper import parsing
from sol_scraper.cache import IssueCache
from sol_scraper.export import export_tables
from sol_scraper.scraper import SeriesScraper

BASE = "https://sol.example/index.php"

ARCHIVE_1 = f"""
<div class="obj_issue_summary"><a class="title" href="{BASE}/x/issue/view/20">B</a>
  <div class="series"><span class="value">20/07/2025</span></div></div>
<div class="cmp_pagination"><a class="next" href="{BASE}/x/issue/archive/2">Next</a></div>
"""
ARCHIVE_2 = f"""
<div class="obj_issue_summary"><a class="title" href="{BASE}/x/issue/view/10">A</a>
  <div class="series"><span class="value">2019-07-01</span></div></div>
"""


def issue_page(*article_ids):
    items = "".join(
        f'<div class="obj_article_summary"><div class="title">'
        f'<a href="{BASE}/x/article/view/{i}">T</a></div>'
        f'<div class="pages"> 1-8 </div></div>'
        for i in article_ids
    )
    return f'<div class="published"><span class="value"> 2025-07-20 </span></div>{items}'


ARTICLE = """
<html><head>
<meta name="DC.Language" content="pt"/>
<meta name="DC.Type.articleType" content="Artigos"/>
<meta name="DC.Title" content=" A title with a\ttab "/>
<meta name="DC.Identifier.DOI" content="10.5753/x.2025.1"/>
<meta name="DC.Description" xml:lang="en" content="Line one
line two"/>
<meta name="DC.Description" xml:lang="pt" content="Resumo"/>
<meta name="citation_date" content="2025/07/20"/>
<meta name="citation_author" content="Ana Silva"/>
<meta name="citation_author" content="Bruno Costa"/>
<meta name="citation_author_institution" content="UFF"/>
<meta name="citation_pdf_url" content="https://sol.example/pdf/1"/>
</head><body><div class="main_entry">
<ul class="item authors">
  <li><span class="name">Ana Silva</span></li>
  <li><span class="name">Bruno Costa</span>
      <span class="orcid"><a>https://orcid.org/0000-0001</a></span></li>
</ul>
<div class="item keywords"><span class="value"> web,  scraping ,</span></div>
<div class="item references"><div class="value">
  Ref A &amp; B. [link]

  Ref C.
</div></div>
</div></body></html>
"""


class FakeClient:
    def __init__(self, pages):
        self.pages = pages
        self.requested = []

    def archive_url(self, series):
        return f"{BASE}/{series}/issue/archive"

    def issue_url(self, series, issue_id):
        return f"{BASE}/{series}/issue/view/{issue_id}"

    def article_url(self, series, article_id):
        return f"{BASE}/{series}/article/view/{article_id}"

    def get_soup(self, url):
        self.requested.append(url)
        return BeautifulSoup(self.pages[url], "html.parser")


def make_client():
    return FakeClient({
        f"{BASE}/x/issue/archive": ARCHIVE_1,
        f"{BASE}/x/issue/archive/2": ARCHIVE_2,
        f"{BASE}/x/issue/view/20": issue_page(1, 2),
        f"{BASE}/x/issue/view/10": issue_page(3),
        **{f"{BASE}/x/article/view/{i}": ARTICLE for i in (1, 2, 3)},
    })


def test_parse_article():
    paper = parsing.parse_article(BeautifulSoup(ARTICLE, "html.parser"), "1", " 1-8 ")
    assert paper.title == "A title with a\ttab"
    assert paper.pages == "1-8"
    assert (paper.pub_date, paper.pub_year) == ("2025/07/20", "2025")
    assert paper.abstract_alt == "Resumo"
    # An author without institution must not shift the others' affiliations.
    assert [(a.name, a.affiliation, a.orcid) for a in paper.authors] == [
        ("Ana Silva", "", ""),
        ("Bruno Costa", "UFF", "https://orcid.org/0000-0001"),
    ]
    assert paper.keywords == ["web", "scraping"]
    assert paper.references == ["Ref A & B.", "Ref C."]


def test_list_issues_follows_pagination():
    refs = SeriesScraper(make_client(), "x").list_issues()
    assert [(r.id, r.year) for r in refs] == [("20", "2025"), ("10", "2019")]


def test_cache_holds_one_issue_each_and_is_reused(tmp_path):
    cache = IssueCache(tmp_path, "x")
    first = SeriesScraper(make_client(), "x", cache).scrape()
    assert [[p.id for p in issue.papers] for issue in first] == [["1", "2"], ["3"]]
    assert [p.id for p in cache.load("10").papers] == ["3"]

    client = make_client()
    second = SeriesScraper(client, "x", cache).scrape()
    assert second == first
    assert all("/article/" not in url and "/issue/view/" not in url
               for url in client.requested)


def test_export_round_trips_awkward_values(tmp_path):
    issues = SeriesScraper(make_client(), "x").scrape()
    papers = [p for issue in issues for p in issue.papers]
    paths = export_tables(papers, tmp_path, "x", "20250101")
    assert [p.name for p in paths] == [
        "papers-x-20250101.csv", "authors-x-20250101.csv",
        "keywords-x-20250101.csv", "references-x-20250101.csv",
    ]

    def read(path):
        with path.open(encoding="utf-8", newline="") as fh:
            return list(csv.reader(fh, delimiter="\t"))

    rows = read(paths[0])
    assert len(rows) == 4 and all(len(row) == 9 for row in rows)
    assert rows[1][1:3] == ["A title with a\ttab", "Line one\nline two"]
    authors = read(paths[1])
    assert authors[1] == ["1", "Ana Silva", "", ""]
    assert len(authors) == 7
    assert read(paths[3])[1] == ["1", "1", "Ref A & B."]
