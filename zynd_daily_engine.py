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

    # 3. The Target Matrix (Subreddits & Pain Point Keywords)
    subreddits = ['LangChain', 'CrewAI', 'AutoGPT', 'artificial', 'LocalLLaMA']
    queries = ['"error"', '"stuck"', '"help"', '"alternative"', '"frustrated"']
    
    # 4. THE FORGED HEADER (This is the magic that bypasses the cloud block)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 ZyndOS/1.0'
    }

    new_leads = []
    
    for sub in subreddits:
        for query in queries:
            # The .json Backdoor URL
            url = f"https://www.reddit.com/r/{sub}/search.json?q={query}&restrict_sr=1&sort=new&limit=10"
            try:
                response = requests.get(url, headers=headers)
                
                # If Reddit lets us through, parse the data
                if response.status_code == 200:
                    data = response.json()
                    posts = data.get('data', {}).get('children', [])
                    
                    for post in posts:
                        post_data = post['data']
                        post_url = f"https://www.reddit.com{post_data['permalink']}"
                        
                        # Skip if we already have it
                        if post_url in existing_urls:
                            continue
                            
                        title = post_data.get('title', '')
                        text = post_data.get('selftext', '').replace('\n', ' ')[:500]
                        author = post_data.get('author', 'unknown')
                        
                        # Skip deleted accounts or empty posts
                        if author == '[deleted]' or not text:
                            continue
                            
                        # Dynamic Lead Scoring
                        score = 6
                        if 'error' in query or 'stuck' in query: score += 2
                        if 'agent' in text.lower() or 'agent' in title.lower(): score += 1
                        if 'alternative' in query: score += 3 # Very high intent to switch tools
                        
                        score = min(score, 10) # Cap at a score of 10
                        date_str = datetime.now().strftime('%Y-%m-%d')
                        
                        # Package the payload
                        new_leads.append([
                            "Reddit .json Backdoor", # Source
                            f"r/{sub}",              # Subreddit
                            f"u/{author}",           # Author
                            title,                   # Post Title
                            text,                    # Post Text
                            post_url,                # Post URL
                            date_str,                # Date
                            score                    # Lead Score (1-10)
                        ])
                        existing_urls.add(post_url)
                        
            except Exception as e:
                print(f"Failed to scrape r/{sub}: {e}")
                continue
            
            # 1.5 second pause between queries so Reddit doesn't ban the Streamlit server
            time.sleep(1.5) 

    # 5. Push directly to Google Sheets
    if new_leads:
        sheet.append_rows(new_leads)
        return len(new_leads)
    
    return 0
