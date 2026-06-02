import requests
import re
from datetime import datetime, timezone, timedelta
import time
import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import random

# Configuration
GITHUB_TOKENS = st.secrets["github"]["tokens"]
SHEET_ID = '11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A'

def make_request(url):
    """Fault-tolerant request handler with token rotation for secondary API checks."""
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

def scan_awesome_directory(repo_path):
    """Scrapes directories, verifies repos are GitHub native, and strictly enforces 180-Day TTL."""
    
    url = f"https://raw.githubusercontent.com/{repo_path}/main/README.md"
    response = requests.get(url)
    
    if response.status_code != 200:
        url = f"https://raw.githubusercontent.com/{repo_path}/master/README.md"
        response = requests.get(url)
        if response.status_code != 200:
            return [], f"Error: Could not find README.md in {repo_path}. Ensure it's a valid public repo."

    content = response.text
    extracted_agents = []
    today = datetime.now().strftime('%Y-%m-%d')
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=180)
    
    # Regex to find markdown links with descriptions
    pattern = re.compile(r'[-*]\s+\[([^\]]+)\]\((http[^\)]+)\)\s*[-:]?\s*(.*)')
    matches = pattern.findall(content)
    
    if not matches:
        return [], "No valid projects found. Ensure it's formatted as a standard markdown list."

    # 🌟 UI UX: Progress Tracker for Live API Verification
    progress_bar = st.progress(0, text=f"Found {len(matches)} links. Verifying 180-Day TTL Activity...")
    
    verified_leads = []
    
    for idx, match in enumerate(matches):
        progress_bar.progress((idx + 1) / len(matches), text=f"Verifying project {idx + 1}/{len(matches)}...")
        
        name = match[0].strip()
        link = match[1].strip()
        description = match[2].strip() or "No description provided"
        
        # 🛑 TTL WALL & GITHUB VALIDATION
        if "github.com/" in link:
            # Extract owner/repo cleanly using regex
            repo_match = re.search(r'github\.com/([^/]+)/([^/\?#]+)', link)
            if repo_match:
                owner = repo_match.group(1)
                repo_name = repo_match.group(2)
                api_url = f"https://api.github.com/repos/{owner}/{repo_name}"
                
                repo_data = make_request(api_url)
                if repo_data:
                    pushed_at_str = repo_data.get('pushed_at')
                    if pushed_at_str:
                        dt = datetime.strptime(pushed_at_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                        # Drop the lead entirely if it hasn't been pushed to in 180 days
                        if dt < cutoff_date:
                            continue
                            
                        # It survived the TTL filter! Add it.
                        verified_leads.append([
                            name,
                            description,
                            f"https://github.com/{owner}/{repo_name}", # Clean URL
                            f"Directory: {repo_path}",
                            today
                        ])
                time.sleep(0.3) # Fast pacing for secondary checks

    progress_bar.empty()

    if not verified_leads:
        return [], "All found projects were dead (failed the 180-day TTL) or not GitHub repositories."

    # Push to Google Sheets
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    gclient = gspread.authorize(creds)
    sheet = gclient.open_by_key(SHEET_ID).worksheet("Directory Leads")

    existing_links = set(sheet.col_values(3)[1:]) if len(sheet.get_all_values()) > 1 else set()
    new_rows = [row for row in verified_leads if row[2] not in existing_links]
    
    if new_rows:
        sheet.append_rows(new_rows)

    display_data = [{"Project": r[0], "Description": r[1][:60]+"...", "Link": r[2]} for r in new_rows]
    return display_data, len(new_rows)
