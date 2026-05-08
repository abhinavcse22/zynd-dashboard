import time
import requests
import gspread
import streamlit as st
from oauth2client.service_account import ServiceAccountCredentials

# --- 1. CLOUD SECRETS SETUP ---
# Pulling tokens directly from Streamlit's encrypted vault
GITHUB_TOKENS = st.secrets["github"]["tokens"]
SHEET_ID = '11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A'

print("🔌 Connecting to Google Cloud via Streamlit Vault...")
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

# Authenticate using the Streamlit Vault dictionary instead of a file
creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
client = gspread.authorize(creds)
sheet = client.open_by_key(SHEET_ID).worksheet("GitHub Leads")
print("✅ Connected to Zynd Master Database!")

# --- 2. THE COMMIT HACKER ---
def get_commit_email(username, headers):
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
        commits = commit_resp.json()
        
        for commit in commits:
            try:
                email = commit['commit']['author']['email']
                if "noreply.github.com" not in email and "bot@" not in email:
                    return email 
            except KeyError:
                continue
    except Exception: return None
    return None

# --- 3. THE TURBO ENRICHMENT LOOP (BATCH UPDATING) ---
def enrich_database():
    print("📥 Pulling all 15,000+ records...")
    records = sheet.get_all_records()
    
    token_index = 0
    cells_to_update = [] # This is our "Batch Payload"
    batch_count = 0

    print("🚀 TURBO MODE ENGAGED: Hacking commits & batching updates...")

    for i, row in enumerate(records):
        sheet_row_number = i + 2 
        
        builder_name = str(row.get('Builder Name', '')).strip()
        current_email = str(row.get('Email', '')).strip()
        
        if builder_name and (not current_email or current_email == 'Not public'):
            
            current_token = GITHUB_TOKENS[token_index % len(GITHUB_TOKENS)]
            headers = {'Authorization': f'token {current_token}', 'Accept': 'application/vnd.github.v3+json'}
            
            url = f"https://api.github.com/users/{builder_name}"
            
            try:
                response = requests.get(url, headers=headers, timeout=10)
                
                if response.status_code == 403:
                    print("⚠️ Rate limit hit. Rotating token immediately...")
                    token_index += 1 
                    continue
                    
                if response.status_code == 200:
                    user_data = response.json()
                    public_email = user_data.get('email')
                    
                    final_email = ""
                    if public_email:
                        final_email = public_email
                        print(f"   ✅ PUBLIC: {builder_name} -> {final_email}")
                    else:
                        hidden_email = get_commit_email(builder_name, headers)
                        if hidden_email:
                            final_email = hidden_email
                            print(f"   🔓 HACKED: {builder_name} -> {final_email}")
                        else:
                            final_email = "Not public"
                    
                    # Add data to our "Batch Payload" instead of updating immediately
                    cells_to_update.append(gspread.Cell(sheet_row_number, 10, final_email))
                    
                    if user_data.get('twitter_username'):
                        cells_to_update.append(gspread.Cell(sheet_row_number, 11, user_data.get('twitter_username')))
                    if user_data.get('blog'):
                        cells_to_update.append(gspread.Cell(sheet_row_number, 12, user_data.get('blog')))
                    if user_data.get('company'):
                        cells_to_update.append(gspread.Cell(sheet_row_number, 13, user_data.get('company')))
                        
                    token_index += 1
                    time.sleep(0.5) # TURBO SPEED DELAY (0.5s instead of 1.0s)
                    
                    # Every time we get 30 updates, blast them to Google Sheets all at once!
                    if len(cells_to_update) >= 30:
                        sheet.update_cells(cells_to_update)
                        batch_count += len(cells_to_update)
                        print(f"⚡ BLASTED {len(cells_to_update)} data points directly to Google Sheets!")
                        cells_to_update = [] # Clear the payload for the next batch
                    
            except Exception as e:
                pass # Ignore random connection drops and keep moving
                
    # Blast any leftover data at the end
    if cells_to_update:
        sheet.update_cells(cells_to_update)
        batch_count += len(cells_to_update)
        
    print(f"\n🎉 Enrichment Complete! Placed {batch_count} new data points into your dashboard.")

if __name__ == "__main__":
    enrich_database()