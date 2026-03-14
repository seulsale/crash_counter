"""Relevance filter using Claude Haiku via tool use.

Evaluates whether news candidates describe vehicular accidents on
Periferico Luis Echeverria in Saltillo, Coahuila.
"""

import logging

import anthropic

logger = logging.getLogger(__name__)

MODEL = "claude-haiku-4-5-20251001"

SYSTEM_PROMPT = (
    "Eres un asistente que evalúa noticias. Para cada noticia, determina si "
    "describe un accidente vehicular ocurrido en el Periférico Luis Echeverría "
    "de Saltillo, Coahuila. Si la noticia menciona un accidente en esa vialidad "
    "(choques, volcaduras, atropellamientos, etc.), marca relevante=true. "
    "Si la noticia habla de otro tema o de otra ubicación, marca relevante=false. "
    "Asigna un nivel de confianza: 'alta' si es claramente sobre un accidente en "
    "el Periférico, 'media' si es probable pero no seguro, 'baja' si es dudoso. "
    "Si puedes extraer la fecha y hora del accidente del texto, ponla en "
    "fecha_accidente en formato ISO 8601; si no, pon null."
)

TOOL_SCHEMA = {
    "name": "evaluar_noticias",
    "description": (
        "Evalúa una lista de noticias y determina cuáles son relevantes "
        "a accidentes vehiculares en el Periférico Luis Echeverría de Saltillo."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "evaluaciones": {
                "type": "array",
                "description": "Lista de evaluaciones, una por cada noticia.",
                "items": {
                    "type": "object",
                    "properties": {
                        "indice": {
                            "type": "integer",
                            "description": "Índice de la noticia en la lista original (base 0).",
                        },
                        "relevante": {
                            "type": "boolean",
                            "description": "True si la noticia describe un accidente en el Periférico.",
                        },
                        "confianza": {
                            "type": "string",
                            "enum": ["alta", "media", "baja"],
                            "description": "Nivel de confianza en la evaluación.",
                        },
                        "fecha_accidente": {
                            "type": ["string", "null"],
                            "description": (
                                "Fecha/hora del accidente en ISO 8601 si se puede "
                                "extraer del texto, o null."
                            ),
                        },
                    },
                    "required": ["indice", "relevante", "confianza", "fecha_accidente"],
                },
            }
        },
        "required": ["evaluaciones"],
    },
}


def filter_candidates(candidates: list[dict]) -> list[dict]:
    """Send candidates to Haiku for relevance evaluation.

    Returns only those marked relevante=True with confianza alta or media.
    Returns [] on empty input or API error.
    """
    if not candidates:
        return []

    # Build the user message listing each candidate
    lines = []
    for i, c in enumerate(candidates):
        lines.append(
            f"[{i}] Título: {c.get('titulo', '')}\n"
            f"    URL: {c.get('url', '')}\n"
            f"    Fecha publicación: {c.get('fecha', '')}"
        )
    user_message = "Evalúa las siguientes noticias:\n\n" + "\n\n".join(lines)

    try:
        client = anthropic.Anthropic()
        response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            tools=[TOOL_SCHEMA],
            tool_choice={"type": "tool", "name": "evaluar_noticias"},
            messages=[{"role": "user", "content": user_message}],
        )
    except Exception:
        logger.exception("Anthropic API error during relevance filtering")
        return []

    # Extract tool use block from response
    evaluations = _extract_evaluations(response)
    if evaluations is None:
        return []

    return _apply_evaluations(candidates, evaluations)


def _extract_evaluations(response) -> list[dict] | None:
    """Extract the evaluaciones list from the API response tool_use block."""
    for block in response.content:
        if getattr(block, "type", None) == "tool_use":
            return block.input.get("evaluaciones", [])
    return None


def _apply_evaluations(candidates: list[dict], evaluations: list[dict]) -> list[dict]:
    """Map Haiku evaluations back to candidates, filtering by relevance.

    Only keeps candidates where relevante=True AND confianza is alta or media.
    Updates fecha if Haiku extracted a fecha_accidente.
    """
    accepted_confidence = {"alta", "media"}
    result = []

    for evaluation in evaluations:
        idx = evaluation.get("indice")
        if idx is None or idx < 0 or idx >= len(candidates):
            continue

        is_relevant = evaluation.get("relevante", False)
        confidence = evaluation.get("confianza", "baja")

        if not is_relevant or confidence not in accepted_confidence:
            continue

        candidate = dict(candidates[idx])  # shallow copy
        candidate["confianza"] = confidence

        # Override fecha if Haiku extracted an accident date
        accident_date = evaluation.get("fecha_accidente")
        if accident_date:
            accident_date = _normalize_timezone(accident_date)
            candidate["fecha"] = accident_date

        result.append(candidate)

    return result


def _normalize_timezone(date_str: str) -> str:
    """Append -06:00 (CST Saltillo) if the date string has no timezone info."""
    # Check for timezone offset patterns: +HH:MM, -HH:MM, Z
    if "+" in date_str[10:] or date_str.endswith("Z"):
        return date_str
    # Check if there's already a negative offset after the time portion
    # A bare datetime like "2026-03-09T14:30:00" has a hyphen at position 4 and 7
    # but not as a TZ offset. TZ offset would be at the end like "-06:00"
    parts_after_date = date_str[10:]  # everything after YYYY-MM-DD
    if parts_after_date.count("-") > 0:
        # Check if the last hyphen looks like a TZ offset (followed by digits)
        last_hyphen = parts_after_date.rfind("-")
        suffix = parts_after_date[last_hyphen + 1 :]
        if ":" in suffix and suffix.replace(":", "").isdigit():
            return date_str

    return date_str + "-06:00"
