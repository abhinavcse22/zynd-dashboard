import pandas as pd
import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

SHEET_ID = '11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A'

def get_influencer_db():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    client = gspread.authorize(creds)
    try:
        return client.open_by_key(SHEET_ID).worksheet("Influencer Leads")
    except gspread.exceptions.WorksheetNotFound:
        return None

def update_influencer_stage(channel_name, new_stage, cost, views_delivered, live_url):
    """Updates specialized creator tracking metrics and auto-injects missing headers."""
    sheet = get_influencer_db()
    if not sheet:
        return False, "Influencer Leads database tab not found."
        
    records = sheet.get_all_values()
    if not records:
        return False, "Database is empty."
        
    headers = records[0]
    
    # 🛡️ Auto-Inject Specialized Columns if they don't exist
    required_cols = ["Campaign Stage", "Sponsorship Cost ($)", "Views Delivered", "Live Video URL", "Last Updated"]
    headers_updated = False
    
    for col in required_cols:
        if col not in headers:
            headers.append(col)
            sheet.update_cell(1, len(headers), col)
            headers_updated = True
            
    # Re-fetch headers if we modified them
    if headers_updated:
        records = sheet.get_all_values()
        headers = records[0]
            
    try:
        name_idx = headers.index("Channel")
        stage_idx = headers.index("Campaign Stage") + 1
        cost_idx = headers.index("Sponsorship Cost ($)") + 1
        views_idx = headers.index("Views Delivered") + 1
        url_idx = headers.index("Live Video URL") + 1
        date_idx = headers.index("Last Updated") + 1
    except ValueError:
        return False, "Critical column mapping error. Could not locate 'Channel' header."
        
    # Locate the specific creator
    row_to_update = None
    for i, row in enumerate(records[1:], start=2):
        if len(row) > name_idx and row[name_idx] == channel_name:
            row_to_update = i
            break
            
    if not row_to_update:
        return False, f"Channel '{channel_name}' not found in the ledger."
        
    today = datetime.now().strftime('%Y-%m-%d')
    
    # Batch update to save API limits
    cells = [
        gspread.Cell(row=row_to_update, col=stage_idx, value=new_stage),
        gspread.Cell(row=row_to_update, col=cost_idx, value=cost),
        gspread.Cell(row=row_to_update, col=views_idx, value=views_delivered),
        gspread.Cell(row=row_to_update, col=url_idx, value=live_url),
        gspread.Cell(row=row_to_update, col=date_idx, value=today)
    ]
    
    sheet.update_cells(cells)
    return True, f"Successfully updated campaign metrics for {channel_name}."
