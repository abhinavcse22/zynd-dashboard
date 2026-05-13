import requests
import time
import random
from datetime import datetime
import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- CONFIGURATION ---
GITHUB_TOKENS = st.secrets["github"]["tokens"]
SHEET_ID = '11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A'

def get_headers():
    """Randomly selects a token from your pool to bypass rate limits."""
    token = random.choice(GITHUB_TOKENS)
    return {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}

def extract_hidden_email(username):
    """The OSINT trick: Digs into public events to find hidden commit emails."""
    url = f"https://api.github.com/users/{username}/events/public"
    response = requests.get(url, headers=get_headers())
    
    if response.status_code == 200:
        events = response.json()
        for event in events:
            if event['type'] == 'PushEvent':
                commits = event.get('payload', {}).get('commits', [])
                for commit in commits:
                    author_email = commit.get('author', {}).get('email', '')
                    if author_email and "noreply.github.com" not in author_email:
                        return author_email, "Hidden (Commit Hack)"
    return "None", "Not Found"

def run_fork_sniper(target_repo, max_results=20):
    """Finds devs who forked a repo, extracts data, and pushes to Google Sheets."""
    url = f"https://api.github.com/repos/{target_repo}/forks?sort=newest&per_page={max_results}"
    response = requests.get(url, headers=get_headers())
    
    if response.status_code != 200:
        raise Exception(f"GitHub API Error: {response.text}")
        
    forks = response.json()
    sniped_leads = []
    date_str = datetime.now().strftime('%Y-%m-%d')
    
    for fork in forks:
        owner = fork['owner']
        username = owner['login']
        profile_url = owner['html_url']
        
        user_response = requests.get(f"https://api.github.com/users/{username}", headers=get_headers()).json()
        name = user_response.get('name', username)
        bio = user_response.get('bio', '')
        twitter = user_response.get('twitter_username', '')
        
        # OSINT Email Router (Public vs Hidden)
        email = user_response.get('email')
        email_type = "Public (Bio)" if email else "Not Found"
        
        if not email:
            email, email_type = extract_hidden_email(username)
            
        time.sleep(0.5) 
        
        sniped_leads.append([
            f"Forked {target_repo}",        # Source
            username,                       # Username
            str(name),                      # Name
            profile_url,                    # Profile URL
            email,                          # Email
            email_type,                     # Email Type
            f"https://x.com/{twitter}" if twitter else "None", # Twitter
            str(bio).replace('\n', ' '),    # Bio
            date_str                        # Date
        ])

    # --- PUSH TO GOOGLE SHEETS ---
    if not sniped_leads:
        return []

    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SHEET_ID).worksheet("Fork Sniper Leads")
    
    # Deduplication: Prevent saving the same profile twice
    existing_records = sheet.get_all_values()
    existing_urls = set()
    if len(existing_records) > 0:
        url_idx = 3 # 'Profile URL' is the 4th column (index 3)
        existing_urls = {str(row[url_idx]).lower() for row in existing_records[1:] if len(row) > url_idx}
        
    new_rows_to_add = [row for row in sniped_leads if row[3].lower() not in existing_urls]
    
    if new_rows_to_add:
        sheet.append_rows(new_rows_to_add)
        
    # Return the data as a list of dictionaries so the Streamlit dashboard can still draw the table
    display_data = []
    for row in sniped_leads:
        display_data.append({
            "Intent Source": row[0], "Username": row[1], "Name": row[2], 
            "Profile": row[3], "Email": row[4], "Email Type": row[5], "Twitter": row[6]
        })
        
    return display_data, len(new_rows_to_add)
