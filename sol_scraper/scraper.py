"""Orchestration: series -> issues -> articles."""

from __future__ import annotations

import logging

from . import parsing
from .cache import IssueCache
from .client import SolClient
from .models import Issue, IssueRef

logger = logging.getLogger(__name__)


class SeriesScraper:
    """Collects the metadata of every article of a SOL series."""

    def __init__(
        self, client: SolClient, series: str, cache: IssueCache | None = None
    ) -> None:
        self.client = client
        self.series = series
        self.cache = cache

    def list_issues(self) -> list[IssueRef]:
        """Returns every published issue, following archive pagination."""
        issues: list[IssueRef] = []
        seen_urls: set[str] = set()
        url: str | None = self.client.archive_url(self.series)
        while url and url not in seen_urls:
            seen_urls.add(url)
            soup = self.client.get_soup(url)
            issues.extend(parsing.parse_archive(soup))
            url = parsing.parse_next_archive_page(soup)
        return issues

    def scrape_issue(self, issue_id: str) -> Issue:
        """Returns an issue with all its papers, from the cache if possible."""
        cached = self.cache.load(issue_id) if self.cache else None
        if cached:
            logger.info(
                "Issue %s: %d article(s) loaded from cache.",
                issue_id, len(cached.papers),
            )
            return cached

        url = self.client.issue_url(self.series, issue_id)
        logger.info("Issue %s: fetching %s", issue_id, url)
        soup = self.client.get_soup(url)
        issue = Issue(id=issue_id, published=parsing.parse_issue_date(soup))
        articles = parsing.parse_issue_articles(soup)
        logger.info(
            "  %d article(s) found. Published: %s", len(articles), issue.published
        )

        for article in articles:
            url = self.client.article_url(self.series, article.id)
            logger.info("  Scraping %s", url)
            issue.papers.append(
                parsing.parse_article(
                    self.client.get_soup(url), article.id, article.pages
                )
            )

        if self.cache:
            self.cache.save(issue)
        return issue

    def scrape(self) -> list[Issue]:
        """Scrapes the whole series."""
        refs = self.list_issues()
        years = sorted({ref.year for ref in refs if ref.year})
        logger.info(
            "Series: %s, published issues: %d, first year: %s, last year: %s",
            self.series, len(refs),
            years[0] if years else "?", years[-1] if years else "?",
        )
        return [self.scrape_issue(ref.id) for ref in refs]
