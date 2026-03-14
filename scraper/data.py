"""Data helpers for loading, saving, and manipulating accidentes.json."""

import json
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Monterrey")

# Resolve DEFAULT_PATH relative to the project root (two levels up from this file).
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PATH = _PROJECT_ROOT / "docs" / "data" / "accidentes.json"

MAX_ACCIDENTS = 200


def empty_data() -> dict:
    """Return the canonical empty data structure."""
    return {
        "ultimo_accidente": None,
        "racha_maxima_dias": 0,
        "ultima_ejecucion": None,
        "total_accidentes": 0,
        "fuentes_consultadas": [
            "Google News RSS",
            "Vanguardia (vanguardia.com.mx)",
            "Zócalo (zocalo.com.mx)",
            "El Diario de Coahuila (eldiariodecoahuila.com.mx)",
        ],
        "accidentes": [],
    }


def load_data(path: Path = DEFAULT_PATH) -> dict:
    """Load accidentes.json from *path*; return empty_data() on any error."""
    try:
        path = Path(path)
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return empty_data()


def save_data(data: dict, path: Path = DEFAULT_PATH) -> None:
    """Save *data* as JSON to *path*, updating ultima_ejecucion first."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data["ultima_ejecucion"] = datetime.now(tz=TZ).isoformat()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def add_accident(data: dict, accident: dict) -> None:
    """Add an accident entry, update counters, sort, cap, and recalculate streak."""
    data["accidentes"].append(accident)
    data["total_accidentes"] += 1

    # Sort descending by fecha
    data["accidentes"].sort(key=lambda a: a["fecha"], reverse=True)

    # Cap the stored array at MAX_ACCIDENTS (total_accidentes is never decremented)
    if len(data["accidentes"]) > MAX_ACCIDENTS:
        data["accidentes"] = data["accidentes"][:MAX_ACCIDENTS]

    # Update ultimo_accidente to the most recent date in the array
    data["ultimo_accidente"] = data["accidentes"][0]["fecha"]

    # Recalculate max streak
    data["racha_maxima_dias"] = calculate_max_streak(data["accidentes"])


def calculate_max_streak(accidents: list[dict]) -> int:
    """Return the longest gap in days between consecutive accidents.

    Accidents are expected to have a "fecha" key in YYYY-MM-DD format.
    Returns 0 if there are fewer than two accidents.
    """
    if len(accidents) < 2:
        return 0

    # Sort descending by fecha to ensure consistent ordering
    sorted_acc = sorted(accidents, key=lambda a: a["fecha"], reverse=True)

    max_gap = 0
    for i in range(len(sorted_acc) - 1):
        newer = date.fromisoformat(sorted_acc[i]["fecha"])
        older = date.fromisoformat(sorted_acc[i + 1]["fecha"])
        gap = (newer - older).days
        if gap > max_gap:
            max_gap = gap

    return max_gap
