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

def snipe_repo_issues(repo_path, num_issues=20):
    """Scrapes recent issues and extracts active complainers/commenters with strict 180-day TTL."""
    
    url = f"https://api.github.com/repos/{repo_path}/issues?state=all&per_page={num_issues}&sort=updated"
    issues = make_request(url)
    
    if issues is None:
        return [], "GitHub API Error: Check repo name, or you may be temporarily rate-limited."
        
    extracted_leads = []
    today = datetime.now().strftime('%Y-%m-%d')
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=180)
    
    # 🌟 UI UX: Progress Tracker
    progress_bar = st.progress(0, text=f"Deploying Issue Sniper to {repo_path}...")
    
    for idx, issue in enumerate(issues):
        progress_bar.progress((idx + 1) / len(issues), text=f"Analyzing issue thread {idx + 1}/{len(issues)}...")
        
        if 'pull_request' in issue:
            continue
            
        # 🛑 TTL WALL 1: Ignore Stale Issues
        updated_at_str = issue.get('updated_at')
        if updated_at_str:
            dt = datetime.strptime(updated_at_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            if dt < cutoff_date:
                continue # The entire issue is dead. Skip it.
                
        issue_title = issue.get('title', 'Unknown Issue')
        issue_url = issue.get('html_url', '')
        
        author = issue.get('user', {})
        author_name = author.get('login', '')
        
        if author_name and 'bot' not in author_name.lower():
            extracted_leads.append([author_name, repo_path, issue_title, "Opened the issue", issue_url, today])
            
        # Check for comments
        if issue.get('comments', 0) > 0:
            comments_url = issue.get('comments_url')
            comments = make_request(comments_url)
            
            if comments:
                for comment in comments:
                    # 🛑 TTL WALL 2: Ignore Stale Comments (Even on active issues)
                    comment_date_str = comment.get('created_at')
                    if comment_date_str:
                        cdt = datetime.strptime(comment_date_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                        if cdt < cutoff_date:
                            continue # This specific comment is too old

                    commenter = comment.get('user', {}).get('login', '')
                    body_snippet = comment.get('body', '')[:100].replace('\n', ' ') + "..."
                    
                    if commenter and 'bot' not in commenter.lower() and commenter != author_name:
                        extracted_leads.append([commenter, repo_path, issue_title, f"Commented: {body_snippet}", issue_url, today])
            
            time.sleep(0.5) # Anti-ban pacing between heavy comment fetches

    progress_bar.empty()

    if not extracted_leads:
        return [], 0

    # Deduplicate (We only want to message a person once per repo extraction)
    df = pd.DataFrame(extracted_leads, columns=['Username', 'Repo', 'Title', 'Context', 'URL', 'Date'])
    df_unique = df.drop_duplicates(subset=['Username'])
    final_leads = df_unique.values.tolist()

    # Push to Google Sheets
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    gclient = gspread.authorize(creds)
    sheet = gclient.open_by_key(SHEET_ID).worksheet("Issue Leads")

    existing_usernames = set(sheet.col_values(1)[1:]) if len(sheet.get_all_values()) > 1 else set()
    new_rows = [row for row in final_leads if row[0] not in existing_usernames]
    
    if new_rows:
        sheet.append_rows(new_rows)

    display_data = [{"Target": r[0], "Issue": r[2], "Context": r[3]} for r in new_rows]
    return display_data, len(new_rows)
