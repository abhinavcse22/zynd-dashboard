import json
import os
import streamlit as st
import gspread
from datetime import datetime
from oauth2client.service_account import ServiceAccountCredentials
from clients.apify import scrape_posts, filter_posts_by_date, normalize_post
from clients.linkedin_enrichment import enrich_profiles_batch
from clients.sendpilot import add_leads_to_campaign, get_campaign_id
from ai_reasoning import score_post, generate_dm
import config

def push_to_sheet(lead):
    """Syncs LinkedIn lead to 'LinkedIn Leads' sheet."""
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(dict(st.secrets["gcp_service_account"]), scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(config.SHEET_ID).worksheet("LinkedIn Leads")
    
    row = [
        lead.get("linkedin_url"),
        lead.get("first_name"),
        lead.get("company_name"),
        lead.get("current_position"),
        "Message 1 Sent",
        datetime.now().strftime('%Y-%m-%d')
    ]
    sheet.append_row(row)

def run(dry_run=False, limit=None, signal_filter=None):
    # Logic to filter signals
    signals = {k: v for k, v in config.POST_SIGNAL_KEYWORDS.items() if not k.startswith("_")}
    if signal_filter:
        signals = {signal_filter: signals.get(signal_filter)}

    all_raw_posts = []
    for s_type, data in signals.items():
        raw = scrape_posts(data.get("queries", []), max_results_per_query=20)
        filtered = filter_posts_by_date(raw, lookback_days=config.LOOKBACK_DAYS)
        all_raw_posts.extend([normalize_post(p, signal_type=s_type) for p in filtered])

    # Deduplicate and Score
    candidates = all_raw_posts[:limit] if limit else all_raw_posts
    scored = []
    for post in candidates:
        scoring = score_post(post)
        if scoring.get("should_reach_out"):
            scored.append({"post": post, "scoring": scoring})

    # Enrich and Generate DM
    profile_urls = [r["post"].get("author_linkedin_url") for r in scored if r["post"].get("author_linkedin_url")]
    enriched_map = enrich_profiles_batch(profile_urls)

    leads_ready = []
    for record in scored:
        profile = enriched_map.get(record["post"].get("author_linkedin_url"), {})
        dm = generate_dm(record["post"], record["scoring"], profile)
        
        lead_obj = {
            "linkedin_url": record["post"]["author_linkedin_url"],
            "first_name": record["post"].get("author_name", "").split()[0],
            "company_name": profile.get("current_company", ""),
            "current_position": profile.get("current_role", ""),
            "custom_fields": {"connection_note": dm["connection_note"], "followup_msg": dm["followup_msg"]}
        }
        leads_ready.append(lead_obj)

    # Push to SendPilot & Sheet
    if not dry_run and leads_ready:
        add_leads_to_campaign(get_campaign_id(), leads_ready)
        for lead in leads_ready:
            push_to_sheet(lead)
            
    return leads_ready