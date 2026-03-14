"""Tests for scraper.data module — data helpers for accidentes.json."""

import json
from datetime import datetime

import pytest
from zoneinfo import ZoneInfo

from scraper.data import (
    DEFAULT_PATH,
    add_accident,
    calculate_max_streak,
    empty_data,
    load_data,
    save_data,
)

TZ = ZoneInfo("America/Monterrey")


# ---------------------------------------------------------------------------
# test_empty_data
# ---------------------------------------------------------------------------
def test_empty_data():
    """empty_data() returns the canonical empty structure."""
    data = empty_data()

    assert data["ultimo_accidente"] is None
    assert data["racha_maxima_dias"] == 0
    assert data["ultima_ejecucion"] is None
    assert data["total_accidentes"] == 0
    assert data["accidentes"] == []
    assert isinstance(data["fuentes_consultadas"], list)
    assert len(data["fuentes_consultadas"]) == 4
    assert "Google News RSS" in data["fuentes_consultadas"]
    assert "Vanguardia (vanguardia.com.mx)" in data["fuentes_consultadas"]


# ---------------------------------------------------------------------------
# test_add_first_accident
# ---------------------------------------------------------------------------
def test_add_first_accident():
    """Adding the first accident updates total and ultimo_accidente."""
    data = empty_data()
    accident = {
        "fecha": "2026-03-10",
        "titulo": "Choque en Saltillo",
        "fuente": "Vanguardia",
        "url": "https://example.com/1",
        "confianza": "alta",
    }
    add_accident(data, accident)

    assert data["total_accidentes"] == 1
    assert data["ultimo_accidente"] == "2026-03-10"
    assert len(data["accidentes"]) == 1
    assert data["accidentes"][0]["titulo"] == "Choque en Saltillo"


# ---------------------------------------------------------------------------
# test_add_multiple_sorts_descending
# ---------------------------------------------------------------------------
def test_add_multiple_sorts_descending():
    """Accidents are sorted descending by fecha after each add."""
    data = empty_data()

    dates = ["2026-01-15", "2026-03-01", "2026-02-10"]
    for i, date in enumerate(dates):
        accident = {
            "fecha": date,
            "titulo": f"Accidente {i}",
            "fuente": "Test",
            "url": f"https://example.com/{i}",
            "confianza": "media",
        }
        add_accident(data, accident)

    assert data["total_accidentes"] == 3
    fechas = [a["fecha"] for a in data["accidentes"]]
    assert fechas == ["2026-03-01", "2026-02-10", "2026-01-15"]
    # ultimo_accidente should be the most recent date
    assert data["ultimo_accidente"] == "2026-03-01"


# ---------------------------------------------------------------------------
# test_cap_at_200
# ---------------------------------------------------------------------------
def test_cap_at_200():
    """Array is capped at 200 entries but total_accidentes keeps counting."""
    data = empty_data()

    for i in range(210):
        day = (i % 28) + 1  # keep day in 1-28 range
        month = (i // 28) % 12 + 1
        year = 2020 + i // 336
        date_str = f"{year:04d}-{month:02d}-{day:02d}"
        accident = {
            "fecha": date_str,
            "titulo": f"Accidente {i}",
            "fuente": "Test",
            "url": f"https://example.com/{i}",
            "confianza": "baja",
        }
        add_accident(data, accident)

    assert len(data["accidentes"]) == 200
    assert data["total_accidentes"] == 210


# ---------------------------------------------------------------------------
# test_calculate_max_streak
# ---------------------------------------------------------------------------
def test_calculate_max_streak():
    """Max streak is the longest gap in days between consecutive accidents."""
    accidents = [
        {"fecha": "2026-03-10"},
        {"fecha": "2026-03-01"},
        {"fecha": "2026-01-05"},
    ]
    # Sorted desc: Mar 10, Mar 1, Jan 5
    # Gaps: Mar10-Mar1 = 9 days, Mar1-Jan5 = 55 days
    streak = calculate_max_streak(accidents)
    assert streak == 55


def test_calculate_max_streak_empty():
    """No accidents means zero streak."""
    assert calculate_max_streak([]) == 0


def test_calculate_max_streak_single():
    """Single accident means zero streak."""
    assert calculate_max_streak([{"fecha": "2026-01-01"}]) == 0


# ---------------------------------------------------------------------------
# test_load_save_roundtrip
# ---------------------------------------------------------------------------
def test_load_save_roundtrip(tmp_path):
    """save_data persists JSON that load_data can read back."""
    filepath = tmp_path / "accidentes.json"

    data = empty_data()
    accident = {
        "fecha": "2026-02-20",
        "titulo": "Volcadura en carretera",
        "fuente": "Zocalo",
        "url": "https://example.com/volc",
        "confianza": "alta",
    }
    add_accident(data, accident)
    save_data(data, path=filepath)

    loaded = load_data(path=filepath)
    assert loaded["total_accidentes"] == 1
    assert loaded["accidentes"][0]["titulo"] == "Volcadura en carretera"
    assert loaded["ultima_ejecucion"] is not None


def test_load_missing_file(tmp_path):
    """load_data returns empty_data() when the file does not exist."""
    filepath = tmp_path / "nonexistent.json"
    data = load_data(path=filepath)
    assert data == empty_data()


def test_save_creates_parent_dirs(tmp_path):
    """save_data creates parent directories if needed."""
    filepath = tmp_path / "nested" / "dir" / "accidentes.json"
    data = empty_data()
    save_data(data, path=filepath)
    assert filepath.exists()
