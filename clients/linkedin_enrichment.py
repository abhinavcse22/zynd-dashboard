"""LinkedIn profile enrichment via Apify.

Uses the same Apify token already in .env - no new account or cost.
Actor: apify/linkedin-profile-scraper

Given a LinkedIn profile URL (already scraped from the post), this pulls:
- Full name, headline, about section
- Current company name, role, company size hint
- Location, education background hint
- Recent activity (used to judge how active/technical they are)

This handles profile enrichment at zero marginal cost
since Apify is already in the stack for post scraping.
"""

import time
import requests
from config import APIFY_API_TOKEN, APIFY_BASE_URL, LINKEDIN_COOKIE

LINKEDIN_PROFILE_ACTOR = "apify/linkedin-profile-scraper"


def enrich_profile(linkedin_url: str) -> dict:
    """Enrich a LinkedIn profile URL.

    Returns a normalized dict with the fields Claude needs for DM generation.
    Returns an empty dict if the URL is missing or the run fails.
    """
    if not APIFY_API_TOKEN or not linkedin_url:
        return _empty_profile()

    actor_input = {"profileUrls": [linkedin_url]}
    if LINKEDIN_COOKIE:
        actor_input["cookie"] = LINKEDIN_COOKIE

    run_url = f"{APIFY_BASE_URL}/acts/{LINKEDIN_PROFILE_ACTOR}/runs"
    try:
        r = requests.post(
            run_url,
            headers={"Authorization": f"Bearer {APIFY_API_TOKEN}"},
            json={"input": actor_input},
            params={"token": APIFY_API_TOKEN},
            timeout=15,
        )
        r.raise_for_status()
        run_id = r.json().get("data", {}).get("id")
    except requests.RequestException as e:
        print(f"    [LinkedIn Enrichment] Failed to start run: {e}")
        return _empty_profile()

    if not run_id:
        return _empty_profile()

    items = _wait_and_fetch(run_id, timeout_seconds=120)
    if not items:
        return _empty_profile()

    return _normalize(items[0])


def enrich_profiles_batch(linkedin_urls: list[str]) -> dict[str, dict]:
    """Enrich multiple profiles in a single actor run. More credit-efficient.

    Returns a dict keyed by LinkedIn URL -> normalized profile dict.
    """
    if not APIFY_API_TOKEN or not linkedin_urls:
        return {}

    valid_urls = [u for u in linkedin_urls if u]
    if not valid_urls:
        return {}

    actor_input = {"profileUrls": valid_urls}
    if LINKEDIN_COOKIE:
        actor_input["cookie"] = LINKEDIN_COOKIE

    run_url = f"{APIFY_BASE_URL}/acts/{LINKEDIN_PROFILE_ACTOR}/runs"
    try:
        r = requests.post(
            run_url,
            headers={"Authorization": f"Bearer {APIFY_API_TOKEN}"},
            json={"input": actor_input},
            params={"token": APIFY_API_TOKEN},
            timeout=15,
        )
        r.raise_for_status()
        run_id = r.json().get("data", {}).get("id")
    except requests.RequestException as e:
        print(f"    [LinkedIn Enrichment] Batch run failed: {e}")
        return {}

    if not run_id:
        return {}

    items = _wait_and_fetch(run_id, timeout_seconds=180)
    result = {}
    for item in items:
        profile = _normalize(item)
        url = profile.get("linkedin_url") or item.get("linkedInUrl") or item.get("url") or ""
        if url:
            result[url] = profile

    return result


