import requests
import json
import streamlit as st

def generate_outreach_sequence(lead_name, intent_source, bio_or_post, product_pitch="an OS and network for AI agents and Web3 builders"):
    """Generates a highly technical outreach sequence using OpenRouter. Fault-tolerant."""
    
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
                "model": "openrouter/free", # Recommended: upgrade to anthropic/llama models for prod
                "messages": [
                    {"role": "user", "content": prompt}
                ]
            }),
            timeout=15 # Prevent infinite hanging if the LLM provider stalls
        )
        
        # 🛑 FIX: Check status code BEFORE attempting to parse JSON
        if response.status_code != 200:
            return f"API Error ({response.status_code}): The AI provider is currently unreachable or rate-limited."
            
        # 🛑 FIX: Safe JSON parsing
        try:
            response_data = response.json()
            # Safe dict traversal
            choices = response_data.get('choices', [])
            if not choices:
                return "API Error: The AI returned an empty response. Please try again."
                
            content = choices[0].get('message', {}).get('content', '')
            if not content:
                return "API Error: The AI model failed to generate text."
                
            return content
            
        except ValueError:
            return "API Error: Received a malformed response from the AI provider."
            
    except requests.exceptions.Timeout:
        return "Timeout Error: The AI took too long to respond. Please try again."
    except Exception as e:
        return f"System Error: {str(e)}"
