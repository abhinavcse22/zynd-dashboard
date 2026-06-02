import requests
import time
from datetime import datetime, timedelta, timezone
import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials

SHEET_ID = '11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A'

def scrape_discord_server(channel_id, auth_token):
    """
    Active Talker Sniper: Bypasses 403 Admin blocks by targeting channel messages 
    instead of the static server member list. Extracts highly active leads.
    """
    # Sanitize the input (in case you pasted a full URL instead of just the ID)
    clean_channel_id = str(channel_id).strip()
    if "discord.com/channels/" in clean_channel_id:
        clean_channel_id = clean_channel_id.split("/")[-1]
    elif "/" in clean_channel_id:
        clean_channel_id = clean_channel_id.split("/")[-1]

    # Clean the token (removes accidental quotes)
    clean_token = auth_token.replace('"', '').replace("'", "").strip()
    headers = {"Authorization": clean_token}
    
    leads = []
    seen_users = set()
    today = datetime.now().strftime('%Y-%m-%d')
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=180)
    
    last_message_id = ""
    has_more = True
    messages_scanned = 0
    
    # We will scan up to 1000 recent messages in the target channel
    while has_more and messages_scanned < 5000:
        url = f"https://discord.com/api/v9/channels/{clean_channel_id}/messages?limit=100"
        if last_message_id:
            url += f"&before={last_message_id}"
            
        response = requests.get(url, headers=headers)
        
        if response.status_code == 403:
            return leads, "Discord Error 403: You do not have permission to read this channel. Ensure you have accepted the server rules."
        elif response.status_code != 200:
            return leads, f"Discord Error {response.status_code}: Check your token and channel ID."
            
        messages = response.json()
        if not messages:
            break
            
        for msg in messages:
            author = msg.get('author', {})
            user_id = author.get('id', '')
            
            # Skip bots and people we already extracted in this run
            if author.get('bot') or not user_id or user_id in seen_users:
                continue
                
            # Time constraint: Only care about messages sent in the last 180 days
            msg_timestamp_str = msg.get('timestamp', '')
            if msg_timestamp_str:
                try:
                    msg_date = datetime.fromisoformat(msg_timestamp_str.replace("Z", "+00:00"))
                    if msg_date < cutoff_date:
                        has_more = False # We hit the 6-month wall, stop paginating backward
                        continue
                except ValueError:
                    pass

            leads.append([
                author.get('username', ''),
                f"Discord Channel: {clean_channel_id}",
                author.get('global_name', ''),
                str(msg.get('content', ''))[:100].replace('\n', ' '), # Save a snippet of what they said!
                today
            ])
            seen_users.add(user_id)
            
        last_message_id = messages[-1]['id']
        messages_scanned += len(messages)
        time.sleep(1.5) # Anti-Ban Pacing

    # --- PUSH TO GOOGLE SHEETS ---
    if leads:
        try:
            scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
            creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
            gclient = gspread.authorize(creds)
            sheet = gclient.open_by_key(SHEET_ID).worksheet("Discord Leads")
            
            # Deduplicate to ensure we never save the same person twice
            existing_usernames = set(sheet.col_values(1)[1:]) if len(sheet.get_all_values()) > 1 else set()
            new_rows = [row for row in leads if row[0] not in existing_usernames]
            
            if new_rows:
                sheet.append_rows(new_rows)
        except Exception as e:
            return leads, f"Scraped successfully, but failed to save to Google Sheets: {str(e)}"
            
    return leads, "Success"
            
    return leads, "Success"

def scrape_slack_workspace(auth_token):
    """Rips member data from Slack using Cursor Pagination."""
    headers = {"Authorization": f"Bearer {auth_token}"}
    leads = []
    today = datetime.now().strftime('%Y-%m-%d')
    cutoff_date = datetime.now(timezone.utc).timestamp() - (180 * 24 * 60 * 60)
    
    next_cursor = ""
    
    while True:
        url = f"https://slack.com/api/users.list?limit=500"
        if next_cursor: url += f"&cursor={next_cursor}"
        
        response = requests.get(url, headers=headers)
        data = response.json()
        
        if not data.get("ok"):
            return leads, f"Slack Error: {data.get('error')}"
            
        for m in data.get('members', []):
            if m.get('is_bot') or m.get('deleted'): continue
            
            # 🛑 180-DAY TTL CHECK
            updated_timestamp = float(m.get('updated', 0))
            if updated_timestamp < cutoff_date:
                continue
            
            leads.append([
                m.get('name', ''),
                "Slack Workspace",
                m.get('profile', {}).get('real_name', ''),
                m.get('profile', {}).get('title', 'No Title'),
                today
            ])
            
        next_cursor = data.get('response_metadata', {}).get('next_cursor', '')
        if not next_cursor:
            break
            
        time.sleep(1) # Pacing
        
    return leads, "Success"
