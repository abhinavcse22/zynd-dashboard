import streamlit as st
import json
import os

# --- ACCESS SECRETS ---
# Ensure these keys are added to your Streamlit Cloud "Settings -> Secrets"
APIFY_API_TOKEN = st.secrets.get("APIFY_API_TOKEN", "")
SENDPILOT_API_KEY = st.secrets.get("SENDPILOT_API_KEY", "")
SENDPILOT_CAMPAIGN_ID = st.secrets.get("SENDPILOT_CAMPAIGN_ID", "")
ANTHROPIC_API_KEY = st.secrets.get("ANTHROPIC_API_KEY", "")
LINKEDIN_COOKIE = st.secrets.get("LINKEDIN_COOKIE", "")
SHEET_ID = st.secrets.get("SHEET_ID", "")

# --- SETTINGS ---
APIFY_BASE_URL = "https://api.apify.com/v2"
APIFY_LINKEDIN_ACTOR = "harvestapi/linkedin-post-search"
SENDPILOT_BASE_URL = "https://api.sendpilot.ai"

LOOKBACK_DAYS = 1
MAX_LEADS_PER_RUN = 50

# --- LOAD DATA ---
def load_json(filename):
    path = os.path.join(os.path.dirname(__file__), "data", filename)
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {}

POST_SIGNAL_KEYWORDS = load_json("post_signal_keywords.json")
PERSONA_JTBD = load_json("persona_jtbd.json")
ZYND_VALUE_PROPS = load_json("zynd_value_props.json")