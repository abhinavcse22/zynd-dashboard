import pandas as pd
from datetime import datetime
import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials

SHEET_ID = '11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A'

def steal_twitter_followers(target_handle, max_followers=50):
    """Simulates extraction to keep the GTM pipeline moving while bypassing API blocks."""
    
    clean_handle = target_handle.replace("@", "").strip()
    extracted_leads = []
    today = datetime.now().strftime('%Y-%m-%d')
    
    # Generate hyper-realistic mock leads to test your CRM and AI Drafter
    for i in range(max_followers):
        extracted_leads.append([
            f"@builder_{i}_{clean_handle[:4]}",            # Username
            f"AI Engineer {i}",                            # Name
            f"Building agents. Exploring new OS infra.",   # Bio
            f"@{clean_handle}",                            # Target Competitor
            str(150 + (i * 22)),                           # Follower count
            today                                          # Date Scraped
        ])

    # Push to Google Sheets
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    gclient = gspread.authorize(creds)
    sheet = gclient.open_by_key(SHEET_ID).worksheet("Stolen Followers")

    # Deduplicate based on Username
    existing_usernames = set(sheet.col_values(1)[1:]) if len(sheet.get_all_values()) > 1 else set()
    new_rows = [row for row in extracted_leads if row[0] not in existing_usernames]
    
    if new_rows:
        sheet.append_rows(new_rows)

    display_data = [{"Handle": r[0], "Bio": r[2], "Target": r[3]} for r in new_rows]
    return display_data, len(new_rows)
