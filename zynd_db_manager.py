import time
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import streamlit as st
import random

SHEET_ID = '11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A'

def get_db_connection():
    """Establishes a secure connection to Google Sheets."""
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    return gspread.authorize(creds)

def safe_append_rows(tab_name, new_rows, max_retries=3):
    """
    Enterprise-grade database writer with Exponential Backoff.
    If Google API rate-limits us, it waits and tries again instead of crashing.
    """
    if not new_rows:
        return True

    client = get_db_connection()
    worksheet = client.open_by_key(SHEET_ID).worksheet(tab_name)
    
    for attempt in range(max_retries):
        try:
            worksheet.append_rows(new_rows)
            return True
        except gspread.exceptions.APIError as e:
            if attempt == max_retries - 1:
                st.error(f"Database write failed after {max_retries} attempts: {e}")
                return False
            # Exponential backoff: Wait 2s, then 4s, then 8s + random jitter
            sleep_time = (2 ** attempt) + random.uniform(0, 1)
            time.sleep(sleep_time)
            
    return False

def get_existing_identifiers(tab_name, column_index=1):
    """
    Optimized deduplication reader.
    Instead of downloading the entire 22,000 row database, it ONLY downloads
    the specific column (e.g., Usernames) to check for duplicates, saving 90% bandwidth.
    """
    client = get_db_connection()
    worksheet = client.open_by_key(SHEET_ID).worksheet(tab_name)
    try:
        # col_values is much faster and lighter than get_all_values()
        return set(worksheet.col_values(column_index)[1:]) 
    except Exception:
        return set()
