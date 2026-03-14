"""Tests for scraper.dedup — deduplication by URL and title similarity."""

import pytest

from scraper.dedup import (
    SIMILARITY_THRESHOLD,
    _similarity,
    dedup_against_existing,
    dedup_batch,
)


# ---------------------------------------------------------------------------
# test_dedup_by_exact_url
# ---------------------------------------------------------------------------
def test_dedup_by_exact_url():
    """Candidates with a URL already in existing entries are removed."""
    candidates = [
        {"titulo": "Choque en Periferico", "url": "https://a.com/1"},
        {"titulo": "Volcadura en carretera", "url": "https://a.com/2"},
    ]
    existing = [
        {"titulo": "Choque viejo", "url": "https://a.com/1"},
    ]

    result = dedup_against_existing(candidates, existing)

    assert len(result) == 1
    assert result[0]["url"] == "https://a.com/2"


# ---------------------------------------------------------------------------
# test_dedup_by_similar_title
# ---------------------------------------------------------------------------
def test_dedup_by_similar_title():
    """Candidates with similar titles to existing entries are removed."""
    candidates = [
        {
            "titulo": "Choque en Periferico Luis Echeverria deja 3 heridos",
            "url": "https://b.com/1",
        },
    ]
    existing = [
        {
            "titulo": "Choque en Periferico Luis Echeverria deja 3 heridos en Saltillo",
            "url": "https://a.com/99",
        },
    ]

    result = dedup_against_existing(candidates, existing)

    # Titles are very similar (high Jaccard), so the candidate should be filtered
    assert len(result) == 0


# ---------------------------------------------------------------------------
# test_dedup_batch_groups_same_news
# ---------------------------------------------------------------------------
def test_dedup_batch_groups_same_news():
    """Within a batch, near-duplicate titles keep only the first occurrence."""
    candidates = [
        {"titulo": "Choque en Periferico Luis Echeverria Saltillo", "url": "https://a.com/1"},
        {"titulo": "Choque en Periferico Luis Echeverria en Saltillo", "url": "https://b.com/1"},
        {"titulo": "Lluvia causa inundaciones en Monterrey", "url": "https://c.com/1"},
    ]

    result = dedup_batch(candidates)

    # First two are near-duplicates; only the first should survive
    assert len(result) == 2
    urls = [c["url"] for c in result]
    assert "https://a.com/1" in urls
    assert "https://c.com/1" in urls


# ---------------------------------------------------------------------------
# test_dedup_batch_empty_list
# ---------------------------------------------------------------------------
def test_dedup_batch_empty_list():
    """Empty input returns empty output."""
    assert dedup_batch([]) == []


# ---------------------------------------------------------------------------
# test_different_titles_not_grouped
# ---------------------------------------------------------------------------
def test_different_titles_not_grouped():
    """Completely different titles are not considered duplicates."""
    candidates = [
        {"titulo": "Choque en Periferico", "url": "https://a.com/1"},
        {"titulo": "Lluvia causa inundaciones", "url": "https://a.com/2"},
    ]
    existing = [
        {"titulo": "Politica nacional Mexico 2026", "url": "https://z.com/1"},
    ]

    result = dedup_against_existing(candidates, existing)

    assert len(result) == 2
