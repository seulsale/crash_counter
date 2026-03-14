"""Deduplication logic using URL matching and Jaccard title similarity."""

SIMILARITY_THRESHOLD = 0.7


def dedup_against_existing(
    candidates: list[dict], existing: list[dict]
) -> list[dict]:
    """Filter out candidates that duplicate any existing entry.

    A candidate is considered a duplicate if:
    - Its URL exactly matches an existing entry's URL, OR
    - Its title has Jaccard similarity >= SIMILARITY_THRESHOLD with any
      existing entry's title.
    """
    existing_urls = {entry.get("url") for entry in existing}
    existing_titles = [entry.get("titulo", "") for entry in existing]

    result = []
    for candidate in candidates:
        url = candidate.get("url", "")
        title = candidate.get("titulo", "")

        # Check exact URL match
        if url in existing_urls:
            continue

        # Check title similarity against all existing titles
        is_duplicate = False
        for existing_title in existing_titles:
            if _similarity(title, existing_title) >= SIMILARITY_THRESHOLD:
                is_duplicate = True
                break

        if not is_duplicate:
            result.append(candidate)

    return result


def dedup_batch(candidates: list[dict]) -> list[dict]:
    """Deduplicate within a batch by title similarity.

    Keeps the first occurrence when near-duplicate titles are found.
    """
    if not candidates:
        return []

    result = [candidates[0]]

    for candidate in candidates[1:]:
        title = candidate.get("titulo", "")
        is_duplicate = False

        for kept in result:
            kept_title = kept.get("titulo", "")
            if _similarity(title, kept_title) >= SIMILARITY_THRESHOLD:
                is_duplicate = True
                break

        if not is_duplicate:
            result.append(candidate)

    return result


def _similarity(a: str, b: str) -> float:
    """Jaccard coefficient over word tokens (split on whitespace).

    Returns a value between 0.0 (no overlap) and 1.0 (identical word sets).
    """
    tokens_a = set(a.lower().split())
    tokens_b = set(b.lower().split())

    if not tokens_a and not tokens_b:
        return 1.0
    if not tokens_a or not tokens_b:
        return 0.0

    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b

    return len(intersection) / len(union)
