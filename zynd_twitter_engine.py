import time
import json
from datetime import datetime
import gspread
import streamlit as st
from oauth2client.service_account import ServiceAccountCredentials
from duckduckgo_search import DDGS
import re
import random
import requests

SHEET_ID = '11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A'

TWITTER_QUERIES = [
    'site:x.com "AI agent" builder',
    'site:x.com "LangGraph" error OR stuck',
    'site:x.com "CrewAI" issue OR framework',
    'site:x.com "n8n" workflow automation'
]

def ai_qualify_post(text):
    """Passes the raw post to an LLM to drop false positives via JSON schema."""
    prompt = f"""
    You are a strict B2B lead qualification engine.
    Analyze this tweet. Is the author a developer actively building AI agents, workflows, or LLM applications?
    
    Post: "{text}"
    
    Respond EXACTLY with this JSON structure and nothing else. No markdown formatting.
    {{
        "is_agent_builder": true or false,
        "score": <integer 1 to 10 based on intent to buy/use tools>
    }}
    """
    try:
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {st.secrets['openrouter']['api_key']}",
                "Content-Type": "application/json"
            },
            json={
                "model": "openrouter/free",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1
            },
            timeout=12
        )
        if response.status_code == 200:
            content = response.json()['choices'][0]['message']['content']
            content = content.replace("```json", "").replace("```", "").strip()
            return json.loads(content)
    except Exception:
        return {"is_agent_builder": True, "score": 5} # Fallback
    return {"is_agent_builder": True, "score": 5}

def run_twitter_scraper():
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

    ignored_routes = ['search', 'hashtag', 'home', 'explore', 'i', 'messages']
    new_leads = []
    
    ddgs = DDGS()
    
    for query in TWITTER_QUERIES:
        print(f"📡 Sweeping X.com for: {query}")
        try:
            results = ddgs.text(query, max_results=15)
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
                
                print(f"🧠 AI analyzing Tweet context from @{username}...")
                ai_eval = ai_qualify_post(clean_text)
                
                if not ai_eval.get("is_agent_builder", False):
                    print("❌ AI Filtered Out: False positive or irrelevant.")
                    continue

                score = ai_eval.get("score", 6)
                date_str = datetime.now().strftime('%Y-%m-%d')
                
                new_leads.append([
                    "Twitter AI-Filtered", 
                    "Twitter", 
                    f"@{username}", 
                    f"https://x.com/{username}", 
                    post_url, 
                    query, 
                    clean_text, 
                    date_str, 
                    score
                ])
                existing_urls.add(post_url_lower)
                time.sleep(1) # Pacing for LLM
        
        except Exception as e:
            if "402" in str(e) or "ratelimit" in str(e).lower():
                break
            continue
            
        time.sleep(random.uniform(3.0, 5.0)) 

    if new_leads:
        sheet.append_rows(new_leads)
        return len(new_leads)
    
    return 0