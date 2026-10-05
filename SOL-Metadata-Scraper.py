# -*- coding: utf-8 -*-
"""
SOL to ACM-DL Converter
Scrapes proceedings data from SOL (SBC Open Library) and generates
the XML files required for import into the ACM Digital Library.

@author: Viterbo, J.
"""

import json
import time
import warnings

import requests
from bs4 import BeautifulSoup
from datetime import datetime
from pathlib import Path
from requests.exceptions import RequestException


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SOL_BASE_URL = "https://sol.sbc.org.br/index.php"


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def fetch_html(url: str) -> bytes | None:
    """
    Makes an HTTP GET request to *url* and returns the raw content if the
    response is a successful HTML/XML page, or None otherwise.
    """
    try:
        session = requests.Session()
        response = session.get(
            url,
            headers={"Accept-Language": "en"},
            cookies={"from-my": "browser"},
            stream=True,
        )
        content_type = response.headers.get("Content-Type", "").lower()
        if response.status_code == 200 and "html" in content_type:
            return response.content
        return None
    except RequestException as exc:
        print(f"[ERROR] Request failed for {url}: {exc}")
        return None


def parse_html(url: str) -> BeautifulSoup:
    """Fetches *url* and returns a BeautifulSoup object."""
    html = fetch_html(url)
    return BeautifulSoup(html, "html.parser")


# ---------------------------------------------------------------------------
# HTML encoding
# ---------------------------------------------------------------------------

