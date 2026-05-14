import os
import streamlit as st
from groq import Groq

# Initialize the ultra-fast Groq client
client = Groq(api_key=st.secrets["groq"]["api_key"])

def generate_outreach_sequence(lead_name, intent_source, bio_or_post):
    """Generates a highly technical, multi-step outreach sequence."""
    
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
        completion = client.chat.completions.create(
            model="llama3-70b-8192",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=1024,
            top_p=1,
            stream=False,
            stop=None,
        )
        return completion.choices[0].message.content
    except Exception as e:
        return f"Error connecting to AI API: {str(e)}"
