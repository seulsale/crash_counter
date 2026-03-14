"""Tests for scraper.main module — main scraper orchestration."""

from unittest.mock import MagicMock, call, patch

from scraper.data import empty_data


# ---------------------------------------------------------------------------
# test_run_scraper_full_flow
# ---------------------------------------------------------------------------
@patch("scraper.main.save_data")
@patch("scraper.main.add_accident")
@patch("scraper.main.filter_candidates")
@patch("scraper.main.dedup_batch")
@patch("scraper.main.dedup_against_existing")
@patch("scraper.main.search_local_portals")
@patch("scraper.main.search_google_news")
@patch("scraper.main.load_data")
def test_run_scraper_full_flow(
    mock_load,
    mock_google,
    mock_portals,
    mock_dedup_existing,
    mock_dedup_batch,
    mock_filter,
    mock_add,
    mock_save,
):
    """Full flow: sources return candidates, dedup keeps some, filter confirms one."""
    from scraper.main import run_scraper

    data = empty_data()
    mock_load.return_value = data

    google_candidate = {
        "titulo": "Choque en Periférico Saltillo",
        "url": "https://example.com/1",
        "fecha": "2026-03-10",
        "snippet": "Un choque...",
        "fuente": "Google News",
    }
    portal_candidate = {
        "titulo": "Volcadura en Periférico Echeverría",
        "url": "https://example.com/2",
        "fecha": "2026-03-09",
        "snippet": "Volcadura...",
        "fuente": "Vanguardia",
    }

    mock_google.return_value = [google_candidate]
    mock_portals.return_value = [portal_candidate]

    # Dedup passes both through
    mock_dedup_existing.return_value = [google_candidate, portal_candidate]
    mock_dedup_batch.return_value = [google_candidate, portal_candidate]

    # Filter confirms only the first one
    confirmed = {
        "titulo": "Choque en Periférico Saltillo",
        "url": "https://example.com/1",
        "fecha": "2026-03-10",
        "fuente": "Google News",
        "confianza": "alta",
    }
    mock_filter.return_value = [confirmed]

    run_scraper()

    # Verify sources were called
    mock_google.assert_called_once()
    mock_portals.assert_called_once()

    # Verify dedup was called with combined candidates
    mock_dedup_existing.assert_called_once_with(
        [google_candidate, portal_candidate], data["accidentes"]
    )
    mock_dedup_batch.assert_called_once_with(
        [google_candidate, portal_candidate]
    )

    # Verify filter was called
    mock_filter.assert_called_once_with(
        [google_candidate, portal_candidate]
    )

    # Verify add_accident was called for the confirmed accident
    mock_add.assert_called_once_with(data, {
        "fecha": "2026-03-10",
        "titulo": "Choque en Periférico Saltillo",
        "fuente": "Google News",
        "url": "https://example.com/1",
        "confianza": "alta",
    })

    # Verify save was called
    mock_save.assert_called_once_with(data)


# ---------------------------------------------------------------------------
# test_run_scraper_no_results_still_saves
# ---------------------------------------------------------------------------
@patch("scraper.main.save_data")
@patch("scraper.main.search_local_portals")
@patch("scraper.main.search_google_news")
@patch("scraper.main.load_data")
def test_run_scraper_no_results_still_saves(
    mock_load,
    mock_google,
    mock_portals,
    mock_save,
):
    """When sources return no candidates, save_data is still called."""
    from scraper.main import run_scraper

    data = empty_data()
    mock_load.return_value = data

    mock_google.return_value = []
    mock_portals.return_value = []

    run_scraper()

    # Save must still be called to update ultima_ejecucion
    mock_save.assert_called_once_with(data)
