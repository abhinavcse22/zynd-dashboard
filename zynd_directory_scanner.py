import requests
import re
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials

SHEET_ID = '11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A'

def scan_awesome_directory(repo_path):
    """Scrapes 'Awesome' GitHub directories to extract established AI agent projects."""
    
    # We hit the raw markdown file directly to bypass UI scraping issues
    url = f"https://raw.githubusercontent.com/{repo_path}/main/README.md"
    response = requests.get(url)
    
    if response.status_code != 200:
        # Fallback to master branch if main doesn't exist
        url = f"https://raw.githubusercontent.com/{repo_path}/master/README.md"
        response = requests.get(url)
        if response.status_code != 200:
            return [], f"Error: Could not find README.md in {repo_path}. Ensure it's a valid public repo."

    content = response.text
    extracted_agents = []
    today = datetime.now().strftime('%Y-%m-%d')
    
    # Regex to find markdown links with descriptions: - [Project Name](link) - Description
    # This is the standard format for almost all directory lists
    pattern = re.compile(r'[-*]\s+\[([^\]]+)\]\((http[^\)]+)\)\s*[-:]?\s*(.*)')
    matches = pattern.findall(content)
    
    for match in matches:
        name = match[0].strip()
        link = match[1].strip()
        description = match[2].strip()
        
        # Filter out table of contents or generic internal links
        if "github.com" in link or "http" in link:
            extracted_agents.append([
                name,
                description if description else "No description provided",
                link,
                f"Directory: {repo_path}",
                today
            ])

    if not extracted_agents:
        return [], "No valid projects found in this directory. Ensure it's formatted as a standard markdown list."

    # Push to Google Sheets
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    gclient = gspread.authorize(creds)
    sheet = gclient.open_by_key(SHEET_ID).worksheet("Directory Leads")

    existing_links = set(sheet.col_values(3)[1:]) if len(sheet.get_all_values()) > 1 else set()
    new_rows = [row for row in extracted_agents if row[2] not in existing_links]
    
    if new_rows:
        sheet.append_rows(new_rows)

    display_data = [{"Project": r[0], "Description": r[1][:60]+"...", "Link": r[2]} for r in new_rows]
    return display_data, len(new_rows)
