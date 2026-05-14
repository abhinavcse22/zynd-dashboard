import requests
import json
import streamlit as st

def generate_outreach_sequence(lead_name, intent_source, bio_or_post):
    """Generates a highly technical outreach sequence using OpenRouter."""
    
    prompt = f"""
    You are a technical founder doing elite developer outreach for 'Zynd', an OS and network for AI agents and Web3 builders.
    
    Target Lead: {lead_name}
    Lead's Intent Signal: {intent_source}
    Lead's Context/Bio/Post: {bio_or_post}
    
    Write a 3-step outreach sequence to get this developer to build or publish on Zynd. 
    Rule 1: Be highly technical. No marketing fluff.
    Rule 2: Reference their specific context or intent signal.
    Rule 3: Keep it short (under 4 sentences per message).
    
    Format the output clearly as:
    Message 1 (Initial Pitch):
    Message 2 (Value Add Follow-up - 3 days later):
    Message 3 (The Breakup - 7 days later):
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
                "model": "mistralai/mistral-7b-instruct:free",
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
