"""Export of the collected metadata to delimited text files."""

from __future__ import annotations

import csv
from collections.abc import Iterable, Iterator
from pathlib import Path

from .models import Paper

Row = list[str]

# The files have always been tab-separated, despite the .csv extension.
DELIMITER = "\t"


def paper_rows(papers: Iterable[Paper]) -> Iterator[Row]:
    for p in papers:
        yield [
            p.id, p.title, p.abstract, p.doi, p.pages, p.section,
            p.pub_year, p.pub_date, p.pdf_url,
        ]


def author_rows(papers: Iterable[Paper]) -> Iterator[Row]:
    for p in papers:
        for author in p.authors:
            yield [p.id, author.name, author.affiliation, author.orcid]


def keyword_rows(papers: Iterable[Paper]) -> Iterator[Row]:
    for p in papers:
        for seq, keyword in enumerate(p.keywords, start=1):
            yield [p.id, str(seq), keyword]


def reference_rows(papers: Iterable[Paper]) -> Iterator[Row]:
    for p in papers:
        for seq, reference in enumerate(p.references, start=1):
            yield [p.id, str(seq), reference]


# name -> (header, row generator); one output file per entry.
TABLES = {
    "papers": (
        ["Paper_id", "Title", "Abstract", "DOI", "Pages", "Sections",
         "Year", "Date", "URL"],
        paper_rows,
    ),
    "authors": (["Paper_id", "Name", "Affiliation", "ORCID"], author_rows),
    "keywords": (["Paper_id", "Seq", "Keyword"], keyword_rows),
    "references": (["Paper_id", "Seq", "Reference"], reference_rows),
}


def export_tables(
    papers: list[Paper], output_dir: Path | str, series: str, datestamp: str
) -> list[Path]:
    """Writes one ``<table>-<series>-<datestamp>.csv`` file per table and
    returns the paths written."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    paths = []
    for name, (header, rows) in TABLES.items():
        path = output_dir / f"{name}-{series}-{datestamp}.csv"
        with path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.writer(fh, delimiter=DELIMITER)
            writer.writerow(header)
            writer.writerows(rows(papers))
        paths.append(path)
    return paths
