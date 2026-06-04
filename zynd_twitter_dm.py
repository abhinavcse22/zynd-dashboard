import streamlit as st
import gspread
import requests
import time
import random
import asyncio
from oauth2client.service_account import ServiceAccountCredentials
from twikit import Client

SHEET_ID = '11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A'

def generate_twitter_dm(prospect_name, bio):
    headers = {
        "Authorization": f"Bearer {st.secrets['openrouter']['api_key']}",
        "Content-Type": "application/json"
    }
    
    prompt = f"""
    Act as Abhinav, a technical founder. Write a Twitter DM to a developer you just found.
    Lead Name/Handle: {prospect_name}
    Their Bio/Tweet Context: {bio}
    
    Rules:
    1. EXTREMELY short. 1-2 sentences maximum.
    2. Tone is super casual (Twitter style). No corporate speak.
    3. Mention you're building Zynd (a workspace for AI agents).
    4. Ask if they are open to checking it out.
    
    Return ONLY the exact text of the DM. No quotes, no intro, no labels.
    """
    
    data = {
        "model": "openai/gpt-4o-mini",
        "messages": [{"role": "user", "content": prompt}]
    }
    
    try:
        response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=data, timeout=20)
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content'].replace('"', '').strip()
        return None
    except Exception:
        return None

async def async_dispatch(max_dms, mode, custom_msg, status_container, sheet, records, status_col_idx):
    """Asynchronous core function to handle twikit network calls."""
    client = Client(language='en-US')
    
    try:
        if status_container: status_container.warning("Authenticating with Twitter API backend...")
        client.set_cookies({
            'auth_token': st.secrets["twitter"]["auth_token"], 
            'ct0': st.secrets["twitter"]["ct0"]
        })
    except Exception as e:
        return 0, f"Authentication Failed: {str(e)}"

    dms_fired = 0
    skipped = 0

    for idx, row in enumerate(records):
        if dms_fired >= max_dms: break
            
        # Target lock on the handle
        raw_handle = str(row.get("Tweet URL", row.get("Username", row.get("handle", row.get("User", ""))))).strip()
        if not raw_handle or "http" in raw_handle:
            url = str(row.get("Content", row.get("Profile URL", row.get("User URL", row.get("Post URL", "")))))
            if "x.com/" in url or "twitter.com/" in url:
                parts = url.split("/")
                for i, p in enumerate(parts):
                    if p in ["x.com", "twitter.com"] and i + 1 < len(parts):
                        raw_handle = parts[i + 1]
                        break
                        
        handle = raw_handle.replace("@", "").split("?")[0].strip()
        
        if not handle or "http" in handle:
            skipped += 1
            continue
            
        status = str(row.get("outreach_status", "Pending")).strip()
        bio = str(row.get("Unnamed_6", row.get("bio", str(row.get("Content", ""))))).strip()
        
        if status in ["DM Sent", "DO NOT CONTACT 🛑", "DMs Closed / Failed", "Not Found"]:
            skipped += 1
            continue
            
        if mode == "✍️ Custom Template":
            if status_container: status_container.info(f"Applying custom template for @{handle}...")
            message = custom_msg.replace("{name}", handle).replace("{bio}", bio)
        else:
            if status_container: status_container.info(f"Drafting AI DM for @{handle}...")
            message = generate_twitter_dm(handle, bio)
        
        if not message:
            continue
            
        if status_container: status_container.warning(f"Locating @{handle} on Twitter servers...")
        
        try:
            # 1. Get internal Twitter User ID via API
            user = await client.get_user_by_screen_name(handle)
            
            # 2. Send the DM directly through the backend API
            if status_container: status_container.warning(f"User ID found ({user.id}). Firing payload...")
            await client.send_dm(user.id, message)
            
            dms_fired += 1
            
            if status_col_idx:
                sheet.update_cell(idx + 2, status_col_idx, "DM Sent")
                
            try:
                import zynd_outreach_history
                zynd_outreach_history.log_outreach_event(handle, "Abhinav", "Twitter / X (API)", "Initial Pitch", message)
            except:
                pass
            
            if dms_fired < max_dms:
                delay = random.randint(50, 90) # Faster delays since API is less suspicious than erratic browser behavior
                if status_container: status_container.success(f"API Payload delivered! Sleeping {delay} seconds...")
                await asyncio.sleep(delay)
                
        except Exception as e:
            error_str = str(e).lower()
            if status_container: status_container.error(f"Failed to message @{handle}: {str(e)}")
            
            if "not found" in error_str or "suspended" in error_str:
                if status_col_idx: sheet.update_cell(idx + 2, status_col_idx, "Not Found")
            elif "cannot send messages" in error_str or "403" in error_str:
                if status_col_idx: sheet.update_cell(idx + 2, status_col_idx, "DMs Closed / Failed")
            else:
                if status_col_idx: sheet.update_cell(idx + 2, status_col_idx, "API Error")
            
            await asyncio.sleep(5)
            
    return dms_fired, f"Twitter API cycle concluded. Sent {dms_fired} messages. Skipped {skipped}."

def dispatch_twitter_dms(max_dms=5, mode="AI Generated", custom_msg="", status_container=None):
    """Synchronous wrapper to handle Streamlit execution."""
    if "twitter" not in st.secrets or "auth_token" not in st.secrets["twitter"] or "ct0" not in st.secrets["twitter"]:
        return 0, "Error: [twitter] auth_token OR ct0 secret is missing."

    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    client = gspread.authorize(creds)
    
    try:
        sheet = client.open_by_key(SHEET_ID).worksheet("Twitter Leads")
        raw_data = sheet.get_all_values()
        
        if not raw_data or len(raw_data) < 2:
            return 0, "No leads found in the database."
            
        headers = raw_data[0]
        cleaned_headers = []
        for idx, h in enumerate(headers):
            h_clean = str(h).strip()
            if not h_clean: h_clean = f"Unnamed_{idx}"
            elif h_clean in cleaned_headers: h_clean = f"{h_clean}_{idx}"
            cleaned_headers.append(h_clean)
            
        records = []
        for row in raw_data[1:]:
            row = row + [""] * (len(cleaned_headers) - len(row))
            records.append(dict(zip(cleaned_headers, row)))
            
        status_col_idx = cleaned_headers.index("outreach_status") + 1 if "outreach_status" in cleaned_headers else None
    except Exception as e:
        return 0, f"Database Error: {str(e)}"

    # Run the async twikit logic in a new event loop so it doesn't crash Streamlit
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        sent, msg = loop.run_until_complete(
            async_dispatch(max_dms, mode, custom_msg, status_container, sheet, records, status_col_idx)
        )
        loop.close()
        return sent, msg
    except Exception as e:
        return 0, f"Async Engine Failure: {str(e)}"