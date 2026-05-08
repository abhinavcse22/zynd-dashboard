import requests
import time
from datetime import datetime
import gspread
import streamlit as st
from oauth2client.service_account import ServiceAccountCredentials

# --- 1. GOOGLE SHEETS CLOUD SETUP ---
SHEET_ID = '11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A'

def get_sheet():
    """Connects to the sheet using Streamlit Cloud Secrets."""
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    # Pulling credentials directly from the vault we set up
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    client = gspread.authorize(creds)
    return client.open_by_key(SHEET_ID).worksheet("Reddit Leads")

# --- 2. CONFIGURATION ---
INTENT_MATRIX = {
    "Competitor Mention (Poach them)": ['moltbook', 'openclaw', 'langgraph', 'autogen'],
    "Pain Point (Zynd fixes this)": ['agent got stuck', 'agent hallucinated', 'issue with my agent', 'crewai loop', 'langchain error', "agents can't communicate"],
    "Agent Network/Swarm (Direct match)": ['agentic network', 'multi-agent system', 'agents talking to each other', 'agent swarm', 'agent ecosystem'],
    "Agent Builders (Recruit them)": ['custom tool for my agent', 'built an mcp', 'my ai agent successfully', 'built an autonomous agent', 'smolagents']
}

def rate_reddit_lead(intent, match):
    score = 5 
    intent_lower = intent.lower()
    match_lower = match.lower()
    if 'competitor' in intent_lower or 'pain point' in intent_lower: score += 4
    elif 'direct match' in intent_lower or 'network' in intent_lower: score += 3
    else: score += 1
    if 'agent' in match_lower or 'langchain' in match_lower or 'crewai' in match_lower: score += 1
    return min(score, 10)

def run_reddit_scraper():
    """The main function called by your Dashboard buttons."""
    sheet = get_sheet()
    
    print("📥 Pulling existing leads from Google Sheets...")
    records = sheet.get_all_records()
    existing_urls = {str(row.get('Post URL', '')) for row in records if row.get('Post URL')}
    
    new_leads_for_sheets = []
    headers = {
        'User-Agent': 'Mozilla/5.0 (ZyndHarvester/1.0; contact: abhinav@zynd.ai)'
    }

    print(f"\n🚀 Starting Daily Engine. Scanning Reddit...")

    for intent_category, queries in INTENT_MATRIX.items():
        for query in queries:
            print(f"🔍 Searching: {query}")
            url = "https://www.reddit.com/search.json"
            params = {'q': query, 'sort': 'new', 't': 'day', 'limit': 100}
            
            try:
                response = requests.get(url, headers=headers, params=params)
                if response.status_code == 200:
                    children = response.json().get('data', {}).get('children', [])
                    for child in children:
                        post = child['data']
                        post_url = f"https://reddit.com{post.get('permalink', '')}"
                        
                        if post_url in existing_urls:
                            continue
                            
                        match = query
                        score = rate_reddit_lead(intent_category, match)
                        snippet = (post.get('title', '') + " - " + post.get('selftext', ''))[:150].replace('\n', ' ')
                        date_str = datetime.fromtimestamp(post.get('created_utc', 0)).strftime('%Y-%m-%d')
                        author = f"u/{post.get('author', 'Unknown')}"
                        profile_url = f"https://reddit.com/user/{post.get('author', '')}"
                        
                        row_data = [intent_category, "Reddit", author, profile_url, post_url, match, snippet, date_str, score]
                        new_leads_for_sheets.append(row_data)
                        existing_urls.add(post_url)
                        
                elif response.status_code == 429:
                    print("⚠️ Reddit rate limit. Pausing...")
                    time.sleep(10)
            except Exception as e:
                print(f"⚠️ Request error: {e}")
                
            time.sleep(2) # Safety delay between queries

    if new_leads_for_sheets:
        print(f"⬆️ Uploading {len(new_leads_for_sheets)} BRAND NEW leads...")
        sheet.append_rows(new_leads_for_sheets)
        print("🎉 Success! Reddit leads updated.")
    else:
        print("⚠️ No new leads today.")

if __name__ == "__main__":
    run_reddit_scraper()
