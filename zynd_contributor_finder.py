import requests
import time
import pandas as pd
from datetime import datetime, timezone, timedelta
import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import random

# Configuration
GITHUB_TOKENS = st.secrets["github"]["tokens"]
SHEET_ID = '11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A'

def make_request(url):
    """Fault-tolerant request handler with token rotation to prevent 403 crashes."""
    if isinstance(GITHUB_TOKENS, str): tokens = [GITHUB_TOKENS]
    else: tokens = GITHUB_TOKENS
        
    retries = 3
    while retries > 0:
        token = random.choice(tokens)
        headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            return response.json()
        elif response.status_code in [403, 429]:
            time.sleep(int(response.headers.get('retry-after', 2))) 
            retries -= 1
        else:
            return None
    return None

def hunt_contributors(repo_path):
    """Extracts elite developers who have successfully merged code in the last 180 days."""
    
    # 🛑 THE TTL WALL: Calculate the 6-month cutoff date exactly
    cutoff_date = (datetime.now(timezone.utc) - timedelta(days=180)).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    # 🧠 THE HACK: Query the COMMITS endpoint with the 'since' parameter, not the contributors endpoint.
    url = f"https://api.github.com/repos/{repo_path}/commits?since={cutoff_date}&per_page=100"
    
    with st.spinner(f"Scanning the last 180 days of commits in {repo_path}..."):
        commits = make_request(url)
        
        if commits is None:
            return [], "GitHub API Error: Check repo name or ensure your token has not hit a rate limit."
            
        if not commits:
            return [], "No active commits found in the last 180 days. This repository might be abandoned."

    # Aggregate the active contributors dynamically
    active_contributors = {}
    for commit in commits:
        author = commit.get('author')
        if not author: 
            continue # Skip commits not linked to a public GitHub account
            
        username = author.get('login', '')
        if not username or 'bot' in username.lower() or '[bot]' in username.lower():
            continue # Skip automated CI/CD bots
            
        if username not in active_contributors:
            active_contributors[username] = {
                'commits_in_window': 0,
                'profile_url': author.get('html_url', '')
            }
        active_contributors[username]['commits_in_window'] += 1

    extracted_leads = []
    today = datetime.now().strftime('%Y-%m-%d')
    
    for username, data in active_contributors.items():
        extracted_leads.append([
            username,
            repo_path,
            data['commits_in_window'],
            data['profile_url'],
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

    display_data = [{"Developer": r[0], "Recent Commits (180d)": r[2], "Profile": r[3]} for r in new_rows]
    return display_data, len(new_rows)
