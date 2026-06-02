import pandas as pd
from datetime import datetime
import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials

SHEET_ID = '11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A'
TARGET_TABS = ["GitHub Leads", "Reddit Leads", "Twitter Leads", "Fork Sniper Leads", "github_stargazer_leads"]
OWNERS = ["Abhinav", "Co-Founder"]

def get_db_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    return gspread.authorize(creds).open_by_key(SHEET_ID)

def enforce_dnc_list():
    """Scans the database and moves any 'DO NOT CONTACT 🛑' leads to the DNC Vault."""
    client = get_db_client()
    try:
        dnc_sheet = client.worksheet("DNC Vault")
    except gspread.exceptions.WorksheetNotFound:
        dnc_sheet = client.add_worksheet(title="DNC Vault", rows="1000", cols="5")
        dnc_sheet.append_row(["Identifier", "Original Source", "Date Added", "Reason"])

    existing_dnc = set(dnc_sheet.col_values(1)[1:]) if len(dnc_sheet.get_all_values()) > 0 else set()
    new_dnc_entries = []

    for tab in TARGET_TABS:
        try:
            sheet = client.worksheet(tab)
            records = sheet.get_all_records()
            
            for row in records:
                if row.get('Status') == "DO NOT CONTACT 🛑":
                    identifier = str(row.get('Username') or row.get('github_username') or row.get('Lead ID', 'Unknown'))
                    if identifier not in existing_dnc and identifier != 'Unknown':
                        new_dnc_entries.append([
                            identifier, tab, datetime.now().strftime('%Y-%m-%d'), "Requested Opt-Out"
                        ])
                        existing_dnc.add(identifier)
        except Exception:
            continue

    if new_dnc_entries:
        dnc_sheet.append_rows(new_dnc_entries)
    return len(new_dnc_entries)

def auto_assign_leads():
    """Round-robin assignment of fresh leads to your team."""
    client = get_db_client()
    total_assigned = 0
    owner_index = 0

    # UI Feedback
    progress_bar = st.progress(0, text="Scanning for unassigned leads...")

    for idx, tab in enumerate(TARGET_TABS):
        progress_bar.progress((idx + 1) / len(TARGET_TABS), text=f"Routing leads in {tab}...")
        try:
            sheet = client.worksheet(tab)
            records = sheet.get_all_values()
            if len(records) < 2: continue
            
            headers = records[0]
            if 'Lead Owner' not in headers: continue
            
            col_owner = headers.index('Lead Owner') + 1
            cells_to_update = []
            
            for i, row in enumerate(records[1:], start=2):
                current_owner = row[col_owner - 1].strip() if len(row) >= col_owner else ""
                
                if current_owner == "" or current_owner == "Unassigned":
                    assigned_to = OWNERS[owner_index % len(OWNERS)]
                    cells_to_update.append(gspread.Cell(row=i, col=col_owner, value=assigned_to))
                    owner_index += 1
                    total_assigned += 1
            
            if cells_to_update:
                sheet.update_cells(cells_to_update)
                
        except Exception as e:
            continue
            
    progress_bar.empty()
    return total_assigned

def get_followup_radar():
    """Finds leads across all databases that are due for follow-up today or overdue."""
    client = get_db_client()
    due_today = []
    today_date = datetime.now().date()

    for tab in TARGET_TABS:
        try:
            sheet = client.worksheet(tab)
            records = sheet.get_all_records()
            
            for row in records:
                follow_up_str = str(row.get('Next Follow-Up', '')).strip()
                status = str(row.get('Status', '')).strip()
                
                # Ignore leads we aren't actively tracking or that are dead
                if not follow_up_str or status in ["DO NOT CONTACT 🛑", "Not Contacted", "Replied - Pass"]:
                    continue
                    
                try:
                    follow_up_date = datetime.strptime(follow_up_str, '%Y-%m-%d').date()
                    if follow_up_date <= today_date:
                        due_today.append({
                            "Target": row.get('Username') or row.get('github_username') or "Unknown",
                            "Owner": row.get('Lead Owner', 'Unassigned'),
                            "Stage": status,
                            "Source": tab,
                            "Due Date": follow_up_str
                        })
                except ValueError:
                    continue # Ignore poorly formatted dates
                    
        except Exception:
            continue

    return due_today
