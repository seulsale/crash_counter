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
    "Algunas noticias incluyen una descripción del artículo — úsala para "
    "determinar si el accidente ocurrió en el Periférico aunque el título no lo "
    "mencione explícitamente. "
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


BATCH_SIZE = 25


def filter_candidates(candidates: list[dict]) -> list[dict]:
    """Send candidates to Haiku for relevance evaluation in batches.

    Returns only those marked relevante=True with confianza alta or media.
    Returns [] on empty input or API error.
    """
    if not candidates:
        return []

    client = anthropic.Anthropic()
    all_confirmed = []

    # Process in batches to avoid output truncation on large candidate lists
    for batch_start in range(0, len(candidates), BATCH_SIZE):
        batch = candidates[batch_start:batch_start + BATCH_SIZE]
        batch_num = batch_start // BATCH_SIZE + 1
        total_batches = (len(candidates) + BATCH_SIZE - 1) // BATCH_SIZE
        logger.info(
            "Filtering batch %d/%d (%d candidates)",
            batch_num, total_batches, len(batch),
        )

        confirmed = _filter_batch(client, batch)
        all_confirmed.extend(confirmed)

    return all_confirmed


def _build_user_message(candidates: list[dict]) -> str:
    """Build the user message listing candidates for Haiku evaluation."""
    lines = []
    for i, c in enumerate(candidates):
        entry = (
            f"[{i}] Título: {c.get('titulo', '')}\n"
            f"    URL: {c.get('url', '')}\n"
            f"    Fecha publicación: {c.get('fecha', '')}"
        )
        snippet = c.get("snippet", "")
        # Only include snippet if it's a real description, not HTML junk
        if (snippet
                and snippet != c.get("titulo", "")
                and not snippet.strip().startswith("<")):
            entry += f"\n    Descripción: {snippet[:300]}"
        lines.append(entry)
    return "Evalúa las siguientes noticias:\n\n" + "\n\n".join(lines)


def _filter_batch(client, candidates: list[dict]) -> list[dict]:
    """Send a single batch of candidates to Haiku and return confirmed ones."""
    user_message = _build_user_message(candidates)

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=[TOOL_SCHEMA],
            tool_choice={"type": "tool", "name": "evaluar_noticias"},
            messages=[{"role": "user", "content": user_message}],
        )
    except Exception:
        logger.exception("Anthropic API error during relevance filtering")
        return []

    logger.info(
        "Haiku response: stop_reason=%s, content_blocks=%d",
        response.stop_reason,
        len(response.content),
    )

    if response.stop_reason == "max_tokens":
        logger.warning("Haiku response truncated (max_tokens) for batch of %d", len(candidates))

    evaluations = _extract_evaluations(response)
    if evaluations is None:
        logger.warning("No tool_use block found in Haiku response")
        return []

    logger.info("Haiku returned %d evaluations", len(evaluations))
    relevant_count = sum(
        1 for e in evaluations if e.get("relevante", False)
    )
    logger.info("Evaluations marked relevante=True: %d", relevant_count)

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
