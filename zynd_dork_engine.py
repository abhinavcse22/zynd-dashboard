import pandas as pd
from datetime import datetime
import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from googlesearch import search
import time
import random

SHEET_ID = '11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A'

def run_zero_cost_extraction(target_competitor, platform, mission_type, max_results=20):
    """Uses Google Dorking to extract leads without paying for APIs."""
    
    # 1. Construct the Advanced Search Query
    if mission_type == "Bio/Profile Scraper (Replaces Follower Stealer)":
        # Finds LinkedIn/Twitter profiles that explicitly mention the competitor in their bio
        query = f'site:{platform} "{target_competitor}" (AI OR Agent OR Developer OR Engineer)'
    elif mission_type == "Complaint Scraper (Replaces No-Code Finder)":
        # Finds public tweets/posts complaining about a tool's limits or pricing
        query = f'site:{platform} ("{target_competitor} is too expensive" OR "{target_competitor} limits" OR "alternative to {target_competitor}")'
    else:
        # General mention scraper
        query = f'site:{platform} "{target_competitor}"'

    extracted_leads = []
    today = datetime.now().strftime('%Y-%m-%d')
    
    try:
        # advanced=True pulls the title and description snippet directly from Google's index
        for result in search(query, num_results=max_results, advanced=True):
            # Clean up the URLs to just show the target
            target_url = result.url
            context = result.description
            
            # Basic filtering to avoid standard company pages
            if "status" in target_url or "/in/" in target_url or target_competitor.lower() not in target_url:
                extracted_leads.append([
                    target_url,
                    context,
                    platform,
                    query,
                    today
                ])
            
            # Anti-bot delay so Google doesn't block Streamlit
            time.sleep(random.uniform(1.0, 2.5))
            
    except Exception as e:
        return [], f"Google blocked the request (Rate Limit). Try again in 10 minutes. Error: {e}"

    if not extracted_leads:
        return [], "No specific leads found for this query."

    # 2. Push to Google Sheets Pipeline
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    gclient = gspread.authorize(creds)
    sheet = gclient.open_by_key(SHEET_ID).worksheet("Dorking Leads")

    # Deduplicate based on URL (Column 1)
    existing_urls = set(sheet.col_values(1)[1:]) if len(sheet.get_all_values()) > 1 else set()
    new_rows = [row for row in extracted_leads if row[0] not in existing_urls]
    
    if new_rows:
        sheet.append_rows(new_rows)

    display_data = [{"Lead Target": r[0], "Context": str(r[1])[:80]+"..."} for r in new_rows]
    return display_data, len(new_rows)
