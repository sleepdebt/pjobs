import re
import time
from urllib.parse import urlparse

import requests

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


def parse_since(since: str | None) -> str | None:
    """Convert a --since string like '24h' or '7d' to a Google tbs value."""
    if not since:
        return None
    since = since.lower().strip()
    if since in SINCE_TO_TBS:
        return SINCE_TO_TBS[since]
    # Handle arbitrary values like '5d'
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


def build_query(title: str, sources: list[str]) -> str:
    """Build a Google search query for a job title across selected ATS sources."""
    site_filters = " OR ".join(SOURCES[s] for s in sources if s in SOURCES)
    return f'({site_filters}) "{title}"'


def is_relevant(job: dict, searched_title: str) -> bool:
    """
    Check whether a job result is actually relevant to the searched title.
    Uses the extracted job title (from URL slug or search result) to verify
    it contains meaningful keywords from the searched title.
    Falls back to True for sources where we can't parse the title from the URL.
    """
    job_title = job.get("title") or ""

    # If we couldn't extract a title from the URL, trust the search query
    if not job_title:
        return True

    job_title_lower = job_title.lower()
    searched_lower = searched_title.lower()

    # Extract significant words from the searched title (skip common stop words)
    STOP_WORDS = {"of", "the", "and", "in", "at", "for", "to", "a", "an"}
    keywords = [w for w in searched_lower.split() if w not in STOP_WORDS]

    # Require at least half the significant keywords to appear in the job title
    if not keywords:
        return True

    matches = sum(1 for kw in keywords if kw in job_title_lower)
    return matches >= max(1, len(keywords) // 2)


def search_jobs(titles: list[str], sources: list[str], since: str | None = None, serpapi_key: str | None = None) -> list[dict]:
    """
    Search for job listings across ATS platforms.
    Returns a deduplicated, relevance-filtered list of job dicts.
    """
    tbs = parse_since(since)
    seen_urls = set()
    results = []

    for title in titles:
        query = build_query(title, sources)
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

            # Use search result title to refine job title if available
            if hit.get("result_title"):
                extracted = extract_title_from_result(hit["result_title"])
                if extracted:
                    job["title"] = extracted

            job["searched_title"] = title

            # Filter out irrelevant results
            if not is_relevant(job, title):
                continue

            results.append(job)

        # Be polite — avoid hammering Google between queries
        if not serpapi_key and len(titles) > 1:
            time.sleep(2)

    return results


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
    """
    Parse an ATS job URL into a structured job dict.
    Returns None if the URL doesn't match a known source pattern.
    """
    parsed = urlparse(url)
    hostname = parsed.hostname or ""
    path_parts = [p for p in parsed.path.split("/") if p]

    if "lever.co" in hostname:
        # https://jobs.lever.co/COMPANY/JOB-SLUG
        if not path_parts:
            return None
        company = _slug_to_name(path_parts[0])
        title = _slug_to_title(path_parts[1]) if len(path_parts) > 1 else None
        return {"title": title, "company": company, "source": "Lever", "url": url}

    elif "greenhouse.io" in hostname:
        # https://boards.greenhouse.io/COMPANY/jobs/12345
        if not path_parts:
            return None
        company = _slug_to_name(path_parts[0])
        return {"title": None, "company": company, "source": "Greenhouse", "url": url}

    elif "ashby.com" in hostname:
        # https://jobs.ashby.com/COMPANY/JOB-SLUG
        if not path_parts:
            return None
        company = _slug_to_name(path_parts[0])
        title = _slug_to_title(path_parts[1]) if len(path_parts) > 1 else None
        return {"title": title, "company": company, "source": "Ashby", "url": url}

    elif "wellfound.com" in hostname:
        # https://wellfound.com/jobs/12345-job-title-slug
        if not path_parts or path_parts[0] != "jobs":
            return None
        slug = path_parts[1] if len(path_parts) > 1 else None
        # Wellfound slugs start with a numeric ID: "12345-vp-of-product"
        title = _slug_to_title(re.sub(r"^\d+-", "", slug)) if slug else None
        return {"title": title, "company": None, "source": "Wellfound", "url": url}

    elif "builtin.com" in hostname:
        # https://builtin.com/job/CATEGORY/JOB-TITLE-SLUG/ID
        if not path_parts or path_parts[0] != "job":
            return None
        # Title slug is typically the third segment
        title_slug = path_parts[2] if len(path_parts) > 2 else None
        title = _slug_to_title(title_slug) if title_slug else None
        return {"title": title, "company": None, "source": "BuiltIn", "url": url}

    return None


def _slug_to_name(slug: str) -> str:
    """Convert a URL slug to a readable company name. e.g. 'acme-corp' → 'Acme Corp'"""
    return " ".join(word.capitalize() for word in slug.replace("-", " ").split())


def _slug_to_title(slug: str) -> str | None:
    """
    Convert a job URL slug to a readable title.
    e.g. 'vp-of-product-abc123' → 'VP of Product'
    """
    if not slug:
        return None
    # Strip trailing UUIDs or numeric IDs
    slug = re.sub(r"-[a-f0-9]{8,}$", "", slug)
    slug = re.sub(r"-\d+$", "", slug)

    # Words that should stay lowercase (unless first word)
    LOWERCASE_WORDS = {"of", "the", "and", "in", "at", "for", "to", "a", "an"}
    # Known abbreviations that should be all-caps
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
    """
    Try to extract a clean job title from a Google search result title string.
    e.g. 'VP of Product at Acme Corp | Lever' → 'VP of Product'
    """
    # Strip source suffixes
    for sep in [" at ", " | ", " - ", " — "]:
        if sep in result_title:
            result_title = result_title.split(sep)[0].strip()
    return result_title if result_title else None
