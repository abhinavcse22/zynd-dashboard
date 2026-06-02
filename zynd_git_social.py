import requests
import json
import streamlit as st
import random

# Synchronized with your master secrets structure
try:
    GITHUB_TOKENS = st.secrets["github"]["tokens"]
except KeyError:
    GITHUB_TOKENS = []

def fetch_latest_commit_and_post(repo_path):
    """Fetches the latest commit from a repo and writes a social post safely."""
    
    # 0. Clean the input (In case someone pastes the full URL)
    clean_repo = repo_path.replace("https://github.com/", "").strip("/")
    
    # 1. Fetch the latest commit data from GitHub
    headers = {"Accept": "application/vnd.github.v3+json"}
    if GITHUB_TOKENS:
        token = random.choice(GITHUB_TOKENS) if isinstance(GITHUB_TOKENS, list) else GITHUB_TOKENS
        headers["Authorization"] = f"token {token}"
        
    url = f"https://api.github.com/repos/{clean_repo}/commits?per_page=1"
    
    response = requests.get(url, headers=headers, timeout=10)
    if response.status_code != 200:
        return None, f"GitHub API Error: {response.status_code}. Ensure the repository is public or your tokens have access."
        
    commits = response.json()
    if not commits:
        return None, "Error: This repository currently has zero commits."
        
    commit_data = commits[0]
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
            }),
            timeout=20 # 🛑 Prevent infinite hanging
        )
        
        # 🛑 Safe Parsing Check
        if ai_response.status_code != 200:
            return None, f"AI API Error ({ai_response.status_code}): Service unavailable."
            
        response_data = ai_response.json()
        choices = response_data.get('choices', [])
        
        if not choices:
            return None, "AI Error: Model returned an empty response."
            
        post_content = choices[0].get('message', {}).get('content', '')
        
        return {
            "author": author, 
            "message": commit_msg, 
            "url": commit_url, 
            "post": post_content
        }, "Success"
        
    except requests.exceptions.Timeout:
        return None, "Timeout Error: The AI took too long to respond. Please try again."
    except Exception as e:
        return None, f"System Error: {str(e)}"