def html_escape(text: str) -> str:
    """Escapes the characters &, ", <, > for safe embedding in XML."""
    return (
        text
        .replace("&", "&amp;")
        .replace('"', "&quot;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


# ---------------------------------------------------------------------------
# SOL scraping
# ---------------------------------------------------------------------------

def get_issue_paper_ids(proc_path: str, proc_id: str) -> tuple[list, list, str]:
    """
    Fetches the issue index page and returns:
      - list of article submission IDs
      - list of page ranges (one per article)
      - publication date string
    """
    issue_url = f"{SOL_BASE_URL}/{proc_path}/issue/view/{proc_id}"
    print(f"\nFetching issue at: {issue_url}")

    soup = parse_html(issue_url)

    date_pub = (
        soup.find("div", class_="published")
        .find("span", class_="value")
        .string.strip()
    )

    paper_ids, page_ranges = [], []

    for article_div in soup.find_all("div", class_="obj_article_summary"):
        title_div = article_div.find("div", class_="title")
        pages_div = article_div.find("div", class_="pages")

        if title_div:
            href = title_div.find_all("a")[0]["href"]
            submission_id = href.rstrip("/").split("/")[-1]
            paper_ids.append(submission_id)
            page_ranges.append(
                pages_div.string.strip() if pages_div else "no page number"
            )

    print(f"* Total of {len(paper_ids)} articles. Published: {date_pub}")
    return paper_ids, page_ranges, date_pub


def scrape_article(proc_path: str, submission_id: str, pages: str) -> dict:
    """
    Visits the SOL article page for *submission_id* and returns a dict with
    all metadata needed to build the ACM-DL XML files.
    """
    url = f"{SOL_BASE_URL}/{proc_path}/article/view/{submission_id}"
    print(f"  Scraping: {url}")

    soup = parse_html(url)

    meta = {
        "id": submission_id,
        "pages": pages.strip(),
        "authors_list": [],
        "affils_list": [],
        "orcids_list": [],
        "refs": "",
        "kwds": "",
        "abstract": "",
        "abstract_alt": "",
        "title_alt": "",
        "doi": None,
        "url": None,
    }
    section_raw = ""

    for tag in soup.find_all("meta"):
        name = tag.get("name")
        content = tag.get("content", "")

        if name == "DC.Language":
            meta["lang"] = content
        elif name == "DC.Type.articleType":
            section_raw = content
        elif name == "DC.Title":
            meta["title"] = content
        elif name == "DC.Title.Alternative":
            meta["title_alt"] = content
        elif name == "DC.Identifier.DOI":
            meta["doi"] = content
        elif name == "DC.Description":
            if tag.get("xml:lang") == "en":
                meta["abstract"] = content
            elif tag.get("xml:lang") == "pt":
                meta["abstract_alt"] = content
        elif name in ("citation_date", "DC.Date.created"):
            meta["pub_date"] = content
            meta["pub_year"] = content[:4]
        elif name == "citation_author":
            meta["authors_list"].append(content)
        elif name == "citation_author_institution":
            meta["affils_list"].append(content)
        elif name == "citation_firstpage":
            meta["first_page"] = content
        elif name == "citation_lastpage":
            meta["last_page"] = content
        elif name == "citation_pdf_url":
            meta["url"] = content

    meta["section"] = section_raw
    meta["title"] = meta.get("title", "").strip()
    meta["title_alt"] = meta["title_alt"].strip()
    meta["abstract"] = meta["abstract"].strip()
    meta["abstract_alt"] = meta["abstract_alt"].strip()
    if meta["doi"]:
        meta["doi"] = meta["doi"].strip()

    ref_div = soup.find("div", class_="item references")
    if ref_div:
        val_div = ref_div.find("div", class_="value")
        if val_div:
            meta["refs"] = val_div.text

    kwd_div = soup.find("div", class_="item keywords")
    if kwd_div:
        val_span = kwd_div.find("span", class_="value")
        if val_span:
            meta["kwds"] = val_span.text

    # Collect ORCIDs (one per author, empty string if absent)
    orc_div = soup.find("div", class_="main_entry")
    if orc_div:
        orc_ul = orc_div.find("ul", class_="item authors")
        if orc_ul:
            for aut in orc_ul.find_all("li"):
                orcid = ""
                orc_span = aut.find("span", class_="orcid")
                if orc_span:
                    orc_a = orc_span.find("a")
                    if orc_a:
                        orcid = orc_a.text.strip()
                meta["orcids_list"].append(orcid)

    return meta


# ---------------------------------------------------------------------------
# Params / institutions helpers
# ---------------------------------------------------------------------------

def load_params(filepath: str = "params.txt") -> dict:
    """
    Reads key=value pairs from *filepath* (one per line) and returns them as
    a dict.  The separator is the first '=' on each line so that values may
    contain '=' characters.
    """
    params = {}
    with open(filepath, "r", encoding="utf-8") as fh:
        for line in fh:
            if "=" in line:
                key, _, value = line.partition("=")
                params[key.strip()] = value.rstrip("\n").strip()
    return params


def append_param(filepath: str, key: str, val: str) -> None:
    """Appends a new key=value line to *filepath*."""
    with open(filepath, "a", encoding="utf-8") as fh:
        fh.write(f"{key}={val}\n")




# ---------------------------------------------------------------------------
# CSV writer
# ---------------------------------------------------------------------------

class CsvWriter:
    """
    Writes the BITS XML files required by the ACM Digital Library.

    Parameters
    ----------
    params : dict
        Configuration loaded from params.txt.
    """

    def __init__(self, params: dict):
        self.params = params

    # ------------------------------------------------------------------
    # Metadata writers
    # ------------------------------------------------------------------

    def _write_papers(self, fh, paper: dict):
        fh.write(f'{paper["id"]}')
        fh.write(f'\t{paper["title"]}')
        fh.write(f'\t{paper["abstract"]}')
#           fh.write(f'\t{paper["kwds"]}')
        fh.write(f'\t{paper["doi"]}')
        fh.write(f'\t{paper["pages"]}')
        fh.write(f'\t{paper["section"]}')
        fh.write(f'\t{paper["pub_year"]}')
        fh.write(f'\t{paper["pub_date"]}')
        fh.write(f'\t{paper["url"]}')
        fh.write('\n')

    def _write_authors(self, fh, paper: dict):
        for seq, (full_name, affil, orcid) in enumerate(
            zip(paper["authors_list"], paper["affils_list"], paper["orcids_list"]),
            start=1,
        ):

            fh.write(f'{paper["id"]}')
            fh.write(f'\t{full_name}')
            fh.write(f'\t{affil}')
            if orcid:
                fh.write(f'\t{orcid}')
            fh.write('\n')

    def _write_keywords(self, fh, paper: dict):
        seq = 1
        if paper["kwds"]:
            for kwd in paper["kwds"].split(","):
                    fh.write(f'{paper["id"]}')
                    fh.write(f'\t{seq}')
                    fh.write(f'\t{kwd.strip()}')
                    fh.write('\n')
                    seq += 1

    def _write_references(self, fh, paper: dict):
        seq = 1
        for line in paper["refs"].splitlines():
            line = line.replace("[link]", "").strip()
            if line:
                fh.write(f'{paper["id"]}')
                fh.write(f'\t{seq}')
                fh.write(f'\t{html_escape(line)}')
                fh.write('\n')
                seq += 1


    # ------------------------------------------------------------------
    # Papers CSV
    # ------------------------------------------------------------------

    def write_main_file(self, proc_path, papers: list[dict], date_pub: str):
        """Writes the top-level book XML file that references all articles."""
        papers_output_file = f"papers-{proc_path}-{date_pub}.csv"
        authors_output_file = f"authors-{proc_path}-{date_pub}.csv"
        keywords_output_file = f"keywords-{proc_path}-{date_pub}.csv"
        references_output_file = f"references-{proc_path}-{date_pub}.csv"

        with open(papers_output_file, "w", encoding="utf-8") as fh:
            fh.write('Paper_id\tTitle\tAbstract\tDOI\tPages\tSections\tYear\tDate\tURL\n')
            for paper in papers:
                self._write_papers(fh, paper)

        with open(authors_output_file, "w", encoding="utf-8") as fh:
            fh.write('Paper_id\tName\tAffiliation\tORCID\n')
            for paper in papers:
                self._write_authors(fh, paper)

        with open(keywords_output_file, "w", encoding="utf-8") as fh:
            fh.write('Paper_id\tSeq\tKeyword\n')
            for paper in papers:
                self._write_keywords(fh, paper)

        with open(references_output_file, "w", encoding="utf-8") as fh:
            fh.write('Paper_id\tSeq\tReference\n')
            for paper in papers:
                self._write_references(fh, paper)

        print("\nDone. CSV files written")


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

def cache_path(proc_id: str) -> Path:
    """Returns the path of the JSON cache file for *proc_id*."""
    return Path(f"cache_{proc_id}.json")


def save_cache(proc_id: str, date_pub: str, papers: list[dict]) -> None:
    """Saves *papers* and *date_pub* to a JSON cache file."""
    payload = {"date_pub": date_pub, "papers": papers}
    path = cache_path(proc_id)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    print(f"  * Cache saved to {path}")


def load_cache(proc_id: str) -> tuple[list[dict], str] | None:
    """
    Loads papers and date_pub from the JSON cache file for *proc_id*.
    Returns (papers, date_pub) if the file exists, or None otherwise.
    """
    path = cache_path(proc_id)
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as fh:
        payload = json.load(fh)
    print(f"  * Cache found at {path} — skipping web scraping.")
    return payload["papers"], payload["date_pub"]


def get_series_issues(path):
    
    vetyear=[]    
    href_vet=[]    
    baselink = "https://sol.sbc.org.br/index.php/"+path
    indexlink=baselink+"/issue/archive"

    #print("Vai contar o número de artigos em "+path)
    
    """ 
    Getting the content of the archive page 
    """
    res = parse_html(indexlink)
    divs = res.findAll('div', class_= 'obj_issue_summary')
    issues = len(divs)
    for div in divs:
        #print(str(div))
        value = div.findAll('span', class_= 'value')
        hrefs = div.findAll('a', class_= 'title')
        for href in hrefs:
            href_vet.append(href['href'])
        issuedate = value[0].text.strip()
        if issuedate.find("/") != -1:
            issuedateparts = issuedate.split('/')
            issueyear = issuedateparts[2]
        else:
            issuedateparts = issuedate.split('-')
            issueyear = issuedateparts[0]
        if not (issueyear in vetyear):
            vetyear.append(issueyear)
        vetyear.sort()

    return issues, vetyear, href_vet



# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    warnings.filterwarnings("ignore")

    params = load_params("scraper-config.txt")
    datestamp = datetime.now().strftime("%Y%m%d")
    
    proc_path = "semish"
    k_issue, years, issue_links = get_series_issues(proc_path)
    print("Serie: "+proc_path+", Edições_publicadas: "+str(k_issue)+", Ano_inicial: "+years[0]+", Ano_final: "+years[len(years)-1])
    
    papers = []

    for link in issue_links:
        link_parts = link.split('/')
        proc_ID = link_parts[-1]
        cached = load_cache(proc_ID)
        if cached:
            papers, date_pub = cached
            print(f"\n-> {len(papers)} article(s) recovered.")
        else:
            paper_ids, page_ranges, date_pub = get_issue_paper_ids(proc_path, proc_ID)
            print(f"* Total of {len(paper_ids)} articles found\n")
            for submission_id, pages in zip(paper_ids, page_ranges):
                paper = scrape_article(proc_path, submission_id, pages)
                papers.append(paper)
                time.sleep(2.5)
            save_cache(proc_ID, date_pub, papers)
            print(f"\n-> {len(papers)} article(s) collected.")

    writer = CsvWriter(params)
    writer.write_main_file(proc_path, papers, datestamp)


if __name__ == "__main__":
    main()
