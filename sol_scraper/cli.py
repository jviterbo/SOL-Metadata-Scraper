"""Command-line interface."""

from __future__ import annotations

import argparse
import logging
from datetime import datetime
from pathlib import Path

from .cache import IssueCache
from .client import FetchError, SolClient
from .export import export_tables
from .scraper import SeriesScraper

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sol_scraper",
        description="Collects the metadata of a SOL series and exports it as CSV.",
    )
    parser.add_argument(
        "series", help="path of the series in SOL, e.g. 'semish'"
    )
    parser.add_argument(
        "-o", "--output-dir", type=Path, default=Path("."),
        help="directory for the CSV files (default: current directory)",
    )
    parser.add_argument(
        "--cache-dir", type=Path, default=Path("cache"),
        help="directory for the per-issue cache (default: ./cache)",
    )
    parser.add_argument(
        "--no-cache", action="store_true", help="neither read nor write the cache"
    )
    parser.add_argument(
        "--delay", type=float, default=2.5,
        help="seconds between requests (default: 2.5)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    cache = None if args.no_cache else IssueCache(args.cache_dir, args.series)
    scraper = SeriesScraper(SolClient(delay=args.delay), args.series, cache)

    try:
        issues = scraper.scrape()
    except FetchError as exc:
        logger.error("%s", exc)
        logger.error("Aborted. Issues already cached will be reused on the next run.")
        return 1

    papers = [paper for issue in issues for paper in issue.papers]
    datestamp = datetime.now().strftime("%Y%m%d")
    paths = export_tables(papers, args.output_dir, args.series, datestamp)

    logger.info("\nDone: %d article(s) from %d issue(s).", len(papers), len(issues))
    for path in paths:
        logger.info("  %s", path)
    return 0
