import requests
import pandas as pd
from datetime import datetime
import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials

SHEET_ID = '11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A'

def steal_twitter_followers(target_handle, max_followers=50):
    """Hits the live RapidAPI endpoint to extract real Twitter followers."""
    
    # Ensure the user didn't accidentally include the @ symbol
    clean_handle = target_handle.replace("@", "").strip()
    
    url = f"https://twitter-api45.p.rapidapi.com/followers.php?screenname={clean_handle}"
    
    # Pulls the real API key from your Streamlit secrets
    api_key = st.secrets.get("rapidapi", {}).get("key", "")
    if not api_key:
        raise Exception("RapidAPI Key is missing in Streamlit Secrets. Cannot fetch real data.")

    headers = {
        "X-RapidAPI-Key": api_key,
        "X-RapidAPI-Host": "twitter-api45.p.rapidapi.com"
    }
    
    response = requests.get(url, headers=headers)
    
    if response.status_code != 200:
        raise Exception(f"Live API Error: {response.status_code} - {response.text}")

    data = response.json()
    
    # RapidAPI Twitter45 usually returns a dictionary with an "instructions" or "timeline" list.
    # Depending on the exact scraper version, we extract the user data:
    
    # Fallback to empty list if structure changes
    users = [] 
    
    # Parsing the real Twitter JSON payload
    try:
        # Most Twitter scrapers return a list of user objects
        if isinstance(data, list):
            users = data
        elif 'users' in data:
            users = data['users']
        else:
             users = data.get('timeline', []) # Backup parsing
    except Exception:
        raise Exception("Could not parse the live Twitter data. The API structure may have changed.")

    if not users:
        return [], 0

    extracted_leads = []
    today = datetime.now().strftime('%Y-%m-%d')
    
    for user in users[:max_followers]:
        # Handle different potential JSON key names from the scraper
        username = user.get('screen_name', user.get('username', 'Unknown'))
        name = user.get('name', 'Unknown')
        bio = user.get('description', user.get('bio', 'No bio provided'))
        followers = str(user.get('followers_count', 0))
        
        extracted_leads.append([
            f"@{username}",
            name,
            bio,
            f"@{clean_handle}",
            followers,
            today
        ])

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

    display_data = [{"Handle": r[0], "Bio": str(r[2])[:60]+"...", "Target": r[3]} for r in new_rows]
    return display_data, len(new_rows)
