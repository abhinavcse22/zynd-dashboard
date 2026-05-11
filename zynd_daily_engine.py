import requests
import time
from datetime import datetime
import gspread
import streamlit as st
from oauth2client.service_account import ServiceAccountCredentials

SHEET_ID = '11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A'

# Upgrade 1: We added specific subreddits to scan directly, bypassing the search limit.
TARGET_SUBREDDITS = ['LangChain', 'CrewAI', 'n8n', 'LocalLLaMA', 'AI_Agents', 'automation']

INTENT_MATRIX = {
    "Competitor Mention": ['moltbook', 'openclaw', 'langgraph', 'autogen'],
    "Pain Point": ['agent got stuck', 'agent hallucinated', 'issue with my agent', 'crewai loop', 'langchain error'],
    "Agent Network": ['agentic network', 'multi-agent system', 'agents talking to each other'],
    "Agent Builders": ['custom tool for my agent', 'built an mcp', 'my ai agent successfully']
}

def run_reddit_scraper():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SHEET_ID).worksheet("Reddit Leads")
    
    records = sheet.get_all_records()
    existing_urls = {str(row.get('Post URL', '')) for row in records if row.get('Post URL')}
    new_leads = []
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

    print("📡 Scanning Subreddits directly...")
    for sub in TARGET_SUBREDDITS:
        url = f"https://www.reddit.com/r/{sub}/new.json?limit=100"
        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                children = response.json().get('data', {}).get('children', [])
                for child in children:
                    post = child['data']
                    post_url = f"https://reddit.com{post.get('permalink', '')}"
                    if post_url in existing_urls: continue
                    
                    # Score based on GTM
                    score = 7 # Direct subreddit post is automatically warm
                    snippet = (post.get('title', '') + " - " + post.get('selftext', ''))[:150].replace('\n', ' ')
                    date_str = datetime.fromtimestamp(post.get('created_utc', 0)).strftime('%Y-%m-%d')
                    author = f"u/{post.get('author', 'Unknown')}"
                    
                    new_leads.append(["Subreddit Scan", "Reddit", author, f"https://reddit.com/user/{post.get('author', '')}", post_url, sub, snippet, date_str, score])
                    existing_urls.add(post_url)
            time.sleep(2) # Respect Reddit rate limits
        except: pass

    print("📡 Running specific intent searches...")
    for intent_category, queries in INTENT_MATRIX.items():
        for query in queries:
            url = f"https://www.reddit.com/search.json?q={query}&sort=new&t=week&limit=100"
            try:
                response = requests.get(url, headers=headers)
                if response.status_code == 200:
                    children = response.json().get('data', {}).get('children', [])
                    for child in children:
                        post = child['data']
                        post_url = f"https://reddit.com{post.get('permalink', '')}"
                        if post_url in existing_urls: continue
                        
                        score = 8 if 'pain' in intent_category.lower() else 6
                        snippet = (post.get('title', '') + " - " + post.get('selftext', ''))[:150].replace('\n', ' ')
                        date_str = datetime.fromtimestamp(post.get('created_utc', 0)).strftime('%Y-%m-%d')
                        author = f"u/{post.get('author', 'Unknown')}"
                        
                        new_leads.append([intent_category, "Reddit", author, f"https://reddit.com/user/{post.get('author', '')}", post_url, query, snippet, date_str, score])
                        existing_urls.add(post_url)
            except: pass
            time.sleep(2)

    if new_leads:
        sheet.append_rows(new_leads)
        print(f"✅ Added {len(new_leads)} new Reddit leads.")
