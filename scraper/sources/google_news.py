"""Source: Google News RSS feed."""

import logging
import time
from calendar import timegm
from datetime import datetime, timezone
from urllib.parse import quote
from zoneinfo import ZoneInfo

import feedparser

logger = logging.getLogger(__name__)

TZ_SALTILLO = ZoneInfo("America/Monterrey")

SEARCH_TERMS = [
    "accidente Periférico Luis Echeverría Saltillo",
    "choque Periférico Saltillo",
    "volcadura Periférico Echeverría Saltillo",
    "accidente Periférico Saltillo Coahuila",
]

GOOGLE_NEWS_RSS_URL = (
    "https://news.google.com/rss/search?q={query}&hl=es-419&gl=MX&ceid=MX:es-419"
)


def _parse_date(parsed_time):
    """Convert feedparser's time.struct_time to ISO string in Saltillo timezone.

    Args:
        parsed_time: A time.struct_time from feedparser, or None.

    Returns:
        ISO-formatted datetime string in the Saltillo timezone.
    """
    if parsed_time is None:
        now = datetime.now(tz=TZ_SALTILLO)
        return now.isoformat()

    timestamp = timegm(parsed_time)
    dt_utc = datetime.fromtimestamp(timestamp, tz=timezone.utc)
    dt_local = dt_utc.astimezone(TZ_SALTILLO)
    return dt_local.isoformat()


def search_google_news():
    """Search Google News RSS for accident reports on the Periferico.

    Iterates all SEARCH_TERMS, fetches each RSS feed, deduplicates by URL
    within the batch, and returns a list of candidate dicts.

    Returns:
        List of dicts with keys: titulo, url, fecha, snippet, fuente.
    """
    seen_urls = set()
    candidates = []

    for term in SEARCH_TERMS:
        try:
            url = GOOGLE_NEWS_RSS_URL.format(query=quote(term))
            logger.info("Fetching Google News RSS for: %s", term)
            feed = feedparser.parse(url)

            for entry in feed.entries:
                link = entry.link
                if link in seen_urls:
                    continue
                seen_urls.add(link)

                candidate = {
                    "titulo": entry.title,
                    "url": link,
                    "fecha": _parse_date(entry.published_parsed),
                    "snippet": getattr(entry, "summary", ""),
                    "fuente": "Google News",
                }
                candidates.append(candidate)

            logger.info(
                "Found %d entries for term: %s", len(feed.entries), term
            )
        except Exception:
            logger.exception("Error fetching Google News for term: %s", term)

        time.sleep(1)

    logger.info(
        "Google News search complete: %d unique candidates", len(candidates)
    )
    return candidates
