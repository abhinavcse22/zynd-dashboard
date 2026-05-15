import requests
import json
import streamlit as st

GITHUB_TOKEN = st.secrets.get("github", {}).get("token", "")

def fetch_latest_commit_and_post(repo_path):
    """Fetches the latest commit from your repo and writes a social post about it."""
    
    # 1. Fetch the latest commit data from GitHub
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"} if GITHUB_TOKEN else {}
    url = f"https://api.github.com/repos/{repo_path}/commits?per_page=1"
    
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        return None, f"GitHub Error: {response.status_code}. Check repo name."
        
    commit_data = response.json()[0]
    commit_msg = commit_data['commit']['message']
    author = commit_data['commit']['author']['name']
    commit_url = commit_data['html_url']
    
    # 2. Feed the raw code commit to the AI to translate into marketing
    prompt = f"""
    You are the ghostwriter for Zynd OS. 
    Our developer ({author}) just pushed this technical update to our GitHub:
    "{commit_msg}"
    
    Write a highly engaging, 1st-person (plural "We") Twitter/LinkedIn post announcing this new feature or fix. 
    
    RULES:
    1. Translate the technical jargon into why a user should care (Value drop).
    2. Keep it under 100 words.
    3. Make it sound like a fast-moving, elite startup building in public.
    4. End with a CTA to check out Zynd OS.
    """

    try:
        ai_response = requests.post(
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
        post_content = ai_response.json()['choices'][0]['message']['content']
        return {"author": author, "message": commit_msg, "url": commit_url, "post": post_content}, "Success"
    except Exception as e:
        return None, f"AI Error: {str(e)}"
