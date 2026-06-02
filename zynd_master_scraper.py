import time
import requests
import gspread
import streamlit as st
import concurrent.futures
import random
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta

# --- 1. CLOUD SECRETS SETUP ---
GITHUB_TOKENS = st.secrets["github"]["tokens"]
SHEET_ID = '11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A'
TARGET_TABS = ["GitHub Leads", "Fork Sniper Leads", "github_stargazer_leads", "Issue Leads", "Contributor Leads"]

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
client = gspread.authorize(creds)

def get_commit_email(username, headers):
    """Dual-Layer OSINT: Safely extracts hidden emails without the Fork Trap."""
    
    # --- LAYER 1: The Events Hack (Fastest) ---
    events_url = f"https://api.github.com/users/{username}/events/public?per_page=10"
    try:
        resp = requests.get(events_url, headers=headers, timeout=5)
        if resp.status_code == 200:
            for event in resp.json():
                if event['type'] == 'PushEvent':
                    for commit in event.get('payload', {}).get('commits', []):
                        email = commit.get('author', {}).get('email', '')
                        if email and "noreply.github.com" not in email and "bot@" not in email:
                            return email
    except Exception: 
        pass 

    # --- LAYER 2: The Repo Deep-Dive (Strictly filtered by owner/author) ---
    repos_url = f"https://api.github.com/users/{username}/repos?type=owner&sort=pushed&per_page=1"
    try:
        repo_resp = requests.get(repos_url, headers=headers, timeout=5)
        if repo_resp.status_code == 200 and repo_resp.json():
            repo_name = repo_resp.json()[0]['name']
            
            commits_url = f"https://api.github.com/repos/{username}/{repo_name}/commits?author={username}&per_page=3"
            commit_resp = requests.get(commits_url, headers=headers, timeout=5)
            
            if commit_resp.status_code == 200:
                for commit in commit_resp.json():
                    try:
                        email = commit['commit']['author']['email']
                        if email and "noreply.github.com" not in email and "bot@" not in email:
                            return email 
                    except KeyError: 
                        continue
    except Exception: 
        pass

    return None

def fetch_github_data_thread(builder_name, sheet_row_number, col_indices):
    """The individual thread task. Grabs a token, hits GitHub, returns cells."""
    col_idx_email, col_idx_twitter, col_idx_blog, col_idx_company = col_indices
    cells = []
    log_msg = None
    
    attempts = 0
    while attempts < 3:
        token = random.choice(GITHUB_TOKENS)
        headers = {'Authorization': f'token {token}', 'Accept': 'application/vnd.github.v3+json'}
        url = f"https://api.github.com/users/{builder_name}"
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code in [403, 429]:
                attempts += 1
                time.sleep(1 + random.uniform(0, 1)) 
                continue 
                
            if response.status_code == 200:
                user_data = response.json()
                public_email = user_data.get('email')
                
                final_email = public_email if public_email else get_commit_email(builder_name, headers) or "Not public"
                
                if final_email != "Not public":
                    log_msg = f"   🔓 Hacked/Enriched: **{builder_name}** -> `{final_email}`"
                
                if col_idx_email: cells.append(gspread.Cell(sheet_row_number, col_idx_email, final_email))
                if col_idx_twitter and user_data.get('twitter_username'): cells.append(gspread.Cell(sheet_row_number, col_idx_twitter, user_data.get('twitter_username')))
                if col_idx_blog and user_data.get('blog'): cells.append(gspread.Cell(sheet_row_number, col_idx_blog, user_data.get('blog')))
                if col_idx_company and user_data.get('company'): cells.append(gspread.Cell(sheet_row_number, col_idx_company, user_data.get('company')))
                break 
            else:
                break 
        except Exception:
            break
            
    return cells, log_msg

