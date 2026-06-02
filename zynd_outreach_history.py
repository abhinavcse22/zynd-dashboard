import pandas as pd
from datetime import datetime
import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials

SHEET_ID = '11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A'

def get_history_db():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    client = gspread.authorize(creds)
    
    # 🛡️ Auto-Initialization: Create the ledger if it doesn't exist
    try:
        return client.open_by_key(SHEET_ID).worksheet("Outreach History")
    except gspread.exceptions.WorksheetNotFound:
        sheet = client.open_by_key(SHEET_ID).add_worksheet(title="Outreach History", rows="1000", cols="6")
        sheet.append_row(["Timestamp (UTC)", "Lead Identifier", "Owner", "Platform", "Message Type", "Notes/Snippet"])
        return sheet

def log_outreach_event(lead_identifier, owner, platform, message_type, notes=""):
    """Appends a permanent record of an outbound communication event."""
    sheet = get_history_db()
    if not sheet:
        return False, "Failed to connect to the Outreach History ledger."
        
    timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    
    # Check headers to ensure safe alignment
    headers = sheet.row_values(1)
    expected_headers = ["Timestamp (UTC)", "Lead Identifier", "Owner", "Platform", "Message Type", "Notes/Snippet"]
    
    if not headers:
        sheet.append_row(expected_headers)
        headers = expected_headers
        
    try:
        new_row = [""] * len(headers)
        new_row[headers.index("Timestamp (UTC)")] = timestamp
        new_row[headers.index("Lead Identifier")] = lead_identifier
        new_row[headers.index("Owner")] = owner
        new_row[headers.index("Platform")] = platform
        new_row[headers.index("Message Type")] = message_type
        new_row[headers.index("Notes/Snippet")] = notes
        
        sheet.append_row(new_row)
        return True, f"Outreach event successfully logged for {lead_identifier}."
        
    except ValueError:
        return False, "Ledger headers are corrupted. Delete the 'Outreach History' tab and let the engine recreate it."
    except Exception as e:
        return False, f"System Error: {str(e)}"
