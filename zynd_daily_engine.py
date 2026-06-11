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
    prompt = f"""
    Evaluate this Reddit post snippet: "{text}"
    Is the author likely a developer, engineer, or founder working with AI agents, LLMs, or coding frameworks? 
    Even if they just mention a tool, a framework, a project, or an error, assume they are a builder.
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

def run_reddit_scraper():
    print("\n" + "="*60)
    print("🚀 STARTING REDDIT X-RAY ENGINE (HIGH-VOLUME RSS + LINK DEEP LOGGING)")
    print("="*60)
    
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SHEET_ID).worksheet("Reddit Leads")
    
    raw_data = sheet.get_all_values()
    existing_urls = set()
    if len(raw_data) > 0 and 'Post URL' in raw_data[0]:
        url_idx = raw_data[0].index('Post URL')
        existing_urls = {str(row[url_idx]) for row in raw_data[1:] if len(row) > url_idx and row[url_idx]}

    subreddits = ['LangChain', 'crewAI', 'AutoGPT', 'LocalLLaMA', 'artificial', 'n8n', 'SideProject']
    target_keywords = ['error', 'stuck', 'help', 'alternative', 'issue', 'bug', 'fail', 'agent', 'building', 'project', 'workflow', 'api']
    
    new_leads = []
    stats = {"scraped": 0, "dropped_keyword": 0, "dropped_ai": 0, "saved": 0}
    
    for sub in subreddits:
        print(f"\n📡 [SCANNING RSS FEED]: r/{sub}")
        try:
            feed_url = f"https://www.reddit.com/r/{sub}/new.rss"
            feed = feedparser.parse(feed_url)
            
            if not feed.entries:
                print(f"   ⚠️ RSS Feed empty or ratelimited for r/{sub}.")
                continue
                
            print(f"   📥 Pulled {len(feed.entries)} recent entries from feed.")
            stats["scraped"] += len(feed.entries)
            
            for entry in feed.entries:
                title = entry.title
                text = entry.get('summary', '')
                post_url = entry.link
                author = entry.get('author', 'Unknown').replace('/u/', '')
                
                if post_url in existing_urls: 
                    continue 
                    
                combined_text = f"{title} {text}".lower()
                has_target = any(word in combined_text for word in target_keywords)
                
                if not has_target: 
                    stats["dropped_keyword"] += 1
                    continue 
                
                # --- VISIBLE TELEMETRY LINK LOGGER ---
                print(f"\n   ✅ [KEYWORD MATCH]: '{title[:40]}...'")
                print(f"      🔗 Link: {post_url}")
                print(f"      🧠 Analyzing context via AI...")
                
                ai_eval = ai_qualify_post(combined_text[:600])
                
                if not ai_eval.get("is_agent_builder", False):
                    print(f"      ❌ [AI REJECTED]: Dropping link -> {post_url}")
                    stats["dropped_ai"] += 1
                    continue
                    
                print(f"      🔥 [AI APPROVED]: Capturing link -> {post_url}")
                score = ai_eval.get("score", 6)
                date_str = datetime.now().strftime('%Y-%m-%d')
                clean_text = re.sub('<[^<]+>', '', text)[:500].replace('\n', ' ')
                
                new_leads.append([
                    "Reddit RSS + AI Filter", f"r/{sub}", f"u/{author}", title, 
                    clean_text, post_url, date_str, score                    
                ])
                existing_urls.add(post_url)
                stats["saved"] += 1
                time.sleep(0.5) 
                
        except Exception as e:
            print(f"   🚨 Feed Exception on r/{sub}: {e}")
        
        time.sleep(1) 

    print("\n" + "="*60)
    print(f"📊 REDDIT TARGET TELEMETRY LOGS ANALYSIS SUMMARY:")
    print(f"   📥 Total Posts Checked:    {stats['scraped']}")
    print(f"   🗑️ Dropped by Keyword Ref: {stats['dropped_keyword']}")
    print(f"   🤖 Dropped by AI Filter:  {stats['dropped_ai']}")
    print(f"   ✅ Total Live Links Saved: {stats['saved']}")
    print("="*60)

    if new_leads:
        sheet.append_rows(new_leads)
        return len(new_leads)
    return 0