import requests
from bs4 import BeautifulSoup
import gspread
import streamlit as st
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import time
import urllib.parse

# --- CONFIGURATION ---
SHEET_ID = '11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A'

def run_twitter_scraper():
    """Unlimited Twitter Harvester via DuckDuckGo OSINT"""
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    client = gspread.authorize(creds)
    
    try:
        sheet = client.open_by_key(SHEET_ID).worksheet("Twitter Leads")
    except:
        return 0

    records = sheet.get_all_records()
    seen_urls = {str(row.get('Tweet URL', '')) for row in records}

    # GTM Search Dorks (Using twitter.com for better DDG indexing)
    queries = [
        'site:twitter.com "building an AI agent"',
        'site:twitter.com "LangGraph" "stuck"',
        'site:twitter.com "CrewAI" "issue"'
    ]

    new_leads = []
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; rv:109.0) Gecko/20100101 Firefox/115.0',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5'
    }

    print("🦆 Initiating DuckDuckGo OSINT Bypass...")

    for query in queries:
        url = "https://html.duckduckgo.com/html/"
        data = {'q': query}
        
        try:
            # DuckDuckGo uses a POST request for their HTML search
            response = requests.post(url, headers=headers, data=data, timeout=15)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                results = soup.find_all('a', class_='result__snippet')
                
                for result in results:
                    tweet_url = result.get('href', '')
                    
                    # Unpack DuckDuckGo's redirect URL to get the real Twitter link
                    if 'uddg=' in tweet_url:
                        tweet_url = urllib.parse.unquote(tweet_url.split('uddg=')[1].split('&')[0])
                    
                    # Ensure it's a specific tweet, not just a profile
                    if 'status' not in tweet_url: continue
                    
                    # Clean the URL
                    clean_url = tweet_url.split('?')[0].replace('twitter.com', 'x.com')
                    if clean_url in seen_urls: continue
                    
                    author = clean_url.split('/')[3]
                    content = result.text.strip()
                    date = datetime.now().strftime("%Y-%m-%d")
                    
                    # Score based on pain points
                    score = 7
                    if any(x in content.lower() for x in ['stuck', 'issue', 'error', 'help']): score = 10
                    
                    new_leads.append(["Twitter", author, clean_url, content, date, score])
                    seen_urls.add(clean_url)
                    
            time.sleep(3) # Safety delay between searches
        except Exception as e:
            continue

    if new_leads:
        sheet.append_rows(new_leads)
        return len(new_leads)
    return 0
