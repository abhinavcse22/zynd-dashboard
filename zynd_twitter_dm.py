import streamlit as st
import gspread
import requests
import time
import random
import asyncio
import re
from oauth2client.service_account import ServiceAccountCredentials
from twikit import Client

SHEET_ID = '11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A'

def generate_twitter_dm(prospect_name, bio):
    """Generates the highly-constrained founder-style cold DM payload."""
    headers = {
        "Authorization": f"Bearer {st.secrets['openrouter']['api_key']}",
        "Content-Type": "application/json"
    }
    
    prompt = f"""
    You are Abhinav, a highly technical founder reaching out to a developer on X.
    Target Context: {bio}

    Draft a casual DM. You MUST use this exact fill-in-the-blank structure:
    [Short 3-5 word observation] + " building zynd (agent os) btw." + [1 short technical question]

    STRICT RULES:
    1. ALL LOWERCASE.
    2. NEVER start with an "@" symbol, a name, or a greeting. Start directly with the observation (e.g., "saw you are...", "noticed your...").
    3. YOU MUST MENTION "zynd" exactly as shown. Do not drop it.
    4. No punctuation at the very end of the message.
    5. MAX 25 WORDS total.

    Example 1: saw you scaling rag pipelines. building zynd (agent os) btw. what vector db are you using
    Example 2: noticed you doing web3 research. building zynd (agent os) btw. what rpc provider do u use

    Return ONLY the raw text to send. No quotes, no intro.
    """
    
    data = {
        "model": "openai/gpt-4o-mini", 
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2
    }
    
    try:
        response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=data, timeout=20)
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content'].replace('"', '').strip()
    except Exception as e:
        print(f"⚠️ OpenRouter Error: {e}")
    return None

async def try_api_send(tw_auth, tw_ct0, handle, message):
    """Executes pure cloud-native direct messaging via official client cookies."""
    client = Client(language='en-US')
    client.set_cookies({
        'auth_token': tw_auth, 
        'ct0': tw_ct0
    })
    user = await client.get_user_by_screen_name(handle)
    await client.send_dm(user.id, message)
    return True

def dispatch_twitter_dms(max_dms=5, mode="AI Generated", custom_msg="", status_container=None):
    """Master controller called directly by the Streamlit UI."""
    tw_auth = st.secrets.get("twitter", {}).get("auth_token", "")
    tw_ct0 = st.secrets.get("twitter", {}).get("ct0", "")
    
    if not tw_auth or not tw_ct0:
        return 0, "Error: Missing Twitter tokens in Streamlit Secrets."

    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    client = gspread.authorize(creds)
    
    try:
        sheet = client.open_by_key(SHEET_ID).worksheet("Twitter Leads")
        raw_data = sheet.get_all_values()
        if not raw_data or len(raw_data) < 2: 
            return 0, "No leads found."
            
        headers = [str(h).strip() if str(h).strip() else f"Unnamed_{idx}" for idx, h in enumerate(raw_data[0])]
        records = [dict(zip(headers, row + [""] * (len(headers) - len(row)))) for row in raw_data[1:]]
        
        status_col_name = next((h for h in ["outreach_status", "Status", "status"] if h in headers), None)
        status_col_idx = headers.index(status_col_name) + 1 if status_col_name else None
    except Exception as e:
        return 0, f"Database Error: {str(e)}"
        
    dms_fired = 0
    
    for idx, row in enumerate(records):
        if dms_fired >= max_dms: 
            break
            
        raw_handle = str(row.get("Tweet URL", row.get("Username", row.get("handle", row.get("User", ""))))).strip()
        if not raw_handle or "http" in raw_handle:
            url = str(row.get("Content", row.get("Profile URL", row.get("User URL", ""))))
            if "x.com/" in url or "twitter.com/" in url:
                parts = url.split("/")
                for i, p in enumerate(parts):
                    if p in ["x.com", "twitter.com"] and i + 1 < len(parts):
                        raw_handle = parts[i + 1]
                        break
                        
        handle = raw_handle.replace("@", "").split("?")[0].strip()
        if not handle or "http" in handle: 
            continue
            
        status = str(row.get(status_col_name, "Pending")).strip().lower() if status_col_name else "pending"
        bio = str(row.get("Unnamed_6", row.get("bio", str(row.get("Content", ""))))).strip()
        
        if any(kw in status for kw in ["sent", "stop", "failed", "closed"]): 
            continue
            
        # 1. Draft Message Matrix
        if mode == "✍️ Custom Template":
            message = custom_msg.replace("{name}", handle).replace("{bio}", bio)
        else:
            if status_container: 
                status_container.info(f"Drafting AI DM for @{handle}...")
            message = generate_twitter_dm(handle, bio)
            
        if not message: 
            continue
            
        # 2. Pure Cloud API Delivery Loop
        if status_container: 
            status_container.info(f"Deploying Twikit payload to @{handle}...")
            
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(try_api_send(tw_auth, tw_ct0, handle, message))
            loop.close()
            
            dms_fired += 1
            if status_col_idx: 
                sheet.update_cell(idx + 2, status_col_idx, "DM Sent")
                
            if status_container: 
                status_container.success(f"✅ Success! Delivered to @{handle}.")
                
            # Log to outreach ledger
            try:
                import zynd_outreach_history
                zynd_outreach_history.log_outreach_event(handle, "Abhinav", "Twitter / X (Cloud API)", "Initial Pitch", message)
            except: 
                pass
            
            # Anti-throttling human-emulation delay
            if dms_fired < max_dms:
                delay = random.randint(45, 90)
                if status_container: 
                    status_container.write(f"⏳ Cooling down for {delay}s to safeguard account metrics...")
                time.sleep(delay)
                
        except Exception as e:
            if status_container: 
                status_container.error(f"❌ API Rejected delivery for @{handle}: {e}")
            if status_col_idx: 
                sheet.update_cell(idx + 2, status_col_idx, "API Failed / Closed")
            time.sleep(3)
            continue
                
    return dms_fired, f"Cloud Outbound Engine Cycle Concluded. Sent {dms_fired} DMs."