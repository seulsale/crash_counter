"""Tests for Google News RSS source."""

import time
from unittest.mock import MagicMock, patch

import pytest

from scraper.sources.google_news import (
    SEARCH_TERMS,
    _parse_date,
    search_google_news,
)


class TestSearchTerms:
    """Validate that search terms are correctly defined."""

    def test_search_terms_contain_periferico(self):
        """Every search term must reference the Periferico."""
        for term in SEARCH_TERMS:
            assert "periférico" in term.lower() or "periferico" in term.lower(), (
                f"Search term missing 'periférico': {term}"
            )


class TestParseDate:
    """Test date parsing helper."""

    def test_parse_date_with_valid_struct_time(self):
        """A valid struct_time should produce an ISO string."""
        sample = time.strptime("2025-06-15 10:30:00", "%Y-%m-%d %H:%M:%S")
        result = _parse_date(sample)
        assert "2025-06-15" in result
        assert isinstance(result, str)

    def test_parse_date_with_none_returns_current(self):
        """None input should fall back to current time."""
        result = _parse_date(None)
        assert isinstance(result, str)
        # Should contain today's year at minimum
        assert "202" in result


class TestSearchGoogleNews:
    """Test the main search function."""

    @staticmethod
    def _make_entry(title, link, published_parsed=None):
        """Create a mock feedparser entry."""
        entry = MagicMock()
        entry.title = title
        entry.link = link
        entry.published_parsed = published_parsed
        entry.get = lambda key, default="": {
            "summary": f"Snippet for {title}",
        }.get(key, default)
        entry.summary = f"Snippet for {title}"
        return entry

    @patch("scraper.sources.google_news.time.sleep")
    @patch("scraper.sources.google_news.feedparser.parse")
    def test_search_returns_candidates(self, mock_parse, mock_sleep):
        """Mocked feedparser should return well-structured candidates."""
        entry = self._make_entry(
            "Accidente en Periférico",
            "https://example.com/article1",
            time.strptime("2025-06-15 10:30:00", "%Y-%m-%d %H:%M:%S"),
        )
        mock_parse.return_value = MagicMock(entries=[entry])

        results = search_google_news()

        assert len(results) >= 1
        candidate = results[0]
        assert "titulo" in candidate
        assert "url" in candidate
        assert "fecha" in candidate
        assert "snippet" in candidate
        assert "fuente" in candidate
        assert candidate["fuente"] == "Google News"
        assert candidate["url"] == "https://example.com/article1"

    @patch("scraper.sources.google_news.time.sleep")
    @patch("scraper.sources.google_news.feedparser.parse")
    def test_search_deduplicates_by_url(self, mock_parse, mock_sleep):
        """Duplicate URLs across different search terms must be removed."""
        entry1 = self._make_entry(
            "Accidente en Periférico",
            "https://example.com/same-article",
        )
        entry2 = self._make_entry(
            "Choque en Periférico",
            "https://example.com/same-article",
        )
        mock_parse.return_value = MagicMock(entries=[entry1, entry2])

        results = search_google_news()

        urls = [r["url"] for r in results]
        assert len(urls) == len(set(urls)), "Duplicate URLs found in results"
