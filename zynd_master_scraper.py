import time
import requests
import gspread
import streamlit as st
from oauth2client.service_account import ServiceAccountCredentials

# --- 1. CLOUD SECRETS SETUP ---
GITHUB_TOKENS = st.secrets["github"]["tokens"]
SHEET_ID = '11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A'

# Tabs that contain GitHub Usernames needing enrichment
TARGET_TABS = ["GitHub Leads", "Fork Sniper Leads", "github_stargazer_leads", "Issue Leads", "Contributor Leads"]

print("🔌 Connecting to Google Cloud via Streamlit Vault...")
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
client = gspread.authorize(creds)

def get_commit_email(username, headers):
    """Digs into the most recent commit to find non-public email addresses."""
    repos_url = f"https://api.github.com/users/{username}/repos?sort=updated&per_page=1"
    try:
        repo_resp = requests.get(repos_url, headers=headers, timeout=10)
        if repo_resp.status_code != 200: return None
        repos = repo_resp.json()
        if not repos: return None
            
        repo_name = repos[0]['name']
        commits_url = f"https://api.github.com/repos/{username}/{repo_name}/commits?per_page=3"
        
        commit_resp = requests.get(commits_url, headers=headers, timeout=10)
        if commit_resp.status_code != 200: return None
        
        for commit in commit_resp.json():
            try:
                email = commit['commit']['author']['email']
                if "noreply.github.com" not in email and "bot@" not in email:
                    return email 
            except KeyError:
                continue
    except Exception: return None
    return None

def enrich_database():
    print("🚀 MASTER ENRICHER ENGAGED: Scanning all database tabs...")
    token_index = 0
    total_enriched = 0

    for tab_name in TARGET_TABS:
        try:
            sheet = client.open_by_key(SHEET_ID).worksheet(tab_name)
            records = sheet.get_all_values()
        except Exception as e:
            print(f"⚠️ Skipping tab '{tab_name}' (Not found or error).")
            continue
            
        if not records or len(records) < 2:
            continue

        print(f"\n📂 Processing Tab: {tab_name} ({len(records)-1} rows)")
        headers = records[0]
        
        # 🛡️ DYNAMIC HEADER BINDING (Finds the right column no matter where it is)
        try:
            # Handle slight variations in how you named columns across different tabs
            col_idx_builder = headers.index('Username') if 'Username' in headers else headers.index('Builder Name') if 'Builder Name' in headers else headers.index('github_username')
            
            # Find target columns. If they don't exist in this tab, we will skip writing them to avoid crashes
            col_idx_email = headers.index('Email') + 1 if 'Email' in headers else (headers.index('public_email') + 1 if 'public_email' in headers else None)
            col_idx_twitter = headers.index('Twitter') + 1 if 'Twitter' in headers else (headers.index('twitter_or_x') + 1 if 'twitter_or_x' in headers else None)
            col_idx_blog = headers.index('Blog') + 1 if 'Blog' in headers else (headers.index('website') + 1 if 'website' in headers else None)
            col_idx_company = headers.index('Company') + 1 if 'Company' in headers else (headers.index('company') + 1 if 'company' in headers else None)
        except ValueError:
            print(f"⚠️ Tab '{tab_name}' is missing required Username/Email headers. Skipping.")
            continue

        cells_to_update = [] 

        for i in range(1, len(records)):
            row = records[i]
            sheet_row_number = i + 1 
            
            builder_name = str(row[col_idx_builder]).strip() if len(row) > col_idx_builder else ""
            current_email = str(row[col_idx_email - 1]).strip() if col_idx_email and len(row) > (col_idx_email - 1) else ""
            
            # Only enrich if we have a username and the email is empty or generic
            if builder_name and (not current_email or current_email == 'Not public'):
                
                success = False
                attempts = 0
                
                # 🛡️ RETRY LOOP: Never drop a lead due to rate limits
                while not success and attempts < len(GITHUB_TOKENS):
                    current_token = GITHUB_TOKENS[token_index % len(GITHUB_TOKENS)]
                    req_headers = {'Authorization': f'token {current_token}', 'Accept': 'application/vnd.github.v3+json'}
                    url = f"https://api.github.com/users/{builder_name}"
                    
                    try:
                        response = requests.get(url, headers=req_headers, timeout=10)
                        
                        if response.status_code in [403, 429]:
                            token_index += 1 
                            attempts += 1
                            time.sleep(1)
                            continue # Try the exact same lead again with new token
                            
                        if response.status_code == 200:
                            success = True
                            user_data = response.json()
                            public_email = user_data.get('email')
                            
                            final_email = public_email if public_email else get_commit_email(builder_name, req_headers) or "Not public"
                            
                            if final_email != "Not public":
                                print(f"   🔓 Hacked/Found: {builder_name} -> {final_email}")
                            
                            # Append to batch payload ONLY if the column actually exists in this specific tab
                            if col_idx_email: cells_to_update.append(gspread.Cell(sheet_row_number, col_idx_email, final_email))
                            if col_idx_twitter and user_data.get('twitter_username'): cells_to_update.append(gspread.Cell(sheet_row_number, col_idx_twitter, user_data.get('twitter_username')))
                            if col_idx_blog and user_data.get('blog'): cells_to_update.append(gspread.Cell(sheet_row_number, col_idx_blog, user_data.get('blog')))
                            if col_idx_company and user_data.get('company'): cells_to_update.append(gspread.Cell(sheet_row_number, col_idx_company, user_data.get('company')))
                                
                            token_index += 1
                            time.sleep(0.5) 
                            
                            # Fire the payload at 30 cells to prevent Google Sheet timeout
                            if len(cells_to_update) >= 30:
                                sheet.update_cells(cells_to_update)
                                total_enriched += len(cells_to_update)
                                cells_to_update = [] 
                        else:
                            break # 404 error, user doesn't exist, move on
                            
                    except Exception as e:
                        break # Connection error, move on
                    
        # Blast remaining data for the tab
        if cells_to_update:
            sheet.update_cells(cells_to_update)
            total_enriched += len(cells_to_update)
            
    print(f"\n🎉 Multi-Tab Enrichment Complete! Safely mapped {total_enriched} data points into your CRM.")

if __name__ == "__main__":
    enrich_database()
