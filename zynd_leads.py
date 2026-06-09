import requests
import time
from datetime import datetime
from dateutil.relativedelta import relativedelta
import gspread
import streamlit as st
from oauth2client.service_account import ServiceAccountCredentials

# --- 1. GOOGLE SHEETS CLOUD SETUP ---
SHEET_ID = '11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A'

print("🔌 Connecting to Google Cloud via Streamlit Vault...")
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

# Pull credentials directly from Streamlit Secrets, NOT a local file
creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
client = gspread.authorize(creds)
sheet = client.open_by_key(SHEET_ID).worksheet("GitHub Leads")
print("✅ Connected to Zynd Master Database (GitHub Tab)!")

# --- 2. YOUR CONFIGURATION ---
# Pulling tokens directly from Streamlit's encrypted vault
GITHUB_TOKENS = st.secrets["github"]["tokens"]

six_months_ago = (datetime.now() - relativedelta(months=6)).strftime('%Y-%m-%d')

QUERIES = [
    f'topic:ai-agent pushed:>{six_months_ago}',
    f'topic:autonomous-agent pushed:>{six_months_ago}',
    f'"langgraph" "agent" in:readme pushed:>{six_months_ago}',
    f'"crewai" "agent" in:readme pushed:>{six_months_ago}'
]

# --- 3. SAFETY & SCORING ---
def rate_github_lead(tech, what):
    score = 5 
    tech_lower = tech.lower()
    what_lower = what.lower()
    if any(x in tech_lower for x in ['langgraph', 'crewai', 'autogen', 'mcp']): score += 3
    elif 'agent' in tech_lower: score += 1
    if 'agent' in what_lower or 'swarm' in what_lower: score += 1
    return min(score, 10)

def generate_outreach_angle(name, project_name, topics, language):
    tech = "AI agents"
    if "langgraph" in topics: tech = "LangGraph"
    elif "crewai" in topics: tech = "CrewAI"
    elif "mcp" in topics: tech = "MCP servers"
    elif language: tech = language
    return f"Hey {name}, I noticed your work on {project_name}. Building with {tech} right now is super high-leverage. I'm working on Zynd to help agents like yours get discovered. Would love your feedback!"

# --- 4. THE MAIN ENGINE (WITH TOKEN ROTATION) ---
def harvest_leads():
    print("📥 Pulling existing GitHub leads to prevent duplicates...")
    existing_records = sheet.get_all_records()
    seen_urls = {str(row.get('Project URL', '')) for row in existing_records if row.get('Project URL')}
    
    new_leads_for_sheets = []
    token_index = 0  # This keeps track of which token we are currently using

    for query in QUERIES:
        print(f"🔍 Searching: {query}")
        page = 1
        
        while page <= 5: # Limit to 5 pages per query for safety
            # Round-Robin: Pick the current token from the list
            current_token = GITHUB_TOKENS[token_index % len(GITHUB_TOKENS)]
            headers = {'Authorization': f'token {current_token}', 'Accept': 'application/vnd.github.v3+json'}
            
            url = f"https://api.github.com/search/repositories?q={query}&sort=updated&order=desc&per_page=100&page={page}"
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                items = response.json().get('items', [])
                if not items: break 
                
                for item in items:
                    project_url = item['html_url']
                    if project_url in seen_urls: continue
                    
                    builder_name = item['owner']['login']
                    project_name = item['name']
                    topics = item.get('topics', [])
                    language = item.get('language') or 'N/A'
                    tech_used = f"{language}, {', '.join(topics)}" if topics else language
                    desc = item['description'] or "No description provided."
                    
                    score = rate_github_lead(tech_used, desc)
                    angle = generate_outreach_angle(builder_name, project_name, topics, language)
                    
                    # Columns exactly matching your Google Sheet
                    row_data = [
                        "GitHub", builder_name, item['owner']['html_url'], "", project_name, project_url, 
                        tech_used, desc, angle, "", "", "", "", score
                    ]
                    
                    new_leads_for_sheets.append(row_data)
                    seen_urls.add(project_url)
                
                print(f"   ✓ Fetched page {page} ({len(items)} items)")
                page += 1
                time.sleep(2) # Safety delay
                
            elif response.status_code == 403:
                # If a token hits the limit, switch to the next one and try the same page again
                print(f"⚠️ Rate limit hit. Rotating to next token...")
                token_index += 1
                time.sleep(2)
            elif response.status_code == 422: 
                break
            else: 
                time.sleep(5)

    if new_leads_for_sheets:
        print(f"⬆️ Uploading {len(new_leads_for_sheets)} BRAND NEW GitHub leads to Google Sheets...")
        sheet.append_rows(new_leads_for_sheets)
        print("🎉 Success! Your team's dashboard is now updated.")
    else:
        print("⚠️ No new GitHub leads found today.")

if __name__ == "__main__":
    harvest_leads()
