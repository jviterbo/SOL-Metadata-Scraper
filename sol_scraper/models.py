"""Data structures shared by the parsing, cache and export layers."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Author:
    name: str
    affiliation: str = ""
    orcid: str = ""


@dataclass
class Paper:
    """Metadata of a single article."""

    id: str
    pages: str = ""
    title: str = ""
    title_alt: str = ""
    abstract: str = ""
    abstract_alt: str = ""
    language: str = ""
    section: str = ""
    doi: str = ""
    pdf_url: str = ""
    pub_date: str = ""
    first_page: str = ""
    last_page: str = ""
    authors: list[Author] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    references: list[str] = field(default_factory=list)

    @property
    def pub_year(self) -> str:
        return self.pub_date[:4]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Paper:
        data = dict(data)
        authors = [Author(**author) for author in data.pop("authors", [])]
        return cls(authors=authors, **data)


@dataclass
class IssueRef:
    """An issue as listed on the archive page of a series."""

    id: str
    url: str
    published: str = ""

    @property
    def year(self) -> str:
        """Publication year, from a ``dd/mm/yyyy`` or ``yyyy-mm-dd`` date."""
        if "/" in self.published:
            return self.published.split("/")[-1]
        return self.published.split("-")[0]


@dataclass
class ArticleRef:
    """An article as listed on the page of an issue."""

    id: str
    pages: str = ""


@dataclass
class Issue:
    """An issue together with the metadata of all its articles."""

    id: str
    published: str = ""
    papers: list[Paper] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Issue:
        return cls(
            id=data["id"],
            published=data.get("published", ""),
            papers=[Paper.from_dict(paper) for paper in data.get("papers", [])],
        )
