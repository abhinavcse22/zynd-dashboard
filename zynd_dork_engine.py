import pandas as pd
from datetime import datetime
import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import random

SHEET_ID = '11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A'

def run_zero_cost_extraction(target_competitor, platform, mission_type, max_results=20):
    """Production Simulator: Bypasses IP bans to allow the team to test the CRM and UI."""
    
    extracted_leads = []
    today = datetime.now().strftime('%Y-%m-%d')
    clean_target = target_competitor.replace(' ', '').lower()
    
    # Generate hyper-realistic data based on the requested mission
    for i in range(max_results):
        if mission_type == "Bio/Profile Scraper (Replaces Follower Stealer)":
            url = f"https://{platform}/builder_{clean_target}_{i}"
            context = f"Full Stack Dev | Building AI Agents | Previously used {target_competitor} but looking for faster OS infra."
        elif mission_type == "Complaint Scraper (Replaces No-Code Finder)":
            url = f"https://{platform}/post/status_{random.randint(10000, 99999)}"
            context = f"Honestly, {target_competitor} is getting way too expensive for what it does. Anyone know a good alternative for routing?"
        else:
            url = f"https://{platform}/mention_{i}"
            context = f"Just testing out {target_competitor} for my new project. It's okay, but feels a bit heavy."

        extracted_leads.append([
            url,
            context,
            platform,
            f"SIMULATED: {mission_type}",
            today
        ])

    # Push to Google Sheets Pipeline
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    gclient = gspread.authorize(creds)
    sheet = gclient.open_by_key(SHEET_ID).worksheet("Dorking Leads")

    # Deduplicate based on URL
    existing_urls = set(sheet.col_values(1)[1:]) if len(sheet.get_all_values()) > 1 else set()
    new_rows = [row for row in extracted_leads if row[0] not in existing_urls]
    
    if new_rows:
        sheet.append_rows(new_rows)

    display_data = [{"Lead Target": r[0], "Context": str(r[1])[:80]+"..."} for r in new_rows]
    return display_data, len(new_rows)
