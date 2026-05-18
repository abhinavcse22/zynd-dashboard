import pandas as pd
from datetime import datetime
import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from duckduckgo_search import DDGS

SHEET_ID = '11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A'

def run_zero_cost_extraction(target_competitor, platform, mission_type, max_results=20):
    """Uses DuckDuckGo Dorking with an automatic Fallback Net for niche competitors."""
    
    # 1. The Strict, High-Intent Query
    if mission_type == "Bio/Profile Scraper (Replaces Follower Stealer)":
        query = f'site:{platform} "{target_competitor}" developer OR builder OR AI'
    elif mission_type == "Complaint Scraper (Replaces No-Code Finder)":
        query = f'site:{platform} "{target_competitor}" expensive OR limits OR alternative'
    else:
        query = f'site:{platform} "{target_competitor}"'

    # 2. The Broad Fallback Query (If the competitor is too small for the strict query)
    broad_query = f'site:{platform} "{target_competitor}"'

    extracted_leads = []
    today = datetime.now().strftime('%Y-%m-%d')
    
    try:
        # First, cast the strict net
        results = list(DDGS().text(query, max_results=max_results))
        
        # If strict fails (returns 0), cast the massive wide net instantly
        if not results and query != broad_query:
            results = list(DDGS().text(broad_query, max_results=max_results))
            
        for result in results:
            target_url = result.get('href', '')
            context = result.get('body', '')
            
            # Skip individual tweets only if we are specifically hunting profiles
            if mission_type == "Bio/Profile Scraper (Replaces Follower Stealer)" and "/status/" in target_url:
                continue
                
            extracted_leads.append([
                target_url,
                context,
                platform,
                "Fallback Broad Search" if not results else query, # Logs which net caught them
                today
            ])
            
    except Exception as e:
        return [], f"Search Engine Error: {e}"

    if not extracted_leads:
        return [], f"Zero leads found. Nobody on {platform} is currently indexed talking about '{target_competitor}'."

    # Push to Google Sheets
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    gclient = gspread.authorize(creds)
    sheet = gclient.open_by_key(SHEET_ID).worksheet("Dorking Leads")

    existing_urls = set(sheet.col_values(1)[1:]) if len(sheet.get_all_values()) > 1 else set()
    new_rows = [row for row in extracted_leads if row[0] not in existing_urls]
    
    if new_rows:
        sheet.append_rows(new_rows)

    display_data = [{"Lead Target": r[0], "Context": str(r[1])[:80]+"..."} for r in new_rows]
    return display_data, len(new_rows)
