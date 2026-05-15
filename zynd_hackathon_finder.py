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

def hunt_hackathon_projects(keyword_query, max_results=30):
    """Scans GitHub for recently updated repos tagged with hackathon keywords."""
    
    # We search the README and description for hackathon and agent keywords, sorted by recently updated
    url = f"https://api.github.com/search/repositories?q={keyword_query}+in:readme,description&sort=updated&order=desc&per_page={max_results}"
    
    response = requests.get(url, headers=headers())
    
    if response.status_code != 200:
        raise Exception(f"GitHub Search API Error {response.status_code}. Rate limit exceeded or invalid token.")
        
    data = response.json()
    items = data.get('items', [])
    
    if not items:
        return [], 0

    extracted_projects = []
    today = datetime.now().strftime('%Y-%m-%d')
    
    for item in items:
        # Ignore massive repos that just happen to mention hackathons
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
