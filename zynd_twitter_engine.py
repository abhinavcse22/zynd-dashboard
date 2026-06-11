import time
import json
from datetime import datetime
import gspread
import streamlit as st
from oauth2client.service_account import ServiceAccountCredentials
from ddgs import DDGS
import re
import random
import requests

SHEET_ID = '11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A'

# Simplified queries. DuckDuckGo often fails on complex Boolean operators.
TWITTER_QUERIES = [
    'site:x.com "AI agent" building',
    'site:x.com "LangGraph" error',
    'site:x.com "CrewAI" issue',
    'site:x.com "n8n" workflow ai'
]

def ai_qualify_post(text):
    """Smart AI filter with unbreakable JSON regex parsing."""
    prompt = f"""
    Evaluate this tweet snippet: "{text}"
    
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
            print(f"      [🤖 AI Raw Output]: {raw_content.strip()}")
            
            match = re.search(r'\{.*?\}', raw_content, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
                return {"is_agent_builder": data.get("is_builder", True), "score": data.get("score", 6)}
        else:
            print(f"      [⚠️ AI API Error]: Status {response.status_code}")
    except Exception as e:
        print(f"      [⚠️ AI Exception]: {e}")
        
    return {"is_agent_builder": True, "score": 5}

def run_twitter_scraper():
    print("\n" + "="*50)
    print("🚀 STARTING TWITTER/X X-RAY ENGINE")
    print("="*50)

    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SHEET_ID).worksheet("Twitter Leads")
    
    raw_data = sheet.get_all_values()
    existing_urls = set()
    if len(raw_data) > 0:
        try:
            url_idx = raw_data[0].index('Post URL')
            existing_urls = {str(row[url_idx]).lower().strip() for row in raw_data[1:] if len(row) > url_idx}
        except ValueError:
            pass

    print(f"📊 Found {len(existing_urls)} existing leads in database.")
    ignored_routes = ['search', 'hashtag', 'home', 'explore', 'i', 'messages', 'status']
    new_leads = []
    ddgs = DDGS()
    
    for query in TWITTER_QUERIES:
        print(f"\n📡 [SEARCHING DUCKDUCKGO]: {query}")
        try:
            results = list(ddgs.text(query, max_results=15))
            print(f"   📥 DDG returned {len(results)} raw web results.")
            
            for result in results:
                post_url = result.get('href', '')
                post_url_lower = post_url.lower()
                
                if not post_url or post_url_lower in existing_urls:
                    continue
                    
                username_match = re.search(r'(?:twitter\.com|x\.com)/([^/]+)', post_url)
                if not username_match:
                    continue
                    
                username = username_match.group(1).split('?')[0]
                if username.lower() in ignored_routes:
                    continue
                
                clean_text = str(result.get('body', '')).replace('\n', ' ')[:500]
                print(f"\n   👀 Target Found: @{username}")
                print(f"   📝 Snippet: {clean_text[:60]}...")
                print(f"   🧠 Sending to AI for verification...")
                
                ai_eval = ai_qualify_post(clean_text)
                
                if not ai_eval.get("is_agent_builder", False):
                    print("   ❌ [FAIL]: AI rejected @" + username)
                    continue

                print("   🔥 [PASS]: AI APPROVED @" + username)
                score = ai_eval.get("score", 6)
                date_str = datetime.now().strftime('%Y-%m-%d')
                
                new_leads.append([
                    "Twitter Smart Filter", "Twitter", f"@{username}", 
                    f"https://x.com/{username}", post_url, query, 
                    clean_text, date_str, score
                ])
                existing_urls.add(post_url_lower)
                time.sleep(1) 
        
        except Exception as e:
            print(f"   🚨 Critical Error on DDG Search: {e}")
            if "402" in str(e) or "ratelimit" in str(e).lower():
                print("   🛑 Rate limited by DDG. Stopping sweeps.")
                break
            continue
            
        time.sleep(random.uniform(3.0, 5.0)) 

    if new_leads:
        print(f"\n⬆️ Uploading {len(new_leads)} new Twitter leads to Google Sheets!")
        sheet.append_rows(new_leads)
        return len(new_leads)
    
    print("\n🛑 Execution complete. 0 new Twitter leads found.")
    return 0