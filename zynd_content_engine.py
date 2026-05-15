import requests
import json
import streamlit as st

def generate_daily_content(df_reddit, df_twitter):
    """Generates 3 daily content ideas based on live market pain points."""
    
    # 1. Extract the raw pain points directly from your scrapers
    pain_points = []
    
    if not df_reddit.empty:
        content_col = 'Title' if 'Title' in df_reddit.columns else df_reddit.columns[0]
        # Grab the top 3 most recent Reddit complaints
        pain_points.extend(df_reddit[content_col].dropna().astype(str).head(3).tolist())
        
    if not df_twitter.empty:
        tweet_col = 'Tweet' if 'Tweet' in df_twitter.columns else df_twitter.columns[0]
        # Grab the top 3 most recent Twitter signals
        pain_points.extend(df_twitter[tweet_col].dropna().astype(str).head(3).tolist())
        
    context_str = "\n".join([f"- {p}" for p in pain_points]) if pain_points else "General Web3 and AI Agent building challenges."

    # 2. Build the Data-Driven Prompt
    prompt = f"""
    You are the elite Head of Growth for 'Zynd', an OS and network for AI agents and Web3 builders.
    
    Here are the actual pain points and conversations developers are having TODAY based on our raw scraper data:
    {context_str}
    
    Generate 3 high-impact social media posts (for Twitter/LinkedIn) that Zynd should publish today to attract these specific developers.
    
    Rule 1: Do not be overly salesy. Focus on education and solving their specific problem.
    Rule 2: Each post must have a strong hook (first sentence).
    Rule 3: Frame Zynd as the ultimate solution or underlying infrastructure.
    
    Format the output exactly as:
    Post 1 (The Pain-Point Hook):
    [Content]
    
    Post 2 (The Contrarian View):
    [Content]
    
    Post 3 (The Value Drop):
    [Content]
    """

    try:
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {st.secrets['openrouter']['api_key']}",
                "HTTP-Referer": "https://zynd.io", 
                "X-Title": "Zynd OS", 
                "Content-Type": "application/json"
            },
            data=json.dumps({
                "model": "openrouter/free", 
                "messages": [
                    {"role": "user", "content": prompt}
                ]
            })
        )
        
        response_data = response.json()
        
        if response.status_code == 200:
            return response_data['choices'][0]['message']['content']
        else:
            return f"API Error: {response_data.get('error', 'Unknown Error')}"
            
    except Exception as e:
        return f"System Error: {str(e)}"
