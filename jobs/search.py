import re
import time
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

# ATS site filters for Google search
SOURCES = {
    "ashby": "site:jobs.ashby.com",
    "lever": "site:jobs.lever.co",
    "greenhouse": "site:boards.greenhouse.io OR site:job-boards.greenhouse.io",
    "wellfound": "site:wellfound.com/jobs",
    "builtin": "site:builtin.com/job",
}

SOURCE_LABELS = {
    "ashby": "Ashby",
    "lever": "Lever",
    "greenhouse": "Greenhouse",
    "wellfound": "Wellfound",
    "builtin": "BuiltIn",
}

# Map --since values to Google's tbs (time-based search) parameter
SINCE_TO_TBS = {
    "24h": "qdr:d",
    "1d":  "qdr:d",
    "2d":  "qdr:d",
    "3d":  "qdr:w",
    "7d":  "qdr:w",
    "14d": "qdr:m",
    "30d": "qdr:m",
}

# Common US state abbreviation → full name mappings for fuzzy location matching
STATE_ABBREVS = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
    "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
    "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming", "DC": "District of Columbia",
}

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}


def parse_since(since: str | None) -> str | None:
    """Convert a --since string like '24h' or '7d' to a Google tbs value."""
    if not since:
        return None
    since = since.lower().strip()
    if since in SINCE_TO_TBS:
        return SINCE_TO_TBS[since]
    if since.endswith("h"):
        return "qdr:d"
    if since.endswith("d"):
        days = int(since[:-1])
        if days <= 2:
            return "qdr:d"
        elif days <= 7:
            return "qdr:w"
        else:
            return "qdr:m"
    return None


def build_query(title: str, sources: list[str], locations: list[str] | None = None) -> str:
    """Build a Google search query for a job title across selected ATS sources."""
    site_filters = " OR ".join(SOURCES[s] for s in sources if s in SOURCES)
    query = f'({site_filters}) "{title}"'
    if locations:
        location_filters = " OR ".join(f'"{loc}"' for loc in locations)
        query += f" ({location_filters})"
    return query


