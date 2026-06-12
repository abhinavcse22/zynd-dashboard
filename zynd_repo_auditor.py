import requests
import json
import streamlit as st
import base64

def fetch_github_readme(repo_path):
    """Fetches the README file from a GitHub repository."""
    clean_repo = repo_path.replace("https://github.com/", "").strip("/")
    url = f"https://api.github.com/repos/{clean_repo}/readme"
    
    headers = {"Accept": "application/vnd.github.v3+json"}
    tokens = st.secrets.get("github", {}).get("tokens", [])
    
    if tokens:
        token = tokens[0] if isinstance(tokens, list) else tokens
        headers["Authorization"] = f"token {token}"
        
    response = requests.get(url, headers=headers, timeout=10)
    if response.status_code == 200:
        content = response.json().get("content", "")
        if content:
            return base64.b64decode(content).decode("utf-8")
    return None

def generate_repo_revenue_audit(repo_path):
    """Generates the Repo-to-Revenue GTM Audit based on the README."""
    readme_text = fetch_github_readme(repo_path)
    
    if not readme_text:
        return False, "Could not fetch README. Ensure the repo is public and has a README.md file."
        
    prompt = f"""
    You are the Principal GTM Architect at Zynd, an open network for AI agents.
    I am evaluating this GitHub repository to see how it can be monetized as an AI Agent on Zynd.
    
    Repository README:
    {readme_text[:4000]}  # Capped to save tokens

    Write a "Repo-to-Revenue Audit" for this builder. 
    Use this EXACT format with bullet points:
    
    ### 🧬 1. Plain English Translation
    (What this repo actually does, without the dense jargon)
    
    ### 🎯 2. The Ideal Buyer
    (Who would actually pay for this? Be specific)
    
    ### 📦 3. Agent Packaging Strategy
    (How to turn this raw code into a callable, packaged agent category)
    
    ### 💰 4. Suggested Pricing Model
    (Recommend Per-call, Per-task, or Monthly retainer, and give a realistic price point)
    
    ### 🚀 5. Zynd Launch Steps
    (What 1 or 2 things they need to fix/improve before listing it on the Zynd discovery network)
    
    RULES:
    - Tone: Elite, technical, encouraging, direct.
    - Keep it concise. This will be sent as a personalized email or DM.
    - Do not use cheesy marketing buzzwords.
    """

    headers = {
        "Authorization": f"Bearer {st.secrets['openrouter']['api_key']}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json={
                "model": "openai/gpt-4o-mini",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.4
            },
            timeout=20
        )
        
        if response.status_code == 200:
            audit = response.json()['choices'][0]['message']['content'].strip()
            return True, audit
        else:
            return False, f"API Error: {response.status_code} - {response.text}"
            
    except Exception as e:
        return False, f"Generation Failed: {str(e)}"