import time
import json
from datetime import datetime
import gspread
import streamlit as st
from oauth2client.service_account import ServiceAccountCredentials
from ddgs import DDGS
from googlesearch import search
import re
import random
import requests

SHEET_ID = '11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A'

TWITTER_QUERIES = [
    'site:x.com "AI agent" building',
    'site:x.com "LangGraph" error',
    'site:x.com "CrewAI" issue',
    'site:x.com "n8n" workflow ai'
]

def ai_qualify_post(text):
    prompt = f"""
    Evaluate this tweet snippet: "{text}"
    Is the author likely a developer, engineer, or founder working with AI agents, LLMs, or coding frameworks? 
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
            match = re.search(r'\{.*?\}', raw_content, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
                return {"is_agent_builder": data.get("is_builder", True), "score": data.get("score", 6)}
    except Exception:
        pass
    return {"is_agent_builder": True, "score": 5}

def pull_search_results(query):
    """Dual-engine fallback: Tries DDG HTML first, falls back to Google."""
    results = []
    try:
        ddgs = DDGS()
        # The 'html' backend bypasses standard API rate limits
        raw_ddg = list(ddgs.text(query, backend="html", max_results=15))
        for r in raw_ddg:
            results.append({"url": r.get('href', ''), "snippet": r.get('body', '')})
        if results:
            print(f"   📥 DDG returned {len(results)} results.")
            return results
    except Exception as e:
        print(f"   ⚠️ DDG Blocked ({e}). Falling back to Google...")
        
    try:
        raw_google = list(search(query, num_results=10, advanced=True, sleep_interval=2))
        for r in raw_google:
            results.append({"url": r.url, "snippet": r.description})
        print(f"   📥 Google returned {len(results)} results.")
    except Exception as e:
        print(f"   🚨 Google blocked request: {e}")
        
    return results

def run_twitter_scraper():
    print("\n" + "="*50)
    print("🚀 STARTING TWITTER/X X-RAY ENGINE (DUAL-FALLBACK)")
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

    ignored_routes = ['search', 'hashtag', 'home', 'explore', 'i', 'messages', 'status']
    # If the snippet contains these, it's a blocked Twitter login screen, not a real post.
    garbage_snippets = ['something went wrong', 'javascript is not enabled', 'log in to x', 'please log in', 'we’ve detected unusual']
    
    new_leads = []
    stats = {"scraped": 0, "dropped_garbage": 0, "dropped_ai": 0, "saved": 0}
    
    for query in TWITTER_QUERIES:
        print(f"\n📡 [SEARCHING]: {query}")
        
        results = pull_search_results(query)
        stats["scraped"] += len(results)
        
        for result in results:
            post_url = result['url']
            post_url_lower = post_url.lower()
            clean_text = str(result['snippet']).replace('\n', ' ')[:500]
            
            if not post_url or post_url_lower in existing_urls:
                continue
                
            username_match = re.search(r'(?:twitter\.com|x\.com)/([^/]+)', post_url)
            if not username_match:
                continue
                
            username = username_match.group(1).split('?')[0]
            if username.lower() in ignored_routes:
                continue
            
            # STAGE 1: Check for garbage X.com login screens
            is_garbage = any(phrase in clean_text.lower() for phrase in garbage_snippets)
            if is_garbage or len(clean_text) < 15:
                print(f"   🗑️ [GARBAGE SNIPPET]: Ignored @{username} (Twitter Login Wall)")
                stats["dropped_garbage"] += 1
                continue
            
            print(f"\n   👀 Target Found: @{username}")
            print(f"   📝 Snippet: {clean_text[:60]}...")
            print(f"   🧠 Sending to AI for verification...")
            
            ai_eval = ai_qualify_post(clean_text)
            
            if not ai_eval.get("is_agent_builder", False):
                print("   ❌ [FAIL]: AI rejected @" + username)
                stats["dropped_ai"] += 1
                continue

            print("   🔥 [PASS]: AI APPROVED @" + username)
            score = ai_eval.get("score", 6)
            date_str = datetime.now().strftime('%Y-%m-%d')
            
            new_leads.append([
                "Dual-Engine Search", "Twitter", f"@{username}", 
                f"https://x.com/{username}", post_url, query, 
                clean_text, date_str, score
            ])
            existing_urls.add(post_url_lower)
            stats["saved"] += 1
            time.sleep(1) 
            
        time.sleep(random.uniform(2.0, 4.0)) 

    print("\n" + "="*50)
    print(f"📊 TWITTER/X SCRAPE SUMMARY:")
    print(f"   📥 Total Results Scanned: {stats['scraped']}")
    print(f"   🗑️ Dropped (Login Walls): {stats['dropped_garbage']}")
    print(f"   🤖 Dropped by AI Filter:  {stats['dropped_ai']}")
    print(f"   ✅ Total Leads Saved:     {stats['saved']}")
    print("="*50)

    if new_leads:
        sheet.append_rows(new_leads)
        return len(new_leads)
    return 0