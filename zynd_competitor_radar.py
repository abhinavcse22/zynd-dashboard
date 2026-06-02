import requests
from bs4 import BeautifulSoup
import json
import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

SHEET_ID = '11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A'

def get_db_sheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    client = gspread.authorize(creds)
    
    # Ensure the tracker partition exists in your database
    try:
        return client.open_by_key(SHEET_ID).worksheet("Competitor Radar")
    except gspread.exceptions.WorksheetNotFound:
        sheet = client.open_by_key(SHEET_ID).add_worksheet(title="Competitor Radar", rows="1000", cols="5")
        sheet.append_row(["Competitor Name", "Target URL", "Last Scraped Content", "Last Feature Detected", "Date Tracked"])
        return sheet

def fetch_site_text(url):
    """Bypasses standard server blocks to scrape visible text content cleanly."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
    }
    try:
        response = requests.get(url, headers=headers, timeout=12)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            # Strip scripts, styles, and headers to keep core data clean
            for script in soup(["script", "style", "nav", "footer"]):
                script.decompose()
            return " ".join(soup.get_text().split())[:4000] # Cap to prevent cell overflow
    except Exception:
        pass
    return None

def generate_counter_usecase(competitor, live_text):
    """Instructs OpenRouter to build an immediate technical attack post based on rival updates."""
    prompt = f"""
    You are the Principal Systems Architect at Zynd.
    
    We just scraped a competitor ({competitor}) landing/product update page:
    "{live_text[:1500]}"
    
    Write a highly technical "Use Case" social media post (for Twitter/LinkedIn) that breaks down what they are attempting to solve, and immediately contrasts it with Zynd's superior, decentralized x402 infrastructure.
    
    RULES:
    1. Do not use marketing jargon ("revolutionary", "game-changing"). Speak like an engineer.
    2. Focus on engineering realities: scale, developer friction, cost, or centralized choke points.
    3. Use the 1st person plural ("We built Zynd...").
    4. Keep it tightly structured with clean line breaks.
    """
    try:
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {st.secrets['openrouter']['api_key']}",
                "HTTP-Referer": "https://zynd.io", 
                "Content-Type": "application/json"
            },
            data=json.dumps({
                "model": "openrouter/free", 
                "messages": [{"role": "user", "content": prompt}]
            }),
            timeout=15
        )
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
    except Exception:
        pass
    return "AI Engine failed to compute counter positioning data."

def execute_competitor_radar_sweep(competitor_name, target_url):
    """Runs the full diff engine, detects changes, generates use-case, and updates ledger."""
    sheet = get_db_sheet()
    records = sheet.get_all_records()
    today = datetime.now().strftime('%Y-%m-%d')
    
    # 1. Fetch current live structural state
    live_content = fetch_site_text(target_url)
    if not live_content:
        return {"status": "Error", "message": f"Could not establish connection to {target_url} endpoint."}
        
    # 2. Locate existing record to run diff check
    matched_row_idx = None
    historical_content = ""
    
    for i, row in enumerate(records, start=2):
        if str(row.get("Competitor Name")).strip().lower() == competitor_name.strip().lower():
            matched_row_idx = i
            historical_content = str(row.get("Last Scraped Content", ""))
            break

    # 3. Process the Diff Engine
    # If the text matches, no modifications were made by their engineering/marketing team
    if historical_content and live_content[:1000] == historical_content[:1000]:
        return {"status": "No Change", "message": f"Verified {competitor_name}. No adjustments to positioning or features detected."}

    # If we made it here, a change was detected or it's a completely new competitor node!
    st.info(f"💥 Alteration detected in {competitor_name} surface array! Dispatching OpenRouter engine...")
    counter_payload = generate_counter_usecase(competitor_name, live_content)
    
    # 4. Save to Sheets Database
    # Dynamically map headers to prevent grid alignment corruption
    headers = sheet.row_values(1)
    c_name_col = headers.index("Competitor Name") + 1
    url_col = headers.index("Target URL") + 1
    content_col = headers.index("Last Scraped Content") + 1
    feat_col = headers.index("Last Feature Detected") + 1
    date_col = headers.index("Date Tracked") + 1

    if matched_row_idx:
        # Update existing node
        cells = [
            gspread.Cell(row=matched_row_idx, col=content_col, value=live_content),
            gspread.Cell(row=matched_row_idx, col=feat_col, value=counter_payload[:2000]),
            gspread.Cell(row=matched_row_idx, col=date_col, value=today)
        ]
        sheet.update_cells(cells)
    else:
        # Append entirely fresh competitor tracking node
        new_row = [""] * len(headers)
        new_row[c_name_col - 1] = competitor_name
        new_row[url_col - 1] = target_url
        new_row[content_col - 1] = live_content
        new_row[feat_col - 1] = counter_payload[:2000]
        new_row[date_col - 1] = today
        sheet.append_row(new_row)

    return {"status": "Updated", "payload": counter_payload}
