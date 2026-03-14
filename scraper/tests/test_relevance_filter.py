"""Tests for scraper.relevance_filter — Claude Haiku relevance filter."""

from unittest.mock import MagicMock, patch

import pytest

from scraper.relevance_filter import (
    TOOL_SCHEMA,
    filter_candidates,
)


# ---------------------------------------------------------------------------
# test_tool_schema_has_required_fields
# ---------------------------------------------------------------------------
def test_tool_schema_has_required_fields():
    """TOOL_SCHEMA contains the evaluar_noticias tool with correct structure."""
    assert TOOL_SCHEMA["name"] == "evaluar_noticias"
    props = TOOL_SCHEMA["input_schema"]["properties"]
    assert "evaluaciones" in props

    item_props = props["evaluaciones"]["items"]["properties"]
    assert "indice" in item_props
    assert "relevante" in item_props
    assert "confianza" in item_props
    assert "fecha_accidente" in item_props

    # confianza must be an enum with alta/media/baja
    assert set(item_props["confianza"]["enum"]) == {"alta", "media", "baja"}


# ---------------------------------------------------------------------------
# test_filter_returns_only_relevant
# ---------------------------------------------------------------------------
@patch("scraper.relevance_filter.anthropic")
def test_filter_returns_only_relevant(mock_anthropic):
    """Only candidates marked relevante=True with alta/media confianza pass."""
    candidates = [
        {"titulo": "Choque en Periferico", "url": "https://a.com/1", "fecha": "2026-03-10"},
        {"titulo": "Clima en Saltillo", "url": "https://a.com/2", "fecha": "2026-03-10"},
        {"titulo": "Volcadura Periferico", "url": "https://a.com/3", "fecha": "2026-03-10"},
    ]

    # Build mock response: item 0 relevant alta, item 1 not relevant, item 2 relevant baja
    mock_tool_block = MagicMock()
    mock_tool_block.type = "tool_use"
    mock_tool_block.input = {
        "evaluaciones": [
            {"indice": 0, "relevante": True, "confianza": "alta", "fecha_accidente": None},
            {"indice": 1, "relevante": False, "confianza": "alta", "fecha_accidente": None},
            {"indice": 2, "relevante": True, "confianza": "baja", "fecha_accidente": None},
        ]
    }

    mock_response = MagicMock()
    mock_response.content = [mock_tool_block]

    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response
    mock_anthropic.Anthropic.return_value = mock_client

    result = filter_candidates(candidates)

    # Only item 0 passes (relevante=True AND confianza alta or media)
    # Item 2 is relevante=True but confianza=baja, so filtered out
    assert len(result) == 1
    assert result[0]["url"] == "https://a.com/1"


# ---------------------------------------------------------------------------
# test_filter_updates_accident_date
# ---------------------------------------------------------------------------
@patch("scraper.relevance_filter.anthropic")
def test_filter_updates_accident_date(mock_anthropic):
    """If Haiku extracts a fecha_accidente, it overrides the candidate fecha."""
    candidates = [
        {"titulo": "Choque en Periferico", "url": "https://a.com/1", "fecha": "2026-03-10"},
    ]

    mock_tool_block = MagicMock()
    mock_tool_block.type = "tool_use"
    mock_tool_block.input = {
        "evaluaciones": [
            {
                "indice": 0,
                "relevante": True,
                "confianza": "alta",
                "fecha_accidente": "2026-03-09T14:30:00",
            },
        ]
    }

    mock_response = MagicMock()
    mock_response.content = [mock_tool_block]

    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response
    mock_anthropic.Anthropic.return_value = mock_client

    result = filter_candidates(candidates)

    assert len(result) == 1
    # Should have -06:00 appended since no TZ was present
    assert result[0]["fecha"] == "2026-03-09T14:30:00-06:00"


# ---------------------------------------------------------------------------
# test_filter_empty_list
# ---------------------------------------------------------------------------
@patch("scraper.relevance_filter.anthropic")
def test_filter_empty_list(mock_anthropic):
    """An empty candidate list returns [] without calling the API."""
    result = filter_candidates([])

    assert result == []
    mock_anthropic.Anthropic.return_value.messages.create.assert_not_called()


# ---------------------------------------------------------------------------
# test_filter_handles_api_error
# ---------------------------------------------------------------------------
@patch("scraper.relevance_filter.anthropic")
def test_filter_handles_api_error(mock_anthropic):
    """Returns [] when the Anthropic API raises an exception."""
    candidates = [
        {"titulo": "Choque en Periferico", "url": "https://a.com/1", "fecha": "2026-03-10"},
    ]

    mock_client = MagicMock()
    mock_client.messages.create.side_effect = Exception("API timeout")
    mock_anthropic.Anthropic.return_value = mock_client

    result = filter_candidates(candidates)

    assert result == []
