"""Backfill script: fetch the last ~month of data from all sources."""

import logging

from scraper.data import add_accident, load_data, save_data
from scraper.dedup import dedup_against_existing, dedup_batch
from scraper.relevance_filter import filter_candidates
from scraper.sources.google_news import search_google_news
from scraper.sources.local_portals import search_local_portals

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)

FILTER_BATCH_SIZE = 20


def run_backfill():
    """Run a backfill: fetch recent data, deduplicate, filter, and save."""
    logger.info("Starting backfill run")

    # 1. Load existing data
    data = load_data()
    existing_count = len(data["accidentes"])
    logger.info("Loaded data with %d existing accidents", existing_count)

    # 2. Warn if data already has accidents
    if existing_count > 0:
        logger.warning(
            "Data already contains %d accidents. "
            "Duplicates will be removed via deduplication.",
            existing_count,
        )

    # 3. Search Google News RSS (returns ~1 month of recent results)
    google_candidates = search_google_news()
    logger.info("Google News returned %d candidates", len(google_candidates))

    # 4. Search local portals
    portal_candidates = search_local_portals()
    logger.info("Local portals returned %d candidates", len(portal_candidates))

    # Combine all candidates
    candidates = google_candidates + portal_candidates
    logger.info("Total candidates from all sources: %d", len(candidates))

    if not candidates:
        logger.info("No candidates found, saving data and exiting")
        save_data(data)
        return

    # 5. Deduplicate against existing + within batch
    candidates = dedup_against_existing(candidates, data["accidentes"])
    logger.info("After dedup against existing: %d candidates", len(candidates))

    candidates = dedup_batch(candidates)
    logger.info("After batch dedup: %d candidates", len(candidates))

    if not candidates:
        logger.info("No new candidates after dedup, saving data and exiting")
        save_data(data)
        return

    # 6. Filter with Haiku in batches of 20
    all_confirmed = []
    for i in range(0, len(candidates), FILTER_BATCH_SIZE):
        batch = candidates[i : i + FILTER_BATCH_SIZE]
        logger.info(
            "Filtering batch %d-%d of %d candidates",
            i,
            min(i + FILTER_BATCH_SIZE, len(candidates)),
            len(candidates),
        )
        confirmed = filter_candidates(batch)
        all_confirmed.extend(confirmed)

    logger.info("Haiku filter confirmed %d accidents total", len(all_confirmed))

    # 7. Add confirmed accidents
    for accident in all_confirmed:
        entry = {
            "fecha": accident["fecha"],
            "titulo": accident["titulo"],
            "fuente": accident["fuente"],
            "url": accident["url"],
            "confianza": accident["confianza"],
        }
        add_accident(data, entry)
        logger.info("Added accident: %s", entry["titulo"])

    # 8. Save
    save_data(data)
    logger.info(
        "Backfill complete: added %d accidents, total now %d",
        len(all_confirmed),
        data["total_accidentes"],
    )


if __name__ == "__main__":
    run_backfill()
