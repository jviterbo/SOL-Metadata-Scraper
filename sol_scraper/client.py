"""HTTP access to SOL."""

from __future__ import annotations

import logging
import time

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

SOL_BASE_URL = "https://sol.sbc.org.br/index.php"


class FetchError(RuntimeError):
    """Raised when a page cannot be retrieved as HTML."""


class SolClient:
    """Fetches SOL pages politely: one session, a delay between requests,
    a timeout and a few retries on failure."""

    def __init__(
        self,
        base_url: str = SOL_BASE_URL,
        delay: float = 2.5,
        timeout: float = 30.0,
        retries: int = 3,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.delay = delay
        self.timeout = timeout
        self.retries = retries
        self._session = requests.Session()
        self._session.headers["Accept-Language"] = "en"
        self._last_request = 0.0

    # -- URLs ---------------------------------------------------------------

    def archive_url(self, series: str) -> str:
        return f"{self.base_url}/{series}/issue/archive"

    def issue_url(self, series: str, issue_id: str) -> str:
        return f"{self.base_url}/{series}/issue/view/{issue_id}"

    def article_url(self, series: str, article_id: str) -> str:
        return f"{self.base_url}/{series}/article/view/{article_id}"

    # -- Fetching -----------------------------------------------------------

    def get_soup(self, url: str) -> BeautifulSoup:
        """Returns the parsed page at *url*, or raises :class:`FetchError`."""
        last_error: Exception | None = None
        for attempt in range(1, self.retries + 1):
            try:
                return BeautifulSoup(self._get_html(url), "html.parser")
            except (requests.RequestException, FetchError) as exc:
                last_error = exc
                logger.warning(
                    "Attempt %d/%d failed for %s: %s",
                    attempt, self.retries, url, exc,
                )
        raise FetchError(f"Could not fetch {url}: {last_error}")

    def _get_html(self, url: str) -> bytes:
        self._wait()
        response = self._session.get(url, timeout=self.timeout)
        content_type = response.headers.get("Content-Type", "").lower()
        if response.status_code != 200:
            raise FetchError(f"HTTP {response.status_code}")
        if "html" not in content_type:
            raise FetchError(f"unexpected content type {content_type!r}")
        return response.content

    def _wait(self) -> None:
        """Sleeps so consecutive requests are at least ``delay`` apart."""
        remaining = self._last_request + self.delay - time.monotonic()
        if remaining > 0:
            time.sleep(remaining)
        self._last_request = time.monotonic()
