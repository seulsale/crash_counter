"""Main scraper orchestration: fetch, deduplicate, filter, and store accidents."""

import logging

import requests
from bs4 import BeautifulSoup

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


_PERIFERICO_TERMS = ("periférico", "periferico", "periférico")


def _needs_snippet(candidate):
    """Check if a candidate needs its snippet enriched.

    Returns True for Google News candidates whose title doesn't mention
    the Periférico but were found by a Periférico-related search term.
    """
    title = candidate.get("titulo", "").lower()
    if "periférico" in title or "periferico" in title:
        return False
    term = candidate.get("termino_busqueda", "")
    return any(t in term.lower() for t in _PERIFERICO_TERMS)


def _extract_source_name(title):
    """Extract source name suffix like '- vanguardia.com.mx' from a title."""
    if " - " in title:
        return title.rsplit(" - ", 1)[-1].strip()
    return ""


def _find_article_on_source(source_href, title):
    """Search the source site for the article and extract meta description.

    Fetches the source site's Saltillo/seguridad section and looks for
    an article matching the title. If found, fetches the article page
    and returns its meta description.
    """
    if not source_href:
        return ""

    # Clean title (remove source suffix)
    clean_title = title.rsplit(" - ", 1)[0].strip().lower()

    # Try known section pages on the source
    section_urls = []
    if "vanguardia" in source_href:
        section_urls = [
            source_href.rstrip("/") + "/coahuila/saltillo/seguridad",
            source_href.rstrip("/") + "/coahuila/saltillo",
        ]
    else:
        return ""

    for section_url in section_urls:
        try:
            resp = requests.get(
                section_url,
                headers={"User-Agent": "CrashCounter/1.0"},
                timeout=10,
            )
            resp.raise_for_status()
            soup = BeautifulSoup(resp.content, "html.parser")

            # Search for a link whose text closely matches the article title
            for a_tag in soup.find_all("a", href=True):
                link_text = a_tag.get_text(strip=True).lower()
                if len(link_text) < 20:
                    continue
                # Require the first 40 chars of the title to appear in the link
                if clean_title[:40] in link_text:
                    article_url = a_tag["href"]
                    if not article_url.startswith("http"):
                        article_url = source_href.rstrip("/") + article_url
                    return _fetch_meta_description(article_url)
        except Exception:
            continue

    return ""


def _fetch_meta_description(url):
    """Fetch a page and extract its meta description."""
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": "CrashCounter/1.0"},
            timeout=10,
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, "html.parser")
        for attr in ("description", "og:description"):
            tag = (soup.find("meta", attrs={"name": attr})
                   or soup.find("meta", attrs={"property": attr}))
            if tag and tag.get("content"):
                return tag["content"]
    except Exception:
        logger.debug("Could not fetch description for %s", url)
    return ""


def _enrich_snippets(candidates):
    """Fetch article descriptions for ambiguous candidates.

    For Google News candidates whose title doesn't mention the Periférico
    but were found by a Periférico search term, fetches the original
    article page and extracts the meta description as the snippet.
    """
    to_enrich = [c for c in candidates if _needs_snippet(c)]
    if not to_enrich:
        return

    logger.info("Enriching snippets for %d ambiguous candidates", len(to_enrich))
    for candidate in to_enrich:
        desc = _find_article_on_source(
            candidate.get("source_href", ""),
            candidate["titulo"],
        )
        if desc:
            candidate["snippet"] = desc
            logger.info("Enriched: %s", candidate["titulo"][:60])


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

    # 8b. Enrich candidates with article descriptions when title is ambiguous
    _enrich_snippets(candidates)

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
