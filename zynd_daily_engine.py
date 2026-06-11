import requests
import time
import json
from datetime import datetime
import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials

SHEET_ID = '11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A'

def ai_qualify_post(text):
    """Passes the raw post to an LLM to drop false positives via strict JSON schema."""
    prompt = f"""
    You are a strict B2B lead qualification engine for Zynd OS.
    Analyze this Reddit post. Is the author a developer actively building AI agents, workflows, or LLM applications?
    
    Post: "{text}"
    
    Respond EXACTLY with this JSON structure and nothing else. No markdown formatting.
    {{
        "is_agent_builder": true or false,
        "score": <integer 1 to 10 based on intent to buy/use developer tools>
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
                "temperature": 0.1 # Low temp for strict logical analysis
            },
            timeout=12
        )
        if response.status_code == 200:
            content = response.json()['choices'][0]['message']['content']
            # Clean markdown blocks if the LLM hallucinated them
            content = content.replace("```json", "").replace("```", "").strip()
            return json.loads(content)
    except Exception as e:
        print(f"⚠️ AI Qualification failed (API busy). Defaulting to pass to prevent data loss. Error: {e}")
        return {"is_agent_builder": True, "score": 5} 
    return {"is_agent_builder": True, "score": 5}

def run_reddit_scraper():
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
    pain_keywords = ['error', 'stuck', 'help', 'alternative', 'frustrated', 'issue', 'bug', 'fail']
    
    new_leads = []
    
    for sub in subreddits:
        print(f"📡 Scanning r/{sub}...")
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(f"https://www.reddit.com/r/{sub}/new.json?limit=15", headers=headers)
            
            if response.status_code == 200:
                posts = response.json().get('data', {}).get('children', [])
                for post in posts:
                    data = post['data']
                    title = data.get('title', '')
                    text = data.get('selftext', '')
                    author = data.get('author', 'Unknown')
                    post_url = f"https://www.reddit.com{data.get('permalink', '')}"
                    
                    if post_url in existing_urls: continue
                        
                    combined_text = f"{title} {text}".lower()
                    has_pain = any(word in combined_text for word in pain_keywords)
                    
                    # STAGE 1: Keyword Pre-filter (Instant & Free)
                    if not has_pain: continue 
                    
                    print(f"🔍 Keyword matched. Sending to AI for JSON qualification: {title[:30]}...")
                    
                    # STAGE 2: AI Intelligence Filter
                    ai_eval = ai_qualify_post(combined_text[:800])
                    
                    if not ai_eval.get("is_agent_builder", False):
                        print("❌ AI Filtered Out: Not a true developer/agent builder.")
                        continue
                        
                    score = ai_eval.get("score", 6)
                    date_str = datetime.now().strftime('%Y-%m-%d')
                    
                    new_leads.append([
                        "Reddit AI-Filtered",    # Tagged so you know the AI passed them
                        f"r/{sub}",              
                        f"u/{author}",           
                        title,                   
                        text.replace('\n', ' ')[:500], 
                        post_url,                
                        date_str,                
                        score                    
                    ])
                    existing_urls.add(post_url)
                    time.sleep(1) # Pacing so we don't anger the LLM API
            else:
                print(f"⚠️ Reddit blocked r/{sub} with HTTP Code: {response.status_code}")
                
        except Exception as e:
            print(f"❌ Failed to scrape r/{sub}: {e}")
        
        time.sleep(2) 

    if new_leads:
        sheet.append_rows(new_leads)
        return len(new_leads)
    
    return 0