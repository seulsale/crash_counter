"""Main scraper orchestration: fetch, deduplicate, filter, and store accidents."""

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


def run_scraper():
    """Run the full scraper pipeline: fetch, dedup, filter, save."""
    logger.info("Starting scraper run")

    # 1. Load existing data
    data = load_data()
    logger.info(
        "Loaded data with %d existing accidents", len(data["accidentes"])
    )

    # 2-3. Search sources
    google_candidates = search_google_news()
    logger.info("Google News returned %d candidates", len(google_candidates))

    portal_candidates = search_local_portals()
    logger.info("Local portals returned %d candidates", len(portal_candidates))

    # 4. Combine all candidates
    candidates = google_candidates + portal_candidates
    logger.info("Total candidates from all sources: %d", len(candidates))

    # 5. If no candidates, save (to update ultima_ejecucion) and return
    if not candidates:
        logger.info("No candidates found, saving data and exiting")
        save_data(data)
        return

    # 6. Deduplicate against existing accidents
    candidates = dedup_against_existing(candidates, data["accidentes"])
    logger.info("After dedup against existing: %d candidates", len(candidates))

    # 7. Deduplicate within batch
    candidates = dedup_batch(candidates)
    logger.info("After batch dedup: %d candidates", len(candidates))

    # 8. If no candidates left after dedup, save and return
    if not candidates:
        logger.info("No new candidates after dedup, saving data and exiting")
        save_data(data)
        return

    # 9. Filter with Haiku
    confirmed = filter_candidates(candidates)
    logger.info("Haiku filter confirmed %d accidents", len(confirmed))

    # 10. Add each confirmed accident
    for accident in confirmed:
        entry = {
            "fecha": accident["fecha"],
            "titulo": accident["titulo"],
            "fuente": accident["fuente"],
            "url": accident["url"],
            "confianza": accident["confianza"],
        }
        add_accident(data, entry)
        logger.info("Added accident: %s", entry["titulo"])

    # 11. Save data
    save_data(data)
    logger.info("Scraper run complete")


if __name__ == "__main__":
    run_scraper()
