import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import time

# --- CONFIGURATION ---
SHEET_ID = '11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A'
TARGET_TABS = ["GitHub Leads", "Reddit Leads", "Twitter Leads", "Fork Sniper Leads", "Issue Leads"]

# The Weighted Intent Matrix for the Zynd Ecosystem
COMPETITORS = ['langchain', 'crewai', 'autogen', 'openai', 'n8n', 'make', 'zapier', 'vercel', 'langgraph']
HIGH_INTENT_ACTIONS = ['forked', 'issue', 'complaint', 'stuck', 'error', 'alternative', 'slow', 'expensive', 'fail']

def calculate_intent_score(row_data, tab_name):
    """Calculates a 0-100 score based on competitor mentions and action weight."""
    score = 0
    
    # 1. Base Platform Weight
    if tab_name == "Fork Sniper Leads": score += 40
    elif tab_name == "Issue Leads": score += 35
    elif tab_name == "Reddit Leads": score += 20
    elif tab_name == "Twitter Leads": score += 15
    else: score += 10 # Default standard OSINT
        
    # Flatten the entire row into a single searchable string
    row_text = " ".join([str(cell).lower() for cell in row_data])
    
    # 2. Competitor Presence Weight
    has_competitor = False
    for comp in COMPETITORS:
        if comp in row_text:
            score += 25
            has_competitor = True
            break # Cap competitor bonus to prevent inflation
            
    # 3. Action / Pain Point Weight
    for action in HIGH_INTENT_ACTIONS:
        if action in row_text:
            score += 20
            # If they mention a pain point AND a competitor, it's a critical lead
            if has_competitor:
                score += 15
            break
            
    return min(score, 100) # Cap at 100

def run_global_intent_scoring():
    """Scans all databases, calculates intent, and batch-updates the CRM."""
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    client = gspread.authorize(creds)
    
    total_scored = 0
    
    # UI Progress Tracking
    progress_bar = st.progress(0, text="Initializing Intent Scoring Engine...")
    
    for idx, tab in enumerate(TARGET_TABS):
        progress_bar.progress((idx + 1) / len(TARGET_TABS), text=f"Scoring leads in {tab}...")
        
        try:
            sheet = client.open_by_key(SHEET_ID).worksheet(tab)
            records = sheet.get_all_values()
            
            if not records or len(records) < 2:
                continue
                
            headers = records[0]
            
            # Auto-inject the Intent Score column if it doesn't exist
            if "Intent Score (0-100)" not in headers:
                headers.append("Intent Score (0-100)")
                sheet.update_cell(1, len(headers), "Intent Score (0-100)")
                records = sheet.get_all_values() # Refresh memory
                
            score_col_idx = headers.index("Intent Score (0-100)") + 1
            cells_to_update = []
            
            # Iterate through rows and score them
            for row_idx, row in enumerate(records[1:], start=2):
                # Skip if already scored to save API calls
                if len(row) >= score_col_idx and str(row[score_col_idx - 1]).strip() != "":
                    continue
                    
                calculated_score = calculate_intent_score(row, tab)
                cells_to_update.append(gspread.Cell(row=row_idx, col=score_col_idx, value=calculated_score))
                
            # Batch update the grid
            if cells_to_update:
                sheet.update_cells(cells_to_update)
                total_scored += len(cells_to_update)
                
            time.sleep(1) # Pacing for Google API limits
                
        except Exception as e:
            st.error(f"Failed to score tab '{tab}': {str(e)}")
            continue

    progress_bar.empty()
    return total_scored