def is_relevant(job: dict, searched_title: str) -> bool:
    """Check whether a job result is relevant to the searched title."""
    job_title = job.get("title") or ""
    if not job_title:
        return True

    job_title_lower = job_title.lower()
    searched_lower = searched_title.lower()

    STOP_WORDS = {"of", "the", "and", "in", "at", "for", "to", "a", "an"}
    keywords = [w for w in searched_lower.split() if w not in STOP_WORDS]

    if not keywords:
        return True

    matches = sum(1 for kw in keywords if kw in job_title_lower)
    return matches >= max(1, len(keywords) // 2)


def matches_location(job_location: str | None, config_locations: list[str]) -> bool:
    """
    Check whether a job's location matches any of the configured location filters.
    Handles remote, city/state names, state abbreviations, and country names.
    Returns True if no locations are configured or if location can't be determined.
    """
    if not config_locations:
        return True
    if not job_location:
        return True  # Can't determine — include rather than exclude

    job_loc_lower = job_location.lower()

    for loc in config_locations:
        loc_lower = loc.lower().strip()

        # Remote matching
        if loc_lower == "remote":
            if any(w in job_loc_lower for w in ["remote", "anywhere", "distributed", "work from home", "wfh"]):
                return True
            continue

        # Direct substring match (e.g. "New York" in "New York, NY")
        if loc_lower in job_loc_lower:
            return True

        # State abbreviation matching: config "Ohio" matches job "Columbus, OH"
        for abbrev, full_name in STATE_ABBREVS.items():
            if loc_lower == full_name.lower():
                # Config has full state name — check for abbreviation in job location
                if abbrev.lower() in [w.strip(",.").lower() for w in job_loc_lower.split()]:
                    return True
            if loc_lower == abbrev.lower():
                # Config has abbreviation — check for full name in job location
                if full_name.lower() in job_loc_lower:
                    return True

    return False


# ---------------------------------------------------------------------------
# Location scraping per ATS source
# ---------------------------------------------------------------------------

def scrape_location(url: str, source: str) -> str | None:
    """
    Fetch a job page and extract its location.
    Returns None if location can't be determined.
    """
    try:
        if source == "Greenhouse":
            return _greenhouse_location(url)
        elif source == "Lever":
            return _lever_location(url)
        elif source == "Ashby":
            return _ashby_location(url)
        elif source == "Wellfound":
            return _wellfound_location(url)
        elif source == "BuiltIn":
            return _builtin_location(url)
    except Exception:
        return None
    return None


def _greenhouse_location(url: str) -> str | None:
    """Use Greenhouse's public API to get location — no scraping needed."""
    parsed = urlparse(url)
    parts = [p for p in parsed.path.split("/") if p]
    # Expected: [company, 'jobs', job_id]
    if len(parts) < 3:
        return None
    company, job_id = parts[0], parts[2]
    api_url = f"https://boards-api.greenhouse.io/v1/boards/{company}/jobs/{job_id}"
    resp = requests.get(api_url, timeout=10, headers=HEADERS)
    data = resp.json()
    return data.get("location", {}).get("name")


def _lever_location(url: str) -> str | None:
    """Scrape Lever job page for location."""
    resp = requests.get(url, timeout=10, headers=HEADERS)
    soup = BeautifulSoup(resp.text, "html.parser")
    # Lever renders location in .sort-by-location or .posting-categories
    for selector in ["sort-by-location", "location", "workplaceTypes"]:
        el = soup.find(class_=selector)
        if el:
            return el.text.strip()
    return None


def _ashby_location(url: str) -> str | None:
    """Scrape Ashby job page for location."""
    resp = requests.get(url, timeout=10, headers=HEADERS)
    soup = BeautifulSoup(resp.text, "html.parser")
    # Ashby typically has location in a <p> or <span> near the job title
    # Look for common location indicators
    for tag in soup.find_all(["span", "p", "div"], limit=50):
        text = tag.text.strip()
        if text and any(kw in text.lower() for kw in ["remote", "hybrid", "on-site", "onsite"]):
            if len(text) < 60:  # Avoid grabbing large blocks of text
                return text
    # Fallback: look for JSON-LD structured data
    script = soup.find("script", type="application/ld+json")
    if script:
        import json
        try:
            data = json.loads(script.string)
            loc = data.get("jobLocation", {})
            if isinstance(loc, dict):
                addr = loc.get("address", {})
                return addr.get("addressLocality") or addr.get("addressRegion")
        except Exception:
            pass
    return None


def _wellfound_location(url: str) -> str | None:
    """Scrape Wellfound job page for location."""
    resp = requests.get(url, timeout=10, headers=HEADERS)
    soup = BeautifulSoup(resp.text, "html.parser")
    # Check JSON-LD first
    script = soup.find("script", type="application/ld+json")
    if script:
        import json
        try:
            data = json.loads(script.string)
            if data.get("jobLocationType") == "TELECOMMUTE":
                return "Remote"
            loc = data.get("jobLocation", {})
            if isinstance(loc, dict):
                addr = loc.get("address", {})
                city = addr.get("addressLocality", "")
                region = addr.get("addressRegion", "")
                return f"{city}, {region}".strip(", ") or None
        except Exception:
            pass
    return None


def _builtin_location(url: str) -> str | None:
    """Scrape BuiltIn job page for location."""
    resp = requests.get(url, timeout=10, headers=HEADERS)
    soup = BeautifulSoup(resp.text, "html.parser")
    # BuiltIn uses JSON-LD
    script = soup.find("script", type="application/ld+json")
    if script:
        import json
        try:
            data = json.loads(script.string)
            if data.get("jobLocationType") == "TELECOMMUTE":
                return "Remote"
            loc = data.get("jobLocation", {})
            if isinstance(loc, list):
                loc = loc[0] if loc else {}
            addr = loc.get("address", {})
            city = addr.get("addressLocality", "")
            region = addr.get("addressRegion", "")
            return f"{city}, {region}".strip(", ") or None
        except Exception:
            pass
    return None


# ---------------------------------------------------------------------------
# Main search function
# ---------------------------------------------------------------------------

def search_jobs(
    titles: list[str],
    sources: list[str],
    since: str | None = None,
    locations: list[str] | None = None,
    serpapi_key: str | None = None,
) -> list[dict]:
    """
    Search for job listings across ATS platforms.
    Returns a deduplicated, relevance-filtered, and location-filtered list of job dicts.
    """
    tbs = parse_since(since)
    seen_urls = set()
    candidates = []

    for title in titles:
        query = build_query(title, sources, locations=locations)
        if serpapi_key:
            hits = _serpapi_search(query, tbs, serpapi_key)
        else:
            hits = _google_search(query, tbs)

        for hit in hits:
            url = hit.get("url", "")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)

            job = parse_job_url(url)
            if not job:
                continue

            if hit.get("result_title"):
                extracted = extract_title_from_result(hit["result_title"])
                if extracted:
                    job["title"] = extracted

            job["searched_title"] = title

            if not is_relevant(job, title):
                continue

            candidates.append(job)

        if not serpapi_key and len(titles) > 1:
            time.sleep(2)

    # If location filtering is configured, scrape each result page for location
    if locations:
        results = []
        for job in candidates:
            job_location = scrape_location(job["url"], job["source"])
            job["location"] = job_location
            if matches_location(job_location, locations):
                results.append(job)
        return results

    return candidates


