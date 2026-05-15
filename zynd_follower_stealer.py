import requests
import pandas as pd
from datetime import datetime
import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials

SHEET_ID = '11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A'
# RAPID_API_KEY = st.secrets.get("rapidapi", {}).get("key", "")

def steal_twitter_followers(target_handle, max_followers=50):
    """Extracts the follower list of a competitor's Twitter account."""
    
    # Growth Hacker Note: To make this live, you would plug in a RapidAPI Twitter endpoint here.
    # We are simulating the successful data extraction structure for your pipeline.
    url = f"https://twitter-api45.p.rapidapi.com/followers.php?screenname={target_handle}"
    
    headers = {
        "X-RapidAPI-Key": st.secrets.get("rapidapi", {}).get("key", "demo_key"),
        "X-RapidAPI-Host": "twitter-api45.p.rapidapi.com"
    }
    
    try:
        # response = requests.get(url, headers=headers)
        # data = response.json()
        
        # SIMULATED RESPONSE ARCHITECTURE (Replace with real API response mapping)
        # Assuming the API returns a list of user objects
        extracted_leads = []
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Mocking the loop for the pipeline
        for i in range(max_followers):
            extracted_leads.append([
                f"@dev_follower_{i}",          # Username
                f"Web3/AI Builder {i}",        # Name
                "Building AI agents. Interested in OSS.", # Bio
                f"@{target_handle}",           # Target
                str(100 + i * 10),             # Follower count
                today                          # Date
            ])
            
        if not extracted_leads:
            return [], 0

        # Push to Google Sheets
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
        gclient = gspread.authorize(creds)
        sheet = gclient.open_by_key(SHEET_ID).worksheet("Stolen Followers")

        # Deduplicate based on Username (Column 1)
        existing_usernames = set(sheet.col_values(1)[1:]) if len(sheet.get_all_values()) > 1 else set()
        new_rows = [row for row in extracted_leads if row[0] not in existing_usernames]
        
        if new_rows:
            sheet.append_rows(new_rows)

        display_data = [{"Handle": r[0], "Bio": str(r[2])[:50]+"...", "Target": r[3]} for r in new_rows]
        return display_data, len(new_rows)
        
    except Exception as e:
        raise Exception(f"API Connection Error: {str(e)}")
