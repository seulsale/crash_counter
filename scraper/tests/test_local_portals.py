"""Tests for local Saltillo news portals source."""

from unittest.mock import MagicMock, patch

import pytest

from scraper.sources.local_portals import (
    PORTALS,
    USER_AGENT,
    _extract_vanguardia,
    search_local_portals,
)


class TestConstants:
    """Validate module-level constants."""

    def test_user_agent_is_descriptive(self):
        """User agent should identify the project clearly."""
        assert "CrashCounter" in USER_AGENT
        assert len(USER_AGENT) > 10

    def test_portals_defined(self):
        """At least three portals should be configured."""
        assert len(PORTALS) >= 3
        for portal in PORTALS:
            assert "name" in portal
            assert "url" in portal
            assert portal["url"].startswith("https://")


class TestExtractVanguardia:
    """Test the Vanguardia HTML extractor."""

    SAMPLE_HTML = """
    <html><body>
        <article>
            <a href="/coahuila/accidente-periferico-2025">
                Accidente en Periférico deja 3 heridos
            </a>
            <time datetime="2025-06-15T08:30:00-06:00">15 jun 2025</time>
        </article>
        <article>
            <a href="/coahuila/otra-nota">
                Nota sin relación
            </a>
            <time datetime="2025-06-14T12:00:00-06:00">14 jun 2025</time>
        </article>
    </body></html>
    """

    def test_extract_vanguardia(self):
        """Extractor should find articles from sample HTML."""
        results = _extract_vanguardia(self.SAMPLE_HTML, "https://vanguardia.com.mx")

        assert len(results) >= 1
        article = results[0]
        assert "titulo" in article
        assert "url" in article
        assert "fecha" in article
        assert article["url"].startswith("https://")
        assert "Accidente" in article["titulo"] or "Nota" in article["titulo"]


class TestSearchLocalPortals:
    """Test the main search function."""

    @patch("scraper.sources.local_portals.time.sleep")
    @patch("scraper.sources.local_portals.requests.get")
    def test_search_handles_errors(self, mock_get, mock_sleep):
        """HTTP errors should not crash the search."""
        mock_get.side_effect = Exception("Connection refused")

        results = search_local_portals()

        # Should return empty list, not raise
        assert isinstance(results, list)
        assert len(results) == 0
