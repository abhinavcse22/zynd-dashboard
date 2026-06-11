import time
import json
from datetime import datetime
import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import re
import feedparser
import requests

SHEET_ID = '11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A'

def ai_qualify_post(text):
    """Smart AI filter with unbreakable JSON regex parsing."""
    prompt = f"""
    Evaluate this Reddit post snippet: "{text}"
    
    Is the author likely a developer, engineer, or founder working with AI agents, LLMs, or coding frameworks? 
    Even if they just mention an error, a tool, or a framework, assume they are a builder.
    
    Respond EXACTLY with this JSON structure and nothing else:
    {{"is_builder": true, "score": 8}}
    """
    try:
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {st.secrets['openrouter']['api_key']}", "Content-Type": "application/json"},
            json={"model": "openrouter/free", "messages": [{"role": "user", "content": prompt}], "temperature": 0.1},
            timeout=15
        )
        if response.status_code == 200:
            raw_content = response.json()['choices'][0]['message']['content']
            print(f"   [🤖 AI Raw Output]: {raw_content.strip()}")
            match = re.search(r'\{.*?\}', raw_content, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
                return {"is_agent_builder": data.get("is_builder", True), "score": data.get("score", 6)}
    except Exception as e:
        print(f"   [⚠️ AI Exception]: {e}")
        
    return {"is_agent_builder": True, "score": 5}

def run_reddit_scraper():
    print("\n" + "="*50)
    print("🚀 STARTING REDDIT X-RAY ENGINE (RSS GHOST ROUTE)")
    print("="*50)
    
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SHEET_ID).worksheet("Reddit Leads")
    
    raw_data = sheet.get_all_values()
    existing_urls = set()
    if len(raw_data) > 0 and 'Post URL' in raw_data[0]:
        url_idx = raw_data[0].index('Post URL')
        existing_urls = {str(row[url_idx]) for row in raw_data[1:] if len(row) > url_idx and row[url_idx]}

    subreddits = ['LangChain', 'crewAI', 'AutoGPT', 'LocalLLaMA', 'artificial']
    pain_keywords = ['error', 'stuck', 'help', 'alternative', 'frustrated', 'issue', 'bug', 'fail', 'agent']
    
    new_leads = []
    
    for sub in subreddits:
        print(f"\n📡 [SCANNING RSS FEED]: r/{sub}")
        try:
            # Bypass 403 using Reddit's RSS Syndication Feed
            feed_url = f"https://www.reddit.com/r/{sub}/new.rss"
            feed = feedparser.parse(feed_url)
            
            if not feed.entries:
                print(f"   ⚠️ RSS Feed empty or blocked for r/{sub}.")
                continue
                
            print(f"   📥 Pulled {len(feed.entries)} recent posts via RSS.")
            
            for entry in feed.entries[:15]:
                title = entry.title
                text = entry.get('summary', '')
                post_url = entry.link
                # RSS authors look like '/u/username'
                author = entry.get('author', 'Unknown').replace('/u/', '')
                
                if post_url in existing_urls: 
                    continue 
                    
                combined_text = f"{title} {text}".lower()
                has_pain = any(word in combined_text for word in pain_keywords)
                
                if not has_pain: 
                    continue 
                
                print(f"   ✅ [STAGE 1 PASS]: Keywords found -> '{title[:40]}...'")
                print(f"   🧠 Sending to AI for verification...")
                
                ai_eval = ai_qualify_post(combined_text[:600])
                
                if not ai_eval.get("is_agent_builder", False):
                    print("   ❌ [STAGE 2 FAIL]: AI rejected.")
                    continue
                    
                print("   🔥 [STAGE 2 PASS]: AI APPROVED! Lead Captured.")
                score = ai_eval.get("score", 6)
                date_str = datetime.now().strftime('%Y-%m-%d')
                
                # Strip HTML tags from RSS summary
                clean_text = re.sub('<[^<]+>', '', text)[:500].replace('\n', ' ')
                
                new_leads.append([
                    "Reddit RSS + AI Filter", f"r/{sub}", f"u/{author}", title, 
                    clean_text, post_url, date_str, score                    
                ])
                existing_urls.add(post_url)
                time.sleep(1) 
                
        except Exception as e:
            print(f"   🚨 Critical Error on r/{sub}: {e}")
        
        time.sleep(2) 

    if new_leads:
        print(f"\n⬆️ Uploading {len(new_leads)} new leads to Google Sheets!")
        sheet.append_rows(new_leads)
        return len(new_leads)
    
    print("\n🛑 Execution complete. 0 new leads found.")
    return 0