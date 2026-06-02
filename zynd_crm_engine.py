import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# Configuration
SHEET_ID = '11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A'

def update_lead_status(tab_name, search_column_name, lead_identifier, owner, status, follow_up_date):
    """Finds a lead dynamically and updates their CRM status."""
    
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    client = gspread.authorize(creds)
    
    try:
        sheet = client.open_by_key(SHEET_ID).worksheet(tab_name)
        records = sheet.get_all_values()
        
        if not records:
            return False, "Database is empty."

        headers = records[0]
        
        # 1. DYNAMIC LOOKUP: Find the target column by its name, not its integer position
        if search_column_name not in headers:
            return False, f"Could not find the identifier column: '{search_column_name}'"
            
        search_col_idx = headers.index(search_column_name)
        
        # 2. Find the exact row number
        row_to_update = None
        for i, row in enumerate(records):
            if len(row) > search_col_idx and row[search_col_idx] == lead_identifier:
                row_to_update = i + 1 
                break
                
        if not row_to_update:
            return False, "Lead not found in database."

        # 3. Calculate target columns dynamically
        try:
            col_owner = headers.index('Lead Owner') + 1
            col_status = headers.index('Status') + 1
            col_last_contact = headers.index('Last Contact Date') + 1
            col_follow_up = headers.index('Next Follow-Up') + 1
        except ValueError:
            return False, "Missing CRM headers. Make sure 'Lead Owner', 'Status', 'Last Contact Date', and 'Next Follow-Up' exist."

        # 4. Execute the Batch Update Payload
        today = datetime.now().strftime('%Y-%m-%d')
        
        cells_to_update = [
            gspread.Cell(row=row_to_update, col=col_owner, value=owner),
            gspread.Cell(row=row_to_update, col=col_status, value=status),
            gspread.Cell(row=row_to_update, col=col_last_contact, value=today),
            gspread.Cell(row=row_to_update, col=col_follow_up, value=follow_up_date)
        ]
        sheet.update_cells(cells_to_update)
        
        return True, "CRM Updated Successfully."
        
    except Exception as e:
        return False, str(e)
