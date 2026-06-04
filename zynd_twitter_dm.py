import streamlit as st
import gspread
import requests
import time
import random
from oauth2client.service_account import ServiceAccountCredentials

# --- SELENIUM STEALTH IMPORTS ---
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys

SHEET_ID = '11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A'

def generate_twitter_dm(prospect_name, bio):
    """Hits OpenRouter to craft a very short, highly casual Twitter DM."""
    headers = {
        "Authorization": f"Bearer {st.secrets['openrouter']['api_key']}",
        "Content-Type": "application/json"
    }
    
    prompt = f"""
    Act as Abhinav, a technical founder. Write a Twitter DM to a developer you just found.
    Lead Name/Handle: {prospect_name}
    Their Bio: {bio}
    
    Rules:
    1. EXTREMELY short. 1-2 sentences maximum.
    2. Tone is super casual (Twitter style). No corporate speak.
    3. Mention you're building Zynd (a workspace for AI agents).
    4. Ask if they are open to checking it out.
    
    Return ONLY the exact text of the DM. No quotes, no intro, no labels.
    """
    
    data = {
        "model": "openai/gpt-4o-mini",
        "messages": [{"role": "user", "content": prompt}]
    }
    
    try:
        response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=data, timeout=20)
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content'].replace('"', '').strip()
        return None
    except Exception:
        return None

def setup_stealth_browser():
    """Configures a headless Chromium instance to bypass bot detection on Linux."""
    options = Options()
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    
    # Spoof a standard residential Mac/Chrome user agent
    options.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
    
    # Strip automation flags
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    
    # Execute JS to hide WebDriver footprint
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    return driver

def dispatch_twitter_dms(max_dms=5, status_container=None):
    if "twitter" not in st.secrets or "auth_token" not in st.secrets["twitter"]:
        return 0, "Error: [twitter] auth_token secret is missing."

    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    client = gspread.authorize(creds)
    
    try:
        sheet = client.open_by_key(SHEET_ID).worksheet("Twitter Leads")
        records = sheet.get_all_records()
        headers = sheet.row_values(1)
        status_col_idx = headers.index("outreach_status") + 1 if "outreach_status" in headers else None
    except Exception as e:
        return 0, f"Database Error: {str(e)}"
        
    dms_fired = 0
    driver = None
    
    try:
        if status_container: status_container.warning("Booting headless stealth browser...")
        driver = setup_stealth_browser()
        
        # INJECT COOKIE BYPASS
        driver.get("https://x.com/robots.txt") # Load simple page on domain first to set cookie
        driver.add_cookie({
            'name': 'auth_token',
            'value': st.secrets["twitter"]["auth_token"],
            'domain': '.x.com',
            'path': '/',
            'secure': True
        })
        
        for idx, row in enumerate(records):
            if dms_fired >= max_dms: break
                
            handle = str(row.get("handle", "")).replace("@", "").strip()
            status = str(row.get("outreach_status", "Pending")).strip()
            bio = str(row.get("bio", "")).strip()
            
            if not handle or status in ["DM Sent", "DO NOT CONTACT 🛑", "Failed"]:
                continue
                
            if status_container: status_container.info(f"Drafting AI DM for @{handle}...")
            message = generate_twitter_dm(handle, bio)
            
            if not message:
                continue
                
            if status_container: status_container.warning(f"Navigating to @{handle}'s inbox...")
            
            # Direct navigation to the user's DM window
            driver.get(f"https://x.com/messages/compose?recipient_id={handle}")
            time.sleep(random.uniform(5.5, 8.2)) # Let React UI load
            
            try:
                # Target the DM text box (Twitter's DOM changes often, this targets the main input role)
                message_box = WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'div[data-testid="dmComposerTextInput"]'))
                )
                
                # Human-like typing delay
                for char in message:
                    message_box.send_keys(char)
                    time.sleep(random.uniform(0.02, 0.08))
                    
                time.sleep(random.uniform(1.1, 2.5))
                message_box.send_keys(Keys.RETURN) # Hit Enter to send
                
                dms_fired += 1
                
                if status_col_idx:
                    sheet.update_cell(idx + 2, status_col_idx, "DM Sent")
                    
                import zynd_outreach_history
                zynd_outreach_history.log_outreach_event(handle, "Abhinav", "Twitter / X", "Initial Pitch", message)
                
                if dms_fired < max_dms:
                    delay = random.randint(90, 180)
                    if status_container: status_container.success(f"DM Sent! Sleeping {delay} seconds to avoid rate limits...")
                    time.sleep(delay)
                    
            except Exception as e:
                if status_container: status_container.error(f"Could not message @{handle}. Their DMs might be closed.")
                if status_col_idx: sheet.update_cell(idx + 2, status_col_idx, "DMs Closed / Failed")
                time.sleep(5)
                
    except Exception as e:
        return dms_fired, f"Critical Browser Failure: {str(e)}"
        
    finally:
        if driver:
            driver.quit() # Always close the browser to free up Linux memory
            
    return dms_fired, "Twitter automation cycle concluded."