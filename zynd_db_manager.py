import time
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import streamlit as st
import random
import threading

SHEET_ID = '11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A'

# 🔒 THE FIX: Global Thread Lock. This prevents the 5-thread scraper swarm 
# from crashing the Google API by forcing concurrent writes into a single-file queue.
db_lock = threading.Lock()

# --- SAFE SHADOW MODE INITIALIZATION ---
def get_supabase_client():
    try:
        if "supabase" in st.secrets and "url" in st.secrets["supabase"]:
            from supabase import create_client
            url: str = st.secrets["supabase"]["url"]
            key: str = st.secrets["supabase"]["key"]
            return create_client(url, key)
    except Exception as e:
        print(f"ℹ️ [SHADOW MODE] Supabase connection bypassed: {e}")
    return None

def get_db_connection():
    """Establishes a secure connection to Google Sheets."""
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    return gspread.authorize(creds)

def safe_append_rows(tab_name, new_rows, unique_url_index=None):
    """
    Enterprise-grade dual-writer. 
    Thread-safe writing to Google Sheets AND Supabase.
    """
    if not new_rows:
        return True

    # 1. Supabase Shadow Write Execution (Non-blocking)
    supabase = get_supabase_client()
    if supabase:
        try:
            payload = []
            for row in new_rows:
                post_url = str(row[unique_url_index]) if unique_url_index is not None and len(row) > unique_url_index else None
                payload.append({
                    "source_tab": tab_name,
                    "post_url": post_url,
                    "raw_data": row
                })
            supabase.table("zynd_master_leads").upsert(payload, on_conflict="post_url").execute()
            print(f"✅ [SUPABASE DATA LAKE] Backed up {len(new_rows)} leads.")
        except Exception as e:
            print(f"⚠️ [SUPABASE FAILED] Continuing safely to Google Sheets: {e}")

    # 2. Google Sheets Backup Legacy Routing (Thread-Safe)
    with db_lock: # 🚦 TRAFFIC CONTROL: Only one thread enters this block at a time
        try:
            client = get_db_connection()
            worksheet = client.open_by_key(SHEET_ID).worksheet(tab_name)
        except Exception as e:
            st.error(f"Database Mapping Error: Could not locate worksheet grid. {e}")
            return False
            
        for attempt in range(5): # Increased from 3 to 5 for heavy batch processing
            try:
                worksheet.append_rows(new_rows)
                print(f"✅ [GOOGLE SHEETS] Logged {len(new_rows)} rows to {tab_name}.")
                return True
            except gspread.exceptions.APIError as e:
                if attempt == 4:
                    print(f"🚨 [FATAL WRITE ERROR] Max retries hit for {tab_name}. Data dropped. {e}")
                    return False
                
                # Smart exponential backoff: 2s, 4s, 8s, 16s + jitter
                delay = (2 ** attempt) + random.uniform(1.0, 3.0)
                print(f"🚦 [RATE LIMIT REACHED] Thread paused. Retrying in {delay:.1f}s...")
                time.sleep(delay)

    return False

def get_existing_identifiers(tab_name, column_index=1):
    """Optimized deduplication reader."""
    client = get_db_connection()
    worksheet = client.open_by_key(SHEET_ID).worksheet(tab_name)
    try:
        return set(worksheet.col_values(column_index)[1:]) 
    except Exception:
        return set()