def enrich_database():
    total_enriched = 0
    total_stale_skipped = 0
    cutoff_date = datetime.now() - timedelta(days=180)

    with st.status("🚀 Multi-Threaded Enricher Engaged. Spinning up Swarm...", expanded=True) as status:
        
        for tab_name in TARGET_TABS:
            try:
                sheet = client.open_by_key(SHEET_ID).worksheet(tab_name)
                records = sheet.get_all_values()
            except Exception:
                continue
                
            if not records or len(records) < 2:
                continue

            headers = records[0]
            
            try:
                col_idx_builder = headers.index('Username') if 'Username' in headers else headers.index('Builder Name') if 'Builder Name' in headers else headers.index('github_username')
                col_idx_email = headers.index('Email') + 1 if 'Email' in headers else (headers.index('public_email') + 1 if 'public_email' in headers else None)
                col_idx_twitter = headers.index('Twitter') + 1 if 'Twitter' in headers else (headers.index('twitter_or_x') + 1 if 'twitter_or_x' in headers else None)
                col_idx_blog = headers.index('Blog') + 1 if 'Blog' in headers else (headers.index('website') + 1 if 'website' in headers else None)
                col_idx_company = headers.index('Company') + 1 if 'Company' in headers else (headers.index('company') + 1 if 'company' in headers else None)
                
                col_indices = (col_idx_email, col_idx_twitter, col_idx_blog, col_idx_company)
                
                col_idx_date = None
                for date_variant in ['Date', 'Date Scraped', 'Date Found', 'Date Extracted', 'created_at', 'starred_at']:
                    if date_variant in headers:
                        col_idx_date = headers.index(date_variant)
                        break
            except ValueError:
                status.write(f"⚠️ Missing core 'Username' header in '{tab_name}'. Skipping.")
                continue

            # 1. QUEUE BUILDING (Filter for 180-day TTL & missing emails first)
            tasks = []
            for i in range(1, len(records)):
                row = records[i]
                sheet_row_number = i + 1 
                
                if col_idx_date and len(row) > col_idx_date:
                    raw_date = str(row[col_idx_date]).strip()
                    if raw_date:
                        try:
                            clean_date = raw_date[:10] 
                            if datetime.strptime(clean_date, '%Y-%m-%d') < cutoff_date:
                                total_stale_skipped += 1
                                continue
                        except ValueError:
                            pass 
                
                builder_name = str(row[col_idx_builder]).strip() if len(row) > col_idx_builder else ""
                current_email = str(row[col_idx_email - 1]).strip() if col_idx_email and len(row) > (col_idx_email - 1) else ""
                
                if builder_name and (not current_email or current_email == 'Not public'):
                    tasks.append((builder_name, sheet_row_number))

            if not tasks:
                continue

            status.write(f"📂 **{tab_name}**: Deploying swarm for {len(tasks)} active targets...")
            progress_bar = st.progress(0)
            cells_to_update = []
            
            # 2. THE CONCURRENT SWARM (Multithreading)
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                future_to_task = {executor.submit(fetch_github_data_thread, t[0], t[1], col_indices): t for t in tasks}
                
                for completed_count, future in enumerate(concurrent.futures.as_completed(future_to_task)):
                    progress_bar.progress(int(((completed_count + 1) / len(tasks)) * 100))
                    
                    try:
                        result_cells, log_msg = future.result()
                        if log_msg:
                            status.write(log_msg)
                        if result_cells:
                            cells_to_update.extend(result_cells)
                            
                        # Batch Push to Sheets (Protecting Google API Limits)
                        if len(cells_to_update) >= 30:
                            sheet.update_cells(cells_to_update)
                            total_enriched += len(cells_to_update)
                            cells_to_update = []
                    except Exception:
                        pass
                        
            # Push remaining cells
            if cells_to_update:
                sheet.update_cells(cells_to_update)
                total_enriched += len(cells_to_update)
                
            progress_bar.empty()

        status.update(label=f"🎉 Turbo Enrichment Complete! Mapped {total_enriched} data points. Blocked {total_stale_skipped} stale queries.", state="complete", expanded=True)

if __name__ == "__main__":
    enrich_database()
