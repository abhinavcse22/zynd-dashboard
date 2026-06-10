import streamlit as st
import gspread
import requests
import time
import random
import re
import shutil
from oauth2client.service_account import ServiceAccountCredentials

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

SHEET_ID = '11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A'

def generate_twitter_dm(prospect_name, bio, status_container):
    """Generates the highly-constrained founder-style cold DM payload."""
    headers = {
        "Authorization": f"Bearer {st.secrets['openrouter']['api_key']}",
        "Content-Type": "application/json"
    }
    
    prompt = f"""
    You are Abhinav, a highly technical founder reaching out to a developer on X.
    Target Context: {bio}

    Draft a casual DM. You MUST use this exact fill-in-the-blank structure:
    [Short 3-5 word observation] + " building zynd (agent os) btw." + [1 short technical question]

    STRICT RULES:
    1. ALL LOWERCASE.
    2. NEVER start with an "@" symbol, a name, or a greeting.
    3. YOU MUST MENTION "zynd" exactly as shown. 
    4. No punctuation at the very end of the message.
    5. MAX 25 WORDS total.
    """
    
    data = {
        "model": "openai/gpt-4o-mini", 
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2
    }
    
    try:
        response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=data, timeout=15)
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content'].replace('"', '').strip()
    except Exception as e:
        if status_container: status_container.error(f"AI Generation Error: {e}")
    return None

def setup_stealth_browser():
    options = Options()
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1920,1080')
    options.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)

    # Detect if running in Streamlit Cloud Linux Environment
    sys_chromedriver = shutil.which("chromedriver")
    sys_chromium = shutil.which("chromium") or shutil.which("chromium-browser")
    
    if sys_chromium and sys_chromedriver:
        options.binary_location = sys_chromium
        service = Service(executable_path=sys_chromedriver)
    else:
        # Fallback for local Mac testing
        from webdriver_manager.chrome import ChromeDriverManager
        service = Service(ChromeDriverManager().install())
        
    driver = webdriver.Chrome(service=service, options=options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver

from selenium.webdriver.common.keys import Keys

def try_browser_send(driver, handle, message):
    driver.get(f"https://x.com/messages/compose?recipient_id={handle}")
    time.sleep(random.uniform(6.5, 9.2)) 
    
    # Destroy annoying Modals / E2EE Popups via JavaScript
    try:
        driver.execute_script("""
            document.querySelectorAll('[role="dialog"]').forEach(e => e.remove());
            document.querySelectorAll('div[style*="background-color: rgba(0"]').forEach(e => e.remove());
        """)
        time.sleep(1)
    except:
        pass

    # Find the DM input box (Strict DM selectors only)
    selectors = ['div[data-testid="dmComposerTextInput"]', 'textarea[data-testid="dm-composer-textarea"]']
    message_box = None
    for selector in selectors:
        try:
            message_box = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
            if message_box: break
        except: pass
    
    if not message_box:
        raise Exception("Inbox unreachable. (DMs might be closed, or Twitter is blocking the Cloud IP).")
    
    # Emulate human typing
    for char in message:
        message_box.send_keys(char)
        time.sleep(random.uniform(0.01, 0.05))
        
    time.sleep(random.uniform(1.0, 2.0))
    
    # 🚨 THE FIX: Wait for the Send button, or fallback to hitting the ENTER key
    try:
        send_button = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[data-testid="dmComposerSendButton"]'))
        )
        driver.execute_script("arguments[0].click();", send_button)
    except:
        # If the button is hidden or missing, just hit ENTER inside the text box
        message_box.send_keys(Keys.RETURN)
        
    time.sleep(random.uniform(3.0, 4.5))
    return True

def dispatch_twitter_dms(max_dms=5, mode="AI Generated", custom_msg="", status_container=None):
    tw_auth = st.secrets.get("twitter", {}).get("auth_token", "")
    tw_ct0 = st.secrets.get("twitter", {}).get("ct0", "")
    
    if not tw_auth or not tw_ct0:
        return 0, "Error: Missing Twitter tokens in Streamlit Secrets."

    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    client = gspread.authorize(creds)
    
    try:
        sheet = client.open_by_key(SHEET_ID).worksheet("Twitter Leads")
        raw_data = sheet.get_all_values()
        if not raw_data or len(raw_data) < 2: return 0, "No leads found."
            
        headers = [str(h).strip() if str(h).strip() else f"Unnamed_{idx}" for idx, h in enumerate(raw_data[0])]
        records = [dict(zip(headers, row + [""] * (len(headers) - len(row)))) for row in raw_data[1:]]
        
        status_col_name = next((h for h in ["outreach_status", "Status", "status"] if h in headers), None)
        status_col_idx = headers.index(status_col_name) + 1 if status_col_name else None
    except Exception as e:
        return 0, f"Database Error: {str(e)}"
        
    dms_fired = 0
    driver = None
    
    for idx, row in enumerate(records):
        if dms_fired >= max_dms: break
            
        raw_handle = str(row.get("Tweet URL", row.get("Username", row.get("handle", row.get("User", ""))))).strip()
        handle = raw_handle.replace("@", "").split("?")[0].strip()
        
        if not handle or "http" in handle: continue
            
        status = str(row.get(status_col_name, "Pending")).strip().lower() if status_col_name else "pending"
        bio = str(row.get("Unnamed_6", row.get("bio", str(row.get("Content", ""))))).strip()
        
        if any(kw in status for kw in ["sent", "stop", "failed", "closed"]): continue
            
        # 1. Draft Message
        if status_container: status_container.info(f"🧠 AI Context Engine analyzing @{handle}...")
        
        if mode == "✍️ Custom Template":
            message = custom_msg.replace("{name}", handle).replace("{bio}", bio)
        else:
            message = generate_twitter_dm(handle, bio, status_container)
            
        if not message: 
            time.sleep(1)
            continue
            
        # 2. Boot Cloud Browser (Lazy Loading)
        if not driver:
            if status_container: status_container.warning("Booting Cloud Stealth Browser... This takes ~10 seconds.")
            driver = setup_stealth_browser()
            driver.get("https://x.com/robots.txt") 
            driver.add_cookie({'name': 'auth_token', 'value': tw_auth, 'domain': '.x.com', 'path': '/', 'secure': True})
            driver.add_cookie({'name': 'ct0', 'value': tw_ct0, 'domain': '.x.com', 'path': '/', 'secure': True})

        if status_container: status_container.info(f"Browser navigating to @{handle}'s inbox...")
        
        # 3. Fire Payload
        try:
            try_browser_send(driver, handle, message)
            dms_fired += 1
            if status_col_idx: sheet.update_cell(idx + 2, status_col_idx, "DM Sent")
            if status_container: status_container.success(f"✅ Browser Success! Delivered to @{handle}.")
            
            try:
                import zynd_outreach_history
                zynd_outreach_history.log_outreach_event(handle, "Abhinav", "Twitter / X (Selenium)", "Initial Pitch", message)
            except: pass
            
            if dms_fired < max_dms:
                delay = random.randint(50, 90)
                if status_container: status_container.write(f"⏳ Sleeping {delay}s to evade Twitter bot detection...")
                time.sleep(delay)
                
        except Exception as e:
            if status_container: status_container.error(f"Browser failed for @{handle}: {e}")
            if status_col_idx: sheet.update_cell(idx + 2, status_col_idx, "DMs Closed / Failed")
            time.sleep(3)
            continue
            
    if driver: driver.quit()
    return dms_fired, f"Cloud Browser Engine Concluded. Sent {dms_fired} messages."