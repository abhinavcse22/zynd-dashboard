"""SendPilot API client.

Push leads with personalized connection note + follow-up message
into a pre-configured SendPilot LinkedIn outreach campaign.

API docs: https://docs.sendpilot.ai
Base URL: https://api.sendpilot.ai
Auth: X-API-Key header

Campaign setup (do this once in SendPilot UI):
  - Step 1: Connection request using {{connection_note}} variable
  - Step 2 (after accept): Message using {{followup_msg}} variable
  - Copy the campaign ID into .env as SENDPILOT_CAMPAIGN_ID
"""

import time
import requests
from config import SENDPILOT_API_KEY, SENDPILOT_BASE_URL, SENDPILOT_CAMPAIGN_ID


def _headers():
    return {
        "X-API-Key": SENDPILOT_API_KEY,
        "Content-Type": "application/json",
    }


def check_api_key() -> bool:
    """Verify the SendPilot API key works by listing campaigns."""
    try:
        r = requests.get(
            f"{SENDPILOT_BASE_URL}/v1/campaigns",
            headers=_headers(),
            timeout=10,
        )
        return r.status_code == 200
    except requests.RequestException:
        return False


def get_campaign_id() -> str:
    cid = SENDPILOT_CAMPAIGN_ID
    if not cid:
        raise ValueError(
            "SENDPILOT_CAMPAIGN_ID not set in .env. "
            "Create a campaign in SendPilot with {{connection_note}} and {{followup_msg}} "
            "sequence steps, then add its ID to .env."
        )
    return cid


def add_leads_to_campaign(campaign_id: str, leads: list[dict]) -> dict:
    """Add leads with personalized messages to a SendPilot campaign.

    Each lead dict:
    {
        "linkedin_url": "https://linkedin.com/in/...",
        "first_name": "Jane",
        "last_name": "Doe",
        "company_name": "Acme",
        "current_position": "AI Engineer",
        "location": "San Francisco",
        "custom_fields": {
            "connection_note": "...",   # under 300 chars
            "followup_msg": "...",      # under 800 chars
            "signal_type": "...",
            "post_angle": "...",
        }
    }
    """
    formatted = []
    for lead in leads:
        entry = {
            "linkedinUrl": lead["linkedin_url"],
            "firstName": lead.get("first_name", ""),
            "lastName": lead.get("last_name", ""),
            "company": lead.get("company_name", ""),
            "title": lead.get("current_position", ""),
        }
        # SendPilot customFields is a flat string:string object
        if lead.get("custom_fields"):
            entry["customFields"] = {
                k: str(v) for k, v in lead["custom_fields"].items() if v
            }
        formatted.append(entry)

    added = skipped = invalid = 0
    errors = []

    # SendPilot caps at 100 leads per request
    for i in range(0, len(formatted), 100):
        batch = formatted[i:i + 100]
        payload = {"campaignId": campaign_id, "leads": batch}

        try:
            r = requests.post(
                f"{SENDPILOT_BASE_URL}/v1/leads",
                headers=_headers(),
                json=payload,
                timeout=30,
            )
            if r.status_code == 429:
                print("    [SendPilot] Rate limited - waiting 60s...")
                time.sleep(60)
                r = requests.post(
                    f"{SENDPILOT_BASE_URL}/v1/leads",
                    headers=_headers(),
                    json=payload,
                    timeout=30,
                )
            r.raise_for_status()
            result = r.json()
            added += result.get("leadsAdded", 0)
            skipped += result.get("duplicatesSkipped", 0)
            invalid += result.get("invalidEntries", 0)
            for err in result.get("errors", []):
                errors.append(f"{err.get('linkedinUrl', '?')}: {err.get('reason', '?')}")
        except requests.RequestException as e:
            errors.append(str(e))

    return {"added_count": added, "skipped_count": skipped, "invalid_count": invalid, "errors": errors}
