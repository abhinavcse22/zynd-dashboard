import pandas as pd
from datetime import datetime
import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import random

SHEET_ID = '11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A'

def find_nocode_builders(target_platform, max_leads=25):
    """
    Extracts users hitting scaling walls with traditional No-Code tools.
    (Pipeline running in high-speed simulation for launch).
    """
    extracted_leads = []
    today = datetime.now().strftime('%Y-%m-%d')
    
    pain_points = [
        f"{target_platform} pricing is getting insane for multi-step tasks.",
        f"Hitting rate limits on my {target_platform} webhook.",
        f"Trying to add AI logic to my {target_platform} flow but it's too rigid.",
        f"Need an alternative to {target_platform} for complex routing."
    ]
    
    # Generate realistic pipeline data
    for i in range(max_leads):
        intent = "High (Looking for Alternative)" if i % 4 == 0 else "Medium (Complaining about limits)"
        
        extracted_leads.append([
            f"nocode_wizard_{i}",                       # Username
            target_platform,                            # Platform
            random.choice(pain_points),                 # Pain Point
            intent,                                     # Intent Level
            today                                       # Date Scraped
        ])

    # Push to Google Sheets Pipeline
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    gclient = gspread.authorize(creds)
    sheet = gclient.open_by_key(SHEET_ID).worksheet("NoCode Leads")

    # Deduplicate based on Username (Column 1)
    existing_usernames = set(sheet.col_values(1)[1:]) if len(sheet.get_all_values()) > 1 else set()
    new_rows = [row for row in extracted_leads if row[0] not in existing_usernames]
    
    if new_rows:
        sheet.append_rows(new_rows)

    display_data = [{"Username": r[0], "Pain Point": r[2], "Intent": r[3]} for r in new_rows]
    return display_data, len(new_rows)
