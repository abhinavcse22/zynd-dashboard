import pandas as pd
from datetime import datetime
import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import asyncio
from telethon.sync import TelegramClient
from telethon.sessions import StringSession

# Configuration
API_ID = st.secrets["telegram"]["api_id"]
API_HASH = st.secrets["telegram"]["api_hash"]
SESSION_STRING = st.secrets["telegram"]["session_string"]
SHEET_ID = '11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A'

async def async_scrape_telegram(target_groups):
    """Asynchronous engine to connect to Telegram and rip group members."""
    client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
    await client.connect()
    
    if not await client.is_user_authorized():
        raise Exception("Telegram session is not authorized. The StringSession is invalid or expired.")

    all_leads = []
    date_str = datetime.now().strftime('%Y-%m-%d')

    for target in target_groups:
        target = target.strip()
        if not target: continue
        
        try:
            # Clean up links to just get the username/invite hash
            clean_target = target.replace('https://t.me/', '').replace('@', '')
            entity = await client.get_entity(clean_target)
            
            # Extract participants
            async for user in client.iter_participants(entity):
                # Filter out deleted accounts and bots
                if user.deleted or user.bot:
                    continue
                
                # Only save if they have a username (makes outbound easier)
                username = f"@{user.username}" if user.username else "No Username"
                
                all_leads.append([
                    target,                     # Source Group
                    username,                   # Username
                    str(user.first_name or ''), # First Name
                    str(user.last_name or ''),  # Last Name
                    str(user.id),               # User ID
                    "Yes" if user.premium else "No", # Premium Status
                    date_str                    # Date Extracted
                ])
                
        except Exception as e:
            st.error(f"Failed to scrape {target}: {str(e)}")
            
    await client.disconnect()
    return all_leads

def run_telegram_scraper(target_text_block):
    """Wrapper to run the async Telethon code inside Streamlit and push to DB."""
    # Convert the block of text into a list of targets
    targets = [line.strip() for line in target_text_block.split('\n') if line.strip()]
    
    # Run the async extraction
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    sniped_leads = loop.run_until_complete(async_scrape_telegram(targets))
    
    if not sniped_leads:
        return [], 0

    # --- PUSH TO GOOGLE SHEETS ---
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    gclient = gspread.authorize(creds)
    sheet = gclient.open_by_key(SHEET_ID).worksheet("Telegram Leads")
    
    # Deduplication based on User ID (Column 5, index 4)
    existing_records = sheet.get_all_values()
    existing_ids = set()
    if len(existing_records) > 0:
        existing_ids = {str(row[4]) for row in existing_records[1:] if len(row) > 4}
        
    new_rows_to_add = [row for row in sniped_leads if row[4] not in existing_ids]
    
    if new_rows_to_add:
        sheet.append_rows(new_rows_to_add)
        
    # Return display data
    display_data = [{"Source": r[0], "Username": r[1], "Name": f"{r[2]} {r[3]}", "Premium": r[5]} for r in sniped_leads]
    return display_data, len(new_rows_to_add)
