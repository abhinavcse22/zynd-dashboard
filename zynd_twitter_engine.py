import time
from datetime import datetime
import gspread
import streamlit as st
from oauth2client.service_account import ServiceAccountCredentials
from tweety import Twitter

SHEET_ID = '11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A'

# High-intent Twitter searches
TWITTER_QUERIES = [
    '("building an AI agent" OR "my AI agent") -filter:links',
    '("LangGraph" OR "CrewAI" OR "Autogen") ("stuck" OR "error" OR "issue")',
    '("built an MCP" OR "n8n workflow")'
]

def run_twitter_scraper():
    # 1. Connect to Google Sheets
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SHEET_ID).worksheet("Twitter Leads")
    
    records = sheet.get_all_records()
    existing_urls = {str(row.get('Post URL', '')) for row in records if row.get('Post URL')}
    new_leads = []
    
    # 2. Authenticate using Strict Dual-Token Bypass
    app = Twitter("session")
    
    # Load both tokens from secrets
    auth_token = st.secrets["twitter"]["auth_token"]
    ct0_token = st.secrets["twitter"]["ct0"]
    
    cookies = {
        "auth_token": auth_token,
        "ct0": ct0_token
    }
    
    print("🐦 Authenticating with Dual Tokens...")
    try:
        # Force-feed the raw cookies to bypass automatic handshake generation
        app.load_cookies(cookies)
    except Exception as e:
        raise Exception(f"Twitter Auth Failed. Both tokens must be from an active, logged-in browser session. Error: {e}")

    # 3. Scrape Users & Posts
    for query in TWITTER_QUERIES:
        try:
            tweets = app.search(query, pages=2) 
            
            for tweet in tweets:
                post_url = f"https://x.com/{tweet.author.username}/status/{tweet.id}"
                if post_url in existing_urls: continue
                
                if getattr(tweet, 'is_retweet', False): continue
                
                score = 8 if 'stuck' in query or 'error' in query else 6
                
                try:
                    date_str = tweet.date.strftime('%Y-%m-%d')
                except:
                    date_str = datetime.now().strftime('%Y-%m-%d')
                
                clean_text = str(tweet.text).replace('\n', ' ')[:500]
                
                new_leads.append([
                    "Build in Public", 
                    "Twitter", 
                    tweet.author.name, 
                    f"https://x.com/{tweet.author.username}", 
                    post_url, 
                    query, 
                    clean_text, 
                    date_str, 
                    score
                ])
                existing_urls.add(post_url)
            
            time.sleep(5) 
            
        except Exception as e:
            print(f"Failed to scrape query {query}: {e}")

    # 4. Push to Database
    if new_leads:
        sheet.append_rows(new_leads)
        return len(new_leads)
    return 0
