import requests
import json
import streamlit as st
import time

def generate_outreach_sequence(lead_name, intent_source, bio_or_post, product_pitch="an OS and network for AI agents and Web3 builders"):
    """
    Advanced Dynamic Outreach Sequencer.
    Maintains 100% backward compatibility with app.py while introducing 
    multi-model fallback routing and auto-retry mechanics to guarantee uptime.
    """
    
    # Core prompt formula structured for maximum conversion context
    prompt = f"""
    You are a technical founder doing elite developer outreach for 'Zynd', {product_pitch}.
    
    Target Lead: {lead_name}
    Lead's Intent Signal: {intent_source}
    Lead's Context/Bio/Post: {bio_or_post}
    
    Write a 3-step outreach sequence to get this developer to build or publish on Zynd. 
    Rule 1: Be highly technical. No marketing fluff.
    Rule 2: Reference their specific context or intent signal in the first message.
    Rule 3: Keep it extremely concise (under 4 sentences per message).
    
    Format the output exactly as follows:
    ### Message 1 (Initial Pitch):
    [Content]
    
    ### Message 2 (Value Add Follow-up - 3 days later):
    [Content]
    
    ### Message 3 (The Breakup - 7 days later):
    [Content]
    """

    # Dynamic model hierarchy: if the primary free model rate-limits or fails, the engine auto-escalates
    model_stack = [
        "openrouter/free",              # Primary Free Tier Router
        "meta-llama/llama-3-8b-instruct:free", # High-speed backup A
        "mistralai/mistral-7b-instruct:free"   # High-speed backup B
    ]
    
    try:
        api_key = st.secrets["openrouter"]["api_key"]
    except KeyError:
        return "Configuration Error: 'api_key' missing under [openrouter] section in Streamlit Secrets."

    headers = {
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "https://zynd.io", 
        "X-Title": "Zynd OS Advanced", 
        "Content-Type": "application/json"
    }

    # Execute structured fallback loops
    for model in model_stack:
        retries = 2
        while retries > 0:
            try:
                response = requests.post(
                    url="https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    data=json.dumps({
                        "model": model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.3
                    }),
                    timeout=10 # Aggressive timeout to trigger fallback quickly if stuck
                )
                
                # If hit with a transient rate limit (429) or server issue (5xx), wait and retry
                if response.status_code in [429, 500, 502, 503, 504]:
                    retries -= 1
                    time.sleep(2)
                    continue
                    
                if response.status_code == 200:
                    response_data = response.json()
                    choices = response_data.get('choices', [])
                    if choices:
                        content = choices[0].get('message', {}).get('content', '').strip()
                        if content:
                            return content
                            
                # If status code is an explicit rejection (like 401), break out of this model's loop
                break
                
            except requests.exceptions.RequestException:
                retries -= 1
                time.sleep(1)
                
        # If the code reaches here, the current model failed. It loops to the next backup in the stack.
        continue

    return "System Degradation Notice: All primary and fallback AI models are currently unresponsive or rate-limited. Please try again in a few moments."