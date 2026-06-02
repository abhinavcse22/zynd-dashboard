import requests
import pandas as pd
from datetime import datetime, timezone, timedelta
import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import random
import time

# Configuration
GITHUB_TOKENS = st.secrets["github"]["tokens"]
SHEET_ID = '11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A'

def make_request(url):
    """Fault-tolerant search request handler with token rotation to prevent UI crashes."""
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

def hunt_hackathon_projects(keyword_query, max_results=30):
    """Scans GitHub for active hackathon repos with strict 180-day TTL enforcement."""
    
    # 🛑 TTL WALL: Calculate exactly 180 days ago
    cutoff_date_str = (datetime.now(timezone.utc) - timedelta(days=180)).strftime('%Y-%m-%d')
    
    # 🧠 HACK: Inject the TTL directly into the GitHub search query (`pushed:>YYYY-MM-DD`)
    # This guarantees GitHub ONLY returns repositories modified in the last 6 months.
    query = f"{keyword_query} pushed:>{cutoff_date_str} in:readme,description"
    url = f"https://api.github.com/search/repositories?q={query}&sort=updated&order=desc&per_page={max_results}"
    
    with st.spinner(f"Scanning global hackathon registries for '{keyword_query}'..."):
        data = make_request(url)
        
        if data is None:
            return [], "GitHub Search API Error: Rate limit exceeded or invalid token. App gracefully caught the error."
            
        items = data.get('items', [])
        
        if not items:
            return [], f"No active hackathon projects found for '{keyword_query}' in the last 180 days."

        extracted_projects = []
        today = datetime.now().strftime('%Y-%m-%d')
        
        for item in items:
            # Ignore massive repos that just happen to mention hackathons (Indie Builders Only)
            if item.get('stargazers_count', 0) > 500:
                continue
                
            extracted_projects.append([
                item.get('name', 'Unknown'),
                item.get('owner', {}).get('login', 'Unknown'),
                item.get('description', 'No description') or "No description",
                item.get('stargazers_count', 0),
                item.get('html_url', ''),
                today
            ])

        if not extracted_projects:
            return [], "Found projects, but all were massive enterprise repos (not hackathon builds)."

        # Push to Google Sheets
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
        gclient = gspread.authorize(creds)
        sheet = gclient.open_by_key(SHEET_ID).worksheet("Hackathon Leads")

        # Deduplicate based on Repo Link (Column 5)
        existing_links = set(sheet.col_values(5)[1:]) if len(sheet.get_all_values()) > 1 else set()
        new_rows = [row for row in extracted_projects if row[4] not in existing_links]
        
        if new_rows:
            sheet.append_rows(new_rows)

        display_data = [{"Project": r[0], "Builder": r[1], "Description": str(r[2])[:60]+"..."} for r in new_rows]
        return display_data, len(new_rows)
