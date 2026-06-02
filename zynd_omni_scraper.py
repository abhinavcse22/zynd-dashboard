import requests
import time
from datetime import datetime, timedelta, timezone
import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials

SHEET_ID = '11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A'

def scrape_discord_server(server_id, auth_token):
    """Rips member data from Discord using Pagination and Anti-Ban pacing."""
    headers = {"Authorization": auth_token}
    leads = []
    today = datetime.now().strftime('%Y-%m-%d')
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=180)
    
    last_user_id = "0"
    has_more = True
    
    while has_more:
        # Paginating using the 'after' parameter
        url = f"https://discord.com/api/v9/guilds/{server_id}/members?limit=1000&after={last_user_id}"
        response = requests.get(url, headers=headers)
        
        if response.status_code != 200:
            return leads, f"Discord Error: {response.status_code} - Check permissions or rate limits."
            
        members = response.json()
        if not members:
            break
            
        for m in members:
            user = m.get('user', {})
            if user.get('bot'): continue
            
            # 🛑 180-DAY TTL CHECK: Skip people who joined years ago and went dark
            joined_at_str = m.get('joined_at', '')
            if joined_at_str:
                try:
                    # Discord returns ISO 8601 strings
                    joined_at = datetime.fromisoformat(joined_at_str.replace("Z", "+00:00"))
                    if joined_at < cutoff_date:
                        continue
                except ValueError:
                    pass

            leads.append([
                user.get('username', ''),
                f"Discord Server: {server_id}",
                user.get('global_name', ''),
                "No Bio (Discord)",
                today
            ])
            
            last_user_id = user.get('id', last_user_id)
            
        if len(members) < 1000:
            has_more = False
        else:
            time.sleep(1.5) # Anti-Ban Pacing: Don't hammer the API
            
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
