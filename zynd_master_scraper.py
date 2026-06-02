import time
import requests
import gspread
import streamlit as st
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta

# --- 1. CLOUD SECRETS SETUP ---
GITHUB_TOKENS = st.secrets["github"]["tokens"]
SHEET_ID = '11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A'

# Target Tabs
TARGET_TABS = ["GitHub Leads", "Fork Sniper Leads", "github_stargazer_leads", "Issue Leads", "Contributor Leads"]

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
client = gspread.authorize(creds)

def get_commit_email(username, headers):
    """OSINT trick: Digs into the most recent commit to find hidden email addresses."""
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
    token_index = 0
    total_enriched = 0
    total_stale_skipped = 0
    
    # STRICT 180-DAY TTL ENFORCEMENT
    cutoff_date = datetime.now() - timedelta(days=180)

    with st.status("🚀 Master Enricher Engaged. Connecting to Cloud Database...", expanded=True) as status:
        
        for tab_name in TARGET_TABS:
            try:
                sheet = client.open_by_key(SHEET_ID).worksheet(tab_name)
                records = sheet.get_all_values()
            except Exception as e:
                continue
                
            if not records or len(records) < 2:
                continue

            headers = records[0]
            
            # 🛡️ DYNAMIC HEADER BINDING (Find columns regardless of where they are)
            try:
                col_idx_builder = headers.index('Username') if 'Username' in headers else headers.index('Builder Name') if 'Builder Name' in headers else headers.index('github_username')
                
                # Dynamic mapping for optional target columns
                col_idx_email = headers.index('Email') + 1 if 'Email' in headers else (headers.index('public_email') + 1 if 'public_email' in headers else None)
                col_idx_twitter = headers.index('Twitter') + 1 if 'Twitter' in headers else (headers.index('twitter_or_x') + 1 if 'twitter_or_x' in headers else None)
                col_idx_blog = headers.index('Blog') + 1 if 'Blog' in headers else (headers.index('website') + 1 if 'website' in headers else None)
                col_idx_company = headers.index('Company') + 1 if 'Company' in headers else (headers.index('company') + 1 if 'company' in headers else None)
                
                # Dynamic mapping for the Date column to enforce the 180-day rule
                col_idx_date = None
                for date_variant in ['Date', 'Date Scraped', 'Date Found', 'Date Extracted', 'created_at', 'starred_at']:
                    if date_variant in headers:
                        col_idx_date = headers.index(date_variant)
                        break
                        
            except ValueError:
                status.write(f"⚠️ Missing core 'Username' header in '{tab_name}'. Skipping tab.")
                continue

            status.write(f"📂 **Scanning {tab_name}** ({len(records)-1} records)...")
            cells_to_update = [] 
            progress_bar = st.progress(0)
            total_rows = len(records) - 1

            for i in range(1, len(records)):
                row = records[i]
                sheet_row_number = i + 1 
                progress_bar.progress(int((i / total_rows) * 100))
                
                # --- 🛑 180-DAY TTL CHECK ---
                if col_idx_date and len(row) > col_idx_date:
                    raw_date = str(row[col_idx_date]).strip()
                    if raw_date:
                        try:
                            # Parse standard dates (YYYY-MM-DD) or GitHub ISO formats
                            clean_date = raw_date[:10] 
                            row_date = datetime.strptime(clean_date, '%Y-%m-%d')
                            if row_date < cutoff_date:
                                total_stale_skipped += 1
                                continue # Skip this lead, intent is dead!
                        except ValueError:
                            pass # If date is mangled, assume it's valid and proceed
                
                builder_name = str(row[col_idx_builder]).strip() if len(row) > col_idx_builder else ""
                current_email = str(row[col_idx_email - 1]).strip() if col_idx_email and len(row) > (col_idx_email - 1) else ""
                
                if builder_name and (not current_email or current_email == 'Not public'):
                    
                    success = False
                    attempts = 0
                    
                    # 🛡️ RATE LIMIT RETRY LOOP
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
                                continue # Retry same lead with new token
                                
                            if response.status_code == 200:
                                success = True
                                user_data = response.json()
                                public_email = user_data.get('email')
                                
                                final_email = public_email if public_email else get_commit_email(builder_name, req_headers) or "Not public"
                                
                                if final_email != "Not public":
                                    status.write(f"   🔓 Enriched: **{builder_name}** -> `{final_email}`")
                                
                                # Queue up the payload
                                if col_idx_email: cells_to_update.append(gspread.Cell(sheet_row_number, col_idx_email, final_email))
                                if col_idx_twitter and user_data.get('twitter_username'): cells_to_update.append(gspread.Cell(sheet_row_number, col_idx_twitter, user_data.get('twitter_username')))
                                if col_idx_blog and user_data.get('blog'): cells_to_update.append(gspread.Cell(sheet_row_number, col_idx_blog, user_data.get('blog')))
                                if col_idx_company and user_data.get('company'): cells_to_update.append(gspread.Cell(sheet_row_number, col_idx_company, user_data.get('company')))
                                    
                                token_index += 1
                                time.sleep(0.5) 
                                
                                # 30-cell Batch Blast to Google Sheets
                                if len(cells_to_update) >= 30:
                                    sheet.update_cells(cells_to_update)
                                    total_enriched += len(cells_to_update)
                                    cells_to_update = [] 
                            else:
                                break 
                                
                        except Exception as e:
                            break 
                        
            # Blast remaining data for the tab
            if cells_to_update:
                sheet.update_cells(cells_to_update)
                total_enriched += len(cells_to_update)
            
            progress_bar.empty() 

        # Final Report Out
        status.update(label=f"🎉 Operations Complete! Enriched {total_enriched} data points. Blocked {total_stale_skipped} stale API requests.", state="complete", expanded=True)

if __name__ == "__main__":
    enrich_database()
