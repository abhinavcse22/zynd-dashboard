import requests
import pandas as pd
from datetime import datetime
import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Configuration
GITHUB_TOKEN = st.secrets.get("github", {}).get("token", "")
SHEET_ID = '11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A'

def headers():
    if GITHUB_TOKEN:
        return {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    return {"Accept": "application/vnd.github.v3+json"}

def snipe_repo_issues(repo_path, num_issues=20):
    """Scrapes recent closed/open issues and extracts active complainers/commenters."""
    
    # 1. Fetch recent issues
    issues_url = f"https://api.github.com/repos/{repo_path}/issues?state=all&per_page={num_issues}&sort=updated"
    response = requests.get(issues_url, headers=headers())
    
    if response.status_code != 200:
        raise Exception(f"GitHub API Error: {response.status_code} - Check repo name or token.")
        
    issues = response.json()
    extracted_leads = []
    today = datetime.now().strftime('%Y-%m-%d')
    
    for issue in issues:
        # Skip Pull Requests (they are mixed into the issues endpoint)
        if 'pull_request' in issue:
            continue
            
        issue_title = issue.get('title', 'Unknown Issue')
        issue_url = issue.get('html_url', '')
        
        # Grab the person who opened the issue
        author = issue.get('user', {})
        author_name = author.get('login', '')
        
        if author_name and 'bot' not in author_name.lower():
            extracted_leads.append([
                author_name,          # Username
                repo_path,            # Target Repo
                issue_title,          # Issue Title
                "Opened the issue",   # Pain Point context
                issue_url,            # Issue URL
                today                 # Date Found
            ])
            
        # 2. Fetch people who are commenting on the issue
        if issue.get('comments', 0) > 0:
            comments_url = issue.get('comments_url')
            comments_res = requests.get(comments_url, headers=headers())
            if comments_res.status_code == 200:
                for comment in comments_res.json():
                    commenter = comment.get('user', {}).get('login', '')
                    body_snippet = comment.get('body', '')[:100].replace('\n', ' ') + "..." # Get first 100 chars
                    
                    # Ignore bots and repo owners (we don't want to pitch the LangChain team)
                    if commenter and 'bot' not in commenter.lower():
                        extracted_leads.append([
                            commenter,
                            repo_path,
                            issue_title,
                            f"Commented: {body_snippet}",
                            issue_url,
                            today
                        ])

    if not extracted_leads:
        return [], 0

    # 3. Deduplicate (We only want to message a person once per repo)
    df = pd.DataFrame(extracted_leads, columns=['Username', 'Repo', 'Title', 'Context', 'URL', 'Date'])
    df_unique = df.drop_duplicates(subset=['Username'])
    final_leads = df_unique.values.tolist()

    # 4. Push to Google Sheets
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    gclient = gspread.authorize(creds)
    sheet = gclient.open_by_key(SHEET_ID).worksheet("Issue Leads")

    # Prevent duplicates in the database
    existing_usernames = set(sheet.col_values(1)[1:]) if len(sheet.get_all_values()) > 1 else set()
    new_rows = [row for row in final_leads if row[0] not in existing_usernames]
    
    if new_rows:
        sheet.append_rows(new_rows)

    display_data = [{"Target": r[0], "Issue": r[2], "Context": r[3]} for r in new_rows]
    return display_data, len(new_rows)
