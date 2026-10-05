"""Allows running the scraper with ``python -m sol_scraper``."""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
