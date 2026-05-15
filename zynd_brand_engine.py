import requests
import json
import streamlit as st

def generate_team_post(name, role, bio_vibe, work_done):
    """Generates authentic, 1st-person Build in Public posts for team members."""
    
    prompt = f"""
    You are an expert ghostwriter for elite tech founders and engineers.
    
    Author Profile:
    - Name: {name}
    - Role at Zynd: {role}
    - Personal Vibe/Writing Style: {bio_vibe}
    
    What they actually did today:
    {work_done}
    
    Write 2 different, highly authentic "Build in Public" social media posts (for LinkedIn/Twitter) based on what they did today.
    
    CRITICAL RULES:
    1. DO NOT sound like a corporate marketing robot. Sound like a real human building a startup.
    2. Write in the 1st person ("I", "we").
    3. Show, don't just tell. Explain *why* the work matters or the technical challenge behind it.
    4. Subtly position Zynd as an amazing tool/workplace without sounding like a forced advertisement.
    5. Keep each post between 75 - 150 words.
    
    Format output:
    ### Option 1 (Technical & Deep):
    [Post content]
    
    ### Option 2 (Vision & Growth):
    [Post content]
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
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
        else:
            return "API Error. Check connection."
    except Exception as e:
        return f"System Error: {str(e)}"
