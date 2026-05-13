import requests
import time
from datetime import datetime
import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials

SHEET_ID = '11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A'

def run_reddit_scraper():
    # 1. Connect to Database using your secure Cloud Secrets
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SHEET_ID).worksheet("Reddit Leads")
    
    # 2. Extract existing URLs to prevent duplicate scraping
    raw_data = sheet.get_all_values()
    existing_urls = set()
    if len(raw_data) > 0 and 'Post URL' in raw_data[0]:
        url_idx = raw_data[0].index('Post URL')
        existing_urls = {str(row[url_idx]) for row in raw_data[1:] if len(row) > url_idx and row[url_idx]}

    # 3. The Target Matrix
    subreddits = ['LangChain', 'crewAI', 'AutoGPT', 'LocalLLaMA', 'artificial']
    pain_keywords = ['error', 'stuck', 'help', 'alternative', 'frustrated', 'issue', 'bug', 'fail']
    
    # 4. Aggressive Header Forging (Added Accept headers to look more human)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/javascript, */*; q=0.01'
    }

    new_leads = []
    
    for sub in subreddits:
        # THE HACK: Rip the raw 'new' feed instead of using the search endpoint
        url = f"https://www.reddit.com/r/{sub}/new.json?limit=50"
        
        try:
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                posts = data.get('data', {}).get('children', [])
                
                for post in posts:
                    post_data = post['data']
                    post_url = f"https://www.reddit.com{post_data['permalink']}"
                    
                    if post_url in existing_urls:
                        continue
                        
                    title = post_data.get('title', '')
                    text = post_data.get('selftext', '')
                    author = post_data.get('author', 'unknown')
                    
                    if author == '[deleted]':
                        continue
                        
                    # 5. Local Python Filtering (Bypasses Reddit's search filters)
                    combined_text = (title + " " + text).lower()
                    
                    # Check if any pain keyword exists in the post
                    found_keywords = [kw for kw in pain_keywords if kw in combined_text]
                    
                    if not found_keywords:
                        continue # Skip this post if everything is fine
                        
                    # Dynamic Lead Scoring based on keyword density
                    score = 6 + len(found_keywords) 
                    if 'agent' in combined_text: score += 2
                    score = min(score, 10) # Cap at 10
                    
                    date_str = datetime.now().strftime('%Y-%m-%d')
                    
                    # Package the payload
                    new_leads.append([
                        "Reddit Raw Feed Hack",  # Source
                        f"r/{sub}",              # Subreddit
                        f"u/{author}",           # Author
                        title,                   # Post Title
                        text.replace('\n', ' ')[:500], # Post Text
                        post_url,                # Post URL
                        date_str,                # Date
                        score                    # Lead Score (1-10)
                    ])
                    existing_urls.add(post_url)
            else:
                print(f"⚠️ Reddit blocked r/{sub} with HTTP Code: {response.status_code}")
                
        except Exception as e:
            print(f"❌ Failed to scrape r/{sub}: {e}")
        
        # 2-second pause. DO NOT remove this, or Reddit will instantly ban the Streamlit IP
        time.sleep(2) 

    # 6. Push directly to Google Sheets
    if new_leads:
        sheet.append_rows(new_leads)
        return len(new_leads)
    
    return 0
