import requests
import json
import streamlit as st
from googlesearch import search

def get_live_market_context(competitors):
    """Scrapes Google for the absolute latest news on specific competitors."""
    intel = []
    try:
        query = f"({' OR '.join(competitors)}) (launch OR update OR 'new feature' OR issue)"
        # advanced=True provides descriptions/snippets which the AI needs
        for result in search(query, num_results=5, advanced=True):
            intel.append(f"Source: {result.title}\nSnippet: {result.description}")
    except Exception:
        pass
    return "\n\n".join(intel) if intel else "No major live updates found."

def generate_hybrid_content(df_reddit, df_twitter, competitor_list):
    """Synthesizes database signals with live web intelligence."""
    
    # 1. Fetch Live External Data
    live_signals = get_live_market_context(competitor_list)

    # 2. Extract Internal Database Signals
    db_signals = []
    if not df_reddit.empty:
        col = 'Title' if 'Title' in df_reddit.columns else df_reddit.columns[0]
        db_signals.extend(df_reddit[col].dropna().astype(str).head(3).tolist())
    if not df_twitter.empty:
        col = 'Tweet' if 'Tweet' in df_twitter.columns else df_twitter.columns[0]
        db_signals.extend(df_twitter[col].dropna().astype(str).head(3).tolist())
    
    internal_context = "\n".join([f"- {s}" for s in db_signals])

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
            })
        )
        return response.json()['choices'][0]['message']['content']
    except Exception as e:
        return f"System Error: {str(e)}"
