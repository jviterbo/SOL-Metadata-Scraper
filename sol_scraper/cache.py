"""JSON cache with one file per issue, so interrupted runs can be resumed."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from .models import Issue

logger = logging.getLogger(__name__)


class IssueCache:
    def __init__(self, directory: Path | str, series: str) -> None:
        self.directory = Path(directory) / series

    def path(self, issue_id: str) -> Path:
        return self.directory / f"issue_{issue_id}.json"

    def load(self, issue_id: str) -> Issue | None:
        """Returns the cached issue, or None if it is not in the cache."""
        path = self.path(issue_id)
        if not path.exists():
            return None
        with path.open(encoding="utf-8") as fh:
            return Issue.from_dict(json.load(fh))

    def save(self, issue: Issue) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.path(issue.id)
        with path.open("w", encoding="utf-8") as fh:
            json.dump(issue.to_dict(), fh, ensure_ascii=False, indent=2)
        logger.info("  Cache saved to %s", path)