# ---------------------------------------------------------------------------
# Search backends
# ---------------------------------------------------------------------------

def _google_search(query: str, tbs: str | None) -> list[dict]:
    """Search using the googlesearch-python library (no API key required)."""
    try:
        from googlesearch import search
    except ImportError:
        raise ImportError("Run: pip install googlesearch-python")

    hits = []
    try:
        kwargs = {"num_results": 20, "sleep_interval": 2}
        if tbs:
            kwargs["tbs"] = tbs
        for url in search(query, **kwargs):
            hits.append({"url": url})
    except Exception:
        pass
    return hits


def _serpapi_search(query: str, tbs: str | None, api_key: str) -> list[dict]:
    """Search using SerpAPI for more reliable results with richer metadata."""
    params = {
        "q": query,
        "api_key": api_key,
        "engine": "google",
        "num": 20,
    }
    if tbs:
        params["tbs"] = tbs

    try:
        resp = requests.get("https://serpapi.com/search", params=params, timeout=15)
        data = resp.json()
        return [
            {
                "url": r.get("link", ""),
                "result_title": r.get("title", ""),
                "snippet": r.get("snippet", ""),
                "date": r.get("date"),
            }
            for r in data.get("organic_results", [])
        ]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# URL parsing
# ---------------------------------------------------------------------------

def parse_job_url(url: str) -> dict | None:
    """Parse an ATS job URL into a structured job dict."""
    parsed = urlparse(url)
    hostname = parsed.hostname or ""
    path_parts = [p for p in parsed.path.split("/") if p]

    if "lever.co" in hostname:
        if not path_parts:
            return None
        company = _slug_to_name(path_parts[0])
        title = _slug_to_title(path_parts[1]) if len(path_parts) > 1 else None
        return {"title": title, "company": company, "source": "Lever", "url": url}

    elif "greenhouse.io" in hostname:
        if not path_parts:
            return None
        company = _slug_to_name(path_parts[0])
        return {"title": None, "company": company, "source": "Greenhouse", "url": url}

    elif "ashby.com" in hostname:
        if not path_parts:
            return None
        company = _slug_to_name(path_parts[0])
        title = _slug_to_title(path_parts[1]) if len(path_parts) > 1 else None
        return {"title": title, "company": company, "source": "Ashby", "url": url}

    elif "wellfound.com" in hostname:
        if not path_parts or path_parts[0] != "jobs":
            return None
        slug = path_parts[1] if len(path_parts) > 1 else None
        title = _slug_to_title(re.sub(r"^\d+-", "", slug)) if slug else None
        return {"title": title, "company": None, "source": "Wellfound", "url": url}

    elif "builtin.com" in hostname:
        if not path_parts or path_parts[0] != "job":
            return None
        title_slug = path_parts[2] if len(path_parts) > 2 else None
        title = _slug_to_title(title_slug) if title_slug else None
        return {"title": title, "company": None, "source": "BuiltIn", "url": url}

    return None


def _slug_to_name(slug: str) -> str:
    return " ".join(word.capitalize() for word in slug.replace("-", " ").split())


def _slug_to_title(slug: str) -> str | None:
    if not slug:
        return None
    slug = re.sub(r"-[a-f0-9]{8,}$", "", slug)
    slug = re.sub(r"-\d+$", "", slug)

    LOWERCASE_WORDS = {"of", "the", "and", "in", "at", "for", "to", "a", "an"}
    UPPERCASE_WORDS = {"vp", "cpo", "cto", "ceo", "svp", "evp", "gm", "pm", "hr"}

    words = slug.split("-")
    result = []
    for i, word in enumerate(words):
        if word.lower() in UPPERCASE_WORDS:
            result.append(word.upper())
        elif i > 0 and word.lower() in LOWERCASE_WORDS:
            result.append(word.lower())
        else:
            result.append(word.capitalize())

    return " ".join(result) if result else None


def extract_title_from_result(result_title: str) -> str | None:
    for sep in [" at ", " | ", " - ", " — "]:
        if sep in result_title:
            result_title = result_title.split(sep)[0].strip()
    return result_title if result_title else None
