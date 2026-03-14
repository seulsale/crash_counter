"""Source: local Saltillo news portals."""

import logging
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

TZ_SALTILLO = ZoneInfo("America/Monterrey")

USER_AGENT = "CrashCounter/1.0 — proyecto comunitario de seguridad vial"

PORTALS = [
    {
        "name": "Vanguardia",
        "url": "https://vanguardia.com.mx/coahuila/saltillo",
        "base": "https://vanguardia.com.mx",
        "extractor": "vanguardia",
    },
    {
        "name": "Zócalo",
        "url": "https://www.zocalo.com.mx/seccion/articulos-saltillo",
        "base": "https://www.zocalo.com.mx",
        "extractor": "zocalo",
    },
    {
        "name": "El Diario de Coahuila",
        "url": "https://www.eldiariodecoahuila.com.mx/local/",
        "base": "https://www.eldiariodecoahuila.com.mx",
        "extractor": "diario",
    },
]

KEYWORDS = [
    "accidente",
    "choque",
    "volcadura",
    "periférico",
    "periferico",
    "colisión",
]


def _parse_time_tag(time_tag):
    """Extract a date from a <time datetime='...'> tag.

    Args:
        time_tag: A BeautifulSoup Tag for <time>, or None.

    Returns:
        ISO-formatted datetime string in the Saltillo timezone.
    """
    if time_tag is None:
        return datetime.now(tz=TZ_SALTILLO).isoformat()

    raw = time_tag.get("datetime", "")
    if not raw:
        return datetime.now(tz=TZ_SALTILLO).isoformat()

    try:
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=TZ_SALTILLO)
        return dt.astimezone(TZ_SALTILLO).isoformat()
    except (ValueError, TypeError):
        logger.warning("Could not parse time tag: %s", raw)
        return datetime.now(tz=TZ_SALTILLO).isoformat()


def _normalize_url(href, base_url):
    """Turn a relative or absolute href into a full URL.

    Args:
        href: The href string from an anchor tag.
        base_url: The base URL of the portal.

    Returns:
        A fully qualified URL string.
    """
    if not href:
        return ""
    if href.startswith("http"):
        return href
    if href.startswith("/"):
        return base_url.rstrip("/") + href
    return base_url.rstrip("/") + "/" + href


def _extract_vanguardia(html, base_url):
    """Parse Vanguardia HTML for article links.

    Looks for <article> tags containing <a> and optional <time> tags.

    Args:
        html: Raw HTML string.
        base_url: Base URL for resolving relative links.

    Returns:
        List of dicts with keys: titulo, url, fecha, snippet.
    """
    soup = BeautifulSoup(html, "html.parser")
    results = []

    for article in soup.find_all("article"):
        link = article.find("a")
        if not link:
            continue

        title = link.get_text(strip=True)
        href = _normalize_url(link.get("href", ""), base_url)
        if not href or not title:
            continue

        time_tag = article.find("time")
        fecha = _parse_time_tag(time_tag)

        results.append({
            "titulo": title,
            "url": href,
            "fecha": fecha,
            "snippet": title,
        })

    return results


def _extract_zocalo(html, base_url):
    """Parse Zocalo HTML for article links.

    Looks for h2 and h3 tags containing anchor elements.

    Args:
        html: Raw HTML string.
        base_url: Base URL for resolving relative links.

    Returns:
        List of dicts with keys: titulo, url, fecha, snippet.
    """
    soup = BeautifulSoup(html, "html.parser")
    results = []
    seen = set()

    for heading in soup.select("h2 a[href], h3 a[href]"):
        title = heading.get_text(strip=True)
        href = _normalize_url(heading.get("href", ""), base_url)
        if not href or not title or href in seen:
            continue
        seen.add(href)

        # Try to find a sibling or parent time tag
        parent = heading.find_parent()
        time_tag = parent.find("time") if parent else None
        fecha = _parse_time_tag(time_tag)

        results.append({
            "titulo": title,
            "url": href,
            "fecha": fecha,
            "snippet": title,
        })

    return results


def _extract_diario(html, base_url):
    """Parse El Diario de Coahuila HTML for article links.

    Looks for article anchors, .post-title anchors, and h2 anchors.

    Args:
        html: Raw HTML string.
        base_url: Base URL for resolving relative links.

    Returns:
        List of dicts with keys: titulo, url, fecha, snippet.
    """
    soup = BeautifulSoup(html, "html.parser")
    results = []
    seen = set()

    selectors = "article a[href], .post-title a[href], h2 a[href]"
    for link in soup.select(selectors):
        title = link.get_text(strip=True)
        href = _normalize_url(link.get("href", ""), base_url)
        if not href or not title or href in seen:
            continue
        seen.add(href)

        # Try to find a nearby time tag
        parent = link.find_parent("article") or link.find_parent()
        time_tag = parent.find("time") if parent else None
        fecha = _parse_time_tag(time_tag)

        results.append({
            "titulo": title,
            "url": href,
            "fecha": fecha,
            "snippet": title,
        })

    return results


def _extract_generic(html, base_url):
    """Fallback extractor using the Vanguardia parser.

    Args:
        html: Raw HTML string.
        base_url: Base URL for resolving relative links.

    Returns:
        List of dicts with keys: titulo, url, fecha, snippet.
    """
    return _extract_vanguardia(html, base_url)


# Extractor dispatch dict — NOT using globals()
_EXTRACTORS = {
    "vanguardia": _extract_vanguardia,
    "zocalo": _extract_zocalo,
    "diario": _extract_diario,
    "generic": _extract_generic,
}


def _matches_keywords(title):
    """Check if a title contains any accident-related keyword.

    Args:
        title: The article title string.

    Returns:
        True if any keyword is found (case-insensitive).
    """
    title_lower = title.lower()
    return any(kw in title_lower for kw in KEYWORDS)


def search_local_portals():
    """Search local Saltillo news portals for accident reports.

    Iterates all configured PORTALS, fetches HTML, dispatches to the
    appropriate extractor, and filters results by KEYWORDS in the title.

    Returns:
        List of dicts with keys: titulo, url, fecha, snippet, fuente.
    """
    candidates = []

    for portal in PORTALS:
        portal_name = portal["name"]
        try:
            logger.info("Fetching portal: %s (%s)", portal_name, portal["url"])
            response = requests.get(
                portal["url"],
                headers={"User-Agent": USER_AGENT},
                timeout=15,
            )
            response.raise_for_status()

            extractor_name = portal.get("extractor", "generic")
            extractor_fn = _EXTRACTORS.get(extractor_name, _extract_generic)

            articles = extractor_fn(response.text, portal["base"])
            logger.info(
                "Portal %s returned %d raw articles", portal_name, len(articles)
            )

            for article in articles:
                if _matches_keywords(article["titulo"]):
                    article["fuente"] = portal_name
                    candidates.append(article)

        except Exception:
            logger.exception("Error fetching portal: %s", portal_name)

        time.sleep(1.5)

    logger.info(
        "Local portals search complete: %d candidates", len(candidates)
    )
    return candidates
