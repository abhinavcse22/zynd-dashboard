import pandas as pd
from datetime import datetime, timedelta, timezone
import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import asyncio
from telethon.sync import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.types import UserStatusOffline, UserStatusRecently, UserStatusLastWeek, UserStatusLastMonth

# Configuration
API_ID = st.secrets["telegram"]["api_id"]
API_HASH = st.secrets["telegram"]["api_hash"]
SESSION_STRING = st.secrets["telegram"]["session_string"]
SHEET_ID = '11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A'

async def async_scrape_telegram(target_groups):
    """Asynchronous engine with strict 180-day TTL filtering."""
    client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
    await client.connect()
    
    if not await client.is_user_authorized():
        raise Exception("Telegram session is not authorized. Token is invalid or expired.")

    all_leads = []
    date_str = datetime.now().strftime('%Y-%m-%d')
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=180)

    for target in target_groups:
        target = target.strip()
        if not target: continue
        
        try:
            clean_target = target.replace('https://t.me/', '').replace('@', '')
            entity = await client.get_entity(clean_target)
            
            async for user in client.iter_participants(entity):
                if user.deleted or user.bot:
                    continue
                
                # 🛑 THE 180-DAY TTL WALL: Check when they were last online
                is_active = True
                if isinstance(user.status, UserStatusOffline):
                    if user.status.was_online < cutoff_date:
                        is_active = False # Dead account, skip it
                # If status is Empty (long time ago), skip it
                elif user.status is None or user.status.__class__.__name__ == 'UserStatusEmpty':
                    is_active = False 

                if not is_active:
                    continue
                
                username = f"@{user.username}" if user.username else "No Username"
                
                all_leads.append([
                    target,                     
                    username,                   
                    str(user.first_name or ''), 
                    str(user.last_name or ''),  
                    str(user.id),               
                    "Yes" if user.premium else "No", 
                    date_str                    
                ])
                
        except Exception as e:
            st.error(f"Failed to scrape {target}: {str(e)}")
            
    await client.disconnect()
    return all_leads

def run_telegram_scraper(target_text_block):
    targets = [line.strip() for line in target_text_block.split('\n') if line.strip()]
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    sniped_leads = loop.run_until_complete(async_scrape_telegram(targets))
    
    if not sniped_leads: return [], 0

    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    sheet = gspread.authorize(creds).open_by_key(SHEET_ID).worksheet("Telegram Leads")
    
    existing_records = sheet.get_all_values()
    existing_ids = {str(row[4]) for row in existing_records[1:] if len(row) > 4} if len(existing_records) > 0 else set()
        
    new_rows_to_add = [row for row in sniped_leads if row[4] not in existing_ids]
    if new_rows_to_add: sheet.append_rows(new_rows_to_add)
        
    display_data = [{"Source": r[0], "Username": r[1], "Name": f"{r[2]} {r[3]}", "Premium": r[5]} for r in new_rows_to_add]
    return display_data, len(new_rows_to_add)