def _wait_and_fetch(run_id: str, timeout_seconds: int = 180) -> list[dict]:
    """Poll until the run finishes then return dataset items."""
    status_url = f"{APIFY_BASE_URL}/actor-runs/{run_id}"
    headers = {"Authorization": f"Bearer {APIFY_API_TOKEN}"}
    deadline = time.time() + timeout_seconds
    backoff = 8

    while time.time() < deadline:
        try:
            r = requests.get(status_url, headers=headers, timeout=10)
            r.raise_for_status()
            run_data = r.json().get("data", {})
            status = run_data.get("status", "")
        except requests.RequestException as e:
            print(f"    [LinkedIn Enrichment] Status check error: {e}")
            time.sleep(backoff)
            continue

        if status in ("SUCCEEDED", "FINISHED"):
            dataset_id = run_data.get("defaultDatasetId")
            return _fetch_dataset(dataset_id, headers)
        elif status in ("FAILED", "ABORTED", "TIMED-OUT"):
            print(f"    [LinkedIn Enrichment] Run ended with status: {status}")
            return []

        time.sleep(backoff)
        backoff = min(backoff * 1.5, 30)

    print(f"    [LinkedIn Enrichment] Timed out waiting for run {run_id}")
    return []


def _fetch_dataset(dataset_id: str, headers: dict) -> list[dict]:
    if not dataset_id:
        return []
    try:
        r = requests.get(
            f"{APIFY_BASE_URL}/datasets/{dataset_id}/items",
            headers=headers,
            params={"format": "json", "limit": 200},
            timeout=15,
        )
        r.raise_for_status()
        return r.json() or []
    except requests.RequestException as e:
        print(f"    [LinkedIn Enrichment] Dataset fetch error: {e}")
        return []


def _normalize(raw: dict) -> dict:
    """Map Apify LinkedIn profile scraper output to a consistent schema.

    Field names vary slightly between actor versions - we try all common ones.
    """
    def get(*keys):
        for k in keys:
            v = raw.get(k)
            if v:
                return v
        return ""

    experiences = raw.get("experiences") or raw.get("experience") or []
    current_company = ""
    current_role = ""
    company_size_hint = ""
    if experiences:
        latest = experiences[0] if isinstance(experiences[0], dict) else {}
        current_company = latest.get("companyName") or latest.get("company") or ""
        current_role = latest.get("title") or latest.get("role") or ""
        company_size_hint = latest.get("companySize") or ""

    about = get("about", "summary", "description")
    skills = raw.get("skills") or []
    skill_names = [s.get("name", s) if isinstance(s, dict) else str(s) for s in skills[:20]]

    # Detect framework signals from about + skills
    all_text = f"{about} {' '.join(skill_names)}".lower()
    uses_langchain = "langchain" in all_text or "langgraph" in all_text
    uses_crewai = "crewai" in all_text
    uses_n8n = "n8n" in all_text
    uses_openai = "openai" in all_text or "gpt" in all_text
    uses_web3 = any(kw in all_text for kw in ["solidity", "web3", "base", "ethereum", "usdc", "blockchain"])

    return {
        "linkedin_url": get("linkedInUrl", "url", "profileUrl"),
        "full_name": get("fullName", "name"),
        "headline": get("headline", "title"),
        "about": about[:500] if about else "",
        "location": get("location", "addressCountryOnly", "geo"),
        "current_company": current_company,
        "current_role": current_role,
        "company_size_hint": company_size_hint,
        "follower_count": raw.get("followersCount") or raw.get("followers") or 0,
        "connection_count": raw.get("connectionsCount") or raw.get("connections") or 0,
        "skills": skill_names,
        "uses_langchain": uses_langchain,
        "uses_crewai": uses_crewai,
        "uses_n8n": uses_n8n,
        "uses_openai": uses_openai,
        "uses_web3": uses_web3,
    }


def _empty_profile() -> dict:
    return {
        "linkedin_url": "", "full_name": "", "headline": "", "about": "",
        "location": "", "current_company": "", "current_role": "",
        "company_size_hint": "", "follower_count": 0, "connection_count": 0,
        "skills": [], "uses_langchain": False, "uses_crewai": False,
        "uses_n8n": False, "uses_openai": False, "uses_web3": False,
    }
