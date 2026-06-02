import requests
import json
import streamlit as st
from googlesearch import search

def get_live_market_context(competitors):
    """Scrapes Google for the absolute latest news on specific competitors. Fault-tolerant."""
    intel = []
    try:
        query = f"({' OR '.join(competitors)}) (launch OR update OR 'new feature' OR issue)"
        # advanced=True provides descriptions/snippets which the AI needs
        for result in search(query, num_results=5, advanced=True):
            intel.append(f"Source: {result.title}\nSnippet: {result.description}")
    except Exception as e:
        return f"Market Scan Error: Could not fetch live data. Search engine may be rate-limiting the server."
        
    return "\n\n".join(intel) if intel else "No major live updates found in the last 24 hours."

def generate_hybrid_content(df_reddit, df_twitter, competitor_list):
    """Synthesizes database signals with live web intelligence safely."""
    
    # 1. Fetch Live External Data
    with st.spinner("Scraping live search index for competitor updates..."):
        live_signals = get_live_market_context(competitor_list)

    # 2. Extract Internal Database Signals (Safely)
    db_signals = []
    
    # 🛑 FIX: Safe DataFrame Extraction
    if df_reddit is not None and not df_reddit.empty:
        col = 'Title' if 'Title' in df_reddit.columns else (df_reddit.columns[0] if len(df_reddit.columns) > 0 else None)
        if col: db_signals.extend(df_reddit[col].dropna().astype(str).head(3).tolist())
        
    if df_twitter is not None and not df_twitter.empty:
        col = 'Tweet' if 'Tweet' in df_twitter.columns else (df_twitter.columns[0] if len(df_twitter.columns) > 0 else None)
        if col: db_signals.extend(df_twitter[col].dropna().astype(str).head(3).tolist())
    
    internal_context = "\n".join([f"- {s}" for s in db_signals]) if db_signals else "No recent internal pain points found in database."

    # 3. The Synthesis Prompt
    prompt = f"""
    You are the 'Chief Growth Officer' for Zynd.
    
    INTERNAL DATA (What our target users are complaining about):
    {internal_context}
    
    EXTERNAL DATA (What our competitors are doing/launching right now):
    {live_signals}
    
    TASKS:
    Write 2 long-form, 150-word social posts for LinkedIn/Twitter.
    
    Post 1 (The Hijacker): Direct response to a live competitor update. Contrast their complexity or flaws with Zynd's streamlined OS.
    Post 2 (The Solution): Address a top pain point from our database. Show exactly how Zynd infrastructure fixes it.
    
    RULES:
    - Technical founder voice. 1st person plural ("We built...").
    - Use line breaks for readability.
    - Include a technical insight in every post to prove authority.
    """

    with st.spinner("Synthesizing market data and drafting content..."):
        try:
            response = requests.post(
                url="https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {st.secrets['openrouter']['api_key']}",
                    "HTTP-Referer": "https://zynd.io", 
                    "Content-Type": "application/json"
                },
                data=json.dumps({
                    "model": "openrouter/free", 
                    "messages": [{"role": "user", "content": prompt}]
                }),
                timeout=20 # 🛑 FIX: Prevent infinite hanging
            )
            
            # 🛑 FIX: Check status code BEFORE attempting to parse JSON
            if response.status_code != 200:
                return f"API Error ({response.status_code}): The AI provider is currently unreachable or rate-limited."
            
            response_data = response.json()
            choices = response_data.get('choices', [])
            
            if not choices:
                return "API Error: The AI returned an empty response. Please try again."
                
            return choices[0].get('message', {}).get('content', "Error: No content generated.")
            
        except requests.exceptions.Timeout:
            return "Timeout Error: The AI took too long to respond. Please try again."
        except Exception as e:
            return f"System Error: {str(e)}"
