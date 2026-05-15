import requests
import pandas as pd
from datetime import datetime
import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials

GITHUB_TOKEN = st.secrets.get("github", {}).get("token", "")
SHEET_ID = '11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A'

def headers():
    if GITHUB_TOKEN:
        return {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    return {"Accept": "application/vnd.github.v3+json"}

def hunt_contributors(repo_path):
    """Extracts developers who have successfully merged code into competitor repos."""
    
    url = f"https://api.github.com/repos/{repo_path}/contributors?per_page=100"
    response = requests.get(url, headers=headers())
    
    if response.status_code != 200:
        raise Exception(f"GitHub API Error {response.status_code}. Check repo name.")
        
    contributors = response.json()
    if not contributors:
        return [], 0

    extracted_leads = []
    today = datetime.now().strftime('%Y-%m-%d')
    
    for user in contributors:
        username = user.get('login', '')
        if 'bot' in username.lower() or not username:
            continue
            
        extracted_leads.append([
            username,
            repo_path,
            user.get('contributions', 0),
            user.get('html_url', ''),
            today
        ])

    # Push to Google Sheets
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    gclient = gspread.authorize(creds)
    sheet = gclient.open_by_key(SHEET_ID).worksheet("Contributor Leads")

    existing_usernames = set(sheet.col_values(1)[1:]) if len(sheet.get_all_values()) > 1 else set()
    new_rows = [row for row in extracted_leads if row[0] not in existing_usernames]
    
    if new_rows:
        sheet.append_rows(new_rows)

    display_data = [{"Developer": r[0], "Commits": r[2], "Profile": r[3]} for r in new_rows]
    return display_data, len(new_rows)
