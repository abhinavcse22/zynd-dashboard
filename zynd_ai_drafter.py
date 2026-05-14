import google.generativeai as genai
import streamlit as st

# Configure the Gemini Engine securely
genai.configure(api_key=st.secrets["gemini"]["api_key"])

# Using the hyper-fast Flash model for instantaneous drafting
model = genai.GenerativeModel('gemini-1.5-flash')

def generate_outreach_sequence(lead_name, intent_source, bio_or_post):
    """Generates a highly technical, multi-step outreach sequence using Gemini."""
    
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
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Error connecting to AI API: {str(e)}